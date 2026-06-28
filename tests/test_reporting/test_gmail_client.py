"""Stubbed GmailSender.send test — no network, no real credentials (AC4)."""
import base64
import json
from unittest.mock import patch

from src.reporting.gmail_client import GmailSender


class _StubMessages:
    def __init__(self, captured):
        self._captured = captured

    def send(self, userId, body):
        self._captured["userId"] = userId
        self._captured["raw"] = body["raw"]
        return self

    def execute(self):
        return {"id": "stub-msg-id", "threadId": "t1"}


class _StubUsers:
    def __init__(self, captured):
        self._captured = captured

    def messages(self):
        return _StubMessages(self._captured)


def _stub_service(captured):
    class _Service:
        def users(self):
            return _StubUsers(captured)
    return _Service()


def test_send_stubbed_returns_id_and_raw():
    captured = {}
    body = {"schema_version": 1, "series": {"group_a_total": 30}}
    with patch("src.reporting.gmail_client.build_credentials", return_value=object()), \
         patch("googleapiclient.discovery.build", return_value=_stub_service(captured)):
        sender = GmailSender("secrets/c.json", "secrets/t.json")
        msg_id = sender.send("rmisegal+uoh26b@gmail.com", "HW6 report", body)
    assert msg_id == "stub-msg-id"
    assert captured["userId"] == "me"
    # decode the raw MIME and assert headers + JSON body
    raw = captured["raw"]
    mime = base64.urlsafe_b64decode(raw).decode("utf-8")
    assert "To: rmisegal+uoh26b@gmail.com" in mime
    assert "Subject: HW6 report" in mime
    assert "Content-Type: application/json" in mime
    assert json.dumps(body) in mime


def test_send_raises_when_no_token():
    with patch("src.reporting.gmail_client.build_credentials", return_value=None):
        sender = GmailSender("secrets/c.json", "secrets/t.json")
        try:
            sender.send("a@b.com", "s", {})
            assert False, "expected FileNotFoundError"
        except FileNotFoundError:
            pass
