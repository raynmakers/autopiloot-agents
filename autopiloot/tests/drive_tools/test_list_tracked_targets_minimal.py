#!/usr/bin/env python3
"""
Minimal working tests for list_tracked_targets_from_config.py
Completely avoiding MagicMock to prevent JSON serialization issues
"""

import unittest
import json
import sys
import os
from unittest.mock import patch
import importlib.util


class TestListTrackedTargetsMinimal(unittest.TestCase):
    """Minimal tests to achieve actual code coverage"""

    def test_successful_targets_loading(self):
        """Test successful loading of targets from configuration"""

        # Create test configuration
        test_config = {
            "drive": {
                "tracking": {
                    "targets": [
                        {"id": "file_123", "type": "file", "name": "Test Document.pdf"},
                        {"id": "folder_456", "type": "folder", "name": "Test Folder", "recursive": True}
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

        # Create loader module with functions
        loader_module = type('Module', (), {})
        loader_module.load_app_config = lambda: test_config
        loader_module.get_config_value = lambda key, default=None: test_config.get(key, default)

        # Create mock modules with plain objects
        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'loader': loader_module
        }

        # Create simple base tool class
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        # Mock Field function
        def mock_field(**kwargs):
            return kwargs.get('default', True)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = mock_field

        with patch.dict('sys.modules', mock_modules):
            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)


            # Execute module
            spec.loader.exec_module(module)

            # Create and run tool
            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True

            result = tool.run()

            # Verify result
            self.assertIsInstance(result, str)
            result_data = json.loads(result)

            # Check structure
            self.assertIn("targets", result_data)
            self.assertIn("count", result_data)
            self.assertEqual(len(result_data["targets"]), 2)
            self.assertEqual(result_data["targets"][0]["id"], "file_123")
            self.assertEqual(result_data["targets"][1]["id"], "folder_456")

    def test_no_targets_configured(self):
        """Test when no targets are configured"""

        # Empty configuration
        empty_config = {}

        # Create loader module with functions
        loader_module = type('Module', (), {})
        loader_module.load_app_config = lambda: empty_config
        loader_module.get_config_value = lambda key, default=None: empty_config.get(key, default)

        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'loader': loader_module
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        def mock_field(**kwargs):
            return kwargs.get('default', False)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = mock_field

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)


            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["targets"], [])
            self.assertIn("No tracking targets configured", result_data["message"])

    def test_invalid_target_filtering(self):
        """Test filtering of invalid targets"""

        # Configuration with invalid targets
        config = {
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

        # Create loader module with functions
        loader_module = type('Module', (), {})
        loader_module.load_app_config = lambda: config
        loader_module.get_config_value = lambda key, default=None: config.get(key, default)

        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'loader': loader_module
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)


            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True

            result = tool.run()
            result_data = json.loads(result)

            # Should only include valid targets
            self.assertEqual(len(result_data["targets"]), 2)
            self.assertEqual(result_data["targets"][0]["id"], "valid_file")
            self.assertEqual(result_data["targets"][1]["id"], "valid_folder")

    def test_exception_handling(self):
        """Test exception handling during configuration loading"""

        # Create loader module that raises exception
        loader_module = type('Module', (), {})

        def load_app_config():
            raise Exception("Config loading failed")

        def get_config_value(key, default=None):
            return default

        loader_module.load_app_config = load_app_config
        loader_module.get_config_value = get_config_value

        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'loader': loader_module
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)


            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = True

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "configuration_error")
            self.assertIn("Config loading failed", result_data["message"])

    def test_pattern_preservation(self):
        """Test that include/exclude patterns are preserved correctly"""

        # Configuration with patterns
        config = {
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

        # Create loader module with functions
        loader_module = type('Module', (), {})
        loader_module.load_app_config = lambda: config
        loader_module.get_config_value = lambda key, default=None: config.get(key, default)

        mock_modules = {
            'agency_swarm': type('Module', (), {}),
            'agency_swarm.tools': type('Module', (), {}),
            'pydantic': type('Module', (), {}),
            'loader': loader_module
        }

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool
        mock_modules['pydantic'].Field = lambda **kwargs: kwargs.get('default', True)

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/list_tracked_targets_from_config.py"
            spec = importlib.util.spec_from_file_location("list_tracked_targets", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.ListTrackedTargetsFromConfig()
            tool.include_defaults = False

            result = tool.run()
            result_data = json.loads(result)

            target = result_data["targets"][0]
            self.assertEqual(target["include_patterns"], ["*.pdf", "*.doc*"])
            self.assertEqual(target["exclude_patterns"], ["~*", "*.tmp", "backup/*"])


if __name__ == '__main__':
    unittest.main()