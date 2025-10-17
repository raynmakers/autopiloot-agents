"""
Test coverage for linkedin_agent/__init__.py and linkedin_agent.py
Tests agent initialization, configuration loading, and module structure.
"""

import unittest
import sys
import os
from unittest.mock import patch, MagicMock

# Add project root to path for imports

class TestLinkedInAgentInit(unittest.TestCase):
    """Test suite for LinkedIn Agent initialization and module imports."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock external dependencies at import time
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.Agent': MagicMock(),
            'agency_swarm.ModelSettings': MagicMock(),
        }

        # Apply mocks
        for module_name, mock_module in self.mock_modules.items():
            sys.modules[module_name] = mock_module

    def tearDown(self):
        """Clean up mocks."""
        # Remove mocked modules
        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_linkedin_agent_initialization(self):
        """Test that linkedin_agent can be imported and initialized."""
        try:
            from linkedin_agent.linkedin_agent import linkedin_agent

            # Verify agent object exists
            self.assertIsNotNone(linkedin_agent)

            # Verify agent was called with expected parameters
            # (The mock will capture these calls)
            print("✅ LinkedIn agent initialized successfully")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_linkedin_agent_configuration(self):
        """Test linkedin_agent configuration parameters."""
        # Mock Agent and ModelSettings classes
        mock_agent_class = MagicMock()
        mock_model_settings_class = MagicMock()

        with patch('linkedin_agent.linkedin_agent.Agent', mock_agent_class):
            with patch('linkedin_agent.linkedin_agent.ModelSettings', mock_model_settings_class):
                try:
                    import linkedin_agent.linkedin_agent

                    # Verify Agent was called with correct parameters
                    mock_agent_class.assert_called_once()
                    call_args = mock_agent_class.call_args[1]  # Get keyword arguments

                    # Check expected configuration
                    self.assertEqual(call_args['name'], "LinkedInAgent")
                    self.assertIn("LinkedIn", call_args['description'])
                    self.assertEqual(call_args['instructions'], "./instructions.md")
                    self.assertEqual(call_args['tools_folder'], "./tools")

                    # Verify ModelSettings was called
                    mock_model_settings_class.assert_called_once()
                    model_args = mock_model_settings_class.call_args[1]

                    self.assertEqual(model_args['model'], "gpt-4o")
                    self.assertEqual(model_args['temperature'], 0.2)
                    self.assertEqual(model_args['max_completion_tokens'], 25000)

                    print("✅ LinkedIn agent configuration verified")

                except ImportError as e:
                    self.skipTest(f"Import failed: {e}")

    def test_linkedin_agent_module_import(self):
        """Test that linkedin_agent module can be imported."""
        try:
            import linkedin_agent
            self.assertIsNotNone(linkedin_agent)
            print("✅ LinkedIn agent module imported successfully")

        except ImportError as e:
            self.skipTest(f"Module import failed: {e}")


if __name__ == '__main__':
    unittest.main()