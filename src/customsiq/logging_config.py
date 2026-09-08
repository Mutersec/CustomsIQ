"""Logging setup for CustomsIQ."""

import logging
import sys

from src.customsiq.config import settings


def configure_logging() -> None:
    """Configure root logging once, at CLI/API startup.

    Uses a plain formatter (no timestamp/level noise) and stdout, since the
    CLI's logger output IS the product's user-facing text, not diagnostic noise.
    """
    logging.basicConfig(
        level=settings.log_level, format="%(message)s", stream=sys.stdout, force=True
    )
