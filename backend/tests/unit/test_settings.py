import base64

import pytest
from pydantic import ValidationError

from etheria.core.settings import Settings, to_psycopg_url

KEY = base64.b64encode(bytes(32)).decode()
BASE = {
    "_env_file": None,
    "database_url": "postgresql://a:b@h:1/d",
    "database_owner_url": "postgresql://o:p@h:1/d",
    "neo4j_password": "pw",
    "jwt_secret": "s" * 32,
    "data_encryption_key": KEY,
}


def test_defaults_match_spec() -> None:
    s = Settings(**BASE)
    assert s.access_token_ttl_seconds == 900
    assert s.refresh_token_ttl_days == 14
    assert s.cookie_secure is False


def test_missing_jwt_secret_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**{k: v for k, v in BASE.items() if k != "jwt_secret"})


def test_short_jwt_secret_fails() -> None:
    with pytest.raises(ValidationError, match="jwt_secret"):
        Settings(**{**BASE, "jwt_secret": "short"})


@pytest.mark.parametrize("key", ["not-base64!!", base64.b64encode(bytes(16)).decode()])
def test_bad_encryption_key_fails(key: str) -> None:
    with pytest.raises(ValidationError, match="data_encryption_key"):
        Settings(**{**BASE, "data_encryption_key": key})


def test_secrets_do_not_appear_in_repr() -> None:
    assert "s" * 32 not in repr(Settings(**BASE))


def test_psycopg_url() -> None:
    assert to_psycopg_url("postgresql://u:p@h:5433/d") == "postgresql+psycopg://u:p@h:5433/d"
    assert Settings(**BASE).sqlalchemy_url == "postgresql+psycopg://a:b@h:1/d"


def test_seed_dir_defaults_to_gitignored_backend_data() -> None:
    s = Settings(**BASE)
    assert s.seed_dir.parts[-3:] == ("backend", "data", "seed")
