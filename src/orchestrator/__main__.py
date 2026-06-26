import asyncio
import sys
import time

from src.game.config import load_config
from src.game.movers import GreedyMover
from src.orchestrator.gateway import HttpGateway
from src.orchestrator.recorders import ReplayLog, Telemetry
from src.orchestrator.referee import run_series


async def main() -> None:
    config = load_config("config.yaml")
    telemetry = Telemetry()

    cop_url = f"http://{config.servers.cop.host}:{config.servers.cop.port}/mcp"
    thief_url = f"http://{config.servers.thief.host}:{config.servers.thief.port}/mcp"

    async with (
        HttpGateway(cop_url, "cop", telemetry) as cop_gw,
        HttpGateway(thief_url, "thief", telemetry) as thief_gw,
    ):
        # Boot ping — record latency and fail fast if servers are not up
        try:
            t0 = time.monotonic()
            await cop_gw.ping()
            cop_ms = (time.monotonic() - t0) * 1000
            t0 = time.monotonic()
            await thief_gw.ping()
            thief_ms = (time.monotonic() - t0) * 1000
        except Exception as exc:
            print(f"\nERROR: Could not reach MCP servers ({exc})")
            print("Start them first in two separate terminals:")
            print("  python -m src.mcp_servers.cop_server")
            print("  python -m src.mcp_servers.thief_server")
            sys.exit(1)

        telemetry.set_boot_ping(cop_ms, thief_ms)
        print(f"Servers up — cop ping {cop_ms:.1f}ms  thief ping {thief_ms:.1f}ms\n")

        replay_log = ReplayLog(config.output_run_dir)
        transcript: list = []

        result = await run_series(
            config,
            cop_gw,
            thief_gw,
            GreedyMover(),
            GreedyMover(),
            transcript=transcript,
            replay_log=replay_log,
            print_output=True,
        )
        replay_log.close()

    print("\n=== Series Result ===")
    print(f"Group A total: {result.group_a_total}  Group B total: {result.group_b_total}")
    for i, sg in enumerate(result.sub_games, 1):
        print(
            f"  Sub-game {i}: winner={sg.winner}  cop={sg.cop_score}  "
            f"thief={sg.thief_score}  moves={sg.moves_used}"
        )

    s = telemetry.summary()
    print(f"\n=== Telemetry ===")
    print(
        f"Calls: {s['calls']}  avg: {s['avg_ms']}ms  p95: {s['p95_ms']}ms  "
        f"boot — cop: {s['boot_ping'].get('cop_ms', 0):.1f}ms  "
        f"thief: {s['boot_ping'].get('thief_ms', 0):.1f}ms"
    )
    print(f"Replay log: {replay_log.path}")


if __name__ == "__main__":
    asyncio.run(main())
