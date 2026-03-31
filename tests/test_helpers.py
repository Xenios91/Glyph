"""Unit tests for helper utilities."""
import pytest
from app.utils.helpers import ACCEPT_TYPE


class TestHelpers:
    """Tests for helper constants and functions."""

    def test_accept_type_constant(self):
        """Test that ACCEPT_TYPE constant is correctly defined."""
        assert ACCEPT_TYPE == "text/html"
        assert isinstance(ACCEPT_TYPE, str)
        assert len(ACCEPT_TYPE) > 0
