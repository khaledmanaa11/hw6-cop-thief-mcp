from src.agents.prompts import OUTPUT_SCHEMA, render_observation, system_prompt
from src.game.config import load_config


def test_schema_has_required_additional_properties_false():
    assert OUTPUT_SCHEMA["additionalProperties"] is False
    assert OUTPUT_SCHEMA["required"] == [
        "opponent_guess",
        "confidence",
        "move",
        "message",
        "intent",
        "reasoning",
    ]


def test_system_prompt_uses_cache_control():
    prompt = system_prompt("COP", load_config("config.yaml"))
    assert prompt[0]["cache_control"] == {"type": "ephemeral"}


def test_detective_and_ghost_two_channel_discipline():
    config = load_config("config.yaml")
    cop = system_prompt("COP", config)[0]["text"]
    thief = system_prompt("THIEF", config)[0]["text"]

    assert "THE DETECTIVE" in cop
    assert "THE GHOST" in thief
    assert "reasoning" in cop and "message" in cop
    assert "reasoning" in thief and "message" in thief
    assert "dirty cop" in cop
    assert "best liar" in thief


def test_blind_render_does_not_include_true_coordinate():
    hidden_truth = (2, 2)
    observation = {
        "mode": "blind",
        "moves_used": 1,
        "max_moves": 5,
        "role": "COP",
        "self": [0, 0],
        "grid": [3, 3],
        "barriers": [],
        "sees_opponent": False,
        "opponent_pos": None,
        "opponent_hint": "unseen",
        "legal_moves": ["S"],
        "inbox": [],
    }

    rendered = render_observation(observation, [])

    assert f"({hidden_truth[0]}, {hidden_truth[1]})" not in rendered
    assert "You have no sighting" in rendered
