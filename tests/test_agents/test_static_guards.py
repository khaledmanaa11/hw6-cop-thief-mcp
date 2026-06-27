from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
AGENTS = ROOT / "src" / "agents"
MCP_SERVERS = ROOT / "src" / "mcp_servers"


def _py_texts(path: Path):
    for file in path.rglob("*.py"):
        yield file, file.read_text(encoding="utf-8")


def test_agents_have_no_api_key_literal():
    forbidden = ("ANTHROPIC_API_KEY", "api_key", "sk-ant")
    offenders = []
    for file, text in _py_texts(AGENTS):
        for needle in forbidden:
            if needle in text:
                offenders.append((file, needle))

    assert offenders == []


def test_agents_do_not_contain_default_model_literal_except_config_tests():
    forbidden = ("claude-haiku-4-5-20251001", "claude-opus-4")
    offenders = []
    for file, text in _py_texts(AGENTS):
        for needle in forbidden:
            if needle in text:
                offenders.append((file, needle))

    assert offenders == []


def test_agents_have_no_fixed_grid_literals():
    suspicious = (
        "5x5",
        "5 x 5",
        "(5, 5)",
        "[5, 5]",
        "range(5)",
        "rows = 5",
        "cols = 5",
        "grid_size = (5",
    )
    offenders = []
    for file, text in _py_texts(AGENTS):
        for needle in suspicious:
            if needle in text:
                offenders.append((file, needle))

    assert offenders == []


def test_mcp_servers_untouched_by_llm_imports():
    forbidden = ("anthropic", "LLMAgent", "src.agents")
    offenders = []
    for file, text in _py_texts(MCP_SERVERS):
        for needle in forbidden:
            if needle in text:
                offenders.append((file, needle))

    assert offenders == []
