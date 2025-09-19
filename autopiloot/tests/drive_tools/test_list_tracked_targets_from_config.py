"""
Test suite for ListTrackedTargetsFromConfig tool.
Tests configuration loading and Drive target normalization.
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Mock environment and dependencies before importing
with patch.dict('sys.modules', {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
}):
    # Mock the BaseTool and Field
    from unittest.mock import MagicMock
    mock_base_tool = MagicMock()
    mock_field = MagicMock()

    with patch('drive_agent.tools.list_tracked_targets_from_config.BaseTool', mock_base_tool):
        with patch('drive_agent.tools.list_tracked_targets_from_config.Field', mock_field):
            from drive_agent.tools.list_tracked_targets_from_config import ListTrackedTargetsFromConfig


class TestListTrackedTargetsFromConfig(unittest.TestCase):
    """Test cases for ListTrackedTargetsFromConfig tool."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            "drive_agent": {
                "targets": [
                    {
                        "id": "folder_strategy_docs",
                        "type": "folder",
                        "name": "Strategy Documents",
                        "include_patterns": ["*.pdf", "*.docx"],
                        "exclude_patterns": ["**/archive/**"]
                    },
                    {
                        "id": "file_master_doc",
                        "type": "file",
                        "name": "Master Document",
                        "include_patterns": ["*"],
                        "exclude_patterns": []
                    }
                ],
                "zep": {
                    "namespace": "autopiloot_drive_content"
                }
            }
        }

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_successful_target_loading(self, mock_load_config, mock_load_env):
        """Test successful configuration loading and target normalization."""
        mock_load_config.return_value = self.mock_config

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["target_count"], 2)
        self.assertEqual(result["zep_namespace"], "autopiloot_drive_content")
        self.assertEqual(len(result["targets"]), 2)

        # Check folder target normalization
        folder_target = result["targets"][0]
        self.assertEqual(folder_target["id"], "folder_strategy_docs")
        self.assertEqual(folder_target["type"], "folder")
        self.assertEqual(len(folder_target["include_patterns"]), 2)

        # Check file target normalization
        file_target = result["targets"][1]
        self.assertEqual(file_target["id"], "file_master_doc")
        self.assertEqual(file_target["type"], "file")

        mock_load_env.assert_called_once()
        mock_load_config.assert_called_once()

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_missing_drive_agent_config(self, mock_load_config, mock_load_env):
        """Test handling of missing drive_agent configuration."""
        mock_load_config.return_value = {}

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "config_missing")
        self.assertIn("drive_agent configuration not found", result["message"])

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_empty_targets_list(self, mock_load_config, mock_load_env):
        """Test handling of empty targets list."""
        config = {"drive_agent": {"targets": [], "zep": {"namespace": "test"}}}
        mock_load_config.return_value = config

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["target_count"], 0)
        self.assertEqual(len(result["targets"]), 0)

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_missing_zep_namespace(self, mock_load_config, mock_load_env):
        """Test handling of missing Zep namespace configuration."""
        config = {"drive_agent": {"targets": []}}
        mock_load_config.return_value = config

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "config_invalid")
        self.assertIn("Zep namespace not configured", result["message"])

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_target_validation_missing_fields(self, mock_load_config, mock_load_env):
        """Test validation of targets with missing required fields."""
        config = {
            "drive_agent": {
                "targets": [
                    {"id": "missing_type", "name": "Test"},  # Missing type
                    {"type": "folder", "name": "Test"}       # Missing id
                ],
                "zep": {"namespace": "test"}
            }
        }
        mock_load_config.return_value = config

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "loaded")
        self.assertEqual(result["target_count"], 0)  # Invalid targets filtered out
        self.assertGreater(len(result["validation_warnings"]), 0)

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_pattern_normalization(self, mock_load_config, mock_load_env):
        """Test pattern normalization for include/exclude patterns."""
        config = {
            "drive_agent": {
                "targets": [
                    {
                        "id": "test_folder",
                        "type": "folder",
                        "name": "Test Folder",
                        "include_patterns": "*.pdf",  # String instead of list
                        "exclude_patterns": None      # None instead of list
                    }
                ],
                "zep": {"namespace": "test"}
            }
        }
        mock_load_config.return_value = config

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["status"], "loaded")
        target = result["targets"][0]
        self.assertEqual(target["include_patterns"], ["*.pdf"])  # Normalized to list
        self.assertEqual(target["exclude_patterns"], [])        # Normalized to empty list

    @patch('drive_agent.tools.list_tracked_targets_from_config.load_environment')
    @patch('drive_agent.tools.list_tracked_targets_from_config.load_app_config')
    def test_configuration_exception_handling(self, mock_load_config, mock_load_env):
        """Test handling of configuration loading exceptions."""
        mock_load_config.side_effect = Exception("Config file not found")

        tool = ListTrackedTargetsFromConfig()
        result_str = tool.run()
        result = json.loads(result_str)

        self.assertEqual(result["error"], "config_load_failed")
        self.assertIn("Failed to load Drive targets configuration", result["message"])


if __name__ == '__main__':
    unittest.main()