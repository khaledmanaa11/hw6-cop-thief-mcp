from fastmcp import FastMCP
from src.game.config import load_config
from src.mcp_servers import tools


def build_cop_server(config) -> FastMCP:
    mcp = FastMCP("cop")

    @mcp.tool
    def ping() -> dict:
        return tools.ping_result("cop")

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

    @mcp.tool
    def place_barrier(pos: list[int], cop_barriers_left: int, barriers: list[list[int]]) -> dict:
        return tools.place_barrier_result(pos, cop_barriers_left, barriers, config)

    return mcp


if __name__ == "__main__":
    config = load_config("config.yaml")
    mcp = build_cop_server(config)
    mcp.run(
        transport="http",
        host=config.servers.cop.host,
        port=config.servers.cop.port,
    )
