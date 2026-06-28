import time
import os
from typing import Protocol, runtime_checkable

from fastmcp import Client

from src.orchestrator.recorders import Telemetry


@runtime_checkable
class ServerGateway(Protocol):
    async def ping(self) -> dict: ...
    async def validate_location(self, pos, barriers) -> dict: ...
    async def validate_move(
        self, to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move
    ) -> dict: ...
    async def place_barrier(self, pos, cop_barriers_left, barriers) -> dict: ...
    async def send_message(self, envelope: dict) -> dict: ...


class _BaseGateway:
    """Shared async-context-manager gateway; subclasses provide the transport."""

    def __init__(self, transport, name: str, telemetry: Telemetry) -> None:
        self._transport = transport
        self.name = name
        self._telemetry = telemetry
        self._client: Client | None = None

    async def __aenter__(self) -> "_BaseGateway":
        self._ctx = Client(self._transport)
        self._client = await self._ctx.__aenter__()
        return self

    async def __aexit__(self, *args) -> None:
        await self._ctx.__aexit__(*args)

    async def _call(self, tool_name: str, args: dict) -> dict:
        t0 = time.monotonic()
        result = await self._client.call_tool(tool_name, args)
        ms = (time.monotonic() - t0) * 1000
        self._telemetry.record(tool_name, ms)
        return result.data

    async def ping(self) -> dict:
        return await self._call("ping", {})

    async def validate_location(self, pos, barriers) -> dict:
        return await self._call("validate_location", {
            "pos": list(pos),
            "barriers": [list(b) for b in barriers],
        })

    async def validate_move(
        self, to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move
    ) -> dict:
        return await self._call("validate_move", {
            "to_move": to_move,
            "cop_pos": list(cop_pos),
            "thief_pos": list(thief_pos),
            "cop_barriers_left": cop_barriers_left,
            "barriers": [list(b) for b in barriers],
            "move": move,
        })

    async def place_barrier(self, pos, cop_barriers_left, barriers) -> dict:
        return await self._call("place_barrier", {
            "pos": list(pos),
            "cop_barriers_left": cop_barriers_left,
            "barriers": [list(b) for b in barriers],
        })

    async def send_message(self, envelope: dict) -> dict:
        return await self._call("send_message", {"envelope": envelope})


class InMemoryGateway(_BaseGateway):
    """Wraps a FastMCP server object — no real sockets, for tests."""

    def __init__(self, server, name: str, telemetry: Telemetry) -> None:
        super().__init__(server, name, telemetry)


class HttpGateway(_BaseGateway):
    """Wraps a FastMCP HTTP server. Confirmed URL form: http://host:port/mcp

    auth_token: when set, sends Authorization: Bearer <token> on every call.
    Verified API: Client("url", auth="<token>") — see SDK_REFERENCE §1.1.
    """

    def __init__(
        self,
        url: str,
        name: str,
        telemetry: Telemetry,
        auth_token: str | None = None,
    ) -> None:
        super().__init__(url, name, telemetry)
        self._auth_token = auth_token

    async def __aenter__(self) -> "HttpGateway":
        # CONFIRMED: Client(url, auth="<token>") sends Authorization: Bearer <token>
        # Source: FastMCP v3 docs (context7, 2026-06-27) — SDK_REFERENCE §1.1
        if self._auth_token:
            self._ctx = Client(self._transport, auth=self._auth_token)
        else:
            self._ctx = Client(self._transport)   # unchanged from original
        self._client = await self._ctx.__aenter__()
        return self


def gateway_from_env(role: str, config, telemetry: Telemetry) -> HttpGateway:
    """Build an HttpGateway from env (cloud) or config (local).

    Cloud mode (env set):
        COP_SERVER_URL  / THIEF_SERVER_URL  → public HTTPS URL incl. /mcp path
        COP_AUTH_TOKEN  / THIEF_AUTH_TOKEN  → bearer token (may be unset locally)
    Local mode (env absent):
        falls back to http://{config.servers.<role>.host}:{port}/mcp, no token.

    Args:
        role: "cop" or "thief" (case-insensitive).
        config: loaded Config object (must have config.servers set).
        telemetry: Telemetry instance to pass through.

    Returns:
        Configured HttpGateway (not yet entered as async context manager).
    """
    r = role.lower()
    r_upper = role.upper()
    url = os.environ.get(f"{r_upper}_SERVER_URL")
    if not url:
        ep = getattr(config.servers, r)
        url = f"http://{ep.host}:{ep.port}/mcp"
    raw_token = os.environ.get(f"{r_upper}_AUTH_TOKEN")
    token = raw_token if raw_token else None
    return HttpGateway(url=url, name=r, telemetry=telemetry, auth_token=token)
