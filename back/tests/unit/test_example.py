"""Example unit test to verify test runner works."""

import pytest


def test_basic_math():
    """Test basic math operations."""
    assert 2 + 2 == 4
    assert 3 * 4 == 12
    assert 10 / 2 == 5


def test_string_operations():
    """Test string operations."""
    test_string = "Hello World"
    assert test_string.lower() == "hello world"
    assert test_string.upper() == "HELLO WORLD"
    assert len(test_string) == 11


def test_list_operations():
    """Test list operations."""
    test_list = [1, 2, 3, 4, 5]
    assert len(test_list) == 5
    assert test_list[0] == 1
    assert test_list[-1] == 5
    assert sum(test_list) == 15


class TestExampleClass:
    """Example test class."""
    
    def test_class_method(self):
        """Test within a class."""
        data = {"key": "value", "number": 42}
        assert data["key"] == "value"
        assert data["number"] == 42
        assert "key" in data
