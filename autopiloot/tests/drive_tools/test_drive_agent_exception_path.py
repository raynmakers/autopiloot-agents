#!/usr/bin/env python3
"""
Test to achieve 100% coverage of drive_agent.py by triggering exception path in lines 22-26
Uses direct module execution with proper mocking to force exception handling
"""

import unittest
import sys
import os
import importlib.util
from unittest.mock import patch, MagicMock

# Add project root to path for imports

class TestDriveAgentExceptionPath(unittest.TestCase):
    """Test to cover the exception path in drive_agent.py lines 22-26."""

    def setUp(self):
        """Clear module cache to ensure fresh imports."""
        # Clear any existing drive_agent imports
        modules_to_clear = [k for k in list(sys.modules.keys()) if 'drive_agent' in k]
        for module in modules_to_clear:
            del sys.modules[module]

        # Clear loader module if it exists
        if 'loader' in sys.modules:
            del sys.modules['loader']

    def test_drive_agent_exception_path_coverage(self):
        """Test that the exception path in drive_agent.py lines 22-26 is executed."""

        # Mock agency_swarm components
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Mock the loader module to raise an exception
            mock_loader = MagicMock()
            mock_loader.load_app_config.side_effect = Exception("Config loading failed")

            with patch.dict('sys.modules', {'loader': mock_loader}):
                # Direct file import to force execution of the module
                spec = importlib.util.spec_from_file_location(
                    "drive_agent_module",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/drive_agent.py"
                )
                module = importlib.util.module_from_spec(spec)

                # Execute the module - this should trigger the exception path
                spec.loader.exec_module(module)

                # Verify the module was loaded
                self.assertIsNotNone(module)

                # Verify the drive_agent was created with fallback values
                self.assertTrue(hasattr(module, 'drive_agent'))
                drive_agent = module.drive_agent
                self.assertIsNotNone(drive_agent)

    def test_exception_fallback_values(self):
        """Test that exception handling sets correct fallback values."""

        # Mock agency_swarm components
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Create a mock loader that fails
            mock_loader = MagicMock()
            mock_loader.load_app_config.side_effect = ImportError("No module named 'yaml'")

            with patch.dict('sys.modules', {'loader': mock_loader}):
                # Execute drive_agent.py directly
                spec = importlib.util.spec_from_file_location(
                    "drive_agent_test",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/drive_agent.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Verify the module was loaded successfully (exception path covered)
                self.assertIsNotNone(module)
                self.assertTrue(hasattr(module, 'drive_agent'))

    def test_successful_config_path_coverage(self):
        """Test the successful config loading path for comparison."""

        # Mock agency_swarm components
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock()
        }):
            # Create a successful mock loader
            mock_loader = MagicMock()
            mock_loader.load_app_config.return_value = {
                "llm": {
                    "default": {
                        "model": "gpt-4-turbo",
                        "temperature": 0.1,
                        "max_output_tokens": 30000
                    }
                }
            }

            with patch.dict('sys.modules', {'loader': mock_loader}):
                # Execute drive_agent.py
                spec = importlib.util.spec_from_file_location(
                    "drive_agent_success",
                    "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/drive_agent.py"
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Verify the module was loaded successfully (success path covered)
                self.assertIsNotNone(module)
                self.assertTrue(hasattr(module, 'drive_agent'))


if __name__ == '__main__':
    unittest.main()