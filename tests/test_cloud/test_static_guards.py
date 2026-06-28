"""Static code guards: no secrets in git, ≤150 lines, no forbidden imports."""
from pathlib import Path
import re


def test_no_committed_secrets():
    root = Path(".")
    forbidden_patterns = [
        r"COP_AUTH_TOKEN\s*=\s*\S",    # real token value (not placeholder)
        r"THIEF_AUTH_TOKEN\s*=\s*\S",  # real token value
        r"https://hw6-[a-z]+-[a-z0-9]+-\w+\.a\.run\.app",  # live run.app URL
    ]
    files_to_check = list((root / "src").rglob("*.py")) + [root / "config.yaml"]
    for path in files_to_check:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for pat in forbidden_patterns:
            matches = re.findall(pat, text)
            assert not matches, (
                f"Possible secret or hard-coded URL in {path}: "
                f"pattern '{pat}' matched {matches}"
            )


def test_new_src_files_at_most_150_lines():
    new_files = [
        Path("src/mcp_servers/auth.py"),
    ]
    for path in new_files:
        lines = len(path.read_text(encoding="utf-8").splitlines())
        assert lines <= 150, f"{path} has {lines} lines (max 150)"


def test_auth_module_no_forbidden_imports():
    text = Path("src/mcp_servers/auth.py").read_text(encoding="utf-8")
    forbidden = ["src.game", "src.orchestrator", "src.strategy", "src.agents"]
    for term in forbidden:
        assert term not in text, f"auth.py must not import {term}"
