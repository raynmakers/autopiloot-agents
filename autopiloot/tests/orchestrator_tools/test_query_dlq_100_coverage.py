"""
Comprehensive test suite for QueryDLQ tool targeting 100% coverage.
Tests all query filters, statistics calculation, and error handling paths.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import json
import sys
import os
from datetime import datetime, timezone, timedelta


# Mock external dependencies before imports
mock_modules = {
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'dotenv': MagicMock(),
}

for module_name, mock_module in mock_modules.items():
    sys.modules[module_name] = mock_module

# Create BaseTool mock
class MockBaseTool:
    pass

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

# Create Field mock that returns the default value
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Mock Firestore Query
mock_query_class = MagicMock()
mock_query_class.DESCENDING = 'DESCENDING'
sys.modules['google.cloud.firestore'].Query = mock_query_class

# Import the tool after mocking
from orchestrator_agent.tools.query_dlq import QueryDLQ

# Patch QueryDLQ __init__ to accept kwargs
original_init = QueryDLQ.__init__ if hasattr(QueryDLQ, '__init__') else lambda self: None

def patched_init(self, **kwargs):
    # Set all attributes from kwargs
    self.filter_job_type = kwargs.get('filter_job_type', None)
    self.filter_video_id = kwargs.get('filter_video_id', None)
    self.filter_severity = kwargs.get('filter_severity', None)
    self.time_range_hours = kwargs.get('time_range_hours', 24)
    self.include_statistics = kwargs.get('include_statistics', True)
    self.limit = kwargs.get('limit', 50)

QueryDLQ.__init__ = patched_init


class TestQueryDLQ100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for QueryDLQ."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_query = MagicMock()

        # Chain mock methods
        self.mock_db.collection.return_value = self.mock_collection
        self.mock_collection.where.return_value = self.mock_query
        self.mock_query.where.return_value = self.mock_query
        self.mock_query.order_by.return_value = self.mock_query
        self.mock_query.limit.return_value = self.mock_query

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_successful_query_all_entries(self, mock_client, mock_get_env, mock_exists):
        """Test successful query with no filters (lines 68-149)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        # Mock Firestore documents
        mock_doc1 = MagicMock()
        mock_doc1.id = "dlq_001"
        mock_doc1.to_dict.return_value = {
            "job_type": "single_video",
            "severity": "high",
            "dlq_created_at": datetime.now(timezone.utc),
            "failure_context": {"error_type": "api_error"},
            "processing_attempts": 3
        }

        self.mock_query.stream.return_value = [mock_doc1]

        tool = QueryDLQ(
            time_range_hours=24,
            include_statistics=True,
            limit=50
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("query_executed_at", data)
        self.assertEqual(data["entries_count"], 1)
        self.assertIn("statistics", data)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_query_with_job_type_filter(self, mock_client, mock_get_env, mock_exists):
        """Test query with job_type filter (lines 95-96)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        self.mock_query.stream.return_value = []

        tool = QueryDLQ(
            filter_job_type="channel_scrape",
            include_statistics=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["filters_applied"]["job_type"], "channel_scrape")

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_query_with_severity_filter(self, mock_client, mock_get_env, mock_exists):
        """Test query with severity filter (lines 99-100)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        self.mock_query.stream.return_value = []

        tool = QueryDLQ(
            filter_severity="high",
            include_statistics=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["filters_applied"]["severity"], "high")

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_query_with_video_id_filter_match(self, mock_client, mock_get_env, mock_exists):
        """Test query with video_id filter that matches (lines 117-119)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        # Mock document with matching video_id
        mock_doc = MagicMock()
        mock_doc.id = "dlq_001"
        mock_doc.to_dict.return_value = {
            "video_id": "test_video_123",
            "job_type": "single_video",
            "dlq_created_at": datetime.now(timezone.utc)
        }

        self.mock_query.stream.return_value = [mock_doc]

        tool = QueryDLQ(
            filter_video_id="test_video_123",
            include_statistics=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["entries_count"], 1)
        self.assertEqual(data["entries"][0]["video_id"], "test_video_123")

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_query_with_video_id_filter_no_match(self, mock_client, mock_get_env, mock_exists):
        """Test query with video_id filter that doesn't match (lines 120-121)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        # Mock document without matching video_id
        mock_doc = MagicMock()
        mock_doc.id = "dlq_001"
        mock_doc.to_dict.return_value = {
            "video_id": "different_video",
            "job_type": "single_video",
            "dlq_created_at": datetime.now(timezone.utc)
        }

        self.mock_query.stream.return_value = [mock_doc]

        tool = QueryDLQ(
            filter_video_id="test_video_123",
            include_statistics=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["entries_count"], 0)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_video_id_filter_merge(self, mock_client, mock_get_env, mock_exists):
        """Test video_id filter result merge (lines 124-125)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        # Mock documents
        mock_doc1 = MagicMock()
        mock_doc1.id = "dlq_001"
        mock_doc1.to_dict.return_value = {
            "video_id": "test_video_123",
            "dlq_created_at": datetime.now(timezone.utc)
        }

        mock_doc2 = MagicMock()
        mock_doc2.id = "dlq_002"
        mock_doc2.to_dict.return_value = {
            "video_ids": ["test_video_123", "other_video"],
            "dlq_created_at": datetime.now(timezone.utc)
        }

        self.mock_query.stream.return_value = [mock_doc1, mock_doc2]

        tool = QueryDLQ(
            filter_video_id="test_video_123",
            include_statistics=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["entries_count"], 2)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_timestamp_conversion(self, mock_client, mock_get_env, mock_exists):
        """Test Firestore timestamp to ISO string conversion (lines 128-130)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        mock_timestamp = datetime(2025, 9, 29, 12, 0, 0, tzinfo=timezone.utc)

        mock_doc = MagicMock()
        mock_doc.id = "dlq_001"
        mock_doc.to_dict.return_value = {
            "job_type": "single_video",
            "dlq_created_at": mock_timestamp
        }

        self.mock_query.stream.return_value = [mock_doc]

        tool = QueryDLQ(include_statistics=False)
        result = tool.run()
        data = json.loads(result)

        self.assertIn("dlq_created_at", data["entries"][0])
        self.assertIsInstance(data["entries"][0]["dlq_created_at"], str)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_statistics_included(self, mock_client, mock_get_env, mock_exists):
        """Test statistics calculation when enabled (lines 146-147)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        mock_doc = MagicMock()
        mock_doc.id = "dlq_001"
        mock_doc.to_dict.return_value = {
            "job_type": "single_video",
            "severity": "high",
            "dlq_created_at": datetime.now(timezone.utc),
            "failure_context": {"error_type": "api_error"},
            "recovery_priority": "urgent",
            "processing_attempts": 3
        }

        self.mock_query.stream.return_value = [mock_doc]

        tool = QueryDLQ(include_statistics=True)
        result = tool.run()
        data = json.loads(result)

        self.assertIn("statistics", data)
        self.assertEqual(data["statistics"]["total_entries"], 1)

    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_run_exception_handling(self, mock_client, mock_get_env):
        """Test exception handling in run method (lines 151-155)."""
        mock_get_env.side_effect = Exception("Firestore initialization failed")

        tool = QueryDLQ()
        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["entries"], [])

    def test_validate_invalid_severity(self):
        """Test validation for invalid severity (lines 159-160)."""
        tool = QueryDLQ(filter_severity="invalid")

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("filter_severity must be", str(context.exception))

    def test_validate_invalid_job_type(self):
        """Test validation for invalid job_type (lines 168-169)."""
        tool = QueryDLQ(filter_job_type="invalid_type")

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("filter_job_type must be one of", str(context.exception))

    def test_matches_video_id_direct(self):
        """Test video_id match in direct field (lines 174-175)."""
        tool = QueryDLQ()

        entry = {"video_id": "test_video_123"}

        self.assertTrue(tool._matches_video_id(entry, "test_video_123"))

    def test_matches_video_id_in_list(self):
        """Test video_id match in video_ids list (lines 178-180)."""
        tool = QueryDLQ()

        entry = {"video_ids": ["video_1", "test_video_123", "video_3"]}

        self.assertTrue(tool._matches_video_id(entry, "test_video_123"))

    def test_matches_video_id_in_original_inputs(self):
        """Test video_id match in original_inputs field (lines 183-185)."""
        tool = QueryDLQ()

        entry = {
            "failure_context": {
                "original_inputs": {"video_id": "test_video_123"}
            }
        }

        self.assertTrue(tool._matches_video_id(entry, "test_video_123"))

    def test_matches_video_id_in_original_inputs_list(self):
        """Test video_id match in original_inputs video_ids (lines 187-188)."""
        tool = QueryDLQ()

        entry = {
            "failure_context": {
                "original_inputs": {"video_ids": ["video_1", "test_video_123"]}
            }
        }

        self.assertTrue(tool._matches_video_id(entry, "test_video_123"))

    def test_matches_video_id_no_match(self):
        """Test video_id no match returns False (line 190)."""
        tool = QueryDLQ()

        entry = {"video_id": "different_video"}

        self.assertFalse(tool._matches_video_id(entry, "test_video_123"))

    def test_calculate_statistics_empty_entries(self):
        """Test statistics calculation with empty entries (lines 194-203)."""
        tool = QueryDLQ()

        stats = tool._calculate_statistics([])

        self.assertEqual(stats["total_entries"], 0)
        self.assertEqual(stats["by_job_type"], {})
        self.assertEqual(stats["average_processing_attempts"], 0)

    def test_calculate_statistics_full(self):
        """Test full statistics calculation (lines 205-248)."""
        tool = QueryDLQ()

        entries = [
            {
                "job_type": "single_video",
                "severity": "high",
                "failure_context": {"error_type": "api_error"},
                "recovery_priority": "urgent",
                "processing_attempts": 3
            },
            {
                "job_type": "single_video",
                "severity": "medium",
                "failure_context": {"error_type": "api_error"},
                "recovery_priority": "high",
                "processing_attempts": 2
            },
            {
                "job_type": "channel_scrape",
                "severity": "low",
                "failure_context": {"error_type": "timeout"},
                "recovery_priority": "medium",
                "processing_attempts": 1
            }
        ]

        stats = tool._calculate_statistics(entries)

        self.assertEqual(stats["total_entries"], 3)
        self.assertEqual(stats["by_job_type"]["single_video"], 2)
        self.assertEqual(stats["by_severity"]["high"], 1)
        self.assertEqual(stats["by_error_type"]["api_error"], 2)
        self.assertEqual(stats["recovery_priority_distribution"]["urgent"], 1)
        self.assertEqual(stats["average_processing_attempts"], 2.0)
        self.assertEqual(len(stats["top_error_patterns"]), 2)

    def test_calculate_statistics_zero_attempts(self):
        """Test statistics with zero processing attempts (line 231)."""
        tool = QueryDLQ()

        entries = [
            {
                "job_type": "single_video",
                "severity": "high",
                "failure_context": {"error_type": "api_error"},
                "recovery_priority": "urgent",
                "processing_attempts": 0
            }
        ]

        stats = tool._calculate_statistics(entries)

        self.assertEqual(stats["average_processing_attempts"], 0)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_initialize_firestore_success(self, mock_client, mock_get_env, mock_exists):
        """Test successful Firestore initialization (lines 253-259)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        tool = QueryDLQ()
        db = tool._initialize_firestore()

        self.assertIsNotNone(db)

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    def test_initialize_firestore_missing_file(self, mock_get_env, mock_exists):
        """Test Firestore initialization with missing credentials (lines 256-257)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/missing.json"
        mock_exists.return_value = False

        tool = QueryDLQ()

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('orchestrator_agent.tools.query_dlq.os.path.exists')
    @patch('orchestrator_agent.tools.query_dlq.get_required_env_var')
    @patch('orchestrator_agent.tools.query_dlq.firestore.Client')
    def test_initialize_firestore_exception(self, mock_client, mock_get_env, mock_exists):
        """Test Firestore initialization exception handling (lines 261-262)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.side_effect = Exception("Connection failed")

        tool = QueryDLQ()

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))


if __name__ == "__main__":
    unittest.main()