from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from src.gui.app import _safe_run_path, create_app

FIXTURES = Path(__file__).with_name("fixtures")


def _client() -> TestClient:
    config = SimpleNamespace(gui={"run_dir": str(FIXTURES), "host": "127.0.0.1", "port": 8000})
    return TestClient(create_app(config))


def test_index_serves_html():
    resp = _client().get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_api_runs_lists_fixture_runs():
    resp = _client().get("/api/runs")
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["runs"]]
    assert "replay_3x3.jsonl" in names
    assert "replay_5x5.jsonl" in names


def test_api_run_returns_frames():
    resp = _client().get("/api/runs/replay_3x3.jsonl")
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid"] == [3, 3]
    assert len(body["frames"]) == 3


def test_api_run_missing_is_404():
    assert _client().get("/api/runs/nope.jsonl").status_code == 404


def test_api_run_non_jsonl_name_rejected():
    assert _client().get("/api/runs/secret.txt").status_code == 404


def test_api_run_broken_jsonl_is_400():
    assert _client().get("/api/runs/broken.jsonl").status_code == 400


def test_static_assets_served():
    assert _client().get("/static/app.js").status_code == 200


def test_safe_run_path_blocks_traversal(tmp_path):
    assert _safe_run_path(tmp_path, "../x.jsonl") is None
    assert _safe_run_path(tmp_path, "a/b.jsonl") is None
    assert _safe_run_path(tmp_path, "ok.jsonl") == (tmp_path.resolve() / "ok.jsonl")
