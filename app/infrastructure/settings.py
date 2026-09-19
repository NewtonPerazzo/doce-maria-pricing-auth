from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_database: str = "doce_maria_identity"
    jwt_private_key_path: str = ".keys/access-private.pem"
    jwt_public_key_path: str = ".keys/access-public.pem"
    jwt_issuer: str = "doce-maria-pricing-auth"
    jwt_audience: str = "pricing-api"
    access_token_minutes: int = Field(default=5, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=90)
    password_reset_minutes: int = Field(default=20, ge=1, le=60)
    cors_origins: list[str] = Field(default_factory=list)
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_starttls: bool = False
    mail_from: str = "Doce Maria <no-reply@docemaria.local>"
    auth_requests_per_minute: int = Field(default=30, ge=1)
