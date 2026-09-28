"""Configuration from the environment (backend/.env). Startup fails when a
required secret is missing or malformed (spec 11.1, secret leakage row)."""

import base64
import binascii
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[3]


def to_psycopg_url(url: str) -> str:
    """postgresql://... -> postgresql+psycopg://... (SQLAlchemy's psycopg 3 driver)."""
    return url.replace("postgresql://", "postgresql+psycopg://", 1)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    env: Literal["dev", "test"] = "dev"
    log_level: str = "INFO"

    database_url: str
    database_owner_url: str
    redis_url: str = "redis://localhost:6380/0"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr
    temporal_address: str = "localhost:7233"

    jwt_secret: SecretStr
    data_encryption_key: SecretStr
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_days: int = 14
    cors_origins: list[str] = ["http://localhost:3000"]
    cookie_secure: bool = False

    deepseek_api_key: SecretStr | None = None
    ncbi_api_key: SecretStr | None = None
    bioportal_api_key: SecretStr | None = None

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_is_long(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters")
        return v

    @field_validator("data_encryption_key")
    @classmethod
    def _encryption_key_is_32_bytes(cls, v: SecretStr) -> SecretStr:
        try:
            raw = base64.b64decode(v.get_secret_value(), validate=True)
        except (binascii.Error, ValueError) as e:
            raise ValueError("DATA_ENCRYPTION_KEY must be base64") from e
        if len(raw) != 32:
            raise ValueError("DATA_ENCRYPTION_KEY must decode to 32 bytes (AES-256)")
        return v

    @property
    def sqlalchemy_url(self) -> str:
        return to_psycopg_url(self.database_url)

    @property
    def sqlalchemy_owner_url(self) -> str:
        return to_psycopg_url(self.database_owner_url)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
