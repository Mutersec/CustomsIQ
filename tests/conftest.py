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

from src.customsiq.config import settings

settings.password_iterations = 1_000
