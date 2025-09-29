"""
Comprehensive test suite for DispatchSummarizer tool targeting 100% coverage.
Tests job dispatch, LLM configuration, platform targeting, and validation.
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
from orchestrator_agent.tools.dispatch_summarizer import DispatchSummarizer

# Patch DispatchSummarizer __init__ to accept kwargs
def patched_init(self, **kwargs):
    self.job_type = kwargs.get('job_type')
    self.inputs = kwargs.get('inputs', {})
    self.policy_overrides = kwargs.get('policy_overrides', None)

DispatchSummarizer.__init__ = patched_init


class TestDispatchSummarizer100Coverage(unittest.TestCase):
    """Test suite targeting 100% coverage for DispatchSummarizer."""

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

    @patch('orchestrator_agent.tools.dispatch_summarizer.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_summarizer.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_successful_single_summary_dispatch(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test successful single_summary job dispatch (lines 61-142)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {
            "llm": {
                "default": {
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "max_output_tokens": 1500
                }
            }
        }

        # Mock no existing job
        mock_existing_job = MagicMock()
        mock_existing_job.exists = False
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={
                "video_id": "test_video_123",
                "platforms": ["drive", "zep"]
            },
            policy_overrides={"temperature": 0.3}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "dispatched")
        self.assertEqual(data["job_type"], "single_summary")
        self.assertIn("job_id", data)
        self.assertIn("llm_model", data)
        self.assertEqual(data["target_platforms"], ["drive", "zep"])

    @patch('orchestrator_agent.tools.dispatch_summarizer.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_summarizer.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_successful_batch_summarize_dispatch(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test successful batch_summarize job dispatch (lines 116-119)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {
            "llm": {
                "default": {"model": "gpt-4o", "temperature": 0.2, "max_output_tokens": 1500}
            }
        }

        mock_existing_job = MagicMock()
        mock_existing_job.exists = False
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={
                "video_ids": ["vid1", "vid2", "vid3"]
            }
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "dispatched")
        self.assertEqual(data["estimated_videos"], 3)

        # Verify batch-specific metadata
        call_args = self.mock_doc_ref.set.call_args
        payload = call_args[0][0]
        self.assertEqual(payload["video_ids"], ["vid1", "vid2", "vid3"])
        self.assertEqual(payload["batch_size"], 3)

    @patch('orchestrator_agent.tools.dispatch_summarizer.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_summarizer.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_prerequisites_not_met(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test prerequisites check failure (lines 70-75)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {"llm": {"default": {}}}

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test_video"}
        )

        # Override _check_prerequisites to return False
        tool._check_prerequisites = lambda: {
            "satisfied": False,
            "reason": "Video not transcribed"
        }

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("Prerequisites not met", data["error"])
        self.assertIsNone(data["job_ref"])

    @patch('orchestrator_agent.tools.dispatch_summarizer.audit_logger')
    @patch('orchestrator_agent.tools.dispatch_summarizer.load_app_config')
    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_existing_job_detection(self, mock_client, mock_get_env, mock_exists, mock_config, mock_audit):
        """Test detection of existing job (lines 87-92)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db
        mock_config.return_value = {"llm": {"default": {}}}

        mock_existing_job = MagicMock()
        mock_existing_job.exists = True
        self.mock_doc_ref.get.return_value = mock_existing_job

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test_video"}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "already_exists")
        self.assertIn("Job already dispatched", data["message"])

    def test_validate_single_summary_missing_video_id(self):
        """Test validation for missing video_id (lines 153-154)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("requires 'video_id'", str(context.exception))

    def test_validate_single_summary_video_id_not_string(self):
        """Test validation for video_id not a string (lines 155-156)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": 12345}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("must be a string", str(context.exception))

    def test_validate_platforms_not_list(self):
        """Test validation for platforms not a list (lines 162-163)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test", "platforms": "not_a_list"}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("must be a list", str(context.exception))

    def test_validate_invalid_platform(self):
        """Test validation for invalid platform (lines 165-166)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test", "platforms": ["drive", "invalid"]}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Invalid platform", str(context.exception))

    def test_validate_batch_summarize_missing_video_ids(self):
        """Test validation for missing video_ids (lines 169-170)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("requires 'video_ids'", str(context.exception))

    def test_validate_batch_summarize_video_ids_not_list(self):
        """Test validation for video_ids not a list (lines 171-172)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={"video_ids": "not_a_list"}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("must be a list", str(context.exception))

    def test_validate_batch_summarize_empty_video_ids(self):
        """Test validation for empty video_ids list (lines 173-174)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={"video_ids": []}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("cannot be empty", str(context.exception))

    def test_validate_invalid_job_type(self):
        """Test validation for invalid job type (lines 176-177)."""
        tool = DispatchSummarizer(
            job_type="invalid_type",
            inputs={}
        )

        with self.assertRaises(ValueError) as context:
            tool._validate_inputs()
        self.assertIn("Invalid job_type", str(context.exception))

    def test_check_prerequisites_single_summary(self):
        """Test prerequisites check for single_summary (lines 184-192)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test_video"}
        )

        result = tool._check_prerequisites()

        self.assertTrue(result["satisfied"])
        self.assertEqual(result["video_id"], "test_video")

    def test_check_prerequisites_batch_summarize(self):
        """Test prerequisites check for batch_summarize (lines 193-201)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={"video_ids": ["vid1", "vid2"]}
        )

        result = tool._check_prerequisites()

        self.assertTrue(result["satisfied"])
        self.assertEqual(result["video_count"], 2)

    def test_check_prerequisites_unknown_type(self):
        """Test prerequisites check for unknown type (lines 203-206)."""
        tool = DispatchSummarizer(
            job_type="unknown",
            inputs={}
        )

        result = tool._check_prerequisites()

        self.assertFalse(result["satisfied"])
        self.assertEqual(result["reason"], "Unknown job type")

    def test_build_llm_config_defaults(self):
        """Test LLM config with defaults (lines 211-216)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        config = {
            "llm": {
                "default": {
                    "model": "gpt-4o",
                    "temperature": 0.2,
                    "max_output_tokens": 1500
                }
            }
        }

        llm_config = tool._build_llm_config(config)

        self.assertEqual(llm_config["model"], "gpt-4o")
        self.assertEqual(llm_config["temperature"], 0.2)
        self.assertEqual(llm_config["max_tokens"], 1500)

    def test_build_llm_config_task_specific(self):
        """Test LLM config with task-specific overrides (lines 220-227)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        config = {
            "llm": {
                "default": {"model": "gpt-4o", "temperature": 0.2, "max_output_tokens": 1500},
                "tasks": {
                    "summarizer_generate_short": {
                        "model": "gpt-4.1",
                        "temperature": 0.3,
                        "prompt_id": "coach_v2",
                        "max_output_tokens": 2000
                    }
                }
            }
        }

        llm_config = tool._build_llm_config(config)

        self.assertEqual(llm_config["model"], "gpt-4.1")
        self.assertEqual(llm_config["temperature"], 0.3)
        self.assertEqual(llm_config["prompt_id"], "coach_v2")
        self.assertEqual(llm_config["max_tokens"], 2000)

    def test_build_llm_config_policy_overrides(self):
        """Test LLM config with policy overrides (lines 230-236)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"},
            policy_overrides={
                "prompt_id": "custom_prompt",
                "temperature": 0.5,
                "max_tokens": 3000
            }
        )

        config = {"llm": {"default": {"model": "gpt-4o", "temperature": 0.2, "max_output_tokens": 1500}}}

        llm_config = tool._build_llm_config(config)

        self.assertEqual(llm_config["prompt_id"], "custom_prompt")
        self.assertEqual(llm_config["temperature"], 0.5)
        self.assertEqual(llm_config["max_tokens"], 3000)

    def test_build_llm_config_input_prompt_override(self):
        """Test LLM config with input prompt_override (lines 239-240)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={"video_ids": ["vid1"], "prompt_override": "batch_v1"}
        )

        config = {"llm": {"default": {"model": "gpt-4o", "temperature": 0.2, "max_output_tokens": 1500}}}

        llm_config = tool._build_llm_config(config)

        self.assertEqual(llm_config["prompt_id"], "batch_v1")

    def test_calculate_priority_single_summary(self):
        """Test priority calculation for single_summary (lines 246-247)."""
        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "medium")

    def test_calculate_priority_batch_summarize(self):
        """Test priority calculation for batch_summarize (lines 248-249)."""
        tool = DispatchSummarizer(
            job_type="batch_summarize",
            inputs={"video_ids": ["vid1"]}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "low")

    def test_calculate_priority_unknown_type(self):
        """Test priority calculation for unknown type (line 250)."""
        tool = DispatchSummarizer(
            job_type="unknown",
            inputs={}
        )

        priority = tool._calculate_priority()
        self.assertEqual(priority, "low")

    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_initialize_firestore_success(self, mock_client, mock_get_env, mock_exists):
        """Test successful Firestore initialization (lines 255-261)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.return_value = self.mock_db

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        db = tool._initialize_firestore()
        self.assertIsNotNone(db)

    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_initialize_firestore_missing_credentials(self, mock_get_env, mock_exists):
        """Test Firestore initialization with missing credentials (lines 258-259)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/missing.json"
        mock_exists.return_value = False

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('orchestrator_agent.tools.dispatch_summarizer.os.path.exists')
    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    @patch('orchestrator_agent.tools.dispatch_summarizer.firestore.Client')
    def test_initialize_firestore_exception(self, mock_client, mock_get_env, mock_exists):
        """Test Firestore initialization exception handling (lines 263-264)."""
        mock_get_env.side_effect = lambda key, desc: "/path/to/credentials.json"
        mock_exists.return_value = True
        mock_client.side_effect = Exception("Connection failed")

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        with self.assertRaises(RuntimeError) as context:
            tool._initialize_firestore()
        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('orchestrator_agent.tools.dispatch_summarizer.get_required_env_var')
    def test_run_exception_handling(self, mock_get_env):
        """Test exception handling in run method (lines 144-148)."""
        mock_get_env.side_effect = Exception("Environment error")

        tool = DispatchSummarizer(
            job_type="single_summary",
            inputs={"video_id": "test"}
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertIn("Failed to dispatch summarizer job", data["error"])
        self.assertIsNone(data["job_ref"])


if __name__ == "__main__":
    unittest.main()