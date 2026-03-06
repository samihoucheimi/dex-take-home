# Technical Commentary

## 1. Approach

### Role-Based Access Control

The existing system had no authorisation layer — any authenticated user could create, update, or delete books and authors. The requirement was to restrict mutations to admin users while leaving read endpoints open to all authenticated users.

The obvious implementation path was a new `require_admin` FastAPI dependency that chains on top of the existing `authenticate_user` dependency. FastAPI's `Depends` system is designed for exactly this: you stack dependencies, and each one delegates to the previous. `require_admin` gets a validated `DBUser` from `authenticate_user` for free, then just checks the `is_admin` flag. One extra line of logic, zero duplication of token-validation code.

The `is_admin` boolean already existed on `DBUser` (defaulting to `False`), so no database migration was needed. For a simple binary admin/non-admin split, a boolean field is the right call — a full role/permission table would be correct for a system with many distinct permission levels, but is unnecessary complexity here.

### Book Summaries (LLM)

The core decision was provider and model choice. I used OpenAI throughout (GPT-4o-mini for summaries, text-embedding-3-small for embeddings) for two reasons:

- **Single provider, single API key, single billing account.** One dependency, one point of integration, much simpler to set up and reason about. The trade-off is that an OpenAI outage would take down both features simultaneously, but for an assessment context this is the right call.
- **Model sizing.** GPT-4o-mini is roughly 15x cheaper per token than GPT-4o and sufficient for 2-3 sentence summarisation. text-embedding-3-small produces 1536-dimensional vectors that are adequate for document-level similarity — the larger text-embedding-3-large adds cost and latency without meaningful benefit at this scale.

The concurrency design was straightforward: creating or updating a book should generate both a summary and an embedding without making the caller wait for them sequentially. `asyncio.gather` fires both OpenAI calls simultaneously and returns when both complete: total wait time is the slower of the two calls, not their sum.

For the backfill endpoint (processing existing books that predate the feature), firing hundreds of requests simultaneously would hit OpenAI's rate limits. A semaphore with a concurrency limit of 5 is the standard pattern for this: it acts as a rate limiter without requiring an external queue or worker system.

### Semantic Search

pgvector was the obvious choice given the hint in the README and the fact that the database is already PostgreSQL. Storing embeddings in the same database as books keeps the architecture simple - no separate vector store to operate, no data synchronisation issues.

The search flow is straightforward: embed the query using the same model used to embed book texts, then find books whose stored embeddings are closest in the 1536-dimensional space. Cosine distance (`<=>` in pgvector) is the right metric because text-embedding-3-small produces normalised vectors - cosine distance measures the angle between vectors (i.e. semantic direction) regardless of magnitude, which is exactly what we want for text similarity.

---

## 2. Implementation

### RBAC

`require_admin` was added to `src/utils/auth.py`:

```python
async def require_admin(user: DBUser = Depends(authenticate_user)) -> DBUser:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
```

POST, PATCH, and DELETE endpoints on both the books and authors routers were updated to use `require_admin` instead of `authenticate_user`. GET endpoints were left unchanged.

**Test strategy challenge:** FastAPI's `app.dependency_overrides` is a single global dictionary. When a test uses both an `authenticated_client` (regular user) and an `admin_client`, the second fixture overwrites the first's override - both clients end up pointing at the same user. This meant we couldn't use the HTTP client to set up data as an admin and then test that a regular user gets 403, because there would only be one active user mock.

The fix was to set up test data via the service layer directly (bypassing the HTTP client) whenever a test needs to exercise two different user roles. The service layer writes directly to the test database session without going through the auth middleware at all. This is a pragmatic choice - in a production codebase with a more sophisticated test setup, you could standardise on API-layer setup throughout.

### Book Summaries

Three new fields were added to `DBBook`:

