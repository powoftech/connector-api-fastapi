import logging
from typing import Optional
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import EmailStr
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import RedisDep
from app.database import SessionDep
from app.dependencies import get_current_user
from app.models import User, UserGender

router = APIRouter(prefix="/users", tags=["users"])


async def create_user(
    db: AsyncSession,
    email: EmailStr,
    name: str,
    username: str,
    gender: UserGender,
):
    try:
        # Check if user already exists
        existing_user_query = await db.execute(
            select(User.id).where((User.email == email) | (User.username == username))
        )
        if existing_user_query.scalar_one_or_none():
            raise Exception("User with this email or username already exists")

        # Create new user
        user = User(
            email=email,
            name=name,
            username=username,
            gender=gender,
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        return user

    except Exception as e:
        await db.rollback()
        raise e


async def get_user(
    db: AsyncSession,
    redis: redis.Redis,
    id: Optional[UUID] = None,
    email: Optional[EmailStr] = None,
    username: Optional[str] = None,
    _: User = Depends(get_current_user),
):
    user_query = await db.execute(
        select(User).where(
            or_(
                User.id == id,
                User.email == email,
                User.username == username,
            )
        )
    )
    user = user_query.scalar_one_or_none()
    if not user:
        raise Exception(f"User not found (id:{id}, email:{email}, username:{username})")

    return user


@router.get(
    "/{username}",
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"},
        status.HTTP_401_UNAUTHORIZED: {"description": "Unauthorized"},
        status.HTTP_404_NOT_FOUND: {"description": "Not Found"},
    },
)
async def read_user_with_username(
    db: SessionDep,
    redis: RedisDep,
    username: str,
    current_user: User = Depends(get_current_user),
):
    try:
        user: User = await get_user(db, redis, username=username)

        return {
            "name": user.name,
            "username": user.username,
            "profile_picture": user.profile_picture,
            "bio": user.bio,
            "is_private": user.is_private,
            "is_self": user.id == current_user.id,
            # "posts": user.posts,
            # "replies": user.replies,
        }
    except Exception as e:
        logging.error(f"Failed to read user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to read user"
        )
