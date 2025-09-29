"""
Comprehensive test suite for DispatchScraper tool targeting 100% coverage.
Tests job dispatch, validation, and Firestore integration.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import json
import sys
import os
from datetime import datetime, timezone


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

# Create Field mock
def mock_field(default=None, **kwargs):
    return default

sys.modules['pydantic'].Field = mock_field

# Mock SERVER_TIMESTAMP
sys.modules['google.cloud.firestore'].SERVER_TIMESTAMP = 'SERVER_TIMESTAMP'

# Import the tool after mocking
from orchestrator_agent.tools.dispatch_scraper import DispatchScraper

# Patch DispatchScraper __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.job_type = kwargs.get('job_type')
    self.inputs = kwargs.get('inputs', {})
    self.policy_overrides = kwargs.get('policy_overrides', None)

DispatchScraper.__init__ = patched_init


class TestDispatchScraper100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for DispatchScraper."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()
        self.mock_doc_ref = MagicMock()
        self.mock_active_collection = MagicMock()

        # Chain mock methods
        self.mock_db.collection.return_value = self.mock_collection
        self.mock_collection.document.return_value = self.mock_collection
        self.mock_collection.collection.return_value = self.mock_active_collection
        self.mock_active_collection.document.return_value = self.mock_doc_ref

    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_scraper.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    def test_successful_channel_scrape_dispatch(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test successful channel_scrape job dispatch (lines 62-126)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {}

        # Mock no existing job
        mock_existing_job = MagicMock()
        mock_existing_job.exists = False
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={
                "channels": ["@AlexHormozi"],
                "limit_per_channel": 10
            },
            policy_overrides={"retry_max_attempts": 3}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "dispatched")
        self.assertEqual(data["job_type"], "channel_scrape")
        self.assertIn("job_id", data)
        self.assertIn("priority", data)
        self.assertIn("estimated_quota_usage", data)

        # Verify job was set in Firestore
        self.mock_doc_ref.set.assert_called_once()

        # Verify audit log
        mock_audit.log_job_dispatched.assert_called_once()

    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_scraper.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    def test_successful_sheet_backfill_dispatch(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test successful sheet_backfill job dispatch (lines 103-105)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {}

        # Mock no existing job
        mock_existing_job = MagicMock()
        mock_existing_job.exists = False
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={
                "sheet_id": "abc123",
                "range": "Sheet1!A:D"
            }
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "dispatched")
        self.assertEqual(data["job_type"], "sheet_backfill")

        # Verify sheet-specific metadata was added
        call_args = self.mock_doc_ref.set.call_args
        payload = call_args[0][0]
        self.assertEqual(payload["sheet_id"], "abc123")
        self.assertEqual(payload["sheet_range"], "Sheet1!A:D")

    @patch('orchestrator_agent.tools.dispatch_scraper.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_scraper.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    def test_existing_job_detection(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test detection of existing job (lines 79-84)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {}

        # Mock existing job
        mock_existing_job = MagicMock()
        mock_existing_job.exists = True
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "already_exists")
        self.assertIn("Job already dispatched", data["message"])

    def test_validate_channel_scrape_missing_channels(self):
        """Test validation for missing channels (lines 137-138)."""
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("requires 'channels'", str(context.exception))

    def test_validate_channel_scrape_channels_not_list(self):
        """Test validation for channels not a list (lines 139-140)."""
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": "not_a_list"}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("must be a list", str(context.exception))

    def test_validate_channel_scrape_empty_channels(self):
        """Test validation for empty channels list (lines 141-142)."""
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": []}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("cannot be empty", str(context.exception))

    def test_validate_sheet_backfill_missing_sheet_id(self):
        """Test validation for missing sheet_id (lines 145-146)."""
        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("requires 'sheet_id'", str(context.exception))

    def test_validate_sheet_backfill_sheet_id_not_string(self):
        """Test validation for sheet_id not a string (lines 147-148)."""
        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={"sheet_id": 12345}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("must be a string", str(context.exception))

    def test_validate_invalid_job_type(self):
        """Test validation for invalid job type (lines 150-151)."""
        tool = DispatchScraper(
            job_type="invalid_type",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Invalid job_type", str(context.exception))

    def test_calculate_priority_channel_scrape(self):
        """Test priority calculation for channel_scrape (lines 155-156)."""
        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "high")

    def test_calculate_priority_sheet_backfill(self):
        """Test priority calculation for sheet_backfill (lines 157-158)."""
        tool = DispatchScraper(
            job_type="sheet_backfill",
            inputs={"sheet_id": "abc123"}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "medium")

    def test_calculate_priority_unknown_type(self):
        """Test priority calculation for unknown type (line 159)."""
        tool = DispatchScraper(
            job_type="unknown",
            inputs={}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "low")

    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    def test_initialize_firestore_success(self, mock_client, mock_get_env, mock_exists):
        """Test successful Firestore initialization (lines 164-170)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        db = tool._initialize_firestore()
        self.assertIsNotNone(db)

    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_initialize_firestore_missing_credentials(self, mock_get_env, mock_exists):
        """Test Firestore initialization with missing credentials (lines 167-168)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/missing.json"
        mock_exists.return_value = False

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('orchestrator_agent.tools.dispatch_scraper.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_scraper.firestore.Client')
    def test_initialize_firestore_exception(self, mock_client, mock_get_env, mock_exists):
        """Test Firestore initialization exception handling (lines 172-173)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.side_effect = Exception("Connection failed")

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('orchestrator_agent.tools.dispatch_scraper.get_required_env_var')
    def test_run_exception_handling(self, mock_get_env):
        """Test exception handling in run method (lines 128-132)."""
        mock_get_env.side_effect = Exception("Environment error")

        tool = DispatchScraper(
            job_type="channel_scrape",
            inputs={"channels": ["@Test"]}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("Failed to dispatch scraper job", data["error"])
        self.assertIsNone(data["job_ref"])


if __name__ == "__main__":
    unittest.main()