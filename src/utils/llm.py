"""OpenAI helpers for summary generation and text embeddings."""

from openai import AsyncOpenAI

from src.settings import settings

_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def generate_summary(text: str) -> str:
    """Generate a customer-friendly 2-3 sentence book summary using GPT-4o-mini."""
    response = await _client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You write concise book summaries for an online bookstore. "
                    "Given the text of a book, produce a 2-3 sentence summary that "
                    "highlights the key themes and would help a customer decide whether to buy it."
                ),
            },
            {"role": "user", "content": text},
        ],
    )
    return response.choices[0].message.content


async def generate_embedding(text: str) -> list[float]:
    """Generate a 1536-dimensional embedding for the given text using text-embedding-3-small."""
    response = await _client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding
