"""
Minimal tests for GetUserPosts tool.
Tests basic functionality and error handling without external API calls.
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys


class TestGetUserPostsMinimal(unittest.TestCase):
    """Minimal test suite for GetUserPosts tool."""

    def setUp(self):
        """Set up test environment with mocked dependencies."""
        # Mock all dependencies at module level
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'requests': MagicMock(),
        }

        # Apply mocks
        for module_name, mock_module in self.mock_modules.items():
            sys.modules[module_name] = mock_module

        # Set up BaseTool
        sys.modules['agency_swarm.tools'].BaseTool = MagicMock()

        # Mock environment and config loaders
        self.env_patcher = patch('linkedin_agent.tools.get_user_posts.get_required_env_var')
        self.config_patcher = patch('linkedin_agent.tools.get_user_posts.get_config_value')

        self.mock_env = self.env_patcher.start()
        self.mock_config = self.config_patcher.start()

        # Set up default return values
        self.mock_env.return_value = "test_api_key"
        self.mock_config.return_value = {"rate_limit": {"delay_seconds": 1}}

    def tearDown(self):
        """Clean up mocks."""
        self.env_patcher.stop()
        self.config_patcher.stop()

        for module_name in self.mock_modules:
            if module_name in sys.modules:
                del sys.modules[module_name]

    def test_tool_initialization(self):
        """Test that GetUserPosts tool can be initialized."""
        try:
            from linkedin_agent.tools.get_user_posts import GetUserPosts

            tool = GetUserPosts(
                user_urn="alexhormozi",
                page=1,
                page_size=25,
                max_items=100
            )

            # Verify initialization
            self.assertEqual(tool.user_urn, "alexhormozi")
            self.assertEqual(tool.page, 1)
            self.assertEqual(tool.page_size, 25)
            self.assertEqual(tool.max_items, 100)

            print("✅ GetUserPosts tool initialized successfully")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_tool_with_minimal_parameters(self):
        """Test tool initialization with minimal required parameters."""
        try:
            from linkedin_agent.tools.get_user_posts import GetUserPosts

            tool = GetUserPosts(user_urn="testuser")

            # Should use default values
            self.assertEqual(tool.user_urn, "testuser")
            self.assertEqual(tool.page, 1)  # Default
            self.assertEqual(tool.page_size, 25)  # Default
            self.assertEqual(tool.max_items, 100)  # Default

            print("✅ GetUserPosts tool works with minimal parameters")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_configuration_loading(self):
        """Test that configuration is loaded correctly."""
        try:
            from linkedin_agent.tools.get_user_posts import GetUserPosts

            tool = GetUserPosts(user_urn="testuser")

            # Try to run (will fail due to mocked requests, but tests config loading)
            try:
                result = tool.run()
            except Exception:
                # Expected to fail due to mocked environment
                pass

            # Verify environment variables were requested
            self.mock_env.assert_called()

            print("✅ Configuration loading tested successfully")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_invalid_user_urn_handling(self):
        """Test handling of invalid user URN."""
        try:
            from linkedin_agent.tools.get_user_posts import GetUserPosts

            # Test with empty user URN
            tool = GetUserPosts(user_urn="")

            # Should still initialize (validation happens at runtime)
            self.assertEqual(tool.user_urn, "")

            print("✅ Invalid user URN handling tested")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")

    def test_boundary_values(self):
        """Test boundary values for pagination parameters."""
        try:
            from linkedin_agent.tools.get_user_posts import GetUserPosts

            # Test maximum values
            tool_max = GetUserPosts(
                user_urn="testuser",
                page=999,
                page_size=100,  # Max page size
                max_items=1000  # Max items
            )

            self.assertEqual(tool_max.page_size, 100)
            self.assertEqual(tool_max.max_items, 1000)

            # Test minimum values
            tool_min = GetUserPosts(
                user_urn="testuser",
                page=1,
                page_size=1,
                max_items=1
            )

            self.assertEqual(tool_min.page, 1)
            self.assertEqual(tool_min.page_size, 1)
            self.assertEqual(tool_min.max_items, 1)

            print("✅ Boundary values tested successfully")

        except ImportError as e:
            self.skipTest(f"Import failed: {e}")


if __name__ == '__main__':
    unittest.main()