- `full_text: str | None` — the raw text submitted by an admin; stored for backfill but never returned in API responses (it's often copyrighted content and would waste bandwidth)
- `summary: str | None` — LLM-generated, returned in all book responses
- `embedding: list[float] | None` — stored as a pgvector `Vector(1536)` column, never returned in API responses (1536 floats adds ~12KB to every response for no user-facing value)

`src/utils/llm.py` wraps the OpenAI SDK with two async functions: `generate_summary` (GPT-4o-mini) and `generate_embedding` (text-embedding-3-small). Both use `AsyncOpenAI` — the non-blocking client — so they cooperate with FastAPI's event loop rather than freezing it.

**Bug caught during implementation:** The first version of `BookService.create()` tried to pass `summary` and `embedding` into `BookCreateInput`, which silently dropped them because those fields don't exist on that schema. Fixed by splitting into two steps: create the book first (without LLM fields), then call `repository.update()` with the LLM results.

The `POST /books/backfill-summaries` endpoint queries for all books where `full_text IS NOT NULL AND summary IS NULL` and processes them with `asyncio.Semaphore(5)` to limit concurrent OpenAI requests.

**pgvector setup:** The extension must be activated per database before tables are created. This is done in `app_lifespan.py` at startup:

```python
await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
await conn.run_sync(SQLModel.metadata.create_all)
```

The same `CREATE EXTENSION` call was added to the test `db_session` fixture in `conftest.py`, because tests create tables directly without going through the app lifespan.

**Python type annotation fix:** `list[tuple[DBBook, float]]` as a return type annotation caused a `TypeError` at import time in Python 3.9 because the built-in `list` doesn't support subscripting at runtime in that version. Fixed by adding `from __future__ import annotations` to the affected files — this makes all annotations strings evaluated lazily, avoiding the runtime error.

### Semantic Search

The search repository method uses raw SQL rather than the SQLModel ORM:

```sql
SELECT id, (embedding <=> CAST(:embedding AS vector)) AS distance
FROM books
WHERE embedding IS NOT NULL
ORDER BY distance ASC
LIMIT :limit
```

SQLModel has no native understanding of the `<=>` pgvector operator, so ORM-style query building isn't possible here. `text()` from SQLAlchemy lets us write arbitrary SQL with parameterised inputs (`:embedding`, `:limit`), which prevents SQL injection. The embedding list is cast explicitly to `vector` because Postgres needs to interpret the Python string representation as a native vector type.

**Route ordering:** The `/search` and `/backfill-summaries` endpoints were registered before `/{book_id}` in the router. FastAPI matches routes in registration order - if `/{book_id}` came first, a request to `/books/search` would match it with `book_id="search"`, then fail trying to parse `"search"` as a UUID.

**Test strategy for search:** Accurate vector similarity tests require controlling the embeddings. Tests create two books with orthogonal embeddings — `[1.0, 0.0, ...]` and `[0.0, 1.0, ...]` - and mock the query embedding to return `[1.0, 0.0, ...]`. With cosine distance, the first book scores 1.0 (identical direction) and the second scores 0.0 (orthogonal), verifying the ranking logic without needing real OpenAI responses. One non-obvious issue: pgvector returns numpy arrays from the database, not Python lists, so equality checks required wrapping with `list()` before comparing.

### Manual End-to-End Validation

All three features were tested live via Swagger UI at `http://localhost:8080/docs` with real OpenAI API calls.

**Book creation with LLM summary**: Created "Nineteen Eighty-Four" with a passage of full text. The API returned a summary generated by GPT-4o-mini:

> *"Nineteen Eighty-Four" follows Winston Smith, a disillusioned government worker in the totalitarian state of Oceania, who secretly rebels against the oppressive Party and its enigmatic leader, Big Brother. As he engages in a forbidden romance with Julia and seeks connection with a mysterious resistance, Winston grapples with the devastating consequences of living under constant surveillance and psychological manipulation. Orwell's chilling dystopia explores themes of truth, freedom, and the terrifying power of authoritarian control.*

**Semantic search scoring** — Two queries run against the same book:

| Query | Score |
|-------|-------|
| `"totalitarian government control"` | **0.39** |
| `"DEX AI talent"` | **0.10** |

The first query is semantically aligned with the book's content; the second is unrelated. The score gap confirms the cosine similarity is working as expected. A score of 0.39 for a short query against a paragraph of text is normal - what matters for search is relative ranking across results, not absolute scores.

---

## 3. Discussion

### What went well

The layered architecture (Router → Service → Repository) made it natural to place each concern in the right place. LLM calls live in the service layer, raw SQL lives in the repository, and the router stays thin. Adding three substantial features didn't require restructuring anything.

The async-first design of the existing codebase (FastAPI, asyncio, AsyncOpenAI) made the concurrency patterns straightforward. `asyncio.gather` and `asyncio.Semaphore` are standard library tools, no extra dependencies needed for concurrency.

### What was challenging

**The dependency_overrides conflict** was the trickiest part of the test suite. FastAPI's single global override dict means you can't simultaneously mock two different users in the same test. The workaround (service-layer setup for RBAC tests) works well but is a less obvious constraint.

**The summary-not-saving bug** was subtle: passing LLM-generated fields into a Pydantic schema that doesn't declare those fields causes Pydantic to silently drop them with no error. It only showed up when inspecting the actual database record after creation. The fix was architectural (separate the book creation from the LLM field update into two sequential repository calls).

### What I would do differently

**Standardise test setup.** The mix of API-layer and service-layer data setup in the test files is a pragmatic workaround but makes the tests harder to read at a glance. In a production codebase I'd invest in a cleaner test isolation patte. For example, factory fixtures that accept a user context, or a custom test client class that supports independent dependency overrides per instance.

**Error handling for LLM calls.** The current implementation has no retry logic or graceful degradation. If OpenAI returns a 429 (rate limit) or 500 during book creation, the entire request fails with a 500. In production I'd wrap LLM calls with exponential backoff retries and consider whether a book should be creatable without a summary, with LLM generation deferred to a background task.

**Async background tasks for LLM generation.** Currently the user waits for both OpenAI calls to complete before getting a response. For large full texts this adds several seconds of latency. A better UX would be to create the book immediately, return it with `summary: null`, and generate the summary/embedding asynchronously via FastAPI's `BackgroundTasks` or a task queue.

### How I would extend this given more time

- **HNSW indexing** on the embedding column for fast approximate nearest-neighbour search at scale. Without an index, the current search is a full table scan: fine for hundreds of books, slow for millions.
- **Hybrid search** combining semantic similarity with keyword filters (e.g. filter by author or price range, then rank by embedding distance). pgvector supports this through standard SQL `WHERE` clauses combined with the distance operator.
- **Finer-grained permissions** if the bookstore needed editor vs. admin vs. viewer roles rather than just the binary admin flag - that would warrant a proper roles table.
- **Embedding versioning**: if the embedding model is ever upgraded, all stored embeddings become incompatible with new query embeddings. A `embedding_model` column on `DBBook` and a re-embedding migration job would handle model transitions cleanly.