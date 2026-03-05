from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import DBBook
from src.routes.v1.books.schema import BookCreateInput


class BookRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(self, data: BookCreateInput) -> DBBook:
        book = DBBook(**data.model_dump())
        return await self.db_session.create(book)

    async def retrieve(self, book_id: UUID) -> DBBook:
        stmt = select(DBBook).where(DBBook.id == book_id)
        result = await self.db_session.exec(stmt)
        return result.one()

    async def list(self) -> list[DBBook]:
        stmt = select(DBBook)
        result = await self.db_session.exec(stmt)
        return result.all()

    async def update(self, book_id: UUID, **kwargs) -> DBBook:
        book = await self.retrieve(book_id)
        for key, value in kwargs.items():
            setattr(book, key, value)
        return await self.db_session.update(book)

    async def delete(self, book_id: UUID) -> None:
        book = await self.retrieve(book_id)
        await self.db_session.delete(book)

    async def search_by_embedding(self, embedding: list[float], limit: int = 10) -> list[tuple[DBBook, float]]:
        stmt = text(
            "SELECT id, (embedding <=> CAST(:embedding AS vector)) AS distance "
            "FROM books WHERE embedding IS NOT NULL "
            "ORDER BY distance ASC LIMIT :limit"
        )
        result = await self.db_session.execute(stmt, {"embedding": str(embedding), "limit": limit})
        rows = result.fetchall()

        books_with_scores = []
        for row in rows:
            book = await self.retrieve(book_id=row.id)
            books_with_scores.append((book, row.distance))
        return books_with_scores
