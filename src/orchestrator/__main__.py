import asyncio
import sys
import time

from src.agents.factory import build_agent
from src.agents.llm_client import AnthropicLLM
from src.game.config import load_config
from src.orchestrator.gateway import gateway_from_env
from src.orchestrator.recorders import ReplayLog, Telemetry
from src.orchestrator.referee import run_series
from src.reporting.gmail_client import maybe_send_report


async def main() -> None:
    config = load_config("config.yaml")
    telemetry = Telemetry()

    # gateway_from_env reads COP_SERVER_URL/THIEF_SERVER_URL and auth tokens from env;
    # falls back to config host:port / no token when env is absent (local mode).
    async with (
        gateway_from_env("cop", config, telemetry) as cop_gw,
        gateway_from_env("thief", config, telemetry) as thief_gw,
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

        llm_client = None
        if config.agents["cop"] == "llm" or config.agents["thief"] == "llm":
            llm_cfg = config.agents["llm"]
            if llm_cfg["provider"] != "anthropic":
                raise ValueError(f"Unsupported LLM provider: {llm_cfg['provider']}")
            llm_client = AnthropicLLM(
                model=llm_cfg["model"],
                max_tokens=llm_cfg["max_tokens"],
                temperature=llm_cfg.get("temperature"),
            )

        def group_factory(runtime_role: str):
            return build_agent(runtime_role.lower(), config, llm_client)

        group_a = group_factory
        group_b = group_factory

        result = await run_series(
            config,
            cop_gw,
            thief_gw,
            group_a,
            group_b,
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
    print("\n=== Telemetry ===")
    print(
        f"Calls: {s['calls']}  avg: {s['avg_ms']}ms  p95: {s['p95_ms']}ms  "
        f"boot — cop: {s['boot_ping'].get('cop_ms', 0):.1f}ms  "
        f"thief: {s['boot_ping'].get('thief_ms', 0):.1f}ms"
    )
    if "llm_calls" in s:
        print(
            f"LLM calls: {s['llm_calls']}  avg: {s['llm_avg_ms']}ms  "
            f"input: {s['llm_input_tokens']}  "
            f"cache_write: {s['llm_cache_creation_input_tokens']}  "
            f"cache_read: {s['llm_cache_read_input_tokens']}  "
            f"output: {s['llm_output_tokens']}  "
            f"estimated cost: ${s['llm_estimated_cost_usd']:.6f}"
        )
    print(f"Replay log: {replay_log.path}")
    # Step 8: gated, fail-soft Gmail report hook. No-op unless config.report['enabled']
    # is True AND a token file exists (default disabled -> 165 prior tests stay green).
    maybe_send_report(result, s, config, replay_log.path)


if __name__ == "__main__":
    asyncio.run(main())
