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

    monkeypatch.setattr(__main__, "HttpGateway", _FailingGateway)

    with pytest.raises(SystemExit) as exc:
        await __main__.main()

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "cop_server" in out
    assert "thief_server" in out
