import base64
import hashlib
import hmac

from provider import WhoopWebhookProvider


def _signature(secret: str, timestamp: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), timestamp.encode() + body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def test_whoop_signature_and_trace_id():
    provider = WhoopWebhookProvider()
    secret = "client-secret"
    timestamp = "1784000000000"
    body = b'{"id":"workout-1","type":"workout.updated","trace_id":"trace-1"}'
    headers = {
        "X-WHOOP-Signature": _signature(secret, timestamp, body),
        "X-WHOOP-Signature-Timestamp": timestamp,
    }

    assert provider.matches(headers)
    assert provider.verify(body=body, headers=headers, url="https://example/webhook", secret=secret)
    assert provider.event_key(envelope={"trace_id": "trace-1"}, headers=headers) == "trace-1"


def test_whoop_signature_fails_closed():
    provider = WhoopWebhookProvider()
    body = b"{}"
    headers = {"X-WHOOP-Signature": "bad", "X-WHOOP-Signature-Timestamp": "1"}

    assert not provider.verify(body=body, headers=headers, url="u", secret="secret")
    assert not provider.verify(body=body, headers={}, url="u", secret="secret")
    assert not provider.verify(body=body, headers=headers, url="u", secret="")


def test_register_provider_uses_public_inkbox_extension():
    calls = []

    class Inkbox:
        register_webhook_provider = calls.append

    from provider import register_provider

    register_provider(Inkbox)
    assert calls == [WhoopWebhookProvider]
