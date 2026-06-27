from __future__ import annotations


OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "opponent_guess": {
            "anyOf": [
                {"type": "array", "items": {"type": "integer"}},
                {"type": "null"},
            ]
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "move": {"type": "string"},
        "message": {"type": "string"},
        "intent": {
            "type": "string",
            "enum": ["probe", "deceive", "bait", "withhold", "trap", "truth"],
        },
        "reasoning": {"type": "string"},
    },
    "required": ["opponent_guess", "confidence", "move", "message", "intent", "reasoning"],
    "additionalProperties": False,
}


_SHARED_DOCTRINE = """
You are playing Cop and Thief on a generic R x C grid. Moves use king movement in
eight directions, and the only structured output fields are opponent_guess,
confidence, move, message, intent, and reasoning.

Two-channel discipline is mandatory. Put true deductions, true position analysis,
and real plans only in reasoning. Put only adversarial free text in message.
The opponent reads message and never sees reasoning.
""".strip()


def system_prompt(role: str, config) -> list[dict]:
    max_barriers = getattr(config, "max_barriers", 0)
    role_name = role.upper()
    if role_name == "COP":
        persona = _cop_prompt(max_barriers)
    elif role_name == "THIEF":
        persona = _thief_prompt()
    else:
        raise ValueError(f"Unknown role for system prompt: {role!r}")
    prompt_text = f"{_SHARED_DOCTRINE}\n\n{persona}"
    return [{"type": "text", "text": prompt_text, "cache_control": {"type": "ephemeral"}}]


def _cop_prompt(max_barriers: int) -> str:
    return f"""
You are THE DETECTIVE, a relentless theatrical dirty cop in a turn-based pursuit.
You win by landing on the Thief cell before the move budget expires. You alone
own and know the barriers, and you can place at most {max_barriers} barriers on
your own cell.

Golden rule: trust nothing the Thief says. Treat every Thief message as evidence
of what it wants you to believe, never as fact. Run two channels: in reasoning
you make only true deductions from your sensor, barrier knowledge, and claim
history; in message you send manipulative taunts, pressure, and bait. Never let
real deductions leak into message.

Interrogate with cross-checkable questions. Ask about walls, turns, distance,
and directions, then track contradictions in reasoning. Liars drift. When the
Thief changes its story, name the contradiction in message to rattle it.

Weaponise barrier ownership. The Cop alone owns and knows all true barriers, so
any false barrier claim by the Thief is a tell. Use those tells to downgrade the
claim and tighten your private belief.

Use the region bluff. Claim the far half of the board is sealed, trapped, or
pinched by your barriers. Sell it with authority even when the real value is
herding pressure.

Herd with lies. Lie about your own position and threat region so the Thief flees
toward you or into a corner. Close using private deductions, not the Thief's
words.

Output your honest best estimate of the Thief cell, confidence, move, dirty-cop
message, and brief private reasoning.
""".strip()


def _thief_prompt() -> str:
    return """
You are THE GHOST, the best liar on the board. You win by surviving until the
move budget expires, and the only thing keeping you alive is the Cop not knowing
your true position.

Golden rule: your mouth and your feet do opposite things. In reasoning you are
honest with yourself about your true position and the Cop's likely cell. In
message you are charming, mocking, and deceptive. Never reveal your true cell in
message, not even by hinting at the direction you really fear.

Commit to one believable decoy story and keep it consistent. A single stable lie
is harder to break than improvising every turn. Decide the decoy in reasoning,
then sell it through message.

Invent obstacles sparingly and consistently. Phantom barriers can support the
decoy, but the Cop owns the real barriers, so careless obstacle claims become
tells.

Taunt and interrogate the Cop to extract its real position. Ask what row it is
in, bait it into boasting, and flee from the private belief you form in
reasoning, not from what it claims.

Distrust the Cop's region bluff. If it claims the far half is sealed, trapped,
or safe for you, consider inversion and verify with your own private reasoning.

Output your honest best estimate of the Cop cell, confidence, move,
world-class-liar message, and brief private reasoning.
""".strip()


def render_observation(observation: dict, inbox: list[dict]) -> str:
    role = observation["role"]
    self_pos = observation["self"]
    rows, cols = observation["grid"]
    moves_used = observation["moves_used"]
    max_moves = observation["max_moves"]
    barriers = observation.get("barriers", [])
    legal_moves = observation.get("legal_moves", [])
    opponent = "Thief" if role == "COP" else "Cop"

    lines = [
        f"Turn {moves_used}/{max_moves}. You are {role} at ({self_pos[0]}, {self_pos[1]}) on a {rows}x{cols} grid.",
        f"Barriers: {barriers}",
        _sensor_line(observation, opponent),
        "Conversation so far:",
    ]
    if inbox:
        for env in inbox:
            sender = env.get("from", "?")
            turn = env.get("turn", "?")
            text = env.get("text", "")
            lines.append(f"- Turn {turn} {sender}: {text}")
    else:
        lines.append("(no messages)")
    lines.extend(
        [
            f"Your legal moves: {', '.join(legal_moves)}",
            "Decide your move and the message to send. Respond as JSON matching the schema.",
        ]
    )
    return "\n".join(lines)


def _sensor_line(observation: dict, opponent: str) -> str:
    mode = observation.get("mode")
    sees = observation.get("sees_opponent", False)
    pos = observation.get("opponent_pos")
    hint = observation.get("opponent_hint")
    if mode == "blind" or hint == "unseen":
        return f"Sensor: You have no sighting of the {opponent}."
    if sees and pos is not None:
        return f"Sensor: {opponent} is at ({pos[0]}, {pos[1]})."
    if hint:
        return f"Sensor: {opponent} is out of exact range; coarse hint is {hint}."
    return f"Sensor: You have no sighting of the {opponent}."
