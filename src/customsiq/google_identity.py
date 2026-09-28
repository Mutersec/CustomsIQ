"""Verifying a "Sign in with Google" credential.

The browser's Google button hands back an ID token: a JWT signed by Google.
This checks its signature against Google's published keys, that it was issued
for this app's client ID, that it has not expired, and that Google has verified
the e-mail address. Only then is any of its content trusted.

Uses Google's own `google-auth` library for the cryptography. Its key download
goes through a small `urllib` transport below rather than the `requests`
package, so the only new dependency is `google-auth` itself.
"""

import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import NamedTuple, Optional

from google.auth import exceptions as google_exceptions
from google.auth import transport as google_transport
from google.oauth2 import id_token

from src.customsiq.exceptions import AuthenticationError

logger = logging.getLogger(__name__)

_ISSUERS = ("accounts.google.com", "https://accounts.google.com")


class GoogleIdentity(NamedTuple):
    """The verified facts a Google ID token carries about its owner."""

    sub: str
    email: str
    name: Optional[str]


class _Response(google_transport.Response):
    def __init__(self, status: int, headers: dict, data: bytes) -> None:
        self._status, self._headers, self._data = status, headers, data

    @property
    def status(self) -> int:
        return self._status

    @property
    def headers(self) -> dict:
        return self._headers

    @property
    def data(self) -> bytes:
        return self._data


class _UrllibRequest(google_transport.Request):
    """The minimal google-auth transport: one HTTP GET for Google's public keys."""

    def __call__(
        self,
        url: str,
        method: str = "GET",
        body: Optional[bytes] = None,
        headers: Optional[dict] = None,
        timeout: Optional[float] = None,
        **kwargs: object,
    ) -> _Response:
        request = urllib.request.Request(url, data=body, headers=headers or {}, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout or 10) as response:  # noqa: S310
                return _Response(response.status, dict(response.headers), response.read())
        except urllib.error.HTTPError as exc:
            return _Response(exc.code, dict(exc.headers), exc.read())
        except (urllib.error.URLError, OSError) as exc:
            raise google_exceptions.TransportError(str(exc)) from exc


def _verify_with_google(credential: str, client_id: str) -> dict:
    return dict(id_token.verify_oauth2_token(credential, _UrllibRequest(), client_id))


#: The verification call; tests replace it so no network or real token is needed.
verify_token: Callable[[str, str], dict] = _verify_with_google


def verify_credential(credential: str, client_id: str) -> GoogleIdentity:
    """Verify a Google ID token and return who it belongs to.

    Args:
        credential: The ID token the Google button returned to the browser.
        client_id: This app's OAuth client ID; the token must be issued for it.

    Raises:
        AuthenticationError: The token is invalid, expired, issued for another
            app or by another issuer, or its e-mail is not verified by Google.
    """
    try:
        claims = verify_token(credential, client_id)
    except (ValueError, google_exceptions.GoogleAuthError) as exc:
        logger.info("rejected Google credential: %s", exc)
        raise AuthenticationError("Google sign-in could not be verified") from exc

    if claims.get("aud") != client_id or claims.get("iss") not in _ISSUERS:
        raise AuthenticationError("Google sign-in could not be verified")
    email = str(claims.get("email") or "").strip().lower()
    if not email or claims.get("email_verified") not in (True, "true"):
        raise AuthenticationError("Google has not verified this e-mail address")
    return GoogleIdentity(sub=str(claims["sub"]), email=email, name=claims.get("name"))
