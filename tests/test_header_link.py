"""The header's "CustomsIQ" title is a clickable link back to home."""

import pytest
from fastapi.testclient import TestClient

from src.customsiq.api import app

client = TestClient(app)

_EXPECTED = '<h1><a href="/">Customs<span class="accent">IQ</span></a></h1>'


@pytest.mark.parametrize("path", ["/", "/login"])
def test_title_is_wrapped_in_a_link_to_home(path: str) -> None:
    assert _EXPECTED in client.get(path).text
