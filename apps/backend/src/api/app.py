"""Medical Safety Assistant backend entry point."""

from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import os
import settings  # Load configuration before middleware and routes.
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from api.body_limit import BodyLimitMiddleware

from api.routes.admin import router as admin_router
from api.routes.auth import router as auth_router
from api.routes.ocr import router as ocr_router
from auth.seed import seed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    seed()
    yield


app = FastAPI(title="Medical Safety Assistant API", version="0.1.0", lifespan=lifespan)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(ocr_router)


@app.exception_handler(HTTPException)
async def http_error(_request: Request, error: HTTPException):
    codes = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT", 422: "INVALID_INPUT", 429: "RATE_LIMITED"}
    return JSONResponse(status_code=error.status_code, headers=error.headers, content={"detail": error.detail,
        "error": {"code": codes.get(error.status_code, "REQUEST_FAILED"), "message": error.detail}})


@app.exception_handler(RequestValidationError)
async def validation_error(_request: Request, error: RequestValidationError):
    # Never serialize input values (passwords/tokens) into validation errors.
    return JSONResponse(status_code=422, content={"detail": "Dữ liệu không hợp lệ",
        "error": {"code": "INVALID_INPUT", "message": "Dữ liệu không hợp lệ",
                  "fields": [".".join(map(str, e["loc"])) for e in error.errors()]}})


@app.middleware("http")
async def session_security(request: Request, call_next):
    response = None
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("origin")
        if origin is None:
            try:
                ref = urlsplit(request.headers.get("referer", ""))
                origin = f"{ref.scheme}://{ref.netloc}" if ref.scheme in {"http", "https"} and ref.netloc else None
            except ValueError:
                origin = None
        if origin not in settings.allowed_origins() or request.headers.get("sec-fetch-site") == "cross-site":
            response = JSONResponse(status_code=403, content={"detail": "Nguồn yêu cầu không được phép",
                "error": {"code": "FORBIDDEN", "message": "Nguồn yêu cầu không được phép"}})
    if response is None:
        response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
