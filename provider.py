"""WHOOP webhook authentication for the Inkbox external-event registry."""

from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Any, Mapping


class WhoopWebhookProvider:
    name = "whoop"
    provider_header = "X-WHOOP-Signature"
    skill = "whoop:whoop-coach"

    def matches(self, headers: Mapping[str, str]) -> bool:
        return any(key.lower() == self.provider_header.lower() for key in headers)

    @staticmethod
    def _header(headers: Mapping[str, str], name: str) -> str:
        for key, value in headers.items():
            if key.lower() == name.lower():
                return str(value)
        return ""

    def verify(
        self,
        *,
        body: bytes,
        headers: Mapping[str, str],
        url: str,
        secret: str,
    ) -> bool:
        del url
        if not secret:
            return False
        signature = self._header(headers, "X-WHOOP-Signature")
        timestamp = self._header(headers, "X-WHOOP-Signature-Timestamp")
        if not signature or not timestamp:
            return False
        digest = hmac.new(
            secret.encode("utf-8"),
            timestamp.encode("utf-8") + body,
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("ascii")
        return hmac.compare_digest(expected, signature)

    def event_key(
        self,
        *,
        envelope: Mapping[str, Any],
        headers: Mapping[str, str],
    ) -> str:
        del headers
        return str(envelope.get("trace_id") or "").strip()


def register_provider(inkbox_plugin: Any) -> None:
    register = getattr(inkbox_plugin, "register_webhook_provider", None)
    if not callable(register):
        raise RuntimeError(
            "The installed Inkbox Hermes plugin does not expose companion webhook registration; "
            "update inkbox-ai/hermes-agent-plugin first."
        )
    register(WhoopWebhookProvider)
