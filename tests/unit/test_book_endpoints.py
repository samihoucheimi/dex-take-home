"""Tests for book endpoints."""

import uuid
from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import DBBook
from src.routes.v1.authors.schema import AuthorCreateInput
from src.routes.v1.authors.service import AuthorService
from src.routes.v1.books.schema import BookCreateInput
from src.routes.v1.books.service import BookService


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_success(admin_client: AsyncClient, book_service: BookService):
    # Create test author via API first
    author_data = {"name": "Test Author", "bio": "Test bio"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {
        "title": "Great Book",
        "author_id": author["id"],
        "description": "A wonderful book",
        "price": 29.99,
        "published_date": "2024-01-15T10:00:00",
    }

    response = await admin_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == book_data["title"]
    assert data["author_id"] == author["id"]
    assert data["description"] == book_data["description"]
    assert data["price"] == book_data["price"]
    assert data["id"] is not None

    # Verify book was created in database
    created_book = await book_service.retrieve(book_id=UUID(data["id"]))
    assert created_book.title == book_data["title"]
    assert str(created_book.author_id) == author["id"]


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_without_optional_fields(admin_client: AsyncClient):
    # Create test author via API first
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {
        "title": "Simple Book",
        "author_id": author["id"],
        "price": 19.99,
    }

    response = await admin_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == book_data["title"]
    assert data["description"] is None
    assert data["published_date"] is None


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_invalid_price(admin_client: AsyncClient):
    # Create test author via API first
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {
        "title": "Bad Book",
        "author_id": author["id"],
        "price": -10.00,
    }

    response = await admin_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_zero_price(admin_client: AsyncClient):
    # Create test author via API first
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {
        "title": "Free Book",
        "author_id": author["id"],
        "price": 0,
    }

    response = await admin_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_empty_title(admin_client: AsyncClient):
    # Create test author via API first
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {
        "title": "",
        "author_id": author["id"],
        "price": 15.99,
    }

    response = await admin_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_list_books_empty(admin_client: AsyncClient):
    response = await admin_client.get("/api/v1/books")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_list_books_with_data(admin_client: AsyncClient):
    # Create test author via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    # Create test books via API
    book1_data = {"title": "Book One", "author_id": author["id"], "price": 19.99, "description": "First book"}
    book1_response = await admin_client.post("/api/v1/books", json=book1_data)
    assert book1_response.status_code == 201
    book1 = book1_response.json()

    book2_data = {"title": "Book Two", "author_id": author["id"], "price": 29.99}
    book2_response = await admin_client.post("/api/v1/books", json=book2_data)
    assert book2_response.status_code == 201
    book2 = book2_response.json()

    response = await admin_client.get("/api/v1/books")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(b["id"] == book1["id"] for b in data)
    assert any(b["id"] == book2["id"] for b in data)


@pytest.mark.asyncio(loop_scope="function")
async def test_get_book_success(admin_client: AsyncClient):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "Test Book", "author_id": author["id"], "description": "Test description", "price": 24.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    response = await admin_client.get(f"/api/v1/books/{created_book['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_book["id"]
    assert data["title"] == "Test Book"
    assert data["description"] == "Test description"
    assert data["price"] == 24.99


@pytest.mark.asyncio(loop_scope="function")
async def test_get_book_not_found(admin_client: AsyncClient):
    random_id = uuid.uuid4()
    response = await admin_client.get(f"/api/v1/books/{random_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_title(admin_client: AsyncClient, book_service: BookService):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "Original Title", "author_id": author["id"], "price": 19.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    update_data = {
        "title": "Updated Title",
    }

    response = await admin_client.patch(f"/api/v1/books/{created_book['id']}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated Title"
    assert data["price"] == 19.99

    # Verify title was updated in database
    updated_book = await book_service.retrieve(book_id=UUID(created_book["id"]))
    assert updated_book.title == "Updated Title"


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_price(admin_client: AsyncClient, book_service: BookService):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "Test Book", "author_id": author["id"], "price": 19.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    update_data = {
        "price": 29.99,
    }

    response = await admin_client.patch(f"/api/v1/books/{created_book['id']}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["price"] == 29.99

    # Verify price was updated in database
    updated_book = await book_service.retrieve(book_id=UUID(created_book["id"]))
    assert updated_book.price == 29.99


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_description(admin_client: AsyncClient, book_service: BookService):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "Test Book", "author_id": author["id"], "price": 19.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    update_data = {
        "description": "New description",
    }

    response = await admin_client.patch(f"/api/v1/books/{created_book['id']}", json=update_data)

    assert response.status_code == 200
    data = response.json()
    assert data["description"] == "New description"


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_invalid_price(admin_client: AsyncClient):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "Test Book", "author_id": author["id"], "price": 19.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    update_data = {
        "price": -5.00,
    }

    response = await admin_client.patch(f"/api/v1/books/{created_book['id']}", json=update_data)

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_not_found(admin_client: AsyncClient):
    random_id = uuid.uuid4()
    update_data = {
        "title": "New Title",
    }

    response = await admin_client.patch(f"/api/v1/books/{random_id}", json=update_data)

    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_book_success(admin_client: AsyncClient, book_service: BookService):
    # Create test author and book via API
    author_data = {"name": "Test Author"}
    author_response = await admin_client.post("/api/v1/authors", json=author_data)
    assert author_response.status_code == 201
    author = author_response.json()

    book_data = {"title": "To Delete", "author_id": author["id"], "price": 19.99}
    create_response = await admin_client.post("/api/v1/books", json=book_data)
    assert create_response.status_code == 201
    created_book = create_response.json()

    response = await admin_client.delete(f"/api/v1/books/{created_book['id']}")

    assert response.status_code == 204

    # Verify book was deleted from database
    with pytest.raises(Exception):
        await book_service.retrieve(book_id=UUID(created_book["id"]))


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_book_not_found(admin_client: AsyncClient):
    random_id = uuid.uuid4()
    response = await admin_client.delete(f"/api/v1/books/{random_id}")

    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_forbidden_for_regular_user(authenticated_client: AsyncClient, author_service: AuthorService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))

    book_data = {"title": "Forbidden Book", "author_id": str(author.id), "price": 19.99}
    response = await authenticated_client.post("/api/v1/books", json=book_data)

    assert response.status_code == 403


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_forbidden_for_regular_user(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    response = await authenticated_client.patch(f"/api/v1/books/{book.id}", json={"title": "Hacked Title"})

    assert response.status_code == 403


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_book_forbidden_for_regular_user(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    response = await authenticated_client.delete(f"/api/v1/books/{book.id}")

    assert response.status_code == 403


# --- LLM summary tests ---


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_with_full_text_generates_summary(admin_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    mock_embedding = [0.1] * 1536

    with patch("src.routes.v1.books.service.generate_summary", new_callable=AsyncMock) as mock_summary, \
            patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_summary.return_value = "A compelling story about software."
        mock_emb.return_value = mock_embedding

        response = await admin_client.post("/api/v1/books", json={
            "title": "LLM Book",
            "author_id": str(author.id),
            "price": 19.99,
            "full_text": "This is the full text of the book.",
        })

    assert response.status_code == 201
    data = response.json()
    assert data["summary"] == "A compelling story about software."

    # Verify persisted to DB
    book = await book_service.retrieve(book_id=UUID(data["id"]))
    assert book.summary == "A compelling story about software."
    assert list(book.embedding) == mock_embedding


@pytest.mark.asyncio(loop_scope="function")
async def test_create_book_without_full_text_has_no_summary(admin_client: AsyncClient, author_service: AuthorService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))

    response = await admin_client.post("/api/v1/books", json={
        "title": "No Text Book",
        "author_id": str(author.id),
        "price": 19.99,
    })

    assert response.status_code == 201
    assert response.json()["summary"] is None


@pytest.mark.asyncio(loop_scope="function")
async def test_update_book_with_full_text_regenerates_summary(admin_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Original", author_id=author.id, price=19.99))

    with patch("src.routes.v1.books.service.generate_summary", new_callable=AsyncMock) as mock_summary, \
            patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_summary.return_value = "Updated summary."
        mock_emb.return_value = [0.2] * 1536

        response = await admin_client.patch(f"/api/v1/books/{book.id}", json={"full_text": "New full text."})

    assert response.status_code == 200
    assert response.json()["summary"] == "Updated summary."


@pytest.mark.asyncio(loop_scope="function")
async def test_backfill_summaries_processes_books_without_summary(admin_client: AsyncClient, db_session: AsyncSession, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))

    # Create directly via db_session to set full_text without triggering LLM
    book = DBBook(title="Backfill Book", author_id=author.id, price=19.99, full_text="Text needing a summary.")
    await db_session.create(book)

    with patch("src.routes.v1.books.service.generate_summary", new_callable=AsyncMock) as mock_summary, \
            patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_summary.return_value = "Backfilled summary."
        mock_emb.return_value = [0.3] * 1536

        response = await admin_client.post("/api/v1/books/backfill-summaries")

    assert response.status_code == 200
    assert response.json() == {"processed": 1, "skipped": 0}

    updated_book = await book_service.retrieve(book_id=book.id)
    assert updated_book.summary == "Backfilled summary."


@pytest.mark.asyncio(loop_scope="function")
async def test_backfill_summaries_skips_books_with_existing_summary(admin_client: AsyncClient, db_session: AsyncSession, author_service: AuthorService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))

    # This book already has a summary — backfill should not touch it
    book = DBBook(title="Already Done", author_id=author.id, price=19.99, full_text="Some text.", summary="Existing summary.")
    await db_session.create(book)

    with patch("src.routes.v1.books.service.generate_summary", new_callable=AsyncMock) as mock_summary, \
            patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_summary.return_value = "Should not be set."
        mock_emb.return_value = [0.0] * 1536

        response = await admin_client.post("/api/v1/books/backfill-summaries")

    assert response.status_code == 200
    assert response.json()["processed"] == 0
    mock_summary.assert_not_called()


@pytest.mark.asyncio(loop_scope="function")
async def test_search_books_returns_ranked_results(admin_client: AsyncClient, author_service: AuthorService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))

    # Two orthogonal embeddings — cosine distance between them is 1 (maximally different)
    embedding_a = [1.0] + [0.0] * 1535
    embedding_b = [0.0, 1.0] + [0.0] * 1534

    with patch("src.routes.v1.books.service.generate_summary", new_callable=AsyncMock) as mock_summary, \
            patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_summary.return_value = "Summary A"
        mock_emb.return_value = embedding_a
        book_a = (await admin_client.post("/api/v1/books", json={"title": "Book A", "author_id": str(author.id), "price": 10.00, "full_text": "Text A"})).json()

        mock_summary.return_value = "Summary B"
        mock_emb.return_value = embedding_b
        book_b = (await admin_client.post("/api/v1/books", json={"title": "Book B", "author_id": str(author.id), "price": 10.00, "full_text": "Text B"})).json()

    # Query pointing in direction A — Book A should rank first
    with patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = [1.0] + [0.0] * 1535
        response = await admin_client.get("/api/v1/books/search?q=topic+A")

    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["book"]["id"] == book_a["id"]
    assert results[0]["score"] > results[1]["score"]


@pytest.mark.asyncio(loop_scope="function")
async def test_search_books_empty_when_no_embeddings(admin_client: AsyncClient):
    with patch("src.routes.v1.books.service.generate_embedding", new_callable=AsyncMock) as mock_emb:
        mock_emb.return_value = [0.1] * 1536
        response = await admin_client.get("/api/v1/books/search?q=anything")

    assert response.status_code == 200
    assert response.json() == []
