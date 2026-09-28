"""Command-line entry point: `uv run etheria <command>`."""

import asyncio
import sys

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


def _loop_factory() -> type[asyncio.AbstractEventLoop] | None:
    # psycopg async cannot use Windows' default ProactorEventLoop.
    return asyncio.SelectorEventLoop if sys.platform == "win32" else None


@app.command()
def api(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the FastAPI app."""
    import uvicorn

    from etheria.api.app import create_app

    server = uvicorn.Server(uvicorn.Config(create_app(), host=host, port=port, log_config=None))
    asyncio.run(server.serve(), loop_factory=_loop_factory())


@app.command()
def migrate() -> None:
    """Apply database migrations as the owner role."""
    from etheria.core.settings import get_settings
    from etheria.db.migrate import upgrade

    upgrade(get_settings().database_owner_url)
    typer.echo("database migrated to head")


@app.command()
def seed(
    skip_codes: bool = typer.Option(False, help="Skip phase 7 (external code lookups)."),
    verify_only: bool = typer.Option(False, help="Only phase 8: counts, canaries, NUMBERS.md."),
) -> None:
    """Load the knowledge layer (spec 6.4). Idempotent; exits non-zero on any failure."""
    from etheria.core.settings import get_settings
    from etheria.seed.runner import run_seed

    code = asyncio.run(
        run_seed(get_settings(), skip_codes=skip_codes, verify_only=verify_only),
        loop_factory=_loop_factory(),
    )
    raise typer.Exit(code)
