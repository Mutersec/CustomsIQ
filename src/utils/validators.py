"""Validation utilities for trade compliance"""

HS_CODE_LENGTH = 6
CN_CODE_LENGTH = 8
TARIC_CODE_LENGTH = 10


def validate_cn_code(cn_code: str) -> bool:
    """
    Validate an EU Combined Nomenclature code format.

    Accepts both CN-8 (8 digits) and TARIC (10 digits) codes.

    Args:
        cn_code: CN or TARIC code to validate

    Returns:
        True if valid format, False otherwise
    """
    if not isinstance(cn_code, str):
        return False
    return len(cn_code) in (CN_CODE_LENGTH, TARIC_CODE_LENGTH) and cn_code.isdigit()


def validate_hs_code(code: str) -> bool:
    """
    Validate any code the catalogue can hold: HS-6, CN-8 or TARIC-10.

    HS-6 codes come from the HS 2022 supplement that fills headings the EU CN
    bundle lacks (see scripts/build_hs_supplement.py). Kept separate from
    `validate_cn_code` on purpose: invoice extraction must not start treating
    any six-digit number on a document (a postcode, a date) as a tariff code.

    Args:
        code: HS, CN or TARIC code to validate

    Returns:
        True if valid format, False otherwise
    """
    if not isinstance(code, str):
        return False
    return len(code) in (HS_CODE_LENGTH, CN_CODE_LENGTH, TARIC_CODE_LENGTH) and code.isdigit()


def validate_country_code(country_code: str) -> bool:
    """
    Validate ISO 3166-1 alpha-2 country code.

    Args:
        country_code: Country code (e.g., 'DE', 'FR')

    Returns:
        True if valid, False otherwise
    """
    return isinstance(country_code, str) and len(country_code) == 2 and country_code.isalpha()


def parse_cn_code(cn_code: str) -> tuple[str, str, str, str]:
    """
    Parse a CN or TARIC code into its CN-8 components.

    EU nomenclature structure:
    - CC: Chapter (digits 1-2)
    - HH: Heading (digits 3-4) — with the chapter this forms the HS-4 heading
    - SS: HS subheading (digits 5-6) — completes the international HS-6 code
    - NN: CN subheading (digits 7-8) — completes the EU CN-8 code

    TARIC codes are accepted; their last two digits are an EU-specific TARIC
    subheading and are not part of CN-8, so they are not returned here.

    Returns:
        Tuple of (chapter, heading, hs_subheading, cn_subheading)
    """
    if not validate_cn_code(cn_code):
        raise ValueError(f"Invalid CN code format: {cn_code}")

    return (cn_code[0:2], cn_code[2:4], cn_code[4:6], cn_code[6:8])
