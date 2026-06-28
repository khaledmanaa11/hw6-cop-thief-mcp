"""GmailSender + the orchestrator's fail-soft maybe_send_report hook.

GmailSender wraps the confirmed Gmail API v1 send path (SDK_REFERENCE_gmail §1):
base64.urlsafe_b64encode of an RFC2822 EmailMessage with To/Subject/
Content-Type: application/json headers and the JSON body, then
service.users().messages().send(userId='me', body={'raw': ...}).execute().
"""
from __future__ import annotations

import base64
import json
from email.message import EmailMessage

from src.reporting.auth import SCOPES, build_credentials
from src.reporting.report import build_report


class GmailSender:
    """Wraps gmail.users().messages().send for a JSON-only email body.

    `to`/`subject` come from config (report.to / report.subject) — never literals.
    The sender is the authenticated OAuth account (implicit `from`).
    """

    def __init__(self, credentials_path: str, token_path: str) -> None:
        self._credentials_path = credentials_path
        self._token_path = token_path
        self._scopes = SCOPES

    def send(self, to: str, subject: str, body: dict) -> str:
        """Send `body` (a dict) as the JSON email body; return the sent message id.

        Raises if the token is missing/invalid — the caller (maybe_send_report)
        catches and logs (fail-soft).
        """
        from googleapiclient.discovery import build

        creds = build_credentials(
            self._credentials_path, self._token_path, scopes=self._scopes
        )
        if creds is None:
            raise FileNotFoundError(
                f"Gmail token not found at {self._token_path}; "
                "run `python -m src.reporting auth` first."
            )

        message = EmailMessage()
        message.set_content(json.dumps(body))
        message["To"] = to
        message["Subject"] = subject
        del message["Content-Type"]
        message["Content-Type"] = "application/json"

        # CONFIRMED (SDK ref §1.2): url-safe base64, padding retained.
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        service = build("gmail", "v1", credentials=creds)
        sent = (
            service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
        return sent["id"]


def maybe_send_report(series_result, telemetry, config, replay_path) -> None:
    """Gated, fail-soft report hook for the orchestrator.

    Sends iff config.report['enabled'] is True AND the token file exists at the
    resolved path. Default enabled=False + no token in CI -> no-op, so the 165
    prior tests stay green. Never raises into the orchestrator (fail-soft).
    """
    import os

    report = config.report or {}
    if not report.get("enabled"):
        return  # gate: disabled by default

    token_path = report.get("token_path", "secrets/gmail_token.json")
    if not os.path.exists(token_path):
        return  # gate: no token -> no-op (do not even build the service)

    try:
        a_was_cop = [sg.cop_group == "A" for sg in series_result.sub_games]
        body = build_report(
            series_result, telemetry, config, replay_path,
            a_was_cop_per_subgame=a_was_cop,
        )
        sender = GmailSender(
            report.get("credentials_path", "secrets/gmail_credentials.json"),
            token_path,
        )
        msg_id = sender.send(report.get("to", ""), report.get("subject", ""), body)
        print(f"Report sent: message id {msg_id}")
    except Exception as exc:  # noqa: BLE001 — fail-soft: never crash the series
        print(f"Report send failed (non-fatal): {exc}")
