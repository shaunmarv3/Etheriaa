"""Alembic environment. Migrations are hand-written SQL (RLS, partitions,
SECURITY DEFINER functions) and always run as the owner role."""

from alembic import context
from sqlalchemy import create_engine, pool

from etheria.core.settings import to_psycopg_url


def _owner_url() -> str:
    url = context.config.get_main_option("sqlalchemy.url")
    if not url:
        from etheria.core.settings import get_settings

        url = get_settings().database_owner_url
    return to_psycopg_url(url)


def run() -> None:
    engine = create_engine(_owner_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


run()
