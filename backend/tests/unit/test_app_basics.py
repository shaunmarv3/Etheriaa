import json

import httpx
import pytest
from fastapi import FastAPI
from typer.testing import CliRunner

from etheria.cli import app as cli_app
from etheria.core.errors import Conflict


async def test_health_is_ok_and_carries_a_request_id(client: httpx.AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert len(r.headers["x-request-id"]) == 32


async def test_a_safe_incoming_request_id_is_kept(client: httpx.AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "abc-123"})
    assert r.headers["x-request-id"] == "abc-123"


async def test_an_unsafe_incoming_request_id_is_replaced(client: httpx.AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "bad id <script>"})
    assert r.headers["x-request-id"] != "bad id <script>"
    assert len(r.headers["x-request-id"]) == 32


async def test_not_found_uses_the_error_shape(client: httpx.AsyncClient) -> None:
    r = await client.get("/nope")
    assert r.status_code == 404
    assert r.json() == {
        "error": {"code": "not_found", "message": "Not Found", "request_id": r.headers["x-request-id"]}
    }


async def test_app_errors_map_to_status_and_code(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def taken() -> None:
        raise Conflict("That name is taken", code="email_taken")

    app.add_api_route("/test/conflict", taken)
    r = await client.get("/test/conflict")
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "email_taken"
    assert r.json()["error"]["message"] == "That name is taken"


async def test_unhandled_errors_are_500_without_internals(app: FastAPI, client: httpx.AsyncClient) -> None:
    async def crash() -> None:
        raise RuntimeError("secret internals")

    app.add_api_route("/test/crash", crash)
    r = await client.get("/test/crash")
    assert r.status_code == 500
    assert r.json()["error"]["code"] == "internal_error"
    assert r.json()["error"]["request_id"]
    assert "secret internals" not in r.text


async def test_each_request_is_logged_as_json(
    client: httpx.AsyncClient, capsys: pytest.CaptureFixture[str]
) -> None:
    r = await client.get("/health")
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")]
    entry = next(e for e in lines if e.get("event") == "request")
    assert entry["request_id"] == r.headers["x-request-id"]
    assert (entry["path"], entry["status"]) == ("/health", 200)


def test_cli_lists_its_commands() -> None:
    result = CliRunner().invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    assert "api" in result.output and "migrate" in result.output
