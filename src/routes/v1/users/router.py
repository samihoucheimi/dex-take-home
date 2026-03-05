from fastapi import APIRouter, Depends
from src.db.models import DBUser
from src.routes.v1.users.schema import TokenResponse, UserOutput, UserSignUpInput, UserUpdateInput
from src.routes.v1.users.service import UserService, get_user_service
from src.settings import settings
from src.utils.auth import authenticate_user, authenticate_user_login, create_session_token
from src.utils.redis import redis_client

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/signup", response_model=UserOutput, status_code=201)
async def signup(user_input: UserSignUpInput, user_service: UserService = Depends(get_user_service)):
    user = await user_service.create(data=user_input)
    return UserOutput(**user.model_dump())


@router.post("/login", response_model=TokenResponse)
async def login(user: DBUser = Depends(authenticate_user_login)):
    session_token = create_session_token()
    await redis_client.set(
        f"user_session:{session_token}",
        str(user.id),
        ex=settings.SESSION_EXPIRE_MINUTES * 60,
    )
    return TokenResponse(access_token=session_token, user=UserOutput(**user.model_dump()))


@router.get("/me", response_model=UserOutput)
async def get_me(current_user: DBUser = Depends(authenticate_user)):
    return UserOutput(**current_user.model_dump())


@router.patch("/me", response_model=UserOutput)
async def update_me(
    update_input: UserUpdateInput,
    current_user: DBUser = Depends(authenticate_user),
    user_service: UserService = Depends(get_user_service),
):
    user = await user_service.update(user_id=current_user.id, data=update_input)
    return UserOutput(**user.model_dump())


@router.delete("/me", status_code=204)
async def delete_me(
    current_user: DBUser = Depends(authenticate_user), user_service: UserService = Depends(get_user_service)
):
    await user_service.delete(user_id=current_user.id)
