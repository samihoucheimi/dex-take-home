"""Tests for order endpoints."""

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from src.routes.v1.authors.schema import AuthorCreateInput
from src.routes.v1.authors.service import AuthorService
from src.routes.v1.books.schema import BookCreateInput
from src.routes.v1.books.service import BookService
from src.routes.v1.orders.service import OrderService


@pytest.mark.asyncio(loop_scope="function")
async def test_create_order_success(authenticated_client: AsyncClient, order_service: OrderService, author_service: AuthorService, book_service: BookService, test_user):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    order_data = {"book_id": str(book.id), "quantity": 2}
    response = await authenticated_client.post("/api/v1/orders", json=order_data)

    assert response.status_code == 201
    data = response.json()
    assert data["user_id"] == str(test_user.id)
    assert data["book_id"] == str(book.id)
    assert data["quantity"] == 2
    assert data["total_amount"] == 39.98
    assert data["status"] == "pending"
    assert data["id"] is not None

    created_order = await order_service.retrieve(order_id=UUID(data["id"]))
    assert created_order.user_id == test_user.id
    assert created_order.book_id == book.id
    assert created_order.quantity == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_create_order_default_quantity(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService, test_user):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    order_data = {"book_id": str(book.id)}
    response = await authenticated_client.post("/api/v1/orders", json=order_data)

    assert response.status_code == 201
    data = response.json()
    assert data["quantity"] == 1
    assert data["total_amount"] == 19.99


@pytest.mark.asyncio(loop_scope="function")
async def test_create_order_invalid_quantity(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService, test_user):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    order_data = {"book_id": str(book.id), "quantity": 0}
    response = await authenticated_client.post("/api/v1/orders", json=order_data)

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_create_order_book_not_found(authenticated_client: AsyncClient, test_user):
    order_data = {"book_id": str(uuid.uuid4()), "quantity": 1}
    response = await authenticated_client.post("/api/v1/orders", json=order_data)

    assert response.status_code == 404
    assert "book" in response.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_list_orders_empty(authenticated_client: AsyncClient):
    response = await authenticated_client.get("/api/v1/orders")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


@pytest.mark.asyncio(loop_scope="function")
async def test_list_orders_with_data(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    order1_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 1})
    assert order1_response.status_code == 201
    order1 = order1_response.json()

    order2_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 2})
    assert order2_response.status_code == 201
    order2 = order2_response.json()

    response = await authenticated_client.get("/api/v1/orders")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert any(o["id"] == order1["id"] for o in data)
    assert any(o["id"] == order2["id"] for o in data)


@pytest.mark.asyncio(loop_scope="function")
async def test_get_order_success(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService, test_user):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    create_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 3})
    assert create_response.status_code == 201
    created_order = create_response.json()

    response = await authenticated_client.get(f"/api/v1/orders/{created_order['id']}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_order["id"]
    assert data["user_id"] == str(test_user.id)
    assert data["book_id"] == str(book.id)
    assert data["quantity"] == 3
    assert data["total_amount"] == 59.97
    assert data["status"] == "pending"


@pytest.mark.asyncio(loop_scope="function")
async def test_get_order_not_found(authenticated_client: AsyncClient):
    random_id = uuid.uuid4()
    response = await authenticated_client.get(f"/api/v1/orders/{random_id}")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio(loop_scope="function")
async def test_update_order_quantity(authenticated_client: AsyncClient, order_service: OrderService, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    create_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 1})
    assert create_response.status_code == 201
    created_order = create_response.json()

    response = await authenticated_client.patch(f"/api/v1/orders/{created_order['id']}", json={"quantity": 5})

    assert response.status_code == 200
    data = response.json()
    assert data["quantity"] == 5
    assert data["total_amount"] == 99.95

    updated_order = await order_service.retrieve(order_id=UUID(created_order["id"]))
    assert updated_order.quantity == 5


@pytest.mark.asyncio(loop_scope="function")
async def test_update_order_status(authenticated_client: AsyncClient, order_service: OrderService, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    create_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 1})
    assert create_response.status_code == 201
    created_order = create_response.json()

    response = await authenticated_client.patch(f"/api/v1/orders/{created_order['id']}", json={"status": "completed"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"

    updated_order = await order_service.retrieve(order_id=UUID(created_order["id"]))
    assert updated_order.status == "completed"


@pytest.mark.asyncio(loop_scope="function")
async def test_update_order_invalid_quantity(authenticated_client: AsyncClient, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    create_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 1})
    assert create_response.status_code == 201
    created_order = create_response.json()

    response = await authenticated_client.patch(f"/api/v1/orders/{created_order['id']}", json={"quantity": -1})

    assert response.status_code == 422


@pytest.mark.asyncio(loop_scope="function")
async def test_update_order_not_found(authenticated_client: AsyncClient):
    random_id = uuid.uuid4()
    response = await authenticated_client.patch(f"/api/v1/orders/{random_id}", json={"quantity": 5})

    assert response.status_code == 404


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_order_success(authenticated_client: AsyncClient, order_service: OrderService, author_service: AuthorService, book_service: BookService):
    author = await author_service.create(data=AuthorCreateInput(name="Test Author"))
    book = await book_service.create(data=BookCreateInput(title="Test Book", author_id=author.id, price=19.99))

    create_response = await authenticated_client.post("/api/v1/orders", json={"book_id": str(book.id), "quantity": 1})
    assert create_response.status_code == 201
    created_order = create_response.json()

    response = await authenticated_client.delete(f"/api/v1/orders/{created_order['id']}")

    assert response.status_code == 204

    with pytest.raises(Exception):
        await order_service.retrieve(order_id=UUID(created_order["id"]))


@pytest.mark.asyncio(loop_scope="function")
async def test_delete_order_not_found(authenticated_client: AsyncClient):
    random_id = uuid.uuid4()
    response = await authenticated_client.delete(f"/api/v1/orders/{random_id}")

    assert response.status_code == 404
