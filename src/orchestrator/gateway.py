import time
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
    """Wraps a FastMCP HTTP server. Confirmed URL form: http://host:port/mcp"""

    def __init__(self, url: str, name: str, telemetry: Telemetry) -> None:
        super().__init__(url, name, telemetry)
