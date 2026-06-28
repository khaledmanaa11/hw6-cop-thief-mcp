from pathlib import Path

GUI = Path(__file__).resolve().parents[2] / "src" / "gui"
TEST_GUI = Path(__file__).resolve().parent
FORBIDDEN_TIERS = ("src.game", "src.mcp_servers", "src.orchestrator", "src.strategy", "src.agents")


def _files(root: Path, suffixes: set[str]) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix in suffixes and "__pycache__" not in p.parts]


def test_every_gui_and_test_file_at_most_150_lines():
    files = _files(GUI, {".py", ".js", ".html", ".css"}) + _files(TEST_GUI, {".py"})
    over = [(p.name, len(p.read_text(encoding="utf-8").splitlines())) for p in files]
    over = [item for item in over if item[1] > 150]
    assert not over, over


def test_replay_is_stdlib_only():
    text = (GUI / "replay.py").read_text(encoding="utf-8")
    assert "import src" not in text
    assert "from src" not in text
    for tier in FORBIDDEN_TIERS:
        assert tier not in text


def test_static_has_no_hardcoded_grid_port_model_or_reasoning():
    for name in ("app.js", "index.html", "style.css"):
        text = (GUI / "static" / name).read_text(encoding="utf-8")
        assert "reasoning" not in text
        assert "5x5" not in text
        assert "[5, 5]" not in text
        assert "claude" not in text.lower()
        assert "8000" not in text


def test_gui_source_has_no_api_key_or_model_literal():
    for path in _files(GUI, {".py"}):
        text = path.read_text(encoding="utf-8")
        assert "ANTHROPIC" not in text
        assert "claude-haiku" not in text
        assert "[5, 5]" not in text
