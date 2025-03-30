import time
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, RedirectResponse

from app.routers import auth, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    # from app.database import drop_and_create_tables

    # await drop_and_create_tables()

    yield


app = FastAPI(
    title="Connector API",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)


origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "http://127.0.0.1:3000",
    "https://127.0.0.1:3000",
    "https://connector.rocks",
    "https://www.connector.rocks",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", include_in_schema=False)
async def root():
    return RedirectResponse("/docs")


@app.middleware("http")
async def add_process_time_header(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
):
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time = time.perf_counter() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


app.include_router(auth.router)
app.include_router(users.router)
