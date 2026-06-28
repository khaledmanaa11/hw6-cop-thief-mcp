"""Offline tests for HttpGateway auth and gateway_from_env.
No live server required.
"""
from src.orchestrator.gateway import HttpGateway, gateway_from_env
from src.orchestrator.recorders import Telemetry


def test_http_gateway_sends_auth_when_token_set():
    tel = Telemetry()
    gw = HttpGateway("http://localhost:8001/mcp", "cop", tel, auth_token="my-tok")
    # _auth_token must be stored
    assert gw._auth_token == "my-tok"


def test_http_gateway_no_auth_when_no_token():
    tel = Telemetry()
    gw = HttpGateway("http://localhost:8001/mcp", "cop", tel)
    assert gw._auth_token is None


def test_gateway_from_env_uses_env_url_and_token(monkeypatch):
    monkeypatch.setenv("COP_SERVER_URL", "https://hw6-cop-test.run.app/mcp")
    monkeypatch.setenv("COP_AUTH_TOKEN", "test-secret")

    # Minimal fake config
    class _Ep:
        host = "127.0.0.1"
        port = 8001
    class _Servers:
        cop = _Ep()
        thief = _Ep()
    class _Cfg:
        servers = _Servers()

    tel = Telemetry()
    gw = gateway_from_env("cop", _Cfg(), tel)
    assert gw._transport == "https://hw6-cop-test.run.app/mcp"
    assert gw._auth_token == "test-secret"


def test_gateway_from_env_falls_back_to_config(monkeypatch):
    monkeypatch.delenv("COP_SERVER_URL", raising=False)
    monkeypatch.delenv("COP_AUTH_TOKEN", raising=False)

    class _Ep:
        host = "127.0.0.1"
        port = 8001
    class _Servers:
        cop = _Ep()
        thief = _Ep()
    class _Cfg:
        servers = _Servers()

    tel = Telemetry()
    gw = gateway_from_env("cop", _Cfg(), tel)
    assert gw._transport == "http://127.0.0.1:8001/mcp"
    assert gw._auth_token is None
