from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import jwt
from pwdlib import PasswordHash
from starlette.concurrency import run_in_threadpool

from app.domain.models import AuthError
from app.infrastructure.settings import Settings


class ArgonPasswords:
    def __init__(self):
        self.hasher = PasswordHash.recommended()

    async def hash(self, password: str) -> str:
        return await run_in_threadpool(self.hasher.hash, password)

    async def verify(self, password: str, password_hash: str) -> bool:
        return await run_in_threadpool(self.hasher.verify, password, password_hash)


class RsaTokens:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.private_key = Path(settings.jwt_private_key_path).read_text(encoding="utf-8")
        self.public_key = Path(settings.jwt_public_key_path).read_text(encoding="utf-8")

    def issue(self, user: dict, session: dict, expires_at) -> str:
        return jwt.encode(
            {
                "sub": user["id"],
                "sid": session["id"],
                "ver": user["auth_version"],
                "jti": uuid4().hex,
                "type": "access",
                "iat": datetime.now(UTC),
                "exp": expires_at,
                "iss": self.settings.jwt_issuer,
                "aud": self.settings.jwt_audience,
            },
            self.private_key,
            algorithm="RS256",
        )

    def decode(self, token: str) -> dict:
        try:
            claims = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                issuer=self.settings.jwt_issuer,
                audience=self.settings.jwt_audience,
                options={"require": ["sub", "sid", "ver", "type", "iat", "exp", "iss", "aud"]},
            )
        except jwt.InvalidTokenError as exc:
            raise AuthError("invalid_credentials") from exc
        if claims["type"] != "access" or not isinstance(claims["sid"], str):
            raise AuthError("invalid_credentials")
        return claims
