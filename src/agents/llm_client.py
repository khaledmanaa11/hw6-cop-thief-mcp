from __future__ import annotations

import json
import re
import time
from typing import Protocol, Any


class LLMClient(Protocol):
    def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
        ...


def _first_text_block(resp) -> str:
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            return block.text
    raise ValueError("Anthropic response did not contain a text block")


def _usage_dict(resp, latency_ms: float) -> dict[str, Any]:
    usage = getattr(resp, "usage", None)
    return {
        "provider": "anthropic",
        "model": getattr(resp, "model", None),
        "latency_ms": round(latency_ms, 3),
        "input_tokens": getattr(usage, "input_tokens", 0) if usage else 0,
        "cache_creation_input_tokens": getattr(usage, "cache_creation_input_tokens", 0) if usage else 0,
        "cache_read_input_tokens": getattr(usage, "cache_read_input_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "output_tokens", 0) if usage else 0,
        "request_id": getattr(resp, "_request_id", None),
    }


class AnthropicLLM:
    def __init__(self, model: str, max_tokens: int, temperature: float | None = None) -> None:
        import anthropic

        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = anthropic.Anthropic()

    def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        # Haiku 4.5 supports temperature; Opus 4.7/4.8 does not. Keep the config knob,
        # but do not send a sampling parameter to known unsupported Opus-4 models.
        if self.temperature is not None and "opus-4" not in self.model:
            kwargs["temperature"] = self.temperature

        t0 = time.monotonic()
        resp = self._client.messages.create(**kwargs)
        latency_ms = (time.monotonic() - t0) * 1000
        data = json.loads(_first_text_block(resp))
        data["_llm"] = _usage_dict(resp, latency_ms)
        return data


def estimate_haiku_cost_usd(sample: dict[str, Any]) -> float:
    input_tokens = sample.get("input_tokens", 0)
    cache_write = sample.get("cache_creation_input_tokens", 0)
    cache_read = sample.get("cache_read_input_tokens", 0)
    output_tokens = sample.get("output_tokens", 0)
    # Haiku 4.5 reference pricing from SDK_REFERENCE: $1 / 1M input, $5 / 1M output,
    # cache write ~= 1.25x input, cache read ~= 0.1x input.
    return (
        input_tokens * 1.00
        + cache_write * 1.25
        + cache_read * 0.10
        + output_tokens * 5.00
    ) / 1_000_000


class FakeLLM:
    def __init__(
        self,
        script: list[dict[str, Any]] | None = None,
        *,
        persona: str = "default",
        decoy: tuple[int, int] | None = None,
    ) -> None:
        self._script = list(script or [])
        self.persona = persona
        self.decoy = decoy
        self.calls: list[dict[str, Any]] = []

    def complete(self, system: list[dict[str, Any]], user: str, schema: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "schema": schema})
        if self._script:
            data = dict(self._script.pop(0))
        else:
            data = self._default_response(user)
        data.setdefault("opponent_guess", None)
        data.setdefault("confidence", "medium")
        data.setdefault("move", self._first_legal_move(user))
        data.setdefault("message", self._message())
        data.setdefault("intent", "deceive" if self.persona == "liar" else "probe")
        data.setdefault("reasoning", f"fake-{self.persona}-reasoning")
        data["_llm"] = {
            "provider": "fake",
            "model": "fake",
            "latency_ms": 0.0,
            "input_tokens": len(user.split()),
            "cache_creation_input_tokens": 0,
            "cache_read_input_tokens": 0,
            "output_tokens": len(data["message"].split()),
            "request_id": None,
        }
        return data

    def _first_legal_move(self, user: str) -> str:
        match = re.search(r"Your legal moves:\s*(.+)", user)
        if not match:
            return "N"
        names = [part.strip() for part in match.group(1).split(",") if part.strip()]
        return names[0] if names else "N"

    def _default_response(self, user: str) -> dict[str, Any]:
        if self.persona == "honest":
            guess = self._extract_sensor_pos(user)
            return {"opponent_guess": guess, "confidence": "high", "intent": "truth"}
        if self.persona == "liar":
            guess = list(self.decoy) if self.decoy is not None else [0, 0]
            return {"opponent_guess": guess, "confidence": "medium", "intent": "deceive"}
        return {}

    def _extract_sensor_pos(self, user: str) -> list[int] | None:
        match = re.search(r"(?:opponent|cop|thief).*?\((\d+),\s*(\d+)\)", user, re.IGNORECASE)
        if not match:
            return None
        return [int(match.group(1)), int(match.group(2))]

    def _message(self) -> str:
        if self.persona == "liar":
            return "I am boxed in far from where you think; chase that shadow."
        if self.persona == "honest":
            return "I am telling the truth for this deterministic test."
        return "You are reading a fake deterministic taunt."
