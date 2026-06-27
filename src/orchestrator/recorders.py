import json
import os
from datetime import datetime, timezone
from src.agents.llm_client import estimate_haiku_cost_usd
from src.game.state import GameState


class Telemetry:
    def __init__(self) -> None:
        self._samples: list[tuple[str, float]] = []
        self._llm_samples: list[dict] = []
        self._boot_ping: dict = {}

    def record(self, tool_name: str, ms: float) -> None:
        self._samples.append((tool_name, ms))

    def record_llm(self, sample: dict) -> None:
        self._llm_samples.append(dict(sample))

    def set_boot_ping(self, cop_ms: float, thief_ms: float) -> None:
        self._boot_ping = {"cop_ms": cop_ms, "thief_ms": thief_ms}

    def summary(self) -> dict:
        ms_vals = [ms for _, ms in self._samples]
        avg = sum(ms_vals) / len(ms_vals) if ms_vals else 0.0
        p95 = _p95(ms_vals)
        llm_ms = [sample.get("latency_ms", 0.0) for sample in self._llm_samples]
        llm_avg = sum(llm_ms) / len(llm_ms) if llm_ms else 0.0
        return {
            "calls": len(ms_vals),
            "avg_ms": round(avg, 3),
            "p95_ms": round(p95, 3),
            "boot_ping": self._boot_ping,
            "llm_calls": len(self._llm_samples),
            "llm_avg_ms": round(llm_avg, 3),
            "llm_input_tokens": sum(sample.get("input_tokens", 0) for sample in self._llm_samples),
            "llm_cache_creation_input_tokens": sum(
                sample.get("cache_creation_input_tokens", 0) for sample in self._llm_samples
            ),
            "llm_cache_read_input_tokens": sum(
                sample.get("cache_read_input_tokens", 0) for sample in self._llm_samples
            ),
            "llm_output_tokens": sum(sample.get("output_tokens", 0) for sample in self._llm_samples),
            "llm_estimated_cost_usd": round(
                sum(estimate_haiku_cost_usd(sample) for sample in self._llm_samples), 6
            ),
        }


def _p95(vals: list[float]) -> float:
    if not vals:
        return 0.0
    sorted_vals = sorted(vals)
    k = min(len(sorted_vals) - 1, max(0, int(0.95 * len(sorted_vals))))
    return sorted_vals[k]


def _chebyshev(a: tuple[int, int], b: tuple[int, int]) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def belief_error(guess, truth) -> int | None:
    if guess is None or truth is None:
        return None
    return _chebyshev(tuple(guess), tuple(truth))


def _region_hint(pos: tuple[int, int], rows: int, cols: int) -> str:
    r, c = pos
    north_cut = rows / 3
    south_cut = rows * 2 / 3
    west_cut = cols / 3
    east_cut = cols * 2 / 3

    vertical = "north" if r < north_cut else "south" if r >= south_cut else ""
    horizontal = "west" if c < west_cut else "east" if c >= east_cut else ""
    return f"{vertical}{horizontal}" or "center"


def observe(
    state: GameState,
    side: str,
    last_msg: str | None = None,
    *,
    mode: str = "full",
    params: dict | None = None,
    inbox: list[dict] | None = None,
) -> dict:
    """Dec-POMDP per-agent view.

    Calls without Step-5 keyword arguments keep the Step-3 exact schema for
    existing tests and readers. New calls receive the richer observation shape.
    """
    role = side.upper()
    if role == "COP":
        self_pos, opponent_pos = state.cop_pos, state.thief_pos
    else:
        self_pos, opponent_pos = state.thief_pos, state.cop_pos

    barriers = [list(b) for b in sorted(state.board.barriers)]
    if params is None and inbox is None and mode == "full":
        return {
            "self": list(self_pos),
            "sees_opponent": True,
            "opponent_pos": list(opponent_pos),
            "last_msg": last_msg,
            "barriers": barriers,
        }

    params = params or {}
    max_moves = params.get("max_moves", state.moves_used)
    moves_left = max(0, max_moves - state.moves_used) if "max_moves" in params else 0
    view = {
        "mode": mode,
        "role": role,
        "self": list(self_pos),
        "grid": [state.board.rows, state.board.cols],
        "barriers": barriers,
        "moves_used": state.moves_used,
        "moves_left": moves_left,
        "max_moves": max_moves,
        "cop_barriers_left": state.cop_barriers_left,
        "sees_opponent": False,
        "opponent_pos": None,
        "opponent_hint": "unseen",
        "last_msg": last_msg,
        "inbox": list(inbox or []),
    }

    if mode == "full":
        view["sees_opponent"] = True
        view["opponent_pos"] = list(opponent_pos)
        view["opponent_hint"] = "exact"
        return view

    if mode == "blind":
        return view

    if mode == "noisy":
        noisy = params.get("noisy", {})
        radius = noisy.get("reveal_radius", 0)
        if _chebyshev(self_pos, opponent_pos) <= radius:
            view["sees_opponent"] = True
            view["opponent_pos"] = list(opponent_pos)
            view["opponent_hint"] = "exact"
        elif noisy.get("quadrant_hint", False):
            view["opponent_hint"] = _region_hint(opponent_pos, state.board.rows, state.board.cols)
        else:
            view["opponent_hint"] = "out_of_range"
        return view

    raise ValueError(f"Unknown observation mode: {mode}")


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
