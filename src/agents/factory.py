from __future__ import annotations

import copy
import dataclasses

from src.agents.agent import Agent, LLMAgent, MoverAgent
from src.agents.llm_client import LLMClient
from src.strategy.factory import build_mover


_KNOWN_AGENT_NAMES = {"llm", "greedy", "random", "minimax", "qtable"}


def build_agent(role: str, config, llm_client: LLMClient | None = None) -> Agent:
    role_key = role.lower()
    runtime_role = role.upper()
    name = config.agents[role_key]
    if name not in _KNOWN_AGENT_NAMES:
        raise ValueError("Unknown agent name: %r. Choose from: llm, greedy, random, minimax, qtable" % name)

    if name == "llm":
        if llm_client is None:
            raise ValueError("LLM agent requires an injected LLMClient")
        return LLMAgent(runtime_role, config, llm_client)

    strategy = copy.deepcopy(config.strategy)
    strategy[role_key] = name
    proxy_config = dataclasses.replace(config, strategy=strategy)
    return MoverAgent(build_mover(role_key, proxy_config), role=runtime_role)
