"""Static bearer-token auth gate for the MCP servers.

A FastMCP TokenVerifier that accepts exactly one static bearer token. When the
token is None/empty, build_auth returns None and the server runs open (backward
compatible — the existing tests and local runs are unaffected).

Verified against fastmcp 3.4.2 (see SDK_REFERENCE_fastmcp_auth.md §2):
  FastMCP(name, auth=verifier); verify_token -> AccessToken | None; None -> HTTP 401.
"""
from __future__ import annotations

import secrets

from fastmcp.server.auth import TokenVerifier
from mcp.server.auth.provider import AccessToken


class StaticBearerVerifier(TokenVerifier):
    """Accept exactly one static bearer token; reject everything else (-> 401).

    Uses secrets.compare_digest (constant-time) to avoid timing attacks.
    The token is never logged. A non-matching token returns None, which FastMCP
    surfaces as HTTP 401 Unauthorized.
    """

    def __init__(self, token: str) -> None:
        super().__init__()                 # base init: base_url/scopes all optional
        self._token = token

    async def verify_token(self, token: str) -> AccessToken | None:
        if secrets.compare_digest(
            token.encode("utf-8"), self._token.encode("utf-8")
        ):
            return AccessToken(token=token, client_id="static-bearer", scopes=[])
        return None


def build_auth(token: str | None) -> StaticBearerVerifier | None:
    """Return a verifier when a token is set, else None (open server).

    None/empty token -> None -> FastMCP(name, auth=None) -> open server (today's
    behaviour, so the existing 152 tests still pass).
    Set token -> StaticBearerVerifier(token), passed to FastMCP(name, auth=...).
    """
    if not token:
        return None
    return StaticBearerVerifier(token)
