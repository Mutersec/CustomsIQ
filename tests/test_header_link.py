"""The header's "CustomsIQ" title is a clickable link.

The app page ("/") now requires a session, so it is read signed in. The sign-in
page's brand links to /login rather than "/": for a visitor without a session
"/" only redirects back there.
"""

from fastapi.testclient import TestClient

from src.customsiq.api import app
from tests.helpers import signed_in_test_client

_EXPECTED = '<h1><a href="/">Customs<span class="accent">IQ</span></a></h1>'


def test_the_app_title_links_home() -> None:
    assert _EXPECTED in signed_in_test_client().get("/").text


def test_the_sign_in_page_brand_links_to_itself() -> None:
    assert '<a class="brand" href="/login" aria-label="CustomsIQ">' in (
        TestClient(app).get("/login").text
    )
