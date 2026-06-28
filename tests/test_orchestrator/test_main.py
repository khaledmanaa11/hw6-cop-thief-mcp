import copy
import dataclasses

import pytest


async def test_friendly_failure(monkeypatch, capsys):
    """When servers are unreachable, main() prints help text and exits non-zero."""
    from src.orchestrator import __main__

    class _FailingGateway:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def ping(self):
            raise ConnectionRefusedError("connection refused")

    monkeypatch.setattr(__main__, "gateway_from_env", lambda role, config, telemetry: _FailingGateway())

    with pytest.raises(SystemExit) as exc:
        await __main__.main()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "cop_server" in out
    assert "thief_server" in out


async def test_legacy_agents_do_not_construct_anthropic_without_key(monkeypatch, tmp_path):
    from src.game.engine import SeriesResult, SubGameResult
    from src.game.config import load_config
    from src.orchestrator import __main__

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = load_config("config.yaml")
    agents = copy.deepcopy(cfg.agents)
    agents["cop"] = "minimax"
    agents["thief"] = "minimax"
    cfg = dataclasses.replace(cfg, agents=agents, output_run_dir=str(tmp_path))

    class _Gateway:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def ping(self):
            return {"ok": True}

    class _FailIfConstructed:
        def __init__(self, *args, **kwargs):
            raise AssertionError("AnthropicLLM should not be constructed for legacy movers")

    async def _run_series(config, cop_gw, thief_gw, group_a, group_b, **kwargs):
        assert group_a("COP").__class__.__name__ == "MoverAgent"
        assert group_b("THIEF").__class__.__name__ == "MoverAgent"
        return SeriesResult(
            sub_games=[SubGameResult("COP", 20, 5, 3)],
            group_a_total=20,
            group_b_total=5,
        )

    monkeypatch.setattr(__main__, "load_config", lambda path: cfg)
    monkeypatch.setattr(__main__, "gateway_from_env", lambda role, config, telemetry: _Gateway())
    monkeypatch.setattr(__main__, "AnthropicLLM", _FailIfConstructed)
    monkeypatch.setattr(__main__, "run_series", _run_series)

    await __main__.main()
