import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.application.ports import IdentityRepository, Mailer, PasswordHasher, Tokens
from app.domain.models import AuthError, AuthPolicy


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def public_profile(user: dict) -> dict:
    return {
        key: user[key] for key in ("id", "email", "first_name", "last_name", "phone", "is_active")
    }


class AuthService:
    def __init__(
        self,
        repository: IdentityRepository,
        passwords: PasswordHasher,
        tokens: Tokens,
        mailer: Mailer,
        policy: AuthPolicy,
        dummy_hash: str,
    ):
        self.repository = repository
        self.passwords = passwords
        self.tokens = tokens
        self.mailer = mailer
        self.policy = policy
        self.dummy_hash = dummy_hash

    async def register(self, data: dict) -> dict:
        user = {
            "id": uuid4().hex,
            "email": data["email"].strip().lower(),
            "first_name": data["first_name"].strip(),
            "last_name": data["last_name"].strip(),
            "phone": data["phone"].strip(),
            "is_active": True,
            "password_hash": await self.passwords.hash(data["password"]),
            "auth_version": 1,
            "created_at": datetime.now(UTC),
        }
        if not await self.repository.create_user(user):
            raise AuthError("user_already_exists", 409)
        return public_profile(user)

    async def login(self, email: str, password: str) -> dict:
        user = await self.repository.find_user(email.strip().lower())
        matches = await self.passwords.verify(
            password, user["password_hash"] if user else self.dummy_hash
        )
        if not user or not matches:
            raise AuthError("invalid_credentials")
        if not user["is_active"]:
            raise AuthError("inactive_user", 403)
        now = datetime.now(UTC)
        session_id = uuid4().hex
        refresh = f"{session_id}.{secrets.token_urlsafe(48)}"
        session = {
            "id": session_id,
            "user_id": user["id"],
            "refresh_digest": digest(refresh),
            "used_refresh_digests": [],
            "auth_version": user["auth_version"],
            "created_at": now,
            "expires_at": now + timedelta(days=self.policy.refresh_days),
            "revoked": False,
        }
        await self.repository.create_session(session)
        return self.pair(user, session, refresh)

    def pair(self, user: dict, session: dict, refresh: str) -> dict:
        expiry = datetime.now(UTC) + timedelta(minutes=self.policy.access_minutes)
        return {
            "access_token": self.tokens.issue(user, session, expiry),
            "refresh_token": refresh,
            "token_type": "bearer",
            "access_token_expires_in": self.policy.access_minutes * 60,
        }

    async def refresh(self, refresh_token: str) -> dict:
        session_id = refresh_token.split(".", 1)[0]
        session = await self.repository.get_session(session_id)
        now = datetime.now(UTC)
        if not session or session["revoked"] or session["expires_at"] <= now:
            raise AuthError("session_expired")
        token_digest = digest(refresh_token)
        if not hmac.compare_digest(session["refresh_digest"], token_digest):
            if token_digest in session["used_refresh_digests"]:
                await self.repository.revoke_session(session_id)
            raise AuthError("invalid_refresh_token")
        user = await self.repository.get_user(session["user_id"])
        if not user or not user["is_active"] or user["auth_version"] != session["auth_version"]:
            raise AuthError("session_expired")
        new_token = f"{session_id}.{secrets.token_urlsafe(48)}"
        if not await self.repository.rotate_session(
            session_id, token_digest, digest(new_token), now
        ):
            raise AuthError("invalid_refresh_token")
        return self.pair(user, session, new_token)

    async def logout(self, refresh_token: str) -> None:
        session = await self.repository.get_session(refresh_token.split(".", 1)[0])
        if session:
            token_digest = digest(refresh_token)
            if (
                hmac.compare_digest(session["refresh_digest"], token_digest)
                or token_digest in session["used_refresh_digests"]
            ):
                await self.repository.revoke_session(session["id"])

    async def profile(self, access_token: str) -> dict:
        claims = self.tokens.decode(access_token)
        user = await self.repository.get_user(claims["sub"])
        session = await self.repository.get_session(claims["sid"])
        if (
            not user
            or not session
            or not user["is_active"]
            or session["revoked"]
            or session["user_id"] != user["id"]
            or session["expires_at"] <= datetime.now(UTC)
            or claims.get("ver") != user["auth_version"]
            or session["auth_version"] != user["auth_version"]
        ):
            raise AuthError("session_expired")
        return public_profile(user)

    async def forgot_password(self, email: str) -> None:
        user = await self.repository.find_user(email.strip().lower())
        if not user or not user["is_active"]:
            return
        token = secrets.token_urlsafe(32)
        expiry = datetime.now(UTC) + timedelta(minutes=self.policy.reset_minutes)
        await self.repository.set_reset(user["id"], digest(token), expiry)
        await self.mailer.password_reset(user["email"], token)

    async def reset_password(self, token: str, password: str) -> None:
        hashed = await self.passwords.hash(password)
        if not await self.repository.reset_password(digest(token), hashed, datetime.now(UTC)):
            raise AuthError("invalid_reset_token", 400)
