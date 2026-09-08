"""Tests for validation utilities"""

from src.utils.validators import parse_cn_code, validate_cn_code, validate_country_code


class TestCNValidation:
    """Tests for CN/TARIC code validation"""

    def test_valid_cn_format(self):
        """Test valid CN and TARIC codes"""
        assert validate_cn_code("61091000") is True  # CN-8
        assert validate_cn_code("6109100000") is True  # TARIC-10
        assert validate_cn_code("610910") is False  # HS-6 is not a CN code
        assert validate_cn_code("610910000000") is False  # 12 digits, not EU format

    def test_invalid_cn_format(self):
        """Test invalid CN formats"""
        assert validate_cn_code("6109100a") is False  # Contains letter
        assert validate_cn_code("") is False
        assert validate_cn_code(None) is False

    def test_parse_cn_code(self):
        """Test CN code parsing into its CN-8 components"""
        chapter, heading, hs_subheading, cn_subheading = parse_cn_code("61091000")
        assert chapter == "61"
        assert heading == "09"
        assert hs_subheading == "10"
        assert cn_subheading == "00"

    def test_parse_taric_code_returns_cn8_core(self):
        """A TARIC-10 code parses to the same CN-8 components"""
        assert parse_cn_code("6109100000") == parse_cn_code("61091000")


class TestCountryValidation:
    """Tests for country code validation"""

    def test_valid_country_codes(self):
        """Test valid ISO country codes"""
        assert validate_country_code("DE") is True
        assert validate_country_code("FR") is True
        assert validate_country_code("NL") is True

    def test_invalid_country_codes(self):
        """Test invalid country codes"""
        assert validate_country_code("DEU") is False
        assert validate_country_code("D") is False
        assert validate_country_code("12") is False
        assert validate_country_code("") is False
