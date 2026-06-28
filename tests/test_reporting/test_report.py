"""Pure-builder tests for src/reporting/report.py. No network, no secrets."""
from datetime import datetime, timezone

from src.game.config import Config, ScoringConfig
from src.game.engine import SeriesResult, SubGameResult
from src.reporting.report import build_report


def _cfg(grid=(5, 5), num_games=6):
    return Config(
        grid_size=grid,
        max_moves=25,
        num_games=num_games,
        max_barriers=5,
        scoring=ScoringConfig(20, 10, 5, 5),
        agents={"cop": "llm", "thief": "llm", "llm": {"model": "claude-haiku-4-5-20251001"}},
        observation={"mode": "noisy"},
    )


def _telemetry():
    return {
        "calls": 84, "avg_ms": 1.2, "p95_ms": 3.0,
        "boot_ping": {"cop_ms": 5.0, "thief_ms": 5.0},
        "llm_calls": 48, "llm_avg_ms": 600.0, "llm_input_tokens": 12000,
        "llm_output_tokens": 3000, "llm_estimated_cost_usd": 0.012,
    }


FIXED_NOW = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)


def test_build_report_full_shape():
    res = SeriesResult(
        sub_games=[SubGameResult("COP", 20, 5, 7, cop_group="A", thief_group="B")],
        group_a_total=30, group_b_total=30,
    )
    report = build_report(
        res, _telemetry(), _cfg(), "runs/20260627T120000Z.jsonl",
        a_was_cop_per_subgame=[True], now=FIXED_NOW,
    )
    assert report["schema_version"] == 1
    assert report["generated_at"] == FIXED_NOW.isoformat()
    assert report["config"] == {
        "grid_size": [5, 5], "num_games": 6, "max_moves": 25, "max_barriers": 5,
        "scoring": {"cop_win": 20, "thief_win": 10, "cop_loss": 5, "thief_loss": 5},
    }
    assert report["agents"] == {
        "cop": "llm", "thief": "llm",
        "llm_model": "claude-haiku-4-5-20251001", "observation_mode": "noisy",
    }
    assert report["series"]["group_a_total"] == 30
    assert report["series"]["sub_games"][0] == {
        "index": 1, "winner": "COP", "cop_score": 20, "thief_score": 5,
        "moves_used": 7, "a_was_cop": True,
    }
    assert report["replay_log"] == "runs/20260627T120000Z.jsonl"
    assert report["telemetry"]["calls"] == 84


def test_build_report_resizable_3x3():
    res = SeriesResult(
        sub_games=[
            SubGameResult("THIEF", 5, 10, 12, cop_group="B", thief_group="A"),
            SubGameResult("COP", 20, 5, 9, cop_group="A", thief_group="B"),
        ],
        group_a_total=15, group_b_total=25,
    )
    report = build_report(
        res, _telemetry(), _cfg(grid=(3, 3), num_games=2), "runs/x.jsonl",
        a_was_cop_per_subgame=[False, True], now=FIXED_NOW,
    )
    assert report["config"]["grid_size"] == [3, 3]
    assert report["config"]["num_games"] == 2
    assert len(report["series"]["sub_games"]) == 2
    assert report["series"]["sub_games"][0]["a_was_cop"] is False
    assert report["series"]["sub_games"][1]["a_was_cop"] is True


def test_report_has_no_secrets():
    import json
    res = SeriesResult(
        sub_games=[SubGameResult("COP", 20, 5, 7, "A", "B")],
        group_a_total=20, group_b_total=5,
    )
    # Use empty telemetry so no field names contain words like "token"
    report = build_report(
        res, {}, _cfg(), "runs/x.jsonl",
        a_was_cop_per_subgame=[True], now=FIXED_NOW,
    )
    blob = json.dumps(report).lower()
    for needle in ["token", "credential", "api_key", "secret", "password"]:
        assert needle not in blob, f"report contains {needle!r}"
