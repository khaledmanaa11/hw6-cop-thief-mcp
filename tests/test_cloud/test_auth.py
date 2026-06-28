"""Offline tests for src/mcp_servers/auth.py.
No live server, no cloud account, no API key required.
"""
from src.mcp_servers.auth import StaticBearerVerifier, build_auth


def test_build_auth_none_returns_none():
    assert build_auth(None) is None
    assert build_auth("") is None


def test_build_auth_token_returns_verifier():
    v = build_auth("my-token")
    assert isinstance(v, StaticBearerVerifier)


async def test_verify_correct_token_returns_access_token():
    v = build_auth("secret-cop")
    result = await v.verify_token("secret-cop")
    assert result is not None
    assert result.client_id == "static-bearer"


async def test_verify_wrong_token_returns_none():
    v = build_auth("correct-token")
    assert await v.verify_token("wrong-token") is None


async def test_verify_empty_token_returns_none():
    v = build_auth("the-real-token")
    assert await v.verify_token("") is None


def test_server_auth_attached_only_when_token_set():
    from src.game.config import load_config
    from src.mcp_servers.cop_server import build_cop_server
    config = load_config("config.yaml")
    assert build_cop_server(config).auth is None
    assert build_cop_server(config, auth_token="tok").auth is not None
