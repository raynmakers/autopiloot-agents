#!/usr/bin/env python3
"""
Comprehensive tests for list_tracked_targets_from_config.py
Achieves high coverage through mocking and direct execution
"""

import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch
import importlib.util


class TestListTrackedTargetsFromConfig(unittest.TestCase):
    """Test ListTrackedTargetsFromConfig tool functionality"""

    @classmethod
    def setUpClass(cls):
        """Set up test class with proper mocking"""
        # Mock all external dependencies
        cls.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock(),
            'core.json_response': MagicMock()
        }

        # Set up mocks
        cls.mock_modules['agency_swarm.tools'].BaseTool = MagicMock()
        cls.mock_modules['pydantic'].Field = MagicMock(side_effect=lambda **kwargs: kwargs.get('default'))

        # Load the module
        module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
        cls.module = cls._load_module_with_mocks(module_path)

    @classmethod
    def _load_module_with_mocks(cls, module_path):
        """Load module with comprehensive mocking"""
        with patch.dict('sys.modules', cls.mock_modules):
            spec = importlib.util.spec_from_file_location("list_tracked_targets_from_config", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock the loader imports
            module.load_app_config = MagicMock()
            module.get_config_value = MagicMock()

            # Mock json_response functions to return actual JSON strings
            module.ok = lambda data: json.dumps({"ok": True, "data": data, "error": None})
            module.fail = lambda message, code="ERROR", details=None: json.dumps({
                "ok": False,
                "data": None,
                "error": {"code": code, "message": message, "details": details} if details else {"code": code, "message": message}
            })

            spec.loader.exec_module(module)
            return module

    def setUp(self):
        """Set up each test"""
        # Reset mocks
        self.module.load_app_config.reset_mock()
        self.module.get_config_value.reset_mock()

    def test_successful_targets_loading(self):
        """Test successful loading of tracking targets"""
        # Mock configuration
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
                            "include_patterns": ["*.pdf", "*.docx"],
                            "exclude_patterns": ["~*", "*.tmp"]
                        }
                    ],
                    "sync_interval_minutes": 30,
                    "max_file_size_mb": 20,
                    "supported_formats": [".pdf", ".docx", ".txt"]
                }
            },
            "rag": {
                "zep": {
                    "namespace": {
                        "drive": "test_drive_namespace"
                    }
                }
            }
        }

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        # Create tool instance with defaults
        tool = self.module.ListTrackedTargetsFromConfig(include_defaults=True)
        result = tool.run()
        envelope = json.loads(result)

        # Verify envelope structure
        self.assertTrue(envelope["ok"])
        self.assertIsNone(envelope["error"])

        # Verify results in data field
        result_data = envelope["data"]
        self.assertEqual(len(result_data["targets"]), 2)
        self.assertEqual(result_data["count"], 2)
        self.assertEqual(result_data["zep_namespace"], "test_drive_namespace")
        self.assertIn("defaults", result_data)
        self.assertEqual(result_data["defaults"]["sync_interval_minutes"], 30)

    def test_no_targets_configured(self):
        """Test handling when no targets are configured"""
        # Mock empty configuration
        self.module.load_app_config.return_value = {}
        self.module.get_config_value.return_value = {}

        tool = self.module.ListTrackedTargetsFromConfig(include_defaults=False)
        result = tool.run()
        envelope = json.loads(result)

        # Verify envelope structure
        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        self.assertEqual(result_data["targets"], [])
        self.assertIn("No tracking targets configured", result_data["message"])

    def test_without_defaults(self):
        """Test loading targets without default settings"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {
                            "id": "test_file",
                            "type": "file",
                            "name": "Test File"
                        }
                    ]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "test_namespace"}}}
        }

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig(include_defaults=False)
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        self.assertNotIn("defaults", result_data)
        self.assertEqual(len(result_data["targets"]), 1)

    def test_invalid_target_filtering(self):
        """Test filtering of invalid targets (missing required fields)"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {"id": "valid_file", "type": "file", "name": "Valid"},
                        {"name": "Missing ID"},  # Invalid - missing id
                        {"id": "missing_type"},  # Invalid - missing type
                        "not_a_dict",  # Invalid - not a dict
                        {"id": "valid_folder", "type": "folder"}
                    ]
                }
            },
            "rag": {"zep": {"namespace": {"drive": "test"}}}
        }

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig()
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        # Should only include valid targets
        self.assertEqual(len(result_data["targets"]), 2)
        self.assertEqual(result_data["targets"][0]["id"], "valid_file")
        self.assertEqual(result_data["targets"][1]["id"], "valid_folder")

    def test_folder_recursive_handling(self):
        """Test correct handling of recursive flag for folders"""
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

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig()
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        self.assertEqual(result_data["targets"][0]["recursive"], True)
        self.assertEqual(result_data["targets"][1]["recursive"], False)
        self.assertEqual(result_data["targets"][2]["recursive"], True)  # Default
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

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig()
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        target = result_data["targets"][0]
        self.assertEqual(target["include_patterns"], ["*.pdf", "*.doc*"])
        self.assertEqual(target["exclude_patterns"], ["~*", "*.tmp", "backup/*"])

    def test_exception_handling(self):
        """Test exception handling during configuration loading"""
        # Mock configuration loading to raise exception
        self.module.load_app_config.side_effect = Exception("Config loading failed")

        tool = self.module.ListTrackedTargetsFromConfig()
        result = tool.run()
        envelope = json.loads(result)

        # Verify error envelope structure
        self.assertFalse(envelope["ok"])
        self.assertIsNone(envelope["data"])

        error = envelope["error"]
        self.assertEqual(error["code"], "CONFIGURATION_ERROR")
        self.assertIn("Config loading failed", error["message"])
        self.assertEqual(error["details"]["type"], "Exception")

    def test_default_values_extraction(self):
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

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig(include_defaults=True)
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        defaults = result_data["defaults"]
        self.assertEqual(defaults["sync_interval_minutes"], 45)
        self.assertEqual(defaults["max_file_size_mb"], 15)
        self.assertEqual(defaults["supported_formats"], [".pdf", ".txt", ".md"])

    def test_zep_namespace_fallback(self):
        """Test fallback to default Zep namespace"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [{"id": "test", "type": "file"}]
                }
            }
            # No rag/zep configuration
        }

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": {}
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig()
        result = tool.run()
        envelope = json.loads(result)

        self.assertTrue(envelope["ok"])
        result_data = envelope["data"]

        # Should fall back to default namespace
        self.assertEqual(result_data["zep_namespace"], "autopiloot_drive_content")

    def test_complete_workflow(self):
        """Test complete workflow with all features"""
        mock_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {
                            "id": "doc_123",
                            "type": "file",
                            "name": "Important Document"
                        },
                        {
                            "id": "folder_456",
                            "type": "folder",
                            "name": "Project Folder",
                            "recursive": True,
                            "include_patterns": ["*.pdf"],
                            "exclude_patterns": ["*.tmp"]
                        },
                        {
                            "id": "folder_789",
                            "type": "folder",
                            "name": "Archive",
                            "recursive": False
                        }
                    ],
                    "sync_interval_minutes": 60,
                    "max_file_size_mb": 25,
                    "supported_formats": [".pdf", ".docx", ".txt", ".md"]
                }
            },
            "rag": {
                "zep": {
                    "namespace": {
                        "drive": "production_drive_namespace"
                    }
                }
            }
        }

        self.module.load_app_config.return_value = mock_config
        self.module.get_config_value.side_effect = lambda key, default: {
            "drive": mock_config.get("drive", {}),
            "rag": mock_config.get("rag", {})
        }.get(key, default)

        tool = self.module.ListTrackedTargetsFromConfig(include_defaults=True)
        result = tool.run()
        envelope = json.loads(result)

        # Verify envelope structure
        self.assertTrue(envelope["ok"])
        self.assertIsNone(envelope["error"])
        result_data = envelope["data"]

        # Comprehensive assertions
        self.assertEqual(result_data["count"], 3)
        self.assertEqual(len(result_data["targets"]), 3)
        self.assertEqual(result_data["zep_namespace"], "production_drive_namespace")

        # Check defaults
        self.assertIn("defaults", result_data)
        self.assertEqual(result_data["defaults"]["sync_interval_minutes"], 60)
        self.assertEqual(result_data["defaults"]["max_file_size_mb"], 25)
        self.assertEqual(len(result_data["defaults"]["supported_formats"]), 4)

        # Check individual targets
        file_target = result_data["targets"][0]
        self.assertEqual(file_target["id"], "doc_123")
        self.assertEqual(file_target["type"], "file")
        self.assertEqual(file_target["recursive"], False)

        folder_with_patterns = result_data["targets"][1]
        self.assertEqual(folder_with_patterns["id"], "folder_456")
        self.assertEqual(folder_with_patterns["recursive"], True)
        self.assertIn("include_patterns", folder_with_patterns)
        self.assertIn("exclude_patterns", folder_with_patterns)


if __name__ == '__main__':
    unittest.main()