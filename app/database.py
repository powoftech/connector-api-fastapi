import uuid
from typing import Annotated

from fastapi import Depends
from sqlalchemy import NullPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.models import Base

connect_args = {
    "server_settings": {"jit": "off"},
    "prepared_statement_name_func": lambda: f"__asyncpg_{uuid.uuid4()}__",
}

engine = create_async_engine(
    get_settings().database_url_async,
    echo=True,
    poolclass=NullPool,
    connect_args=connect_args,
)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def drop_and_create_tables():
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)


async def get_session():
    async with async_session() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
