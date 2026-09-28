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


@app.command()
def worker() -> None:
    """Run the Temporal worker: document ingestion (spec 5.3)."""
    from etheria.core.settings import get_settings
    from etheria.ingestion.worker import run_worker

    asyncio.run(run_worker(get_settings()), loop_factory=_loop_factory())


@app.command(name="eval")
def eval_(
    suite: str = typer.Option("extraction", help="Which eval to run: extraction (M3)."),
) -> None:
    """Run an eval with the real models (opt-in: it costs money). Writes docs/evals/."""
    from etheria.core.settings import BACKEND_DIR, get_settings

    if suite != "extraction":
        typer.echo(f"unknown suite: {suite}", err=True)
        raise typer.Exit(2)
    from etheria.ingestion.eval import run_extraction_eval

    code = asyncio.run(
        run_extraction_eval(
            get_settings(),
            BACKEND_DIR / "tests" / "fixtures" / "reports",
            BACKEND_DIR.parent / "docs" / "evals" / "extraction.md",
        ),
        loop_factory=_loop_factory(),
    )
    raise typer.Exit(code)
