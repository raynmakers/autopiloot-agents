#!/usr/bin/env python3
"""
Working coverage test for list_tracked_targets_from_config.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util


class TestListTrackedTargetsFromConfigCoverageWorking(unittest.TestCase):
    """Working tests for ListTrackedTargetsFromConfig tool that properly measure coverage"""

    def _setup_mocks_and_import(self):
        """Set up mocks and import the real module for coverage measurement"""

        # Create Agency Swarm mocks
        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool

        # Create pydantic mock
        pydantic_module = type('Module', (), {})
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)
        pydantic_module.Field = mock_field

        # Create config loader mock
        loader_module = type('Module', (), {})

        def mock_load_app_config():
            return {
                "drive": {
                    "tracking": {
                        "targets": [
                            {
                                "id": "1ABC123def456",
                                "type": "folder",
                                "name": "Test Folder",
                                "sync_interval": "daily",
                                "max_file_size": "50MB"
                            },
                            {
                                "id": "2DEF456ghi789",
                                "type": "file",
                                "name": "Test Document.pdf",
                                "sync_interval": "hourly"
                            }
                        ],
                        "defaults": {
                            "sync_interval": "daily",
                            "max_file_size": "100MB",
                            "include_subfolders": True
                        }
                    }
                }
            }

        def mock_get_config_value(key, default=None):
            config = mock_load_app_config()
            if key == "drive":
                return config.get("drive", default)
            return default

        loader_module.load_app_config = mock_load_app_config
        loader_module.get_config_value = mock_get_config_value

        # Apply all mocks to sys.modules
        sys.modules['agency_swarm'] = agency_swarm_module
        sys.modules['agency_swarm.tools'] = agency_swarm_tools_module
        sys.modules['pydantic'] = pydantic_module
        sys.modules['loader'] = loader_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'list_tracked_targets_from_config.py')
        spec = importlib.util.spec_from_file_location("list_tracked_targets_from_config", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.ListTrackedTargetsFromConfig

    def test_successful_target_listing_with_defaults(self):
        """Test successful target listing with default settings included"""
        ListTrackedTargetsFromConfig = self._setup_mocks_and_import()

        # Create tool with defaults
        tool = ListTrackedTargetsFromConfig(include_defaults=True)

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('targets', result_data)
        self.assertIn('count', result_data)
        self.assertEqual(len(result_data['targets']), 2)
        self.assertEqual(result_data['count'], 2)

        # Check first target (folder)
        folder_target = result_data['targets'][0]
        self.assertEqual(folder_target['id'], '1ABC123def456')
        self.assertEqual(folder_target['type'], 'folder')
        self.assertEqual(folder_target['name'], 'Test Folder')

        # Check second target (file)
        file_target = result_data['targets'][1]
        self.assertEqual(file_target['id'], '2DEF456ghi789')
        self.assertEqual(file_target['type'], 'file')
        self.assertEqual(file_target['name'], 'Test Document.pdf')

    def test_successful_target_listing_without_defaults(self):
        """Test successful target listing without default settings"""
        ListTrackedTargetsFromConfig = self._setup_mocks_and_import()

        # Create tool without defaults
        tool = ListTrackedTargetsFromConfig(include_defaults=False)

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('targets', result_data)
        self.assertIn('count', result_data)
        self.assertEqual(len(result_data['targets']), 2)

    def test_basic_functionality_coverage(self):
        """Test basic functionality to achieve coverage"""
        ListTrackedTargetsFromConfig = self._setup_mocks_and_import()

        # Test with defaults=False
        tool = ListTrackedTargetsFromConfig(include_defaults=False)
        result = tool.run()
        result_data = json.loads(result)

        # Verify basic functionality
        self.assertIn('targets', result_data)
        self.assertIn('count', result_data)

    def test_alternative_configurations(self):
        """Test alternative configurations for coverage"""
        ListTrackedTargetsFromConfig = self._setup_mocks_and_import()

        # Test basic execution paths
        tool1 = ListTrackedTargetsFromConfig(include_defaults=True)
        result1 = tool1.run()
        result_data1 = json.loads(result1)

        tool2 = ListTrackedTargetsFromConfig(include_defaults=False)
        result2 = tool2.run()
        result_data2 = json.loads(result2)

        # Verify both work
        self.assertIn('targets', result_data1)
        self.assertIn('targets', result_data2)


if __name__ == "__main__":
    unittest.main()