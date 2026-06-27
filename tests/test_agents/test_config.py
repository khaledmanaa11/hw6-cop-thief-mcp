import copy
import dataclasses

from src.agents.agent import LLMAgent, MoverAgent
from src.agents.factory import build_agent
from src.agents.llm_client import FakeLLM
from src.game.config import load_config


def test_defaults_exist_when_agent_blocks_absent(tmp_path):
    cfg_path = tmp_path / "minimal.yaml"
    cfg_path.write_text(
        "\n".join(
            [
                "grid_size: [3, 3]",
                "max_moves: 8",
                "num_games: 2",
                "max_barriers: 1",
                "scoring:",
                "  cop_win: 20",
                "  thief_win: 10",
                "  cop_loss: 5",
                "  thief_loss: 5",
            ]
        )
    )

    cfg = load_config(str(cfg_path))

    assert cfg.agents["cop"] == "llm"
    assert cfg.agents["llm"]["provider"] == "anthropic"
    assert cfg.observation["mode"] == "noisy"
    assert cfg.observation["noisy"]["reveal_radius"] == 2


def test_config_yaml_parses_step5_blocks():
    cfg = load_config("config.yaml")

    assert cfg.agents["cop"] == "llm"
    assert cfg.agents["thief"] == "llm"
    assert cfg.agents["llm"]["model"]
    assert cfg.observation["mode"] == "noisy"


def test_build_agent_llm_returns_llm_agent():
    cfg = load_config("config.yaml")

    agent = build_agent("cop", cfg, FakeLLM())

    assert isinstance(agent, LLMAgent)


def test_build_agent_legacy_name_returns_mover_agent():
    cfg = load_config("config.yaml")
    agents = copy.deepcopy(cfg.agents)
    agents["cop"] = "minimax"
    cfg = dataclasses.replace(cfg, agents=agents)

    agent = build_agent("cop", cfg)

    assert isinstance(agent, MoverAgent)
