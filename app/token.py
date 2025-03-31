import json
import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import redis
from fastapi import Request
from fastapi.encoders import jsonable_encoder

from app.config import get_settings


# Login token
def create_login_token(
    email: str,
    expires_delta: timedelta = timedelta(
        minutes=get_settings().verification_email_expiry_minutes,
    ),
):
    payload = {
        "email": email,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    token = encode_jwt(payload)
    return token


def create_verification_code():
    PARTS = 4
    WORDS_EACH_PART = 5
    word_parts = []
    for _ in range(PARTS):
        word_parts.append(
            "".join(
                secrets.choice(string.ascii_lowercase) for _ in range(WORDS_EACH_PART)
            )
        )
    return "-".join(word_parts)


def store_login_token(redis: redis.Redis, token: str, code: str):
    redis.set(
        f"login_token:{token}",
        code,
        ex=get_settings().verification_email_expiry_minutes * 60,
    )


def get_verification_code_from_login_token(redis: redis.Redis, token: str):
    code = str(redis.get(f"login_token:{token}"))
    return code if code else None


def get_email_from_login_token(token: str):
    payload = decode_jwt(token)
    email = payload["email"]
    return email if email else None


def invalidate_login_token(redis: redis.Redis, token: str):
    redis.delete(f"login_token:{token}")


# Access token
def create_access_token(
    user_id: str,
    expires_delta: timedelta = timedelta(
        minutes=get_settings().access_token_expiry_minutes,
    ),
):
    payload = {
        "sub": user_id,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + expires_delta,
    }
    token = encode_jwt(payload)
    return token


def get_user_id_from_access_token(token: str):
    payload = decode_jwt(token)
    user_id = payload["sub"]
    return user_id if user_id else None


# Refresh token
def create_refresh_token():
    token = str(uuid.uuid4())
    return token


def store_refresh_token(
    redis: redis.Redis,
    token: str,
    user_id: str,
    # client_id: str,
    # user_agent: str,
    # ip: str,
    request: Request,
):
    client_id = request.headers.get("client_id", "web-app")
    user_agent = request.headers.get("user-agent", "")
    ip = (
        request.client.host
        if request.client and hasattr(request.client, "host")
        else ""
    )
    iat = datetime.now(timezone.utc)
    exp = datetime.now(timezone.utc) + timedelta(
        days=get_settings().refresh_token_expiry_days
    )

    token_data = {
        "user_id": user_id,
        "client_id": client_id,
        "user_agent": user_agent,
        "ip": ip,
        "iat": iat,
        "exp": exp,
        "is_active": True,
    }

    redis.set(
        f"refresh_token:{token}",
        json.dumps(jsonable_encoder(token_data)),
        ex=get_settings().refresh_token_expiry_days * 24 * 60 * 60,
    )

    redis.sadd(f"user_sessions:{user_id}", token)


def get_token_data_from_refresh_token(redis: redis.Redis, token: str):
    token_data_str = redis.get(f"refresh_token:{token}")
    return json.loads(str(token_data_str)) if token_data_str else None


def validate_refresh_token(redis: redis.Redis, token: str):
    token_data = get_token_data_from_refresh_token(redis, token)

    if not token_data:
        raise ValueError("Invalid token")

    if not token_data["is_active"]:
        raise ValueError("Expired token")

    if datetime.strptime(
        token_data["exp"],
        "%Y-%m-%dT%H:%M:%S.%f%z",
    ) < datetime.now(timezone.utc):
        raise ValueError("Expired token")

    return token_data["user_id"]


def invalidate_refresh_token(redis: redis.Redis, token: str):
    token_data = get_token_data_from_refresh_token(redis, token)
    if not token_data:
        raise ValueError("Invalid token")

    token_data["is_active"] = False
    redis.set(
        f"refresh_token:{token}",
        json.dumps(jsonable_encoder(token_data)),
        ex=(
            datetime.strptime(token_data["exp"], "%Y-%m-%dT%H:%M:%S.%f%z")
            - datetime.now(timezone.utc)
        ).seconds,
    )
    redis.srem(f"user_sessions:{token_data['user_id']}", token)


def encode_jwt(payload: dict):
    token = jwt.encode(
        payload,
        get_settings().jwt_secret_key,
        algorithm=get_settings().jwt_algorithm,
    )
    return token


def decode_jwt(token: str):
    payload = jwt.decode(
        token,
        get_settings().jwt_secret_key,
        algorithms=[get_settings().jwt_algorithm],
    )
    return payload
