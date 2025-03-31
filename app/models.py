import datetime
import enum
import random
import string
import uuid
from typing import List, Optional

from sqlalchemy import ARRAY, UUID, Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    validates,
)

from app.validators import email_validator, name_validator, username_validator

# class MyModel(BaseModel):
#     model_config = ConfigDict(from_attributes=True)

#     metadata: dict[str, str] = Field(alias="metadata_")


class Base(AsyncAttrs, DeclarativeBase):
    pass


class UserGender(str, enum.Enum):
    male = "male"
    female = "female"
    prefer_not_to_say = "prefer_not_to_say"


class UserStatus(str, enum.Enum):
    active = "active"
    deactivated = "deactivated"
    deleted = "deleted"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        insert_default=uuid.uuid4,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    email: Mapped[str] = mapped_column(
        String,
        unique=True,
        index=True,
        nullable=False,
    )
    username: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    gender: Mapped[Optional[UserGender]] = mapped_column(
        Enum(UserGender), default=UserGender.prefer_not_to_say
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus),
        default=UserStatus.active,
    )
    profile_picture: Mapped[Optional[str]] = mapped_column(String)
    bio: Mapped[Optional[str]] = mapped_column(String)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)

    # refresh_tokens: Mapped[List["RefreshToken"]] = relationship(
    #     back_populates="user", cascade="all, delete-orphan"
    # )
    posts: Mapped[List["Post"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @validates("email")
    def validate_email(self, key, email):
        return email_validator(email)

    @validates("username")
    def validate_username(self, key, username):
        return username_validator(username)

    @validates("name")
    def validate_name(self, key, name):
        return name_validator(name)


# class RefreshToken(Base):
#     __tablename__ = "refresh_tokens"

#     id: Mapped[uuid.UUID] = mapped_column(
#         UUID,
#         primary_key=True,
#         insert_default=uuid.uuid4,
#     )
#     created_at: Mapped[datetime.datetime] = mapped_column(
#         DateTime(timezone=True),
#         insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
#     )
#     updated_at: Mapped[datetime.datetime] = mapped_column(
#         DateTime(timezone=True),
#         insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
#     )

#     token: Mapped[str] = mapped_column(String, unique=True)
#     expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

#     user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
#     user: Mapped["User"] = relationship(back_populates="refresh_tokens")


def random_thread_id():
    letters_and_digits = string.ascii_letters + string.digits
    return "".join(random.choices(letters_and_digits, k=12))


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID,
        primary_key=True,
        insert_default=random_thread_id,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        insert_default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    content: Mapped[str] = mapped_column(String)
    media: Mapped[Optional[List[str]]] = mapped_column(ARRAY(String))
    likes: Mapped[int] = mapped_column(Integer, default=0)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    user: Mapped["User"] = relationship(back_populates="posts")
