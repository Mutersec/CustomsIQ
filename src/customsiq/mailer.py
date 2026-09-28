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

import html
import json
import logging
import urllib.error
import urllib.request
from collections.abc import Callable
from functools import cache
from pathlib import Path
from string import Template
from typing import Optional

from src.customsiq.config import settings

logger = logging.getLogger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT_SECONDS = 10


class MailNotConfiguredError(RuntimeError):
    """No e-mail provider is configured, so a verification code cannot be sent."""


class MailDeliveryError(RuntimeError):
    """The provider rejected the message or could not be reached."""


#: Every string of the verification e-mail, per language. `{code}` and
#: `{minutes}` are filled in; everything goes through `html.escape` before it
#: reaches the HTML template.
_TEMPLATES = {
    "en": {
        "subject": "Your CustomsIQ verification code: {code}",
        "text": "Your CustomsIQ verification code is {code}. It expires in {minutes} minutes. "
        "If you did not try to create an account, you can ignore this e-mail.",
        "preheader": "Your code: {code} · valid for {minutes} minutes",
        "heading": "Verify your e-mail address",
        "intro": "Enter this code on the CustomsIQ sign-up page to finish creating your account.",
        "code_label": "Your verification code",
        "expiry": "This code is valid for {minutes} minutes.",
        "ignore": "If you did not try to create an account, you can ignore this e-mail.",
        "never_share": "Never share this code. CustomsIQ will never ask you for it.",
        "footer": "CustomsIQ · EU customs &amp; trade compliance · support@customsiq.org",
    },
    "tr": {
        "subject": "CustomsIQ doğrulama kodunuz: {code}",
        "text": "CustomsIQ doğrulama kodunuz {code}. Kod {minutes} dakika geçerlidir. "
        "Hesap oluşturmaya çalışmadıysanız bu e-postayı yok sayabilirsiniz.",
        "preheader": "Kodunuz: {code} · {minutes} dakika geçerli",
        "heading": "E-posta adresinizi doğrulayın",
        "intro": "Hesabınızı oluşturmayı tamamlamak için bu kodu CustomsIQ kayıt sayfasına girin.",
        "code_label": "Doğrulama kodunuz",
        "expiry": "Bu kod {minutes} dakika geçerlidir.",
        "ignore": "Hesap oluşturmaya çalışmadıysanız bu e-postayı yok sayabilirsiniz.",
        "never_share": "Bu kodu kimseyle paylaşmayın. CustomsIQ sizden kodu asla istemez.",
        "footer": "CustomsIQ · AB gümrük ve ticaret uyumu · support@customsiq.org",
    },
    "de": {
        "subject": "Ihr CustomsIQ-Bestätigungscode: {code}",
        "text": "Ihr CustomsIQ-Bestätigungscode lautet {code}. Er ist {minutes} Minuten gültig. "
        "Wenn Sie kein Konto anlegen wollten, können Sie diese E-Mail ignorieren.",
        "preheader": "Ihr Code: {code} · {minutes} Minuten gültig",
        "heading": "Bestätigen Sie Ihre E-Mail-Adresse",
        "intro": "Geben Sie diesen Code auf der Registrierungsseite von CustomsIQ ein, "
        "um Ihr Konto fertig anzulegen.",
        "code_label": "Ihr Bestätigungscode",
        "expiry": "Dieser Code ist {minutes} Minuten gültig.",
        "ignore": "Wenn Sie kein Konto anlegen wollten, können Sie diese E-Mail ignorieren.",
        "never_share": "Geben Sie diesen Code niemals weiter. "
        "CustomsIQ wird Sie nie danach fragen.",
        "footer": "CustomsIQ · EU-Zoll &amp; Außenhandels-Compliance · support@customsiq.org",
    },
}

LANGUAGES = tuple(_TEMPLATES)

#: Strings that already contain markup (an entity) and must not be escaped again.
_PRE_ESCAPED = frozenset({"footer"})

_TEMPLATE_PATH = Path(__file__).parent / "email_templates" / "verification_code.html"


@cache
def _html_template() -> Template:
    """The card-style HTML e-mail, read once. `string.Template` rather than
    `str.format` so the CSS braces in the file need no escaping."""
    return Template(_TEMPLATE_PATH.read_text(encoding="utf-8"))


def _render(code: str, language: str) -> tuple[str, str, str]:
    """Return (subject, text body, HTML body) for one code in one language."""
    strings = _TEMPLATES.get(language, _TEMPLATES["en"])
    lang = language if language in _TEMPLATES else "en"
    minutes = settings.verification_code_ttl_minutes
    filled = {key: value.format(code=code, minutes=minutes) for key, value in strings.items()}
    fields = {
        key: value if key in _PRE_ESCAPED else html.escape(value) for key, value in filled.items()
    }
    body = _html_template().substitute(fields, code=html.escape(code), lang=lang)
    return filled["subject"], filled["text"], body


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
