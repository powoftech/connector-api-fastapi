import time
from contextlib import asynccontextmanager
from typing import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import ORJSONResponse

from app.config import get_settings
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


if get_settings().environment == "production":
    origins = [
        "https://connector.rocks",
        "https://www.connector.rocks",
    ]
else:
    origins = [
        "http://localhost:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3000",
        "https://127.0.0.1:3000",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if get_settings().environment == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "*.connector.rocks",
        ],
    )


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


# @app.middleware("http")
# async def add_security_headers(
#     request: Request,
#     call_next: Callable[[Request], Awaitable[Response]],
# ):
#     response = await call_next(request)
#     # Add security headers here if needed
#     # --- Add Security Headers ---

#     # Strict-Transport-Security (HSTS)
#     # Tells browsers to always connect via HTTPS for the specified duration.
#     # Include 'includeSubDomains' if all subdomains are HTTPS-only.
#     # Add 'preload' if you want to submit your domain to browser preload lists (requires careful consideration).
#     # IMPORTANT: Only enable HSTS once you are SURE your site works correctly over HTTPS.
#     response.headers["Strict-Transport-Security"] = (
#         "max-age=31536000; includeSubDomains"  # 1 year
#     )

#     # X-Content-Type-Options
#     # Prevents browsers from MIME-sniffing the content-type away from the declared one.
#     response.headers["X-Content-Type-Options"] = "nosniff"

#     # X-Frame-Options
#     # Protects against Clickjacking attacks by controlling if the site can be embedded in an <iframe>.
#     # 'DENY': No embedding allowed.
#     # 'SAMEORIGIN': Embedding allowed only by pages from the same origin.
#     response.headers["X-Frame-Options"] = "DENY"  # Or "SAMEORIGIN" if needed

#     # Referrer-Policy
#     # Controls how much referrer information (the page the user came from) is included with requests.
#     # 'strict-origin-when-cross-origin': Sends full URL on same-origin, only origin on cross-origin HTTPS->HTTPS, no header on HTTPS->HTTP. (Good default)
#     # 'no-referrer': Sends no referrer information.
#     response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

#     # Permissions-Policy (formerly Feature-Policy)
#     # Allows you to selectively enable/disable browser features and APIs (camera, microphone, geolocation, etc.).
#     # Start restrictive and allow only what you need. Example: disable microphone and geolocation.
#     # Check MDN for available directives: https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Permissions-Policy
#     response.headers["Permissions-Policy"] = "microphone=(), geolocation=()"

#     # Content-Security-Policy (CSP) - POWERFUL but COMPLEX
#     # Mitigates XSS by defining allowed sources for content (scripts, styles, images, etc.).
#     # This requires CAREFUL configuration based on YOUR specific application needs (CDNs, inline scripts, etc.).
#     # A VERY restrictive starting point (likely needs loosening):
#     # response.headers["Content-Security-Policy"] = "default-src 'self'; object-src 'none'; script-src 'self'; style-src 'self'; img-src 'self';"
#     # ---> GENERATE A POLICY specific to your app <---
#     # Tools like https://report-uri.com/home/generate or https://csp-evaluator.withgoogle.com/ can help.
#     # Be very careful with 'unsafe-inline' and 'unsafe-eval'. Avoid if possible.
#     # You might initially set it to "Content-Security-Policy-Report-Only" to monitor violations without blocking.
#     # Example allowing Bootstrap CDN and self:
#     # response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; style-src 'self' https://cdn.jsdelivr.net; object-src 'none';"

#     # --- End Security Headers ---
#     return response


app.include_router(auth.router)
app.include_router(users.router)
