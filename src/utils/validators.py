"""Validation utilities for trade compliance"""

from typing import Tuple


def validate_gtip_format(gtip_code: str) -> bool:
    """
    Validate GTIP code format (should be 12 digits).

    Args:
        gtip_code: GTIP code to validate

    Returns:
        True if valid format, False otherwise
    """
    if not isinstance(gtip_code, str):
        return False
    return len(gtip_code) == 12 and gtip_code.isdigit()


def validate_country_code(country_code: str) -> bool:
    """
    Validate ISO 3166-1 alpha-2 country code.

    Args:
        country_code: Country code (e.g., 'TR', 'US')

    Returns:
        True if valid, False otherwise
    """
    return isinstance(country_code, str) and len(country_code) == 2 and country_code.isalpha()


def parse_gtip_code(gtip_code: str) -> Tuple[str, str, str, str]:
    """
    Parse GTIP code into its components.

    GTIP format: CCPPSSAA
    - CC: Chapter (2 digits)
    - PP: Position (2 digits)
    - SS: Subposition (2 digits)
    - AA: Item (2 digits)

    Returns:
        Tuple of (chapter, position, subposition, item)
    """
    if not validate_gtip_format(gtip_code):
        raise ValueError(f"Invalid GTIP format: {gtip_code}")

    return (
        gtip_code[0:2],
        gtip_code[2:4],
        gtip_code[4:8],
        gtip_code[8:12]
    )
