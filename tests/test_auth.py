from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app.infrastructure.settings import Settings
from app.main import create_app
from tests.fakes import CapturingMailer, MemoryIdentityRepository


@pytest.fixture
def context(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = tmp_path / "private.pem"
    public = tmp_path / "public.pem"
    private.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    public.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    settings = Settings(
        _env_file=None, jwt_private_key_path=str(private), jwt_public_key_path=str(public)
    )
    repository, mailer = MemoryIdentityRepository(), CapturingMailer()
    with TestClient(create_app(settings, repository, mailer)) as client:
        yield client, repository, mailer, key


def register(client):
    result = client.post(
        "/users",
        json={
            "email": "alice@example.com",
            "password": "strong-password",
            "first_name": "Alice",
            "last_name": "Baker",
            "phone": "+5511999999999",
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def login(client, password="strong-password"):
    result = client.post(
        "/authentication/login", json={"email": "alice@example.com", "password": password}
    )
    assert result.status_code == 200, result.text
    return result.json()


def profile(client, pair):
    return client.get("/users/me", headers={"Authorization": f"Bearer {pair['access_token']}"})


def test_registration_and_login_do_not_expose_password_hash(context):
    client, repository, _, _ = context
    user = register(client)
    assert "password_hash" not in user
    assert repository.users[user["id"]]["password_hash"].startswith("$argon2id$")
    pair = login(client)
    assert profile(client, pair).json()["id"] == user["id"]
    assert (
        client.post(
            "/authentication/login", json={"email": user["email"], "password": "wrong"}
        ).status_code
        == 401
    )


def test_refresh_rotation_and_replay_revoke_session(context):
    client, _, _, _ = context
    register(client)
    original = login(client)
    rotated = client.post(
        "/authentication/refresh", json={"refresh_token": original["refresh_token"]}
    )
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != original["refresh_token"]
    assert (
        client.post(
            "/authentication/refresh", json={"refresh_token": original["refresh_token"]}
        ).status_code
        == 401
    )
    assert profile(client, rotated.json()).status_code == 401


def test_logout_invalidates_identity_session(context):
    client, _, _, _ = context
    register(client)
    pair = login(client)
    assert (
        client.post(
            "/authentication/logout", json={"refresh_token": pair["refresh_token"]}
        ).status_code
        == 204
    )
    assert profile(client, pair).status_code == 401


def test_email_recovery_is_single_use_and_revokes_previous_sessions(context):
    client, repository, mailer, _ = context
    user = register(client)
    old_pair = login(client)
    known = client.post("/authentication/forgot-password", json={"email": user["email"]})
    unknown = client.post("/authentication/forgot-password", json={"email": "unknown@example.com"})
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert len(mailer.messages) == 1
    token = mailer.messages[0][1]
    assert repository.users[user["id"]]["reset_digest"] != token
    body = {"reset_token": token, "new_password": "new-strong-password"}
    assert client.post("/authentication/reset-password", json=body).status_code == 204
    assert client.post("/authentication/reset-password", json=body).status_code == 400
    assert profile(client, old_pair).status_code == 401
    assert (
        client.post(
            "/authentication/refresh", json={"refresh_token": old_pair["refresh_token"]}
        ).status_code
        == 401
    )
    assert profile(client, login(client, "new-strong-password")).status_code == 200


def test_expired_reset_and_access_tokens_rejected(context):
    client, repository, mailer, key = context
    user = register(client)
    pair = login(client)
    claims = jwt.decode(pair["access_token"], options={"verify_signature": False})
    claims["exp"] = datetime.now(UTC) - timedelta(seconds=1)
    expired = {"access_token": jwt.encode(claims, key, algorithm="RS256")}
    assert profile(client, expired).status_code == 401
    client.post("/authentication/forgot-password", json={"email": user["email"]})
    repository.users[user["id"]]["reset_expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    assert (
        client.post(
            "/authentication/reset-password",
            json={"reset_token": mailer.messages[0][1], "new_password": "new-password"},
        ).status_code
        == 400
    )


def test_rate_limit_and_input_validation(context):
    client, _, _, _ = context
    client.app.state.settings.auth_requests_per_minute = 1
    payload = {"email": "unknown@example.com", "password": "password"}
    assert client.post("/authentication/login", json=payload).status_code == 401
    assert client.post("/authentication/login", json=payload).status_code == 429
    assert (
        client.post(
            "/users",
            json={
                "email": "invalid",
                "password": "x",
                "first_name": " ",
                "last_name": "",
                "phone": "",
            },
        ).status_code
        == 422
    )
