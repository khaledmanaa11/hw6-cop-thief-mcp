from pathlib import Path

from src.gui.replay import fog_view, ghost_marker, list_runs, load_run, running_score, to_frames

FIXTURES = Path(__file__).with_name("fixtures")


def test_load_run_returns_frames_and_metadata():
    run = load_run(FIXTURES / "replay_3x3.jsonl")
    assert run["name"] == "replay_3x3.jsonl"
    assert run["grid"] == [3, 3]
    assert len(run["frames"]) == 3
    assert run["frames"][0]["side"] == "COP"
    fs = run["final_score"]
    assert fs["cop"] == 20
    assert fs["thief"] == 5
    assert fs["available"] is True


def test_to_frames_is_resizable_for_3x3_and_5x5():
    run3 = load_run(FIXTURES / "replay_3x3.jsonl")
    f0 = run3["frames"][0]
    assert f0["board"]["grid"] == [3, 3]
    assert f0["board"]["cop_pos"] == [0, 1]
    assert f0["board"]["thief_pos"] == [2, 2]
    run5 = load_run(FIXTURES / "replay_5x5.jsonl")
    assert run5["grid"] == [5, 5]


def test_conversation_accumulates_public_messages_only():
    run = load_run(FIXTURES / "replay_3x3.jsonl")
    frames = run["frames"]
    assert len(frames[0]["conversation"]) == 1
    assert len(frames[1]["conversation"]) == 2
    assert len(frames[2]["conversation"]) == 3
    texts = [f["conversation"][-1]["text"] for f in frames]
    assert texts[0] == "I am closing the west edge."
    assert texts[1] == "You are chasing old footprints."
    assert texts[2] == "Caught you."
    for frame in frames:
        assert "SECRET_REASONING_DO_NOT_SHOW" not in str(frame["conversation"])


def test_ghost_marker_uses_action_belief_and_error():
    import json
    record = json.loads((FIXTURES / "replay_3x3.jsonl").read_text().splitlines()[0])
    result = ghost_marker(record)
    assert result == {"guess": [2, 2], "error": 0}


def test_fog_view_preserves_blind_noisy_full_without_leakage():
    import json
    lines = (FIXTURES / "replay_3x3.jsonl").read_text().splitlines()
    rec0 = json.loads(lines[0])
    rec2 = json.loads(lines[2])
    thief_fog0 = fog_view(rec0, "THIEF")
    assert thief_fog0["mode"] == "blind"
    assert thief_fog0["opponent_pos"] is None
    cop_fog0 = fog_view(rec0, "COP")
    assert cop_fog0["mode"] == "noisy"
    assert cop_fog0["sees_opponent"] is False
    assert cop_fog0["opponent_hint"] == "southeast"
    cop_fog2 = fog_view(rec2, "COP")
    assert cop_fog2["mode"] == "full"
    assert cop_fog2["opponent_pos"] == [1, 1]


def test_telemetry_moves_left_and_running_score():
    run = load_run(FIXTURES / "replay_3x3.jsonl")
    frames = run["frames"]
    assert frames[0]["llm"]["latency_ms"] == 10
    assert run["telemetry_summary"]["llm_calls"] == 3
    assert running_score(frames)["cop"] == 20


def test_missing_optional_fields_degrade_gracefully():
    frames = to_frames([{"turn": 1, "side": "COP"}])
    assert len(frames) == 1
    assert frames[0]["score"]["available"] is False
    assert frames[0]["fog"]["COP"] == {}
    assert frames[0]["fog"]["THIEF"] == {}


def test_blank_lines_skipped_and_top_level_grid(tmp_path):
    path = tmp_path / "r.jsonl"
    path.write_text('\n{"turn":1,"side":"COP","grid":[4,4]}\n\n', encoding="utf-8")
    run = load_run(path)
    assert run["grid"] == [4, 4]
    assert len(run["frames"]) == 1


def test_series_score_and_cop_thief_score_branches():
    frames = to_frames([
        {"turn": 1, "side": "COP", "series_score": {"cop": 10, "thief": 5}},
        {"turn": 2, "side": "THIEF", "cop_score": 12, "thief_score": 8},
    ])
    assert frames[0]["score"] == {"cop": 10, "thief": 5, "available": True, "note": None}
    assert frames[1]["score"]["cop"] == 12
    assert frames[1]["score"]["thief"] == 8


def test_running_score_empty_and_list_runs(tmp_path):
    assert running_score([])["available"] is False
    (tmp_path / "a.jsonl").write_text('{"turn":1,"side":"COP","obs":{"COP":{"grid":[2,2]}}}\n', encoding="utf-8")
    (tmp_path / "bad.jsonl").write_text("{nope}\n", encoding="utf-8")
    metas = {m["name"]: m for m in list_runs(tmp_path)}
    assert metas["a.jsonl"]["grid"] == [2, 2]
    assert metas["bad.jsonl"]["grid"] is None
