"""Command-line entry point: `uv run etheria <command>`."""

import asyncio
import sys
from typing import Annotated

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


@app.command()
def maintain() -> None:
    """Run the daily maintenance jobs once: partitions, audit retention, thread pruning."""
    from etheria.core.settings import get_settings
    from etheria.db.session import Database
    from etheria.maintenance.jobs import run_all

    async def main() -> None:
        db = Database(get_settings().sqlalchemy_url)
        try:
            typer.echo((await run_all(db)).model_dump_json())
        finally:
            await db.dispose()

    asyncio.run(main(), loop_factory=_loop_factory())


@app.command(name="eval")
def eval_(
    suite: str = typer.Option("extraction", help="Which eval: extraction (M3) or graph (M4)."),
    only: Annotated[
        list[str] | None, typer.Option(help="Run only these scenario ids (graph; no report).")
    ] = None,
) -> None:
    """Run an eval with the real models (opt-in: it costs money). Writes docs/evals/."""
    from etheria.core.settings import BACKEND_DIR, get_settings

    if suite == "graph":
        raise typer.Exit(asyncio.run(_graph_eval(only or []), loop_factory=_loop_factory()))
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


async def _graph_eval(only: list[str]) -> int:
    from redis.asyncio import Redis

    from etheria.api.chat_wiring import build_chat
    from etheria.core.settings import get_settings
    from etheria.db.session import Database
    from etheria.graph.eval import run_suite
    from etheria.knowledge.neo4j import create_driver

    settings = get_settings()
    db, redis, driver = (
        Database(settings.sqlalchemy_url),
        Redis.from_url(settings.redis_url),
        (create_driver(settings)),
    )
    stack = await build_chat(settings, db, redis, driver)
    try:
        if stack.service is None:
            typer.echo("DEEPSEEK_API_KEY is not set", err=True)
            return 2
        return await run_suite(stack, settings, db, only or None)
    finally:
        await stack.close()
        await driver.close()
        await redis.aclose()
        await db.dispose()


@app.command(name="graph-diagram")
def graph_diagram() -> None:
    """Regenerate the Mermaid diagram of the compiled chat graph in docs/ARCHITECTURE.md."""
    from etheria.core.settings import BACKEND_DIR
    from etheria.graph.diagram import write_diagram

    path = BACKEND_DIR.parent / "docs" / "ARCHITECTURE.md"
    write_diagram(path)
    typer.echo(f"wrote {path}")
