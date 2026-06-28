from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Frame = dict[str, Any]
Run = dict[str, Any]
RunMeta = dict[str, Any]
SIDES = ("COP", "THIEF")


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                records.append(json.loads(text))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSONL") from exc
    return records


def _grid(record: dict[str, Any]) -> list[int]:
    for side in SIDES:
        grid = record.get("obs", {}).get(side, {}).get("grid")
        if grid:
            return list(grid)
    if record.get("grid"):
        return list(record["grid"])
    truth = record.get("ground_truth", {})
    coords = [truth.get("cop_pos"), truth.get("thief_pos"), *truth.get("barriers", [])]
    rows = max((p[0] for p in coords if p), default=-1) + 1
    cols = max((p[1] for p in coords if p), default=-1) + 1
    return [rows, cols]


def _board(record: dict[str, Any]) -> dict[str, Any]:
    truth = record.get("ground_truth", {})
    return {"grid": _grid(record), "cop_pos": truth.get("cop_pos"),
            "thief_pos": truth.get("thief_pos"), "barriers": truth.get("barriers", [])}


def _conversation_item(message: dict[str, Any], current: bool) -> dict[str, Any]:
    return {"from": message.get("from"), "turn": message.get("turn"),
            "ts": message.get("ts"), "text": message.get("text", ""), "current": current}


def ghost_marker(record: dict[str, Any]) -> dict[str, Any]:
    action = record.get("action", {})
    return {"guess": action.get("belief"), "error": action.get("belief_error")}


def fog_view(record: dict[str, Any], side: str) -> dict[str, Any]:
    return _json_copy(record.get("obs", {}).get(side.upper(), {}))


def _score_from_record(record: dict[str, Any], previous: dict[str, Any]) -> dict[str, Any]:
    if "score" in record:
        score = dict(record["score"])
        score.setdefault("available", True)
        score.setdefault("note", None)
        return score
    if "series_score" in record:
        score = dict(record["series_score"])
        score.setdefault("available", True)
        score.setdefault("note", None)
        return score
    if "cop_score" in record or "thief_score" in record:
        return {"cop": record.get("cop_score", previous.get("cop", 0)),
                "thief": record.get("thief_score", previous.get("thief", 0)),
                "available": True, "note": None}
    return dict(previous)


def _moves_left(record: dict[str, Any]) -> int | None:
    side = record.get("side", "COP")
    obs = record.get("obs", {}).get(side) or record.get("obs", {}).get("COP", {})
    return obs.get("moves_left")


def _telemetry_summary(frames: list[Frame]) -> dict[str, Any]:
    llm = [frame["llm"] for frame in frames if frame.get("llm")]
    return {"llm_calls": len(llm), "llm_latency_ms": sum(x.get("latency_ms", 0) for x in llm),
            "llm_input_tokens": sum(x.get("input_tokens", 0) for x in llm),
            "llm_output_tokens": sum(x.get("output_tokens", 0) for x in llm)}


def to_frames(records: list[dict[str, Any]]) -> list[Frame]:
    frames: list[Frame] = []
    conversation: list[dict[str, Any]] = []
    beliefs = {"COP": {"guess": None, "error": None}, "THIEF": {"guess": None, "error": None}}
    score: dict[str, Any] = {"cop": 0, "thief": 0, "available": False, "note": "score not present in JSONL"}
    for record in records:
        side = str(record.get("side", "")).upper()
        message = record.get("message") or {}
        if message.get("text") is not None:
            conversation.append(_conversation_item(message, current=False))
        for item in conversation:
            item["current"] = False
        if conversation:
            conversation[-1]["current"] = True
        if side in beliefs:
            beliefs[side] = ghost_marker(record)
        score = _score_from_record(record, score)
        action = record.get("action", {})
        frames.append({"turn": record.get("turn"), "side": side, "move": record.get("move"),
                        "board": _board(record), "message": _json_copy(message) if message else None,
                        "conversation": _json_copy(conversation), "beliefs": _json_copy(beliefs),
                        "fog": {"COP": fog_view(record, "COP"), "THIEF": fog_view(record, "THIEF")},
                        "score": dict(score), "moves_left": _moves_left(record),
                        "llm": _json_copy(action.get("llm", {})),
                        "confidence": action.get("confidence"), "intent": action.get("intent")})
    return frames


def running_score(frames: list[Frame]) -> dict[str, Any]:
    if not frames:
        return {"cop": 0, "thief": 0, "available": False, "note": "empty run"}
    return dict(frames[-1]["score"])


def load_run(path: str | Path) -> Run:
    run_path = Path(path)
    records = _read_jsonl(run_path)
    frames = to_frames(records)
    return {"name": run_path.name, "grid": frames[0]["board"]["grid"] if frames else [0, 0],
            "frames": frames, "final_score": running_score(frames),
            "telemetry_summary": _telemetry_summary(frames)}


def list_runs(run_dir: str | Path) -> list[RunMeta]:
    root = Path(run_dir)
    metas: list[RunMeta] = []
    for path in sorted(root.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            run = load_run(path)
            metas.append({"name": path.name, "mtime": path.stat().st_mtime,
                          "turns": len(run["frames"]), "grid": run["grid"]})
        except (OSError, ValueError):
            metas.append({"name": path.name, "mtime": path.stat().st_mtime, "turns": 0, "grid": None})
    return metas
