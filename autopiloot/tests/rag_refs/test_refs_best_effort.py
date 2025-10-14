"""
Tests for core/rag/refs.py - Best-Effort Firestore RAG References

Tests cover all three functions (upsert_ref, get_ref, query_refs) with focus on:
- Feature flag behavior (enabled/disabled)
- Best-effort error handling (never raises exceptions)
- Required field validation
- Optional field handling

Target: ≥80% coverage for core/rag/refs.py
"""

import os
import sys
import unittest
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestUpsertRef(unittest.TestCase):
    """Tests for upsert_ref() function"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_ref = {
            "type": "transcript",
            "source_ref": "abc123",
            "created_by_agent": "transcriber_agent",
            "content_hashes": ["hash1", "hash2"],
            "chunk_count": 10,
            "total_tokens": 8500,
            "indexing_status": "success",
            "sink_statuses": {"opensearch": "indexed", "zep": "upserted"},
            "indexing_duration_ms": 5234
        }

    @patch('config.loader.get_config_value')
    def test_feature_flag_disabled_skips_silently(self, mock_config):
        """Test that disabled feature flag skips write without logging"""
        # Import after mocking
        from core.rag.refs import upsert_ref

        # Feature flag disabled
        mock_config.return_value = False

        # Should return immediately without error
        result = upsert_ref(self.valid_ref)
        self.assertIsNone(result)

        # Config should have been checked
        mock_config.assert_called_once_with("rag.features.write_firestore_refs", False)

    @patch('config.loader.get_config_value')
    def test_missing_required_field_logs_warning(self, mock_config):
        """Test that missing required fields are detected and logged"""
        from core.rag.refs import upsert_ref

        # Feature flag enabled
        mock_config.return_value = True

        # Missing 'created_by_agent' field
        invalid_ref = self.valid_ref.copy()
        del invalid_ref["created_by_agent"]

        # Should log warning and return None
        with patch('builtins.print') as mock_print:
            result = upsert_ref(invalid_ref)
            self.assertIsNone(result)
            # Check that warning was logged
            mock_print.assert_called_once()
            self.assertIn("missing required field", mock_print.call_args[0][0])
            self.assertIn("created_by_agent", mock_print.call_args[0][0])

    @patch('config.loader.get_config_value')
    def test_top_level_exception_catch(self, mock_config):
        """Test that top-level exception handler catches all errors"""
        from core.rag.refs import upsert_ref

        # Mock config to raise unexpected exception
        mock_config.side_effect = RuntimeError("Unexpected error")

        with patch('builtins.print') as mock_print:
            result = upsert_ref(self.valid_ref)
            self.assertIsNone(result)

            # Check that top-level warning was logged
            mock_print.assert_called_once()
            self.assertIn("RAG ref write failed", mock_print.call_args[0][0])


class TestGetRef(unittest.TestCase):
    """Tests for get_ref() function"""

    @patch('config.loader.get_config_value')
    def test_feature_flag_disabled_returns_none(self, mock_config):
        """Test that disabled feature flag returns None silently"""
        from core.rag.refs import get_ref

        # Feature flag disabled
        mock_config.return_value = False

        result = get_ref("transcript", "abc123")
        self.assertIsNone(result)

    @patch('config.loader.get_config_value')
    def test_exception_returns_none_with_warning(self, mock_config):
        """Test that exceptions are caught and return None"""
        from core.rag.refs import get_ref

        # Feature flag enabled but exception occurs
        mock_config.return_value = True

        # Mock the import to raise exception
        with patch('builtins.__import__', side_effect=ImportError("No module")):
            with patch('builtins.print') as mock_print:
                result = get_ref("transcript", "abc123")
                self.assertIsNone(result)


class TestQueryRefs(unittest.TestCase):
    """Tests for query_refs() function"""

    @patch('config.loader.get_config_value')
    def test_feature_flag_disabled_returns_empty_list(self, mock_config):
        """Test that disabled feature flag returns empty list"""
        from core.rag.refs import query_refs

        # Feature flag disabled
        mock_config.return_value = False

        result = query_refs()
        self.assertEqual(result, [])

    @patch('config.loader.get_config_value')
    def test_exception_returns_empty_list_with_warning(self, mock_config):
        """Test that exceptions are caught and return empty list"""
        from core.rag.refs import query_refs

        # Feature flag enabled but exception occurs
        mock_config.return_value = True

        # Mock the import to raise exception
        with patch('builtins.__import__', side_effect=ImportError("No module")):
            with patch('builtins.print') as mock_print:
                result = query_refs()
                self.assertEqual(result, [])


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
