import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.application.service import AuthService, digest
from app.domain.models import AuthError

router = APIRouter()
bearer = HTTPBearer(auto_error=False)
logger = logging.getLogger(__name__)


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginInput(Input):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RegistrationInput(LoginInput):
    password: str = Field(min_length=8, max_length=128)
    first_name: str = Field(min_length=1, max_length=80)
    last_name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=1, max_length=40)

    @field_validator("first_name", "last_name", "phone")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Field cannot be blank.")
        return value.strip()


class RefreshInput(Input):
    refresh_token: str = Field(min_length=1, max_length=512)


class ForgotInput(Input):
    email: EmailStr


class ResetInput(Input):
    reset_token: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=128)


class ProfileOutput(BaseModel):
    id: str
    email: EmailStr
    first_name: str
    last_name: str
    phone: str
    is_active: bool


class TokenOutput(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    access_token_expires_in: int


def service(request: Request) -> AuthService:
    return request.app.state.service


Service = Annotated[AuthService, Depends(service)]


async def throttle(request: Request):
    repository = request.app.state.service.repository
    address = request.client.host if request.client else "unknown"
    if not await repository.allow_request(
        digest(f"{request.url.path}:{address}"),
        datetime.now(UTC),
        request.app.state.settings.auth_requests_per_minute,
    ):
        raise AuthError("too_many_requests", 429)


@router.post(
    "/users", response_model=ProfileOutput, status_code=201, dependencies=[Depends(throttle)]
)
async def register(data: RegistrationInput, auth: Service):
    return await auth.register(data.model_dump())


@router.post("/authentication/login", response_model=TokenOutput, dependencies=[Depends(throttle)])
async def login(data: LoginInput, auth: Service):
    return await auth.login(str(data.email), data.password)


@router.post(
    "/authentication/refresh", response_model=TokenOutput, dependencies=[Depends(throttle)]
)
async def refresh(data: RefreshInput, auth: Service):
    return await auth.refresh(data.refresh_token)


@router.post("/authentication/logout", status_code=204, dependencies=[Depends(throttle)])
async def logout(data: RefreshInput, auth: Service):
    await auth.logout(data.refresh_token)
    return Response(status_code=204)


@router.get("/users/me", response_model=ProfileOutput)
async def profile(
    auth: Service, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    if not credentials:
        raise AuthError("invalid_credentials")
    return await auth.profile(credentials.credentials)


async def deliver_reset(auth: AuthService, email: str):
    try:
        await auth.forgot_password(email)
    except Exception:
        # Never log recipients, token contents, passwords, or SMTP credentials.
        logger.error("Password reset delivery failed; check mail service availability.")


@router.post("/authentication/forgot-password", status_code=202, dependencies=[Depends(throttle)])
async def forgot(data: ForgotInput, background: BackgroundTasks, auth: Service):
    allowed = await auth.repository.allow_request(
        digest(f"reset:{str(data.email).lower()}"),
        datetime.now(UTC),
        3,
    )
    if allowed:
        background.add_task(deliver_reset, auth, str(data.email))
    return {"message": "If the account exists, a recovery email will be sent."}


@router.post("/authentication/reset-password", status_code=204, dependencies=[Depends(throttle)])
async def reset(data: ResetInput, auth: Service):
    await auth.reset_password(data.reset_token, data.new_password)
    return Response(status_code=204)
