import json
import os
from datetime import datetime, timezone
from src.game.state import GameState


class Telemetry:
    def __init__(self) -> None:
        self._samples: list[tuple[str, float]] = []
        self._boot_ping: dict = {}

    def record(self, tool_name: str, ms: float) -> None:
        self._samples.append((tool_name, ms))

    def set_boot_ping(self, cop_ms: float, thief_ms: float) -> None:
        self._boot_ping = {"cop_ms": cop_ms, "thief_ms": thief_ms}

    def summary(self) -> dict:
        ms_vals = [ms for _, ms in self._samples]
        avg = sum(ms_vals) / len(ms_vals) if ms_vals else 0.0
        p95 = _p95(ms_vals)
        return {
            "calls": len(ms_vals),
            "avg_ms": round(avg, 3),
            "p95_ms": round(p95, 3),
            "boot_ping": self._boot_ping,
        }


def _p95(vals: list[float]) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    k = min(len(sorted_vals) - 1, max(0, int(0.95 * len(sorted_vals))))
    return sorted_vals[k]


def observe(state: GameState, side: str, last_msg: str | None = None) -> dict:
    """Dec-POMDP per-agent view. Step-3 policy: full visibility.
    sees_opponent / opponent_pos fields are present now so Step 5 can tighten them."""
    if side == "COP":
        self_pos, opponent_pos = state.cop_pos, state.thief_pos
    else:
        self_pos, opponent_pos = state.thief_pos, state.cop_pos
    return {
        "self": list(self_pos),
        "sees_opponent": True,
        "opponent_pos": list(opponent_pos),
        "last_msg": last_msg,
        "barriers": [list(b) for b in state.board.barriers],
    }


def render_board(state: GameState) -> str:
    rows, cols = state.board.rows, state.board.cols
    lines = []
    for r in range(rows):
        row_chars = []
        for c in range(cols):
            pos = (r, c)
            if pos == state.cop_pos:
                row_chars.append("C")
            elif pos == state.thief_pos:
                row_chars.append("T")
            elif pos in state.board.barriers:
                row_chars.append("#")
            else:
                row_chars.append(".")
        lines.append(" ".join(row_chars))
    return "\n".join(lines)


class ReplayLog:
    def __init__(self, run_dir: str) -> None:
        os.makedirs(run_dir, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        self._path = os.path.join(run_dir, f"{ts}.jsonl")
        self._fh = open(self._path, "w", encoding="utf-8")

    def write(self, record: dict) -> None:
        self._fh.write(json.dumps(record) + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()

    @property
    def path(self) -> str:
        return self._path
