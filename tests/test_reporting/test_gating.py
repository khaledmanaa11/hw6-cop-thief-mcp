"""Gating, fail-soft, env-override, and hygiene tests for maybe_send_report."""
from unittest.mock import patch

from src.game.engine import SeriesResult, SubGameResult


class _Cfg:
    def __init__(self, report):
        self.report = report


def _res():
    return SeriesResult(
        sub_games=[SubGameResult("COP", 20, 5, 7, "A", "B")],
        group_a_total=20, group_b_total=5,
    )


def test_noop_when_disabled():
    cfg = _Cfg({"enabled": False, "to": "x@y.com", "subject": "s",
                "credentials_path": "c.json", "token_path": "t.json"})
    with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
         patch("googleapiclient.discovery.build") as mock_build:
        from src.reporting.gmail_client import maybe_send_report
        maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
    MockSender.assert_not_called()
    mock_build.assert_not_called()


def test_noop_when_no_token(tmp_path, monkeypatch):
    token = tmp_path / "nope.json"   # does not exist
    cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                "credentials_path": "c.json", "token_path": str(token)})
    monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
    with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
         patch("googleapiclient.discovery.build") as mock_build:
        from src.reporting.gmail_client import maybe_send_report
        maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
    MockSender.assert_not_called()
    mock_build.assert_not_called()


def test_send_called_when_enabled_and_token_present(tmp_path, monkeypatch):
    token = tmp_path / "token.json"
    token.write_text("{}")
    cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                "credentials_path": "c.json", "token_path": str(token)})
    monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
    with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
         patch("src.reporting.gmail_client.build_report",
               return_value={"schema_version": 1}) as mock_build:
        MockSender.return_value.send.return_value = "mid-1"
        from src.reporting.gmail_client import maybe_send_report
        maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
    MockSender.assert_called_once()
    MockSender.return_value.send.assert_called_once()
    mock_build.assert_called_once()
    args = MockSender.return_value.send.call_args.args
    assert args[0] == "x@y.com"
    assert args[1] == "s"
    assert isinstance(args[2], dict) and args[2]["schema_version"] == 1


def test_fail_soft_swallows_send_error(tmp_path, monkeypatch):
    token = tmp_path / "token.json"
    token.write_text("{}")
    cfg = _Cfg({"enabled": True, "to": "x@y.com", "subject": "s",
                "credentials_path": "c.json", "token_path": str(token)})
    monkeypatch.delenv("GMAIL_TOKEN_PATH", raising=False)
    with patch("src.reporting.gmail_client.GmailSender") as MockSender, \
         patch("src.reporting.gmail_client.build_report",
               return_value={"schema_version": 1}):
        MockSender.return_value.send.side_effect = RuntimeError("gmail exploded")
        from src.reporting.gmail_client import maybe_send_report
        maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")   # must not raise


def test_env_overrides_flip_gate_and_path(monkeypatch, tmp_path):
    monkeypatch.setenv("REPORT_ENABLED", "true")
    token = tmp_path / "override.json"
    token.write_text("{}")
    monkeypatch.setenv("GMAIL_TOKEN_PATH", str(token))
    from src.game.config import load_config
    cfg = load_config("config.yaml")
    assert cfg.report["enabled"] is True
    assert cfg.report["token_path"] == str(token)
    # and the hook now reaches the sender (token exists at the overridden path)
    with patch("src.reporting.gmail_client.GmailSender") as MockSender:
        MockSender.return_value.send.return_value = "mid-env"
        from src.reporting.gmail_client import maybe_send_report
        maybe_send_report(_res(), {}, cfg, "runs/x.jsonl")
    MockSender.return_value.send.assert_called_once()


def test_gitignore_and_env_example():
    from pathlib import Path
    gi = Path(".gitignore").read_text(encoding="utf-8")
    assert "secrets/" in gi
    assert "gmail_credentials.json" in gi
    assert "gmail_token.json" in gi
    env = Path(".env.example").read_text(encoding="utf-8")
    for var in ["REPORT_ENABLED", "REPORT_TO", "GMAIL_CREDENTIALS_PATH", "GMAIL_TOKEN_PATH"]:
        assert var in env, f"{var} missing from .env.example"
    # config.yaml has no real secret
    cfg = Path("config.yaml").read_text(encoding="utf-8")
    assert "gmail_token.json" in cfg   # the default path is fine
    assert "token.json" not in cfg.replace("gmail_token.json", "")  # no stray token content


def test_reporting_files_at_most_150_lines():
    from pathlib import Path
    for p in [
        "src/reporting/__init__.py",
        "src/reporting/report.py",
        "src/reporting/gmail_client.py",
        "src/reporting/auth.py",
        "src/reporting/__main__.py",
    ]:
        lines = len(Path(p).read_text(encoding="utf-8").splitlines())
        assert lines <= 150, f"{p} has {lines} lines (max 150)"


def test_no_hardcoded_lecturer_address():
    from pathlib import Path
    addr = "rmisegal+uoh26b@gmail.com"
    for p in Path("src").rglob("*.py"):
        t = p.read_text(encoding="utf-8")
        assert addr not in t, f"{p} hard-codes the lecturer address"


def test_build_credentials_returns_none_when_no_token(tmp_path):
    from src.reporting.auth import build_credentials
    # token path does not exist -> the gate's no-op branch
    assert build_credentials("c.json", str(tmp_path / "nope.json")) is None


def test_build_credentials_refreshes_expired_token(tmp_path):
    from unittest.mock import MagicMock
    token = tmp_path / "token.json"
    token.write_text('{"dummy": "token"}')
    fake_creds = MagicMock()
    fake_creds.expired = True
    fake_creds.refresh_token = "refresh-x"
    fake_creds.to_json.return_value = '{"dummy": "token"}'
    with patch("google.oauth2.credentials.Credentials.from_authorized_user_info",
               return_value=fake_creds), \
         patch("google.auth.transport.requests.Request"):
        from src.reporting.auth import build_credentials
        result = build_credentials("c.json", str(token))
    assert result is fake_creds
    fake_creds.refresh.assert_called_once()
    assert token.read_text() == '{"dummy": "token"}'   # re-persisted via to_json()
