"""Outbound e-mail: the sign-up verification code, via Brevo's HTTP API.

Why Brevo and why HTTP: it has a free tier (300 mails/day, no card), and its
send endpoint is a plain HTTPS POST, which matters because Render's free web
services cannot open outbound SMTP connections. The call is made with
`urllib` from the standard library, so this adds no dependency.

Configuration lives in `config.py` (`brevo_api_key`, `mail_from`, ...). With no
API key the send fails closed with `MailNotConfiguredError`, so a deployment
that forgot the key refuses sign-ups rather than creating unverified accounts.
The one exception is `mail_dev_log_codes`, a local-development switch that
writes the code to the server log instead.
"""

import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Optional

from src.customsiq.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_SECONDS = 10


class MailNotConfiguredError(RuntimeError):
    """No e-mail provider is configured, so a verification code cannot be sent."""


class MailDeliveryError(RuntimeError):
    """The provider rejected the message or could not be reached."""


#: Subject and body per language. `{code}` and `{minutes}` are filled in.
_TEMPLATES = {
    "en": (
        "Your CustomsIQ verification code: {code}",
        "Your CustomsIQ verification code is {code}. It expires in {minutes} minutes. "
        "If you did not try to create an account, you can ignore this e-mail.",
    ),
    "tr": (
        "CustomsIQ doğrulama kodunuz: {code}",
        "CustomsIQ doğrulama kodunuz {code}. Kod {minutes} dakika geçerlidir. "
        "Hesap oluşturmaya çalışmadıysanız bu e-postayı yok sayabilirsiniz.",
    ),
    "de": (
        "Ihr CustomsIQ-Bestätigungscode: {code}",
        "Ihr CustomsIQ-Bestätigungscode lautet {code}. Er ist {minutes} Minuten gültig. "
        "Wenn Sie kein Konto anlegen wollten, können Sie diese E-Mail ignorieren.",
    ),
}

LANGUAGES = tuple(_TEMPLATES)


def _render(code: str, language: str) -> tuple[str, str, str]:
    """Return (subject, text body, HTML body) for one code in one language."""
    subject, body = _TEMPLATES.get(language, _TEMPLATES["en"])
    minutes = settings.verification_code_ttl_minutes
    text = body.format(code=code, minutes=minutes)
    html = (
        '<div style="font-family:Segoe UI,Arial,sans-serif;color:#0b2545;max-width:480px">'
        '<p style="font-size:18px;font-weight:600;margin:0 0 12px">CustomsIQ</p>'
        f'<p style="font-size:32px;letter-spacing:6px;font-weight:700;margin:0 0 16px">{code}</p>'
        f'<p style="font-size:14px;line-height:1.5;margin:0">{text}</p></div>'
    )
    return subject.format(code=code), text, html


def _post(url: str, headers: dict, payload: bytes) -> None:
    """POST one JSON payload. Split out so tests can replace the network call."""
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:  # noqa: S310
        response.read()


#: The function that performs the HTTP call; tests swap it for a fake.
transport: Callable[[str, dict, bytes], None] = _post


def send_verification_code(email: str, code: str, language: str = "en") -> None:
    """E-mail a sign-up verification code.

    Args:
        email: Recipient address, already validated.
        code: The plaintext code. Never logged unless `mail_dev_log_codes` is on.
        language: "en", "tr" or "de"; anything else falls back to English.

    Raises:
        MailNotConfiguredError: No Brevo key and the dev-log switch is off.
        MailDeliveryError: Brevo rejected the message or was unreachable.
    """
    api_key: Optional[str] = settings.brevo_api_key
    if not api_key:
        if settings.mail_dev_log_codes:
            logger.warning("DEV ONLY: verification code for %s is %s", email, code)
            return
        raise MailNotConfiguredError("e-mail delivery is not configured")

    subject, text, html = _render(code, language)
    payload = json.dumps(
        {
            "sender": {"email": settings.mail_from, "name": settings.mail_from_name},
            "to": [{"email": email}],
            "subject": subject,
            "textContent": text,
            "htmlContent": html,
        }
    ).encode("utf-8")
    headers = {
        "api-key": api_key,
        "content-type": "application/json",
        "accept": "application/json",
    }
    try:
        transport(BREVO_SEND_URL, headers, payload)
    except (urllib.error.URLError, OSError) as exc:
        logger.error("verification e-mail to %s failed: %s", email, exc)
        raise MailDeliveryError("the verification e-mail could not be sent") from exc
    logger.info("sent verification code to %s", email)
