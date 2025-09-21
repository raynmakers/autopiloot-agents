#!/usr/bin/env python3
"""
Working tests for list_tracked_targets_from_config.py
Focused on achieving actual code coverage through proper mocking
"""

import unittest
import json
import sys
import os
from unittest.mock import MagicMock, patch
import importlib.util


class TestListTrackedTargetsWorking(unittest.TestCase):
    """Working tests for ListTrackedTargetsFromConfig tool"""

    def test_successful_targets_loading_with_defaults(self):
        """Test successful loading with include_defaults=True"""
        # Mock all dependencies properly
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            # Mock BaseTool and Field properly
            base_tool = MagicMock()
            sys.modules['agency_swarm.tools'].BaseTool = base_tool
            sys.modules['pydantic'].Field = MagicMock(return_value=True)  # Simple return value

            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock the config functions BEFORE loading
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

            # Mock functions
            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": mock_config.get("rag", {})
            }.get(key, default))

            # Execute module
            spec.loader.exec_module(module)

            # Create tool instance
            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True

            # Run the tool
            result = tool.run()

            # Parse and verify result
            self.assertIsInstance(result, str)
            result_data = json.loads(result)

            self.assertEqual(len(result_data["targets"]), 2)
            self.assertEqual(result_data["count"], 2)
            self.assertEqual(result_data["zep_namespace"], "test_namespace")
            self.assertIn("defaults", result_data)
            self.assertEqual(result_data["defaults"]["sync_interval_minutes"], 30)

    def test_no_targets_configured(self):
        """Test when no targets are configured"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=False)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock empty config
            module.load_app_config = MagicMock(return_value={})
            module.get_config_value = MagicMock(return_value={})

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False
            result = tool.run()

            result_data = json.loads(result)
            self.assertEqual(result_data["targets"], [])
            self.assertIn("No tracking targets configured", result_data["message"])

    def test_invalid_target_filtering(self):
        """Test filtering of invalid targets"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock config with invalid targets
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

            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": mock_config.get("rag", {})
            }.get(key, default))

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True
            result = tool.run()

            result_data = json.loads(result)
            # Should only include valid targets
            self.assertEqual(len(result_data["targets"]), 2)
            self.assertEqual(result_data["targets"][0]["id"], "valid_file")
            self.assertEqual(result_data["targets"][1]["id"], "valid_folder")

    def test_folder_recursive_defaults(self):
        """Test correct handling of recursive flag for folders vs files"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

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

            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": mock_config.get("rag", {})
            }.get(key, default))

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False
            result = tool.run()

            result_data = json.loads(result)
            self.assertEqual(result_data["targets"][0]["recursive"], True)
            self.assertEqual(result_data["targets"][1]["recursive"], False)
            self.assertEqual(result_data["targets"][2]["recursive"], True)  # Default for folder
            self.assertEqual(result_data["targets"][3]["recursive"], False)  # Files never recursive

    def test_pattern_preservation(self):
        """Test that include/exclude patterns are preserved correctly"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

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

            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": mock_config.get("rag", {})
            }.get(key, default))

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False
            result = tool.run()

            result_data = json.loads(result)
            target = result_data["targets"][0]
            self.assertEqual(target["include_patterns"], ["*.pdf", "*.doc*"])
            self.assertEqual(target["exclude_patterns"], ["~*", "*.tmp", "backup/*"])

    def test_exception_handling(self):
        """Test exception handling during configuration loading"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            # Mock exception
            module.load_app_config = MagicMock(side_effect=Exception("Config loading failed"))
            module.get_config_value = MagicMock()

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True
            result = tool.run()

            result_data = json.loads(result)
            self.assertEqual(result_data["error"], "configuration_error")
            self.assertIn("Config loading failed", result_data["message"])
            self.assertEqual(result_data["details"]["type"], "Exception")

    def test_zep_namespace_fallback(self):
        """Test fallback to default Zep namespace when not configured"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            mock_config = {
                "drive": {
                    "tracking": {
                        "targets": [{"id": "test", "type": "file"}]
                    }
                }
                # No rag/zep configuration
            }

            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": {}
            }.get(key, default))

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False
            result = tool.run()

            result_data = json.loads(result)
            # Should fall back to default namespace
            self.assertEqual(result_data["zep_namespace"], "autopiloot_drive_content")

    def test_defaults_extraction(self):
        """Test extraction of default values from configuration"""
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'loader': MagicMock()
        }):
            sys.modules['agency_swarm.tools'].BaseTool = MagicMock()
            sys.modules['pydantic'].Field = MagicMock(return_value=True)

            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

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

            module.load_app_config = MagicMock(return_value=mock_config)
            module.get_config_value = MagicMock(side_effect=lambda key, default: {
                "drive": mock_config.get("drive", {}),
                "rag": mock_config.get("rag", {})
            }.get(key, default))

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True
            result = tool.run()

            result_data = json.loads(result)
            defaults = result_data["defaults"]
            self.assertEqual(defaults["sync_interval_minutes"], 45)
            self.assertEqual(defaults["max_file_size_mb"], 15)
            self.assertEqual(defaults["supported_formats"], [".pdf", ".txt", ".md"])


if __name__ == '__main__':
    unittest.main()