"""CLI for the reporting package: `python -m src.reporting auth|send`.

`auth` — one-time OAuth login (writes token.json). Manual operator step (AC9).
`send` — ad-hoc send for the operator. Both are pragma-no-cover (live paths).
"""
from __future__ import annotations

import sys

from src.game.config import load_config
from src.reporting.auth import SCOPES, cmd_auth


def _resolve(config):
    report = config.report or {}
    return report


def main() -> None:  # pragma: no cover — manual operator CLI
    config = load_config("config.yaml")
    report = _resolve(config)
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""

    if cmd == "auth":
        cmd_auth(
            report.get("credentials_path", "secrets/gmail_credentials.json"),
            report.get("token_path", "secrets/gmail_token.json"),
            scopes=SCOPES,
        )
    elif cmd == "send":
        print(
            "Ad-hoc send is not wired in the CLI; run `python -m src.orchestrator` "
            "with report.enabled=true to send a real series report."
        )
    else:
        print("usage: python -m src.reporting {auth|send}")


if __name__ == "__main__":  # pragma: no cover
    main()
