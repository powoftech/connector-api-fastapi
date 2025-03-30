import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import RefreshToken


def create_login_token(
    email: str,
    expires_delta: timedelta = timedelta(
        minutes=get_settings().verification_email_expiry_minutes
    ),
):
    payload = {
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    token = jwt.encode(
        payload,
        get_settings().jwt_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )

    return token


def create_access_token(
    user_id: uuid.UUID,
    username: str,
    expires_delta: timedelta = timedelta(
        minutes=get_settings().access_token_expiry_minutes
    ),
):
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }

    token = jwt.encode(
        payload,
        get_settings().jwt_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )

    return token


async def create_refresh_token(
    db: AsyncSession,
    user_id: uuid.UUID,
    expires_delta: timedelta = timedelta(days=get_settings().refresh_token_expiry_days),
):
    try:
        token = str(uuid.uuid4())
        expire = datetime.now(timezone.utc) + expires_delta

        refresh_token = RefreshToken(token=token, expires_at=expire, user_id=user_id)

        db.add(refresh_token)
        await db.commit()
        await db.refresh(refresh_token)

        return str(refresh_token.token)

    except Exception as e:
        await db.rollback()
        raise e


def decode_jwt(token: str):
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret_key,
            algorithms=[get_settings().jwt_algorithm],
        )
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )
