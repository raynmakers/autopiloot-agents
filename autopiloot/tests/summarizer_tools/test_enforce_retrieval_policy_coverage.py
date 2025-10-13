"""
Comprehensive test suite for EnforceRetrievalPolicy tool.
Tests authorization filtering, content redaction, audit logging, and policy enforcement modes.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone, timedelta

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestEnforceRetrievalPolicy(unittest.TestCase):
    """Test suite for EnforceRetrievalPolicy tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'enforce_retrieval_policy.py'
        )
        spec = importlib.util.spec_from_file_location("enforce_retrieval_policy", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.EnforceRetrievalPolicy

        # Sample results for testing
        self.sample_results = {
            "query": "test query",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "video_id": "vid1",
                    "channel_id": "UC_allowed",
                    "text": "Safe business content about strategy.",
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "video_id": "vid2",
                    "channel_id": "UC_blocked",
                    "text": "Content from unauthorized channel.",
                    "rrf_score": 0.85
                }
            ],
            "sources": {"zep": True, "opensearch": True}
        }

    def test_parse_valid_results(self):
        """Test parsing valid results JSON (lines 56-61)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        parsed = tool._parse_results(json.dumps(self.sample_results))

        self.assertEqual(parsed["query"], "test query")
        self.assertEqual(len(parsed["results"]), 2)

    def test_parse_invalid_results(self):
        """Test parsing invalid JSON (lines 56-61)."""
        tool = self.ToolClass(
            results="invalid json"
        )

        with self.assertRaises(ValueError) as context:
            tool._parse_results("invalid json")

        self.assertIn("Invalid JSON", str(context.exception))

    def test_check_channel_authorization_no_restrictions(self):
        """Test channel auth with no restrictions (lines 63-77)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=None
        )

        result = tool._check_channel_authorization("UC_any_channel")

        self.assertTrue(result["authorized"])
        self.assertIn("No channel restrictions", result["reason"])

    def test_check_channel_authorization_allowed(self):
        """Test channel auth for allowed channel (lines 63-77)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed", "UC_another"]
        )

        result = tool._check_channel_authorization("UC_allowed")

        self.assertTrue(result["authorized"])
        self.assertIn("in allowed list", result["reason"])

    def test_check_channel_authorization_blocked(self):
        """Test channel auth for blocked channel (lines 63-77)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed"]
        )

        result = tool._check_channel_authorization("UC_blocked")

        self.assertFalse(result["authorized"])
        self.assertIn("not in allowed list", result["reason"])

    def test_check_date_authorization_no_restrictions(self):
        """Test date auth with no restrictions (lines 79-115)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            max_age_days=None
        )

        result = tool._check_date_authorization("2025-01-01T00:00:00Z")

        self.assertTrue(result["authorized"])
        self.assertIn("No age restrictions", result["reason"])

    def test_check_date_authorization_recent_content(self):
        """Test date auth for recent content (lines 79-115)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            max_age_days=30
        )

        # Create date within last 30 days
        recent_date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        result = tool._check_date_authorization(recent_date)

        self.assertTrue(result["authorized"])
        self.assertIn("within", result["reason"])

    def test_check_date_authorization_old_content(self):
        """Test date auth for old content (lines 79-115)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            max_age_days=30
        )

        # Create date older than 30 days
        old_date = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        result = tool._check_date_authorization(old_date)

        self.assertFalse(result["authorized"])
        self.assertIn("exceeds", result["reason"])

    def test_check_date_authorization_missing_date(self):
        """Test date auth with missing date (lines 79-115)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            max_age_days=30
        )

        result = tool._check_date_authorization(None)

        self.assertFalse(result["authorized"])
        self.assertIn("No publication date", result["reason"])

    def test_detect_sensitive_content_none(self):
        """Test sensitive content detection with clean text (lines 117-156)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool._detect_sensitive_content("This is clean business content.")

        self.assertFalse(result["has_sensitive"])
        self.assertEqual(len(result["patterns_found"]), 0)
        self.assertEqual(result["severity"], "none")

    def test_detect_sensitive_content_email(self):
        """Test sensitive content detection with email (lines 117-156)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool._detect_sensitive_content("Contact me at john.doe@example.com")

        self.assertTrue(result["has_sensitive"])
        self.assertIn("email", result["patterns_found"])
        self.assertIn(result["severity"], ["medium", "high"])

    def test_detect_sensitive_content_phone(self):
        """Test sensitive content detection with phone (lines 117-156)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool._detect_sensitive_content("Call me at 555-123-4567")

        self.assertTrue(result["has_sensitive"])
        self.assertIn("phone", result["patterns_found"])

    def test_detect_sensitive_content_multiple_patterns(self):
        """Test detection of multiple sensitive patterns (lines 117-156)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        text = "Email: test@example.com, Phone: 555-123-4567"
        result = tool._detect_sensitive_content(text)

        self.assertTrue(result["has_sensitive"])
        self.assertGreaterEqual(len(result["patterns_found"]), 2)

    def test_redact_sensitive_content(self):
        """Test content redaction (lines 158-180)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        original = "Contact john.doe@example.com or call 555-123-4567"
        redacted = tool._redact_sensitive_content(original)

        self.assertNotEqual(original, redacted)
        self.assertIn("[EMAIL REDACTED]", redacted)
        self.assertIn("[PHONE REDACTED]", redacted)
        self.assertNotIn("john.doe@example.com", redacted)
        self.assertNotIn("555-123-4567", redacted)

    @patch('importlib.import_module')
    def test_filter_mode_blocks_unauthorized(self, mock_import):
        """Test filter mode removes unauthorized items (lines 182-240, 305-344)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="filter"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["policy_enforcement"]["original_count"], 2)
        self.assertEqual(data["policy_enforcement"]["filtered_count"], 1)
        self.assertEqual(data["policy_enforcement"]["allowed_count"], 1)

        # Verify blocked channel was filtered
        allowed_chunks = [r["chunk_id"] for r in data["results"]]
        self.assertIn("chunk_1", allowed_chunks)
        self.assertNotIn("chunk_2", allowed_chunks)

    @patch('importlib.import_module')
    def test_redact_mode_masks_sensitive_content(self, mock_import):
        """Test redact mode masks sensitive content (lines 246-253)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        # Add email to first result
        results_with_email = self.sample_results.copy()
        results_with_email["results"] = [
            {
                "chunk_id": "chunk_1",
                "video_id": "vid1",
                "channel_id": "UC_allowed",
                "text": "Contact me at john@example.com for details.",
                "rrf_score": 0.95
            }
        ]

        tool = self.ToolClass(
            results=json.dumps(results_with_email),
            allowed_channels=["UC_allowed"],
            enforcement_mode="redact"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["policy_enforcement"]["redacted_count"], 1)

        # Verify content was redacted
        redacted_result = data["results"][0]
        self.assertTrue(redacted_result.get("redacted", False))
        self.assertIn("[EMAIL REDACTED]", redacted_result["text"])
        self.assertNotIn("john@example.com", redacted_result["text"])

    @patch('importlib.import_module')
    def test_audit_only_mode_allows_violations(self, mock_import):
        """Test audit_only mode logs but allows violations (lines 254-260)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="audit_only"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        # All results should be allowed in audit_only mode
        self.assertEqual(data["policy_enforcement"]["allowed_count"], 2)
        self.assertEqual(data["policy_enforcement"]["filtered_count"], 0)

        # But violations should be logged
        violations = [entry for entry in data["audit_trail"] if entry["violations"]]
        self.assertGreater(len(violations), 0)

    @patch('importlib.import_module')
    def test_audit_trail_completeness(self, mock_import):
        """Test audit trail includes all checks (lines 310-320)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="filter"
        )

        result = tool.run()
        data = json.loads(result)

        # Check audit trail structure
        self.assertIn("audit_trail", data)
        self.assertEqual(len(data["audit_trail"]), 2)

        for entry in data["audit_trail"]:
            self.assertIn("chunk_id", entry)
            self.assertIn("action", entry)
            self.assertIn("violations", entry)
            self.assertIn("audit_log", entry)
            self.assertIn("timestamp", entry)

            # Check audit log details
            audit_log = entry["audit_log"]
            self.assertIn("checks_performed", audit_log)
            self.assertGreater(len(audit_log["checks_performed"]), 0)

    @patch('importlib.import_module')
    def test_no_violations_allows_all(self, mock_import):
        """Test that content with no violations is allowed (lines 232-240)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        # Create clean results
        clean_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "video_id": "vid1",
                    "channel_id": "UC_allowed",
                    "text": "Clean business content.",
                    "rrf_score": 0.95
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(clean_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="filter"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["policy_enforcement"]["filtered_count"], 0)
        self.assertEqual(data["policy_enforcement"]["allowed_count"], 1)

    @patch('importlib.import_module')
    def test_policy_configuration_in_response(self, mock_import):
        """Test policy configuration included in response (lines 356-361)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            allowed_channels=["UC_allowed"],
            max_age_days=30,
            user_id="test_user"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("policy_configuration", data)
        self.assertEqual(data["policy_configuration"]["allowed_channels"], ["UC_allowed"])
        self.assertEqual(data["policy_configuration"]["max_age_days"], 30)
        self.assertEqual(data["policy_configuration"]["user_id"], "test_user")

    @patch('importlib.import_module')
    def test_original_metadata_preserved(self, mock_import):
        """Test original metadata is preserved (lines 347-351)."""
        # Mock loader
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(return_value=[])
        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            enforcement_mode="filter"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("original_metadata", data)
        self.assertEqual(data["original_metadata"]["sources"], self.sample_results["sources"])

    @patch('importlib.import_module')
    def test_exception_handling(self, mock_import):
        """Test exception handling (lines 363-368)."""
        # Mock loader to raise exception
        mock_import.side_effect = Exception("Test exception")

        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "policy_enforcement_failed")
        self.assertIn("Test exception", data["message"])

    def test_apply_policy_with_date_filter(self):
        """Test policy application with date filtering (lines 182-260)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            max_age_days=30
        )

        # Create result with old date
        old_result = {
            "chunk_id": "chunk_old",
            "video_id": "vid_old",
            "channel_id": "UC_test",
            "text": "Old content",
            "published_at": "2020-01-01T00:00:00Z"
        }

        policy_decision = tool._apply_policy_to_result(old_result)

        # Should have date violation
        violations = [v for v in policy_decision["violations"] if v["type"] == "content_too_old"]
        self.assertGreater(len(violations), 0)


if __name__ == '__main__':
    unittest.main()
