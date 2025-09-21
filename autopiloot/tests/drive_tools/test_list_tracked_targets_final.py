#!/usr/bin/env python3
"""
Final working tests for list_tracked_targets_from_config.py
Direct execution approach to achieve actual code coverage
"""

import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch, Mock
import importlib.util


class TestListTrackedTargetsFromConfigFinal(unittest.TestCase):
    """Final working tests for ListTrackedTargetsFromConfig tool"""

    def _load_and_test_tool(self, mock_config, include_defaults=True):
        """Helper method to load tool and execute with mocking"""

        # Create minimal BaseTool implementation
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        # Set up comprehensive mocking
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            # Configure mocks
            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

            # Load module dynamically
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock the config loading functions BEFORE executing module - ensure no MagicMock objects
            def mock_load_app_config():
                return mock_config

            def mock_get_config_value(key, default=None):
                config_map = {
                    "drive": mock_config.get("drive", {}),
                    "rag": mock_config.get("rag", {})
                }
                return config_map.get(key, default)

            module.load_app_config = mock_load_app_config
            module.get_config_value = mock_get_config_value

            # Execute the module to define the class
            spec.loader.exec_module(module)

            # Create and run tool
            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = include_defaults

            return tool.run()

    def test_successful_targets_loading_with_defaults(self):
        """Test successful loading with include_defaults=True"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {
                            "id": "file_123",
                            "type": "file",
                            "name": "Test Document.pdf"
                        },
                        {
                            "id": "folder_456",
                            "type": "folder",
                            "name": "Test Folder",
                            "recursive": True,
                            "include_patterns": ["*.pdf"],
                            "exclude_patterns": ["*.tmp"]
                        }
                    ],
                    "sync_interval_minutes": 30,
                    "max_file_size_mb": 20,
                    "supported_formats": [".pdf", ".docx"]
                }
            },
            "rag": {
                "zep": {
                    "namespace": {
                        "drive": "test_namespace"
                    }
                }
            }
        }

        result = self._load_and_test_tool(mock_config, include_defaults=True)

        # Debug: Print result to understand what we're getting
        print(f"DEBUG: Result type: {type(result)}")
        print(f"DEBUG: Result content: {result}")

        # For debugging, check if it's an error result
        if '"error"' in result:
            print("DEBUG: Got error result, not a successful test")

        # Verify result is string and parse JSON
        self.assertIsInstance(result, str)
        result_data = json.loads(result)

        # Verify structure and content
        self.assertEqual(len(result_data["targets"]), 2)
        self.assertEqual(result_data["count"], 2)
        self.assertEqual(result_data["zep_namespace"], "test_namespace")
        self.assertIn("defaults", result_data)
        self.assertEqual(result_data["defaults"]["sync_interval_minutes"], 30)

    def test_no_targets_configured(self):
        """Test when no targets are configured"""
        mock_config = {}

        result = self._load_and_test_tool(mock_config, include_defaults=False)

        result_data = json.loads(result)
        self.assertEqual(result_data["targets"], [])
        self.assertIn("No tracking targets configured", result_data["message"])

    def test_invalid_target_filtering(self):
        """Test filtering of invalid targets"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {"id": "valid_file", "type": "file", "name": "Valid"},
                        {"name": "Missing ID"},  # Invalid
                        {"id": "missing_type"},  # Invalid
                        "not_a_dict",  # Invalid
                        {"id": "valid_folder", "type": "folder"}
                    ]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "test"}}}
        }

        result = self._load_and_test_tool(mock_config, include_defaults=True)

        result_data = json.loads(result)
        # Should only include valid targets
        self.assertEqual(len(result_data["targets"]), 2)
        self.assertEqual(result_data["targets"][0]["id"], "valid_file")
        self.assertEqual(result_data["targets"][1]["id"], "valid_folder")

    def test_folder_recursive_defaults(self):
        """Test correct handling of recursive flag for folders vs files"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {"id": "folder1", "type": "folder", "recursive": True},
                        {"id": "folder2", "type": "folder", "recursive": False},
                        {"id": "folder3", "type": "folder"},  # Should default to True
                        {"id": "file1", "type": "file", "recursive": True}  # Should be False for files
                    ]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "test"}}}
        }

        result = self._load_and_test_tool(mock_config, include_defaults=False)

        result_data = json.loads(result)
        self.assertEqual(result_data["targets"][0]["recursive"], True)
        self.assertEqual(result_data["targets"][1]["recursive"], False)
        self.assertEqual(result_data["targets"][2]["recursive"], True)  # Default for folder
        self.assertEqual(result_data["targets"][3]["recursive"], False)  # Files never recursive

    def test_pattern_preservation(self):
        """Test that include/exclude patterns are preserved correctly"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {
                            "id": "folder1",
                            "type": "folder",
                            "include_patterns": ["*.pdf", "*.doc*"],
                            "exclude_patterns": ["~*", "*.tmp", "backup/*"]
                        }
                    ]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "test"}}}
        }

        result = self._load_and_test_tool(mock_config, include_defaults=False)

        result_data = json.loads(result)
        target = result_data["targets"][0]
        self.assertEqual(target["include_patterns"], ["*.pdf", "*.doc*"])
        self.assertEqual(target["exclude_patterns"], ["~*", "*.tmp", "backup/*"])

    def test_zep_namespace_fallback(self):
        """Test fallback to default Zep namespace when not configured"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [{"id": "test", "type": "file"}]
                }
            }
            # No rag/zep configuration
        }

        result = self._load_and_test_tool(mock_config, include_defaults=False)

        result_data = json.loads(result)
        # Should fall back to default namespace
        self.assertEqual(result_data["zep_namespace"], "autopiloot_drive_content")

    def test_defaults_extraction(self):
        """Test extraction of default values from configuration"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [{"id": "test", "type": "file"}],
                    "sync_interval_minutes": 45,
                    "max_file_size_mb": 15,
                    "supported_formats": [".pdf", ".txt", ".md"]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "custom_namespace"}}}
        }

        result = self._load_and_test_tool(mock_config, include_defaults=True)

        result_data = json.loads(result)
        defaults = result_data["defaults"]
        self.assertEqual(defaults["sync_interval_minutes"], 45)
        self.assertEqual(defaults["max_file_size_mb"], 15)
        self.assertEqual(defaults["supported_formats"], [".pdf", ".txt", ".md"])

    def test_exception_handling(self):
        """Test exception handling during configuration loading"""
        # Create minimal BaseTool implementation
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock exception
            def mock_load_app_config():
                raise Exception("Config loading failed")

            def mock_get_config_value(key, default=None):
                return default

            module.load_app_config = mock_load_app_config
            module.get_config_value = mock_get_config_value

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True
            result = tool.run()

            result_data = json.loads(result)
            self.assertEqual(result_data["error"], "configuration_error")
            self.assertIn("Config loading failed", result_data["message"])
            self.assertEqual(result_data["details"]["type"], "Exception")


if __name__ == '__main__':
    unittest.main()