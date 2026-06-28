from fastmcp import FastMCP
from src.game.config import load_config
from src.mcp_servers import tools

import os

from src.mcp_servers.auth import build_auth


def build_thief_server(config, auth_token: str | None = None) -> FastMCP:
    mcp = FastMCP("thief", auth=build_auth(auth_token))

    @mcp.tool
    def ping() -> dict:
        return tools.ping_result("thief")

    @mcp.tool
    def validate_location(pos: list[int], barriers: list[list[int]]) -> dict:
        return tools.validate_location_result(pos, barriers, config)

    @mcp.tool
    def validate_move(
        to_move: str,
        cop_pos: list[int],
        thief_pos: list[int],
        cop_barriers_left: int,
        barriers: list[list[int]],
        move: str,
    ) -> dict:
        return tools.validate_move_result(
            to_move, cop_pos, thief_pos, cop_barriers_left, barriers, move, config
        )

    @mcp.tool
    def send_message(envelope: dict) -> dict:
        return tools.send_message_result(envelope)

    return mcp


if __name__ == "__main__":
    config = load_config("config.yaml")
    mcp = build_thief_server(config, auth_token=os.environ.get("THIEF_AUTH_TOKEN"))

    _env_port = os.environ.get("PORT")
    _port = int(_env_port) if _env_port else config.servers.thief.port
    _host = "0.0.0.0" if _env_port else config.servers.thief.host

    mcp.run(transport="http", host=_host, port=_port)
