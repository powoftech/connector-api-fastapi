import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import SessionDep
from app.dependencies import read_current_user
from app.internal.users import get_user
from app.models import User

router = APIRouter(prefix="/users", tags=["users"])


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
    username: str,
    current_user: User = Depends(read_current_user),
):
    try:
        user = await get_user(db, username=username)

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
