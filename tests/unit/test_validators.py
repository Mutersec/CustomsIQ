"""Tests for validation utilities"""

import pytest
from src.utils.validators import (
    validate_gtip_format,
    validate_country_code,
    parse_gtip_code
)


class TestGTIPValidation:
    """Tests for GTIP validation"""

    def test_valid_gtip_format(self):
        """Test valid GTIP codes"""
        assert validate_gtip_format("610910200") == False  # Only 9 digits
        assert validate_gtip_format("6109102000") == False  # Only 10 digits
        assert validate_gtip_format("610910200000") == True  # 12 digits

    def test_invalid_gtip_format(self):
        """Test invalid GTIP formats"""
        assert validate_gtip_format("61091020000a") == False  # Contains letter
        assert validate_gtip_format("") == False
        assert validate_gtip_format(None) == False

    def test_parse_gtip_code(self):
        """Test GTIP code parsing"""
        chapter, position, subposition, item = parse_gtip_code("610910200000")
        assert chapter == "61"
        assert position == "09"
        assert subposition == "1020"
        assert item == "0000"


class TestCountryValidation:
    """Tests for country code validation"""

    def test_valid_country_codes(self):
        """Test valid ISO country codes"""
        assert validate_country_code("TR") == True
        assert validate_country_code("US") == True
        assert validate_country_code("DE") == True

    def test_invalid_country_codes(self):
        """Test invalid country codes"""
        assert validate_country_code("TRX") == False
        assert validate_country_code("T") == False
        assert validate_country_code("12") == False
        assert validate_country_code("") == False
