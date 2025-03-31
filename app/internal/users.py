from typing import Optional
from uuid import UUID

from pydantic import EmailStr
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, UserGender


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
    id: Optional[UUID] = None,
    email: Optional[EmailStr] = None,
    username: Optional[str] = None,
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
