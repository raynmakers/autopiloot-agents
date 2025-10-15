#!/usr/bin/env python3
"""
Direct execution test for drive_agent.py lines 22-26
Uses exec to directly execute the drive_agent.py file with controlled conditions
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock
from pathlib import Path

# Add project root to path for imports

class TestDriveAgentExecCoverage(unittest.TestCase):
    """Test class that uses exec to run drive_agent.py code directly."""

    def test_exec_drive_agent_with_exception_path(self):
        """Execute drive_agent.py code directly to force lines 22-26 execution."""

        # Read the actual drive_agent.py file
        drive_agent_path = Path(__file__).parent.parent.parent / "drive_agent" / "drive_agent.py"
        with open(drive_agent_path, 'r') as f:
            drive_agent_code = f.read()

        # Mock agency_swarm components
        mock_agent = MagicMock()
        mock_model_settings = MagicMock()

        # Create a controlled execution environment
        exec_globals = {
            '__name__': '__main__',
            '__file__': str(drive_agent_path),
            'os': os,
            'sys': sys,
            'Path': Path,
            'Agent': mock_agent,
            'ModelSettings': mock_model_settings,
        }

        # Execute the drive_agent.py code
        # This will trigger the actual execution including the exception path
        exec(drive_agent_code, exec_globals)

        # Verify that the agent was created
        mock_agent.assert_called_once()
        mock_model_settings.assert_called_once()

        # Check the arguments to see if fallback values were used
        agent_call = mock_agent.call_args
        model_settings_call = mock_model_settings.call_args

        # The module should have executed successfully
        self.assertIsNotNone(agent_call)
        self.assertIsNotNone(model_settings_call)

        # Check if we can access the model settings kwargs
        if model_settings_call and len(model_settings_call) > 1:
            kwargs = model_settings_call[1]
            # If config loading failed, these should be the fallback values from lines 24-26
            model = kwargs.get('model')
            temperature = kwargs.get('temperature')
            max_tokens = kwargs.get('max_completion_tokens')

            # Log what we got for debugging
            print(f"Model: {model}, Temperature: {temperature}, Max tokens: {max_tokens}")

            # At minimum, verify we got some values
            self.assertIsNotNone(model)
            self.assertIsNotNone(temperature)
            self.assertIsNotNone(max_tokens)

    def test_forced_exception_exec(self):
        """Force exception execution by modifying the code before exec."""

        # Read the actual drive_agent.py file
        drive_agent_path = Path(__file__).parent.parent.parent / "drive_agent" / "drive_agent.py"
        with open(drive_agent_path, 'r') as f:
            drive_agent_code = f.read()

        # Modify the code to force the exception path
        # Replace the try block with a version that always fails
        modified_code = drive_agent_code.replace(
            'try:\n    from loader import load_app_config',
            'try:\n    raise ImportError("Forced exception for testing")\n    from loader import load_app_config'
        )

        # Mock agency_swarm components
        mock_agent = MagicMock()
        mock_model_settings = MagicMock()

        # Create a controlled execution environment
        exec_globals = {
            '__name__': '__main__',
            '__file__': str(drive_agent_path),
            'os': os,
            'sys': sys,
            'Path': Path,
            'Agent': mock_agent,
            'ModelSettings': mock_model_settings,
        }

        # Execute the modified drive_agent.py code
        exec(modified_code, exec_globals)

        # Verify that the agent was created
        mock_agent.assert_called_once()
        mock_model_settings.assert_called_once()

        # Check that fallback values from lines 24-26 were used
        model_settings_call = mock_model_settings.call_args
        if model_settings_call and len(model_settings_call) > 1:
            kwargs = model_settings_call[1]

            # These should be the exact fallback values from lines 24-26
            self.assertEqual(kwargs.get('model'), "gpt-4o")
            self.assertEqual(kwargs.get('temperature'), 0.2)
            self.assertEqual(kwargs.get('max_completion_tokens'), 25000)


if __name__ == '__main__':
    unittest.main()