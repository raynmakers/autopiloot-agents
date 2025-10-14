"""
Test suite for strategy_agent RAG index wrapper (rag_index_strategy.py).

Tests feature flag behavior, payload building, core library delegation,
and error handling for optional strategy content indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestRagIndexStrategyWrapper(unittest.TestCase):
    """Test suite for RagIndexStrategy tool wrapper (feature-flagged)."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_agency_swarm = MagicMock()
        self.mock_base_tool = MagicMock()
        self.mock_agency_swarm.tools.BaseTool = self.mock_base_tool
        # Mock pydantic module
        self.mock_pydantic = MagicMock()
        sys.modules["pydantic"] = self.mock_pydantic

        sys.modules["agency_swarm"] = self.mock_agency_swarm
        sys.modules['agency_swarm.tools'] = self.mock_agency_swarm.tools

        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'strategy_agent', 'tools', 'rag_index_strategy.py'
        )
        spec = importlib.util.spec_from_file_location("rag_index_strategy", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagIndexStrategy = self.module.RagIndexStrategy

    def tearDown(self):
        """Clean up after each test."""
        if "pydantic" in sys.modules:
            del sys.modules["pydantic"]
        if "agency_swarm" in sys.modules:
            del sys.modules['agency_swarm']
        if 'agency_swarm.tools' in sys.modules:
            del sys.modules['agency_swarm.tools']

    def test_init_with_required_fields(self):
        """Test initialization with only required fields."""
        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content text."
        )

        self.assertEqual(tool.strategy_id, "strategy_123")
        self.assertEqual(tool.text, "Strategic content text.")
        self.assertIsNone(tool.title)
        self.assertIsNone(tool.tags)
        self.assertIsNone(tool.author_id)
        self.assertIsNone(tool.published_at)
        self.assertIsNone(tool.content_type)

    @patch('core.rag.config.get_rag_flag')
    def test_run_feature_disabled(self, mock_get_flag):
        """Test that run() returns skipped when feature flag is false."""
        mock_get_flag.return_value = False

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["strategy_id"], "strategy_123")
        self.assertEqual(result["feature_enabled"], False)
        self.assertIn("rag.features.persist_strategies is false", result["message"])

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_feature_enabled_success(self, mock_get_flag, mock_ingest):
        """Test successful indexing when feature flag is enabled."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Ingested strategy content to Zep"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["strategy_id"], "strategy_123")  # Renamed from content_id
        self.assertEqual(result["feature_enabled"], True)

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_with_all_optional_fields(self, mock_get_flag, mock_ingest):
        """Test run() with all optional fields when feature enabled."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Success"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content",
            title="LinkedIn Post Title",
            tags=["linkedin", "saas", "scaling"],
            author_id="alexhormozi",
            published_at="2025-10-08T14:30:00Z",
            content_type="linkedin_post"
        )

        tool.run()

        # Verify all fields were passed to core library
        mock_ingest.assert_called_once()
        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["content_id"], "strategy_123")
        self.assertEqual(call_args["content_text"], "Strategic content")
        self.assertEqual(call_args["content_type"], "linkedin_post")
        self.assertEqual(call_args["author_id"], "alexhormozi")
        self.assertEqual(call_args["title"], "LinkedIn Post Title")
        self.assertEqual(call_args["tags"], ["linkedin", "saas", "scaling"])
        self.assertEqual(call_args["published_at"], "2025-10-08T14:30:00Z")

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_default_author_id(self, mock_get_flag, mock_ingest):
        """Test that author_id defaults to 'unknown' if not provided."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Success"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
            # author_id not provided
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["author_id"], "unknown")

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_default_content_type(self, mock_get_flag, mock_ingest):
        """Test that content_type defaults to 'strategy' if not provided."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Success"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
            # content_type not provided
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["content_type"], "strategy")

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_renames_content_id_to_strategy_id(self, mock_get_flag, mock_ingest):
        """Test that content_id is renamed to strategy_id in response."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Success"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertIn("strategy_id", result)
        self.assertEqual(result["strategy_id"], "strategy_123")
        self.assertNotIn("content_id", result)

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_core_library_skipped(self, mock_get_flag, mock_ingest):
        """Test handling of skipped status from core library."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "skipped",
            "content_id": "strategy_123",
            "message": "Strategy content ingestion skipped (Zep disabled)"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "skipped")
        self.assertIn("Zep disabled", result["message"])

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_core_library_error(self, mock_get_flag, mock_ingest):
        """Test error handling when core library fails."""
        mock_get_flag.return_value = True
        mock_ingest.side_effect = Exception("Zep connection failed")

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertIn("Zep connection failed", result["message"])
        self.assertEqual(result["strategy_id"], "strategy_123")

    @patch('core.rag.config.get_rag_flag')
    def test_run_feature_flag_checked_first(self, mock_get_flag):
        """Test that feature flag is checked before any processing."""
        mock_get_flag.return_value = False

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        with patch('core.rag.ingest_strategy.ingest') as mock_ingest:
            tool.run()

            # Verify ingest was NOT called when feature disabled
            mock_ingest.assert_not_called()

    @patch('core.rag.ingest_strategy.ingest')
    @patch('core.rag.config.get_rag_flag')
    def test_run_returns_json_string(self, mock_get_flag, mock_ingest):
        """Test that run() returns a JSON string."""
        mock_get_flag.return_value = True
        mock_ingest.return_value = {
            "status": "success",
            "content_id": "strategy_123",
            "message": "Success"
        }

        tool = self.RagIndexStrategy(
            strategy_id="strategy_123",
            text="Strategic content"
        )

        result = tool.run()

        # Verify it's a string
        self.assertIsInstance(result, str)

        # Verify it's valid JSON
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "success")


if __name__ == "__main__":
    unittest.main()
