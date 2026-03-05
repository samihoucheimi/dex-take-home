from __future__ import annotations

import asyncio
import uuid

from fastapi import Depends, HTTPException
from sqlalchemy.exc import NoResultFound
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from src.db.models import DBBook
from src.db.operations import get_db_session
from src.routes.v1.books.repository import BookRepository
from src.routes.v1.books.schema import BookCreateInput, BookSearchResult, BookOutput, BookUpdateInput
from src.utils.llm import generate_embedding, generate_summary


class BookNotFound(HTTPException):
    def __init__(self) -> None:
        super().__init__(status_code=404, detail="Book not found")


async def get_book_service(db_session: AsyncSession = Depends(get_db_session)) -> "BookService":
    return BookService(db_session=db_session)


class BookService:
    def __init__(self, db_session: AsyncSession) -> None:
        self.repository = BookRepository(db_session=db_session)
        self.db_session = db_session

    async def create(self, data: BookCreateInput) -> DBBook:
        book = await self.repository.create(data=data)
        if data.full_text:
            summary, embedding = await asyncio.gather(
                generate_summary(data.full_text),
                generate_embedding(data.full_text),
            )
            book = await self.repository.update(book_id=book.id, summary=summary, embedding=embedding)
        return book

    async def retrieve(self, book_id: uuid.UUID) -> DBBook:
        try:
            return await self.repository.retrieve(book_id=book_id)
        except NoResultFound as exc:
            raise BookNotFound from exc

    async def list(self) -> list[DBBook]:
        return await self.repository.list()

    async def update(self, book_id: uuid.UUID, data: BookUpdateInput) -> DBBook:
        book = await self.retrieve(book_id=book_id)
        update_data = data.model_dump(exclude_unset=True)
        if "full_text" in update_data and update_data["full_text"]:
            summary, embedding = await asyncio.gather(
                generate_summary(update_data["full_text"]),
                generate_embedding(update_data["full_text"]),
            )
            update_data["summary"] = summary
            update_data["embedding"] = embedding
        return await self.repository.update(book_id=book.id, **update_data)

    async def delete(self, book_id: uuid.UUID) -> None:
        book = await self.retrieve(book_id=book_id)
        await self.repository.delete(book_id=book.id)

    async def backfill_summaries(self) -> dict[str, int]:
        stmt = select(DBBook).where(DBBook.full_text.is_not(None), DBBook.summary.is_(None))
        result = await self.db_session.exec(stmt)
        books = result.all()

        semaphore = asyncio.Semaphore(5)

        async def process_book(book: DBBook) -> None:
            async with semaphore:
                summary, embedding = await asyncio.gather(
                    generate_summary(book.full_text),
                    generate_embedding(book.full_text),
                )
                await self.repository.update(book_id=book.id, summary=summary, embedding=embedding)

        await asyncio.gather(*[process_book(b) for b in books])
        return {"processed": len(books), "skipped": 0}

    async def search(self, query: str, limit: int = 10) -> list[BookSearchResult]:
        embedding = await generate_embedding(query)
        books_with_scores = await self.repository.search_by_embedding(embedding=embedding, limit=limit)
        return [
            BookSearchResult(book=BookOutput(**book.model_dump()), score=1 - distance)
            for book, distance in books_with_scores
        ]
