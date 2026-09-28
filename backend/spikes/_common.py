"""Shared helpers for M0 spikes. ASCII output only (cp1252 console)."""

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
_results: list[tuple[str, bool]] = []


def load_env() -> None:
    load_dotenv(BACKEND / ".env")


def require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        sys.exit(f"missing {name} in backend/.env")
    return value


def check(name: str, ok: bool, detail: str = "") -> bool:
    _results.append((name, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  -> {detail}" if detail else ""))
    return ok


def summary() -> int:
    failed = [n for n, ok in _results if not ok]
    print(f"\n{len(_results) - len(failed)}/{len(_results)} checks passed")
    for n in failed:
        print(f"  failed: {n}")
    return 1 if failed else 0


def run(main: Callable[[], Awaitable[int]]) -> None:
    # psycopg async cannot use Windows' default ProactorEventLoop.
    sys.exit(asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop))
