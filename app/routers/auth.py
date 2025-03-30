import logging
import secrets
import string
from datetime import datetime, timezone
from typing import Optional

import resend
import resend.exceptions
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import (
    BaseModel,
    EmailStr,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.cache import RedisDep
from app.config import get_settings
from app.database import SessionDep, get_session
from app.dependencies import get_current_user
from app.jwt import (
    create_access_token,
    create_login_token,
    create_refresh_token,
    decode_jwt,
)
from app.models import RefreshToken, User, UserGender
from app.routers.users import create_user, get_user

router = APIRouter(prefix="/auth", tags=["auth"])

resend.api_key = get_settings().resend_api_key


def generate_verification_code():
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


def generate_email_html(
    origin: str,
    code: str,
    token: str,
    is_new_user: bool,
    expiry_minutes: int,
):
    login_url = f"{origin}/login?token={token}&is-new-user={is_new_user}"
    current_year = datetime.now(timezone.utc).year

    return f"""<body style="background-color: white">
                <table
                  align="center"
                  width="100%"
                  border="0"
                  cellpadding="0"
                  cellspacing="0"
                  role="presentation"
                  style="
                    max-width: 37.5em;
                    padding-left: 12px;
                    padding-right: 12px;
                    margin: 0 auto;
                  "
                >
                  <tbody>
                    <tr style="width: 100%">
                      <td>
                        <h1
                          style="
                            color: black;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            font-size: 24px;
                            font-weight: bold;
                            margin: 40px 0;
                            padding: 0;
                          "
                        >
                          Log in to Connector
                        </h1>
                        <p
                          style="
                            font-size: 14px;
                            line-height: 24px;
                            margin-bottom: 14px;
                            margin-top: 16px;
                            color: black;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            margin: 24px 0;
                          "
                        >
                          To complete the log in process; enter the verification code in the
                          original window, or enter it in a new one by going to the link
                          below:
                        </p>
                        <code
                          style="
                            display: inline-block;
                            padding: 16px 4.5%;
                            width: 90.5%;
                            background-color: #f5f5f5;
                            border-radius: 5px;
                            border: 1px;
                            color: black;
                          "
                          >{code}</code
                        >
                        <a
                          href="{login_url}"
                          style="
                            color: #216fdb;
                            text-decoration-line: none;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            font-size: 14px;
                            text-decoration: underline;
                            display: block;
                            margin: 24px 0;
                          "
                          target="_blank"
                          >{login_url}</a
                        >
                        <p
                          style="
                            font-size: 14px;
                            line-height: 24px;
                            color: black;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            margin: 24px 0;
                          "
                        >
                          This link and code will only be valid for the next {expiry_minutes} minutes.
                        </p>
                        <p
                          style="
                            font-size: 14px;
                            line-height: 24px;
                            color: #999999;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            margin: 24px 0;
                          "
                        >
                          If you didn't try to log in, you can safely ignore this email.
                        </p>
                        <hr
                          style="width: 100%; border: none; border-top: 1px solid #e5e5e5"
                        />
                        <p
                          style="
                            font-size: 14px;
                            line-height: 22px;
                            color: #999999;
                            font-family:
                              -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto',
                              'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans',
                              'Helvetica Neue', sans-serif;
                            margin: 24px 0;
                          "
                        >
                          © {current_year} Connector Inc.
                        </p>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </body>"""


async def send_verification_email(
    origin: str,
    to_email: str,
    verification_code: str,
    token: str,
    is_new_user: bool,
):
    try:
        html = generate_email_html(
            origin,
            verification_code,
            token,
            is_new_user,
            get_settings().verification_email_expiry_minutes,
        )

        params: resend.Emails.SendParams = {
            "from": f"Connector <{get_settings().sender_email}>",
            "to": [to_email],
            "subject": f"{verification_code} - Log in to Connector ",
            "html": html,
        }

        resend.Emails.send(params)
    except resend.exceptions.ResendError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email sending failed",
        )


class LoginRequestBody(BaseModel):
    email: EmailStr


@router.post(
    "/login/email",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}},
)
async def login_with_email(
    body: LoginRequestBody,
    request: Request,
    background_tasks: BackgroundTasks,
    db: SessionDep,
    redis: RedisDep,
):
    origin = request.headers.get("Origin", "")
    try:
        email = body.email
        user_query = await db.execute(select(User.id).where((User.email == email)))
        is_new_user = user_query.scalar_one_or_none() is None

        token = create_login_token(email)
        verification_code = generate_verification_code()

        background_tasks.add_task(
            redis.set,
            name=f"login:{token}",
            value=verification_code,
            ex=get_settings().verification_email_expiry_minutes * 60,
        )
        background_tasks.add_task(
            send_verification_email,
            origin,
            email,
            verification_code,
            token,
            is_new_user,
        )

        return {"token": token, "is_new_user": is_new_user}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Failed to send verification email: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to send verification email",
        )


