from uuid import UUID

from fastapi import APIRouter, Depends
from src.db.models import DBUser
from src.routes.v1.books.schema import BookCreateInput, BookOutput, BookSearchResult, BookUpdateInput
from src.routes.v1.books.service import BookService, get_book_service
from src.utils.auth import authenticate_user, require_admin

router = APIRouter(prefix="/books", tags=["books"])


@router.post("", response_model=BookOutput, status_code=201)
async def create_book(
    book_input: BookCreateInput,
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(require_admin),
):
    book = await book_service.create(data=book_input)
    return BookOutput(**book.model_dump())


@router.get("", response_model=list[BookOutput])
async def list_books(
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(authenticate_user),
):
    books = await book_service.list()
    return [BookOutput(**book.model_dump()) for book in books]


# Must be registered before /{book_id} to avoid FastAPI treating "search" as a UUID
@router.get("/search", response_model=list[BookSearchResult])
async def search_books(
    q: str,
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(authenticate_user),
):
    return await book_service.search(query=q)


# Must be registered before /{book_id} for the same reason
@router.post("/backfill-summaries", response_model=dict)
async def backfill_summaries(
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(require_admin),
):
    return await book_service.backfill_summaries()


@router.get("/{book_id}", response_model=BookOutput)
async def get_book(
    book_id: UUID,
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(authenticate_user),
):
    book = await book_service.retrieve(book_id=book_id)
    return BookOutput(**book.model_dump())


@router.patch("/{book_id}", response_model=BookOutput)
async def update_book(
    book_id: UUID,
    update_input: BookUpdateInput,
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(require_admin),
):
    book = await book_service.update(book_id=book_id, data=update_input)
    return BookOutput(**book.model_dump())


@router.delete("/{book_id}", status_code=204)
async def delete_book(
    book_id: UUID,
    book_service: BookService = Depends(get_book_service),
    current_user: DBUser = Depends(require_admin),
):
    await book_service.delete(book_id=book_id)
