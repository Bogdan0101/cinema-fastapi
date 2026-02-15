from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.exceptions.token import BaseSecurityError
from src.database.models.accounts import UserModel, UserGroupEnum
from src.security.token import get_jwt_manager, JWTAuthManager
from src.database.postgresql import get_postgresql_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/accounts/login/")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_postgresql_db),
    jwt_manager: JWTAuthManager = Depends(get_jwt_manager),
) -> UserModel:
    try:
        payload = jwt_manager.decode_access_token(token)
        user_id = payload.get("user_id")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
            )
    except BaseSecurityError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired",
        )
    stmt = (
        select(UserModel)
        .options(joinedload(UserModel.group), joinedload(UserModel.profile))
        .where(UserModel.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active",
        )
    return user


async def get_current_moderator(
    current_user: UserModel = Depends(get_current_user),
) -> UserModel:
    if current_user.group.name not in [UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not a moderator",
        )
    return current_user