class AttemptUsernameBody(BaseModel):
    username: str


@router.post(
    "/attempt/username",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}},
)
async def attempt_username(
    db: SessionDep,
    body: AttemptUsernameBody,
    request: Request,
    response: Response,
):
    try:
        username = body.username
        user_query = await db.execute(select(User.id).where(User.username == username))
        if user_query.scalar_one_or_none():
            available = False
        else:
            available = True

        return {"available": available}

    except Exception as e:
        logging.error(f"Failed to check username availability: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to check username availability",
        )


class VerifyRequestBody(BaseModel):
    token: str
    verification_code: str
    is_new_user: bool
    name: Optional[str] = None
    username: Optional[str] = None
    gender: Optional[UserGender] = None


@router.post(
    "/verify/email",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}},
)
async def verify_with_email(
    db: SessionDep,
    redis: RedisDep,
    body: VerifyRequestBody,
    response: Response,
    background_tasks: BackgroundTasks,
):
    try:
        token = body.token
        verification_code = body.verification_code
        is_new_user = body.is_new_user

        saved_code: str = redis.get(f"login:{token}") # type: ignore
        if not saved_code:
            raise Exception("Invalid or expired token")

        if verification_code != saved_code:
            raise Exception("Invalid verification code")

        login_payload = decode_jwt(token)
        if not login_payload:
            raise Exception("Invalid payload in token")

        email = login_payload["email"]
        if is_new_user:
            name = body.name
            username = body.username
            gender = body.gender
            if not name or not username or not gender:
                raise Exception("Invalid new user data")

            user = await create_user(db, email, name, username, gender)
        else:
            user: User = await get_user(db, redis, email=email)
        access_token = create_access_token(user_id=user.id, username=user.username)
        refresh_token = await create_refresh_token(db, user_id=user.id)

        background_tasks.add_task(redis.delete, f"login:{token}")
        # Create redirect response with session cookie
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=get_settings().access_token_expiry_minutes * 60,
            domain=get_settings().cookie_domain,
        )
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=get_settings().refresh_token_expiry_days * 24 * 60 * 60,
            domain=get_settings().cookie_domain,
        )

        return {"message": "Login successful"}

    except Exception as e:
        logging.error(f"Failed to verify login: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to verify login",
        )


@router.post(
    "/refresh",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "Bad Request"}},
)
async def refresh_access_token(
    db: SessionDep,
    redis: RedisDep,
    request: Request,
    response: Response,
):
    try:
        refresh_token = request.cookies.get("refresh_token")

        existing_refresh_token_query = await db.execute(
            select(RefreshToken.expires_at, RefreshToken.user_id).where(
                (RefreshToken.token == refresh_token)
            )
        )

        print("Reached here 1")

        existing_refresh_token = existing_refresh_token_query.all()[0]
        existing_refresh_token = {
            "expires_at": existing_refresh_token[0],
            "user_id": existing_refresh_token[1],
        }
        print(existing_refresh_token)

        if not existing_refresh_token or existing_refresh_token[
            "expires_at"
        ] < datetime.now(timezone.utc):
            raise Exception("Invalid refresh token")

        user: User = await get_user(db, redis, id=existing_refresh_token["user_id"])
        print("Reached here 2")
        access_token = create_access_token(user.id, user.username)
        response.set_cookie(
            key="access_token",
            value=access_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=get_settings().access_token_expiry_minutes * 60,
            domain=get_settings().cookie_domain,
        )

        return {"message": "Token refreshed"}

    except Exception as e:
        logging.error(f"Failed to refresh token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to refresh token",
        )


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_session),
):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if refresh_token:
            existing_refresh_token_query = await db.execute(
                select(RefreshToken).where((RefreshToken.token == refresh_token))
            )
            existing_refresh_token = existing_refresh_token_query.scalar_one_or_none()
            await db.delete(existing_refresh_token)

        response.delete_cookie(key="access_token")
        response.delete_cookie(key="refresh_token")

        return {"message": "Logged out"}

    except Exception as e:
        await db.rollback()
        raise e


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return {
        "name": current_user.name,
        "username": current_user.username,
        "profile_picture": current_user.profile_picture,
    }
