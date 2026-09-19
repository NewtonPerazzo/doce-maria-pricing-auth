import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import AsyncMongoClient
from pymongo.errors import PyMongoError
from starlette.exceptions import HTTPException

from app.application.service import AuthService
from app.domain.models import AuthError, AuthPolicy
from app.infrastructure.mail import SmtpMailer
from app.infrastructure.mongo import MongoIdentityRepository
from app.infrastructure.security import ArgonPasswords, RsaTokens
from app.infrastructure.settings import Settings
from app.presentation.routes import router


def create_app(settings: Settings | None = None, repository=None, mailer=None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(application):
        client = None
        try:
            selected_repository = repository
            if selected_repository is None:
                client = AsyncMongoClient(
                    settings.mongodb_uri, tz_aware=True, serverSelectionTimeoutMS=5000
                )
                selected_repository = MongoIdentityRepository(client, settings.mongodb_database)
                await selected_repository.initialize()
            passwords = ArgonPasswords()
            application.state.service = AuthService(
                selected_repository,
                passwords,
                RsaTokens(settings),
                mailer or SmtpMailer(settings),
                AuthPolicy(
                    settings.access_token_minutes,
                    settings.refresh_token_days,
                    settings.password_reset_minutes,
                ),
                await passwords.hash(secrets.token_urlsafe(32)),
            )
            application.state.settings = settings
            yield
        finally:
            if client:
                await client.close()

    application = FastAPI(title="Doce Maria Pricing Auth", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @application.exception_handler(AuthError)
    async def auth_error(request: Request, error: AuthError):
        headers = {"WWW-Authenticate": "Bearer"} if error.status == 401 else {}
        if error.status == 429:
            headers["Retry-After"] = "60"
        return JSONResponse(
            {"error": {"code": error.code}}, status_code=error.status, headers=headers
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        details = [
            {"location": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return JSONResponse(
            {"error": {"code": "validation_error", "details": details}}, status_code=422
        )

    @application.exception_handler(PyMongoError)
    async def database_error(request: Request, error: PyMongoError):
        return JSONResponse({"error": {"code": "database_unavailable"}}, status_code=503)

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException):
        code = {
            404: "endpoint_not_found",
            405: "method_not_allowed",
            403: "forbidden",
            401: "invalid_credentials",
        }.get(error.status_code, "http_error")
        return JSONResponse(
            {"error": {"code": code}}, status_code=error.status_code, headers=error.headers
        )

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, error: Exception):
        logging.getLogger(__name__).error("Unhandled API failure", exc_info=error)
        response = JSONResponse({"error": {"code": "internal_error"}}, status_code=500)
        response.headers["Cache-Control"] = "no-store"
        origin = request.headers.get("origin")
        if origin in settings.cors_origins:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @application.middleware("http")
    async def secure_response(request: Request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.get("/health/live")
    async def live():
        return {"status": "ok"}

    application.include_router(router)
    return application


app = create_app()
