import json
import sys
import types

from src.agents.llm_client import AnthropicLLM, FakeLLM


def test_fake_llm_returns_structured_shape():
    data = FakeLLM().complete([], "Your legal moves: N, S", {})

    for key in (
        "opponent_guess",
        "confidence",
        "move",
        "message",
        "intent",
        "reasoning",
        "_llm",
    ):
        assert key in data
    assert data["move"] == "N"
    assert data["_llm"]["provider"] == "fake"


def test_fake_llm_script_is_deterministic():
    llm = FakeLLM(
        [
            {"move": "N", "message": "first"},
            {"move": "S", "message": "second"},
        ]
    )

    assert llm.complete([], "Your legal moves: N, S", {})["message"] == "first"
    assert llm.complete([], "Your legal moves: N, S", {})["message"] == "second"
    assert len(llm.calls) == 2


def test_anthropic_llm_builds_verified_messages_create_call(monkeypatch):
    captured = {}

    class _Block:
        type = "text"
        text = json.dumps(
            {
                "opponent_guess": None,
                "confidence": "low",
                "move": "N",
                "message": "public",
                "intent": "probe",
                "reasoning": "private",
            }
        )

    class _Usage:
        input_tokens = 11
        cache_creation_input_tokens = 0
        cache_read_input_tokens = 3
        output_tokens = 7

    class _Response:
        content = [_Block()]
        usage = _Usage()
        model = "claude-haiku-4-5-20251001"
        _request_id = "req_test"

    class _Messages:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _Response()

    class _Client:
        def __init__(self):
            self.messages = _Messages()

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=_Client))

    schema = {"type": "object"}
    llm = AnthropicLLM("claude-haiku-4-5-20251001", max_tokens=1024, temperature=0.7)
    data = llm.complete([{"type": "text", "text": "system"}], "turn text", schema)

    assert captured["model"] == "claude-haiku-4-5-20251001"
    assert captured["max_tokens"] == 1024
    assert captured["temperature"] == 0.7
    assert captured["output_config"] == {"format": {"type": "json_schema", "schema": schema}}
    assert captured["system"] == [{"type": "text", "text": "system"}]
    assert captured["messages"] == [{"role": "user", "content": "turn text"}]
    assert data["move"] == "N"
    assert data["_llm"]["request_id"] == "req_test"
