"""Pure JSON report builder for the Gmail reporting step.

Builds a rich-but-compact JSON dict from a SeriesResult + telemetry summary + Config
+ replay-log path, per DECISION_step8 §7. No I/O, no network, no sensitive values.
`now` is injectable so tests get a deterministic `generated_at`.
"""
from __future__ import annotations

from datetime import datetime, timezone

from src.game.config import Config
from src.game.engine import SeriesResult


def build_report(
    series_result: SeriesResult,
    telemetry: dict,
    config: Config,
    replay_path: str,
    *,
    a_was_cop_per_subgame: list[bool],
    now: datetime | None = None,
) -> dict:
    """Return the report dict per DECISION §7 schema.

    Pure: no I/O, no network. `now` is injectable for deterministic tests; when
    omitted, uses datetime.now(timezone.utc). No sensitive values appear anywhere
    — auth-related config paths are not read here.
    """
    generated_at = (now or datetime.now(timezone.utc)).isoformat()

    sub_games = []
    for idx, sg in enumerate(series_result.sub_games, 1):
        if idx - 1 < len(a_was_cop_per_subgame):
            a_was_cop = bool(a_was_cop_per_subgame[idx - 1])
        else:
            a_was_cop = sg.cop_group == "A"
        sub_games.append(
            {
                "index": idx,
                "winner": sg.winner,
                "cop_score": sg.cop_score,
                "thief_score": sg.thief_score,
                "moves_used": sg.moves_used,
                "a_was_cop": a_was_cop,
            }
        )

    agents = config.agents or {}
    llm_cfg = agents.get("llm") or {}
    observation = config.observation or {}
    scoring = config.scoring
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "config": {
            "grid_size": list(config.grid_size),
            "num_games": config.num_games,
            "max_moves": config.max_moves,
            "max_barriers": config.max_barriers,
            "scoring": {
                "cop_win": scoring.cop_win,
                "thief_win": scoring.thief_win,
                "cop_loss": scoring.cop_loss,
                "thief_loss": scoring.thief_loss,
            },
        },
        "agents": {
            "cop": agents.get("cop"),
            "thief": agents.get("thief"),
            "llm_model": llm_cfg.get("model"),
            "observation_mode": observation.get("mode"),
        },
        "series": {
            "group_a_total": series_result.group_a_total,
            "group_b_total": series_result.group_b_total,
            "sub_games": sub_games,
        },
        "telemetry": telemetry,
        "replay_log": replay_path,
    }
