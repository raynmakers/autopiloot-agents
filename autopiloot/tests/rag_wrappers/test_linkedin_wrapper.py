"""
Test suite for linkedin_agent RAG wrapper (rag_index_linkedin.py).

Tests wrapper initialization, engagement metadata handling, payload building,
core library delegation, and error handling for LinkedIn content indexing.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock
import importlib.util


class TestRagIndexLinkedinWrapper(unittest.TestCase):
    """Test suite for RagIndexLinkedin tool wrapper."""

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
            'linkedin_agent', 'tools', 'rag_index_linkedin.py'
        )
        spec = importlib.util.spec_from_file_location("rag_index_linkedin", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.RagIndexLinkedin = self.module.RagIndexLinkedin

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
        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample LinkedIn post text."
        )

        self.assertEqual(tool.post_or_comment_id, "linkedin_post_123")
        self.assertEqual(tool.text, "Sample LinkedIn post text.")
        self.assertIsNone(tool.author)
        self.assertIsNone(tool.permalink)
        self.assertIsNone(tool.created_at)
        self.assertIsNone(tool.tags)
        self.assertEqual(tool.content_type, "post")  # default
        self.assertIsNone(tool.engagement)

    @patch('core.rag.ingest_document.ingest')
    def test_run_success_post(self, mock_ingest):
        """Test successful LinkedIn post indexing."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {
                "opensearch": {"status": "indexed"}
            },
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample post text",
            author="@alexhormozi"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["linkedin_id"], "linkedin_post_123")

    @patch('core.rag.ingest_document.ingest')
    def test_run_success_comment(self, mock_ingest):
        """Test successful LinkedIn comment indexing."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_comment_456",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_comment_456",
            text="Great insights!",
            content_type="comment"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["linkedin_id"], "linkedin_comment_456")

    @patch('core.rag.ingest_document.ingest')
    def test_run_sets_source_and_type(self, mock_ingest):
        """Test that source and document_type are set correctly."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["source"], "linkedin")
        self.assertEqual(call_args["document_type"], "linkedin")

    @patch('core.rag.ingest_document.ingest')
    def test_run_builds_title_with_author(self, mock_ingest):
        """Test title generation with author."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text",
            author="@alexhormozi",
            content_type="post"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["title"], "LinkedIn post by @alexhormozi")

    @patch('core.rag.ingest_document.ingest')
    def test_run_builds_title_without_author(self, mock_ingest):
        """Test title generation without author."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text",
            content_type="post"
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        self.assertEqual(call_args["title"], "LinkedIn post")

    @patch('core.rag.ingest_document.ingest')
    def test_run_with_engagement_metrics(self, mock_ingest):
        """Test engagement metrics are added as tags."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text",
            engagement={"likes": 245, "comments": 18, "shares": 12}
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        tags = call_args.get("tags", [])
        self.assertIn("likes:245", tags)
        self.assertIn("comments:18", tags)
        self.assertIn("shares:12", tags)

    @patch('core.rag.ingest_document.ingest')
    def test_run_with_tags_and_engagement(self, mock_ingest):
        """Test that engagement metrics are appended to existing tags."""
        mock_ingest.return_value = {
            "status": "success",
            "document_id": "linkedin_post_123",
            "chunk_count": 1,
            "sinks": {},
            "message": "Success"
        }

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text",
            tags=["saas", "scaling"],
            engagement={"likes": 100, "comments": 5, "shares": 2}
        )

        tool.run()

        call_args = mock_ingest.call_args[0][0]
        tags = call_args.get("tags", [])
        self.assertIn("saas", tags)
        self.assertIn("scaling", tags)
        self.assertIn("likes:100", tags)
        self.assertIn("comments:5", tags)
        self.assertIn("shares:2", tags)

    @patch('core.rag.ingest_document.ingest')
    def test_run_error_handling(self, mock_ingest):
        """Test error handling when core library fails."""
        mock_ingest.side_effect = Exception("Network error")

        tool = self.RagIndexLinkedin(
            post_or_comment_id="linkedin_post_123",
            text="Sample text"
        )

        result_json = tool.run()
        result = json.loads(result_json)

        self.assertEqual(result["status"], "error")
        self.assertIn("Network error", result["message"])
        self.assertEqual(result["linkedin_id"], "linkedin_post_123")


if __name__ == "__main__":
    unittest.main()
