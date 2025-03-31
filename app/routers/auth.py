import logging
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

from app.cache import RedisDep
from app.config import get_settings
from app.database import SessionDep
from app.dependencies import read_current_user
from app.internal.users import create_user, get_user
from app.models import User, UserGender
from app.token import (
    create_access_token,
    create_login_token,
    create_refresh_token,
    create_verification_code,
    get_email_from_login_token,
    get_verification_code_from_login_token,
    invalidate_login_token,
    invalidate_refresh_token,
    store_login_token,
    store_refresh_token,
    validate_refresh_token,
)
from app.validators import username_validator

router = APIRouter(prefix="/auth", tags=["auth"])

resend.api_key = get_settings().resend_api_key


def generate_email_html(
    origin: str,
    code: str,
    token: str,
    is_new_user: bool,
    expiry_minutes: int,
):
    login_url = f"{origin}/login?token={token}&is-new-user={is_new_user}"
    current_year = datetime.now(timezone.utc).year

    return f"""<body style="background-color: white"> <table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style=" max-width: 37.5em; padding-left: 12px; padding-right: 12px; margin: 0 auto; " > <tbody> <tr style="width: 100%"> <td> <h1 style=" color: black; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; font-size: 24px; font-weight: bold; margin: 40px 0; padding: 0; " > Log in to Connector </h1> <p style=" font-size: 14px; line-height: 24px; margin-bottom: 14px; margin-top: 16px; color: black; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; margin: 24px 0; " > To complete the log in process; enter the verification code in the original window, or enter it in a new one by going to the link below: </p> <code style=" display: inline-block; padding: 16px 4.5%; width: 90.5%; background-color: #f5f5f5; border-radius: 5px; border: 1px; color: black; " >{code}</code > <a href="{login_url}" style=" color: #216fdb; text-decoration-line: none; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; font-size: 14px; text-decoration: underline; display: block; margin: 24px 0; " target="_blank" >{login_url}</a > <p style=" font-size: 14px; line-height: 24px; color: black; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; margin: 24px 0; " > This link and code will only be valid for the next {expiry_minutes} minutes. </p> <p style=" font-size: 14px; line-height: 24px; color: #999999; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; margin: 24px 0; " > If you didn't try to log in, you can safely ignore this email. </p> <hr style="width: 100%; border: none; border-top: 1px solid #e5e5e5" /> <p style=" font-size: 14px; line-height: 22px; color: #999999; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue', sans-serif; margin: 24px 0; " > © {current_year} Connector Inc. </p> </td> </tr> </tbody> </table> </body>"""


async def send_verification_email(
    origin: str,
    to_email: str,
    code: str,
    token: str,
    is_new_user: bool,
):
    try:
        html = generate_email_html(
            origin,
            code,
            token,
            is_new_user,
            get_settings().verification_email_expiry_minutes,
        )

        params: resend.Emails.SendParams = {
            "from": f"Connector <{get_settings().sender_email}>",
            "to": [to_email],
            "subject": f"{code} - Log in to Connector ",
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
        try:
            _ = await get_user(db, email=email)
            is_new_user = False
        except Exception:
            is_new_user = True

        token = create_login_token(email)
        verification_code = create_verification_code()

        store_login_token(redis, token, verification_code)

        background_tasks.add_task(
            send_verification_email,
            origin,
            email,
            verification_code,
            token,
            is_new_user,
        )

        return {"login_token": token, "is_new_user": is_new_user}

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
    body: AttemptUsernameBody,
    db: SessionDep,
):
    try:
        username = username_validator(body.username)

        try:
            _ = await get_user(db, username=username)
            raise ValueError("Username is already taken")
        except Exception:
            pass

        return {"available": True}

    except ValueError as e:
        return {"available": False, "error": str(e)}

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
    body: VerifyRequestBody,
    request: Request,
    response: Response,
    db: SessionDep,
    redis: RedisDep,
):
    try:
        token = body.token
        verification_code = body.verification_code
        is_new_user = body.is_new_user

        email = get_email_from_login_token(token)

        if not email:
            raise Exception("Invalid or expired token")

        saved_verification_code = get_verification_code_from_login_token(redis, token)

        if not saved_verification_code:
            raise Exception("Invalid or expired token")

        if verification_code != saved_verification_code:
            raise Exception("Invalid verification code")

        if is_new_user:
            name = body.name
            username = body.username
            gender = body.gender
            if not name or not username or not gender:
                raise Exception("Invalid new user data")

            user = await create_user(db, email, name, username, gender)
        else:
            user = await get_user(db, email=email)

        user_id = str(user.id)
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token()

        store_refresh_token(redis, refresh_token, user_id, request)
        invalidate_login_token(redis, token)

        # response.set_cookie(
        #     "access_token",
        #     access_token,
        #     httponly=True,
        #     secure=True,
        #     samesite="strict",
        #     expires=get_settings().access_token_expiry_minutes * 60,
        # )

        response.set_cookie(
            "refresh_token",
            refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            expires=get_settings().refresh_token_expiry_days * 24 * 60 * 60,
        )

        return {
            "access_token": access_token,
            "token_type": "bearer",
            # "refresh_token": refresh_token,
        }

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
    request: Request,
    response: Response,
    redis: RedisDep,
):
    try:
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise Exception("Refresh token not found")

        user_id = validate_refresh_token(redis, refresh_token)

        if not user_id:
            raise Exception("Invalid or expired refresh token")

        new_access_token = create_access_token(user_id)
        new_refresh_token = create_refresh_token()

        store_refresh_token(redis, new_refresh_token, user_id, request)
        invalidate_refresh_token(redis, refresh_token)

        # response.set_cookie(
        #     "access_token",
        #     new_access_token,
        #     httponly=True,
        #     secure=True,
        #     samesite="strict",
        #     expires=get_settings().access_token_expiry_minutes * 60,
        # )

        response.set_cookie(
            "refresh_token",
            new_refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            expires=get_settings().refresh_token_expiry_days * 24 * 60 * 60,
        )

        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            # "refresh_token": new_refresh_token,
        }

    except HTTPException:
        raise
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
    redis: RedisDep,
):
    try:
        refresh_token = request.cookies.get("refresh_token")

        if refresh_token:
            invalidate_refresh_token(redis, refresh_token)

        response.delete_cookie("refresh_token")

        return {"message": "Logged out"}

    except Exception as e:
        logging.error(f"Failed to log out: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to log out",
        )


@router.get("/")
async def read_auth(current_user: User = Depends(read_current_user)):
    return {
        "name": current_user.name,
        "username": current_user.username,
        "profile_picture": current_user.profile_picture,
    }
