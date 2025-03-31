from typing import Annotated

import jwt
from fastapi import (
    Depends,
    HTTPException,
    status,
)
from fastapi.security import OAuth2PasswordBearer

from app.database import SessionDep
from app.internal.users import get_user
from app.token import get_user_id_from_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


async def read_current_user(
    db: SessionDep,
    token: Annotated[str, Depends(oauth2_scheme)],
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = get_user_id_from_access_token(token)
        if user_id is None:
            raise credentials_exception
    except jwt.InvalidTokenError:
        raise credentials_exception

    user = await get_user(
        db,
        id=user_id,
    )
    if not user:
        raise credentials_exception

    return user
