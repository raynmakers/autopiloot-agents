"""
Unit tests for centralized Firestore client factory (core/firestore_client.py).

Tests cover:
- Singleton behavior
- Environment variable validation
- Credentials path validation
- Error handling
- Collection helper function
- Client reset for testing
"""

import unittest
import os
from unittest.mock import patch, MagicMock, Mock
from pathlib import Path


class TestFirestoreClient(unittest.TestCase):
    """Test suite for centralized Firestore client factory."""

    def setUp(self):
        """Set up test environment before each test."""
        # Reset the singleton instance before each test
        import sys
        if 'core.firestore_client' in sys.modules:
            del sys.modules['core.firestore_client']

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    def test_get_firestore_client_success(self, mock_optional_env, mock_required_env, mock_client):
        """Test successful Firestore client initialization."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = ""

        # Mock Firestore client
        mock_client_instance = MagicMock()
        mock_client_instance.project = "test-project-id"
        mock_client.return_value = mock_client_instance

        # Import and test
        from firestore_client import get_firestore_client

        client = get_firestore_client()

        # Verify client created with correct project ID
        mock_client.assert_called_once_with(project="test-project-id")
        self.assertEqual(client.project, "test-project-id")

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    def test_singleton_behavior(self, mock_optional_env, mock_required_env, mock_client):
        """Test that get_firestore_client returns the same instance."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = ""

        # Mock Firestore client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Import and test
        from firestore_client import get_firestore_client

        client1 = get_firestore_client()
        client2 = get_firestore_client()

        # Verify same instance returned
        self.assertIs(client1, client2, "Should return same instance (singleton)")

        # Verify Client() called only once
        self.assertEqual(mock_client.call_count, 1, "Client should be created only once")

    @patch('firestore_client.get_required_env_var')
    def test_missing_project_id(self, mock_required_env):
        """Test error handling when GCP_PROJECT_ID is missing."""
        # Mock missing project ID
        mock_required_env.side_effect = RuntimeError("GCP_PROJECT_ID not set")

        # Import and test
        from firestore_client import get_firestore_client

        with self.assertRaises(RuntimeError) as context:
            get_firestore_client()

        self.assertIn("Failed to initialize Firestore client", str(context.exception))

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    @patch('firestore_client.os.path.exists')
    def test_invalid_credentials_path(self, mock_path_exists, mock_optional_env, mock_required_env, mock_client):
        """Test error handling when credentials file doesn't exist."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = "/invalid/path/to/credentials.json"

        # Mock path not existing
        mock_path_exists.return_value = False

        # Import and test
        from firestore_client import get_firestore_client

        with self.assertRaises(RuntimeError) as context:
            get_firestore_client()

        self.assertIn("path does not exist", str(context.exception))

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    def test_get_collection_helper(self, mock_optional_env, mock_required_env, mock_client):
        """Test get_collection convenience function."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = ""

        # Mock Firestore client and collection
        mock_collection = MagicMock()
        mock_collection.id = "videos"

        mock_client_instance = MagicMock()
        mock_client_instance.collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        # Import and test
        from firestore_client import get_collection

        collection = get_collection('videos')

        # Verify collection retrieved correctly
        mock_client_instance.collection.assert_called_once_with('videos')
        self.assertEqual(collection.id, "videos")

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    def test_reset_client(self, mock_optional_env, mock_required_env, mock_client):
        """Test reset_client() for test isolation."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = ""

        # Mock Firestore client
        mock_client_instance1 = MagicMock()
        mock_client_instance2 = MagicMock()
        mock_client.side_effect = [mock_client_instance1, mock_client_instance2]

        # Import and test
        from firestore_client import get_firestore_client, reset_client

        client1 = get_firestore_client()
        reset_client()
        client2 = get_firestore_client()

        # Verify different instances after reset
        self.assertIsNot(client1, client2, "Should return different instances after reset")

        # Verify Client() called twice
        self.assertEqual(mock_client.call_count, 2, "Client should be created twice after reset")

    @patch('firestore_client.firestore.Client')
    @patch('firestore_client.get_required_env_var')
    @patch('firestore_client.get_optional_env_var')
    @patch('firestore_client.os.path.exists')
    def test_valid_credentials_path(self, mock_path_exists, mock_optional_env, mock_required_env, mock_client):
        """Test successful initialization with valid credentials path."""
        # Mock environment variables
        mock_required_env.return_value = "test-project-id"
        mock_optional_env.return_value = "/valid/path/to/credentials.json"

        # Mock path existing
        mock_path_exists.return_value = True

        # Mock Firestore client
        mock_client_instance = MagicMock()
        mock_client.return_value = mock_client_instance

        # Import and test
        from firestore_client import get_firestore_client

        client = get_firestore_client()

        # Verify no error raised
        self.assertIsNotNone(client)
        mock_client.assert_called_once_with(project="test-project-id")


if __name__ == "__main__":
    unittest.main()
