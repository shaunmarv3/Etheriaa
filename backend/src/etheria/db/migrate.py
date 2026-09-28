"""Programmatic Alembic, used by `etheria migrate` and the test harness."""

from alembic import command
from alembic.config import Config

from etheria.core.settings import BACKEND_DIR


def _config(owner_url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.set_main_option("sqlalchemy.url", owner_url.replace("%", "%%"))  # configparser escaping
    return cfg


def upgrade(owner_url: str, revision: str = "head") -> None:
    command.upgrade(_config(owner_url), revision)


def downgrade(owner_url: str, revision: str) -> None:
    command.downgrade(_config(owner_url), revision)
