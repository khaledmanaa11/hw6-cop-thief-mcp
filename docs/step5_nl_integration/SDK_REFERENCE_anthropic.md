# SDK Ground-Truth — `anthropic` Python SDK for Step 5 (`claude-haiku-4-5`)

Verified via the `claude-api` skill on 2026-06-27. **This is authoritative for the Builder/Developer — do NOT guess the SDK shape; copy from here.** The default model is `claude-haiku-4-5-20251001` (alias `claude-haiku-4-5`), config-selectable (swap to `claude-opus-4-8` for a competitive run).

## The real `messages.create` call for structured JSON output

```python
import os, json, anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment — never hard-code

SCHEMA = {
    "type": "object",
    "properties": {
        "opponent_guess": {                       # [row, col] or null
            "anyOf": [
                {"type": "array", "items": {"type": "integer"}},
                {"type": "null"},
            ]
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "move":       {"type": "string"},          # one legal move name (validated by the agent, not the schema)
        "message":    {"type": "string"},          # free text the opponent will read
        "intent":     {"type": "string", "enum": ["probe", "deceive", "bait", "withhold", "trap", "truth"]},
        "reasoning":  {"type": "string"},          # PRIVATE — logged, never sent in the envelope
    },
    "required": ["opponent_guess", "confidence", "move", "message", "intent", "reasoning"],
    "additionalProperties": False,                 # REQUIRED on every object in a structured-output schema
}

resp = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    temperature=0.7,                               # SUPPORTED on Haiku 4.5 (helps varied/creative lies). Omit/remove for Opus 4.8.
    system=[                                        # list form so we can mark the static block cacheable
        {
            "type": "text",
            "text": SYSTEM_PROMPT,                  # the persona (rules + role + deception doctrine) — identical across all ~300 calls in a series
            "cache_control": {"type": "ephemeral"}, # default 5-min TTL; shared prefix billed ~0.1x after the first call
        }
    ],
    messages=[{"role": "user", "content": per_turn_user_text}],  # the volatile per-ply observation+inbox
)

# output_config.format guarantees the first text block is valid JSON for the schema
text = next(b.text for b in resp.content if b.type == "text")
data = json.loads(text)
```

> NOTE the verified canonical form is `output_config={"format": {"type": "json_schema", "schema": SCHEMA}}` passed to `messages.create(...)`. (Add it to the call above; it was omitted here only to keep the prose readable — the Builder MUST include it.) `client.messages.parse(...)` with a Pydantic model is the higher-level alternative, but the project has no Pydantic dependency, so prefer the raw `output_config` + `json.loads` path shown.

## Hard rules (each is a 400 or a silent failure if violated)
- **`additionalProperties: False` on every object** in the schema, and list every property in `required`. Otherwise structured output 400s.
- **`temperature` is fine on Haiku 4.5** (~0.7 recommended for creative lies). It WOULD 400 on Opus 4.8/4.7 — so read `temperature` from config and only pass it when the configured model supports it (or just keep it for Haiku, the default).
- **Caching minimum on Haiku 4.5 is 4096 tokens.** If the static system prompt is shorter than ~4096 tokens it silently will NOT cache (`usage.cache_creation_input_tokens == 0`). The personas are long; if a tiny test prompt is used, don't assert a cache write.
- **Keep the cached prefix byte-identical** across calls: the persona system block must not contain per-ply data, timestamps, or the grid size interpolated per call if that changes — put all volatile content in the `messages` user turn, not in `system`.
- **Structured outputs are incompatible with `citations`** (400) — we don't use citations, so fine.
- **First call per schema pays a one-time compile cost**, then the schema is cached 24h. Expect the first live ply to be slower.
- **API key**: `anthropic.Anthropic()` reads `ANTHROPIC_API_KEY` from the env. Never put it in config.yaml or code. Tests use `FakeLLM` and need no key and no network.

## Telemetry fields (read off `resp.usage`)
- `resp.usage.input_tokens` — uncached input tokens (full price)
- `resp.usage.cache_creation_input_tokens` — tokens written to cache (~1.25x)
- `resp.usage.cache_read_input_tokens` — tokens served from cache (~0.1x)
- `resp.usage.output_tokens` — output tokens
- Total prompt size = input + cache_creation + cache_read. For estimated cost use Haiku 4.5 pricing: $1.00 / 1M input, $5.00 / 1M output (cache read ~0.1x input, cache write ~1.25x input).
- `resp.model` — echoes the served model; `resp._request_id` — log on failures.

## What `FakeLLM` must mimic
`FakeLLM.complete(system, user, schema) -> dict` returns the SAME dict shape the real parse produces:
`{"opponent_guess": [r,c]|None, "confidence": "...", "move": "...", "message": "...", "intent": "...", "reasoning": "..."}`.
No network, deterministic. Default behaviour = a sensible legal move + a canned message so full-series tests pass without scripting every ply. Provide scriptable "honest" and "liar/decoy" personas for the deception-metric tests (§11.6 of the DECISION).
