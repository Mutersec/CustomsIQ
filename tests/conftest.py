"""Suite-wide test configuration.

The only thing here is the password work factor. Production hashes at
`Settings.password_iterations` (600,000 — OWASP's figure for PBKDF2-SHA256),
which costs ~160 ms per hash; at that cost the auth tests alone would add well
over ten seconds to a suite that currently finishes in under one. Lowering it
for tests is the same thing Django documents for its own test settings.

`tests/test_auth.py` still asserts the production default is 600,000 and hashes
once at full cost, so the real setting is covered rather than bypassed.

This runs at import time, before any test module (or `src.customsiq.api`, which
seeds demo accounts on import) is loaded.
"""

import pytest

from src.customsiq.config import settings

settings.password_iterations = 1_000


@pytest.fixture(autouse=True)
def _reset_ip_rate_limits():
    """Clear the per-IP rate-limit state between tests.

    Every TestClient request arrives from the same host, so without this the
    suite is one client hammering the auth and search limiters: tests start
    failing with 429s purely because of how many ran before them, and which
    ones fail depends on ordering. Clearing the buckets keeps each test
    independent while leaving the real production limits in place — the
    limiter's own tests drive it deliberately rather than relying on leftovers.
    """
    from src.customsiq.api import _IP_HITS

    _IP_HITS.clear()
    yield
    _IP_HITS.clear()


@pytest.fixture(autouse=True)
def outbox(monkeypatch: pytest.MonkeyPatch) -> list:
    """Capture verification e-mails instead of sending them.

    Configures a fake Brevo key so the mailer takes its real code path (build
    the payload, call the transport) and swaps only the HTTP call for a list.
    Each captured item is the decoded JSON payload Brevo would have received.
    """
    import json

    from src.customsiq import mailer

    sent: list = []
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(
        mailer, "transport", lambda url, headers, payload: sent.append(json.loads(payload))
    )
    return sent
