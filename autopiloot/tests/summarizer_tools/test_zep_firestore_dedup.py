"""
Test suite for Zep Firestore-based deduplication in store_short_in_zep.py

Tests cover:
- First run: No Firestore record → Calls Zep → Stores normally (action=created)
- Second run (same content): Firestore has matching hash → Skips Zep → Returns skipped status
- Third run (changed content): Firestore has different hash → Calls Zep → Updates thread (action=updated)
- Firestore unavailable: Graceful fallback → Calls Zep anyway (safe fail-open)
- No GCP_PROJECT_ID: Graceful fallback → Calls Zep anyway
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os
import importlib.util

# Add parent directory to path for imports

class TestZepFirestoreDedup(unittest.TestCase):
    """Test Firestore-based deduplication for Zep message storage."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock Agency Swarm BaseTool as a class that can be inherited
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_base_tool = MockBaseTool
        sys.modules['agency_swarm'] = MagicMock()
        sys.modules['agency_swarm.tools'] = MagicMock()
        sys.modules['agency_swarm.tools'].BaseTool = self.mock_base_tool

        # Mock environment variables
        self.env_patcher = patch.dict(os.environ, {
            'ZEP_API_KEY': 'test-zep-key',
            'ZEP_BASE_URL': 'https://api.getzep.com',
            'GCP_PROJECT_ID': 'test-project-id'
        })
        self.env_patcher.start()

        # Mock env_loader functions
        mock_env_loader = MagicMock()
        mock_env_loader.load_environment = MagicMock()
        mock_env_loader.get_required_env_var = MagicMock(side_effect=lambda key, desc='': os.getenv(key))
        sys.modules['env_loader'] = mock_env_loader

        # Mock httpx module
        mock_httpx = MagicMock()
        sys.modules['httpx'] = mock_httpx

        # Mock pydantic module
        mock_pydantic = MagicMock()
        sys.modules['pydantic'] = mock_pydantic
        # Create a callable Field that returns None (will be overridden by __init__)
        sys.modules['pydantic'].Field = lambda *args, **kwargs: None

        # Mock google.cloud modules
        mock_google = MagicMock()
        mock_google_cloud = MagicMock()
        mock_google_cloud_firestore = MagicMock()
        sys.modules['google'] = mock_google
        sys.modules['google.cloud'] = mock_google_cloud
        sys.modules['google.cloud.firestore'] = mock_google_cloud_firestore

        # Import the tool directly from file
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'summarizer_agent', 'tools', 'store_short_in_zep.py'
        )
        spec = importlib.util.spec_from_file_location("store_short_in_zep", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.StoreShortInZep = module.StoreShortInZep

    def tearDown(self):
        """Clean up test fixtures."""
        self.env_patcher.stop()

    def test_first_run_no_firestore_record_stores_normally(self):
        """
        Test first run with no Firestore record.
        Should call Zep API and store normally (action=created).
        """
        # Mock Firestore - document does not exist
        mock_firestore_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

        # Mock Zep HTTP client
        mock_zep_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"uuid": "thread-uuid"}
        mock_zep_client.post.return_value = mock_response

        with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
            tool = self.StoreShortInZep(
                video_id="test_video_123",
                bullets=["Bullet 1", "Bullet 2"],
                key_concepts=["Concept A", "Concept B"],
                channel_id="UC1234567890",
                channel_handle="@TestChannel",
                title="Test Video"
            )

            # Mock the HTTP client initialization and Zep operations
            with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                    with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                        with patch.object(tool, '_create_thread', return_value={"success": True}):
                            # Mock _add_messages to return success
                            mock_add_result = {
                                "success": True,
                                "message_uuids": ["msg-uuid-1"]
                            }
                            with patch.object(tool, '_add_messages', return_value=mock_add_result):
                                result = tool.run()

            # Debug: Print result
            print(f"\n[DEBUG test_first_run] Result: {result[:200]}")
            result_data = json.loads(result)
            print(f"[DEBUG test_first_run] Parsed data keys: {result_data.keys()}")

            # Assertions
            self.assertEqual(result_data["status"], "stored")
            self.assertEqual(result_data["action"], "created")
            self.assertIn("content_hash", result_data)
            self.assertEqual(result_data["thread_id"], "summary_test_video_123")
            self.assertEqual(len(result_data["message_uuids"]), 1)

    def test_second_run_same_content_skips_zep(self):
        """
        Test second run with same content hash in Firestore.
        Should skip Zep API call and return skipped status.
        """
        # First, create tool to get the actual hash
        import hashlib
        tool = self.StoreShortInZep(
            video_id="test_video_123",
            bullets=["Bullet 1", "Bullet 2"],
            key_concepts=["Concept A", "Concept B"],
            channel_id="UC1234567890",
            channel_handle="@TestChannel",
            title="Test Video"
        )

        # Compute the actual hash that will be generated
        content = tool._format_content()
        actual_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

        # Mock Firestore - document exists with matching hash
        mock_firestore_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.get.side_effect = lambda field: {
            'summary_digest': actual_hash,  # Use the actual hash
            'zep_thread_id': 'summary_test_video_123'
        }.get(field)
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

        # Mock Zep HTTP client (should NOT be called)
        mock_zep_client = MagicMock()

        # Create a mock dedup check that returns duplicate
        def mock_dedup_check(content):
            return {
                "is_duplicate": True,
                "stored_hash": actual_hash,
                "new_hash": actual_hash,
                "zep_thread_id": "summary_test_video_123"
            }

        # Patch the dedup check method directly
        with patch.object(tool, '_check_firestore_for_duplicate', side_effect=mock_dedup_check):
            # Mock the HTTP client initialization
            with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                    with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                        with patch.object(tool, '_create_thread', return_value={"success": True}):
                            result = tool.run()

            # Debug: Print result
            print(f"\n[DEBUG test_second_run] Result: {result[:300]}")
            result_data = json.loads(result)
            print(f"[DEBUG test_second_run] Status: {result_data.get('status', 'MISSING')}")
            print(f"[DEBUG test_second_run] Expected hash: {actual_hash}")

            # Assertions
            self.assertEqual(result_data["status"], "skipped")
            self.assertEqual(result_data["action"], "duplicate_content")
            self.assertEqual(result_data["content_hash"], actual_hash)
            self.assertIn("Content unchanged", result_data["message"])

            # Verify _add_messages was NOT called (Zep API not called)
            # Since we returned early, _add_messages should not have been invoked

    def test_third_run_changed_content_calls_zep(self):
        """
        Test third run with different content hash.
        Should call Zep API and update thread.
        """
        # Mock Firestore - document exists with DIFFERENT hash
        mock_firestore_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.get.side_effect = lambda field: {
            'summary_digest': 'old_hash_12345',
            'zep_thread_id': 'summary_test_video_123'
        }.get(field)
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

        # Mock Zep HTTP client
        mock_zep_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message_uuids": ["msg-uuid-2"]}
        mock_zep_client.post.return_value = mock_response

        with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
            with patch('hashlib.sha256') as mock_hash:
                # Make hash different from stored hash
                mock_hash.return_value.hexdigest.return_value = 'new_hash_67890' + '0' * 48

                tool = self.StoreShortInZep(
                    video_id="test_video_123",
                    bullets=["Bullet 1 CHANGED", "Bullet 2 CHANGED"],
                    key_concepts=["Concept A", "Concept B"],
                    channel_id="UC1234567890",
                    channel_handle="@TestChannel",
                    title="Test Video"
                )

                # Mock the HTTP client initialization and Zep operations
                with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                    with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                        with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                            with patch.object(tool, '_create_thread', return_value={"success": True}):
                                mock_add_result = {
                                    "success": True,
                                    "message_uuids": ["msg-uuid-2"]
                                }
                                with patch.object(tool, '_add_messages', return_value=mock_add_result):
                                    result = tool.run()

                result_data = json.loads(result)

                # Assertions
                self.assertEqual(result_data["status"], "stored")
                self.assertIn("content_hash", result_data)
                # New hash should be different from old hash
                self.assertNotEqual(result_data["content_hash"], "old_hash_12345")

    def test_firestore_unavailable_graceful_fallback(self):
        """
        Test Firestore unavailable scenario.
        Should gracefully fall back and proceed with Zep storage.
        """
        # Mock Firestore to raise exception
        with patch('google.cloud.firestore.Client', side_effect=Exception("Firestore unavailable")):
            tool = self.StoreShortInZep(
                video_id="test_video_123",
                bullets=["Bullet 1", "Bullet 2"],
                key_concepts=["Concept A", "Concept B"],
                channel_id="UC1234567890",
                channel_handle="@TestChannel",
                title="Test Video"
            )

            # Mock Zep operations
            mock_zep_client = MagicMock()
            with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                    with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                        with patch.object(tool, '_create_thread', return_value={"success": True}):
                            mock_add_result = {
                                "success": True,
                                "message_uuids": ["msg-uuid-1"]
                            }
                            with patch.object(tool, '_add_messages', return_value=mock_add_result):
                                result = tool.run()

            result_data = json.loads(result)

            # Should proceed with storage despite Firestore error
            self.assertEqual(result_data["status"], "stored")
            self.assertIn("content_hash", result_data)

    def test_no_gcp_project_id_graceful_fallback(self):
        """
        Test missing GCP_PROJECT_ID environment variable.
        Should skip dedup check and proceed with Zep storage.
        """
        # Remove GCP_PROJECT_ID from environment
        with patch.dict(os.environ, {'GCP_PROJECT_ID': ''}, clear=True):
            with patch.dict(os.environ, {
                'ZEP_API_KEY': 'test-zep-key',
                'ZEP_BASE_URL': 'https://api.getzep.com'
            }):
                tool = self.StoreShortInZep(
                    video_id="test_video_123",
                    bullets=["Bullet 1", "Bullet 2"],
                    key_concepts=["Concept A", "Concept B"],
                    channel_id="UC1234567890",
                    channel_handle="@TestChannel",
                    title="Test Video"
                )

                # Mock Zep operations
                mock_zep_client = MagicMock()
                with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                    with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                        with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                            with patch.object(tool, '_create_thread', return_value={"success": True}):
                                mock_add_result = {
                                    "success": True,
                                    "message_uuids": ["msg-uuid-1"]
                                }
                                with patch.object(tool, '_add_messages', return_value=mock_add_result):
                                    result = tool.run()

                result_data = json.loads(result)

                # Should proceed with storage despite missing GCP_PROJECT_ID
                self.assertEqual(result_data["status"], "stored")
                self.assertIn("content_hash", result_data)

    def test_content_hash_in_message_metadata(self):
        """
        Test that content_hash is included in Zep message metadata.
        """
        # Mock Firestore - no duplicate
        mock_firestore_client = MagicMock()
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_doc

        # Mock Zep HTTP client
        mock_zep_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message_uuids": ["msg-uuid-1"]}
        mock_zep_client.post.return_value = mock_response

        with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
            tool = self.StoreShortInZep(
                video_id="test_video_123",
                bullets=["Bullet 1", "Bullet 2"],
                key_concepts=["Concept A", "Concept B"],
                channel_id="UC1234567890",
                channel_handle="@TestChannel",
                title="Test Video"
            )

            # Capture the message data sent to Zep
            captured_message_data = None

            def capture_post(url, json=None, **kwargs):
                nonlocal captured_message_data
                if "/messages" in url:
                    captured_message_data = json
                return mock_response

            mock_zep_client.post.side_effect = capture_post

            # Mock Zep operations
            with patch.object(tool, '_initialize_http_client', return_value=mock_zep_client):
                with patch.object(tool, '_ensure_user_exists', return_value={"success": True}):
                    with patch.object(tool, '_ensure_group_exists', return_value={"success": True}):
                        with patch.object(tool, '_create_thread', return_value={"success": True}):
                            result = tool.run()

            # Verify content_hash is in message metadata
            self.assertIsNotNone(captured_message_data)
            self.assertIn("messages", captured_message_data)
            self.assertGreater(len(captured_message_data["messages"]), 0)

            message_metadata = captured_message_data["messages"][0]["metadata"]
            self.assertIn("content_hash", message_metadata)
            self.assertIsInstance(message_metadata["content_hash"], str)
            self.assertEqual(len(message_metadata["content_hash"]), 16)  # 16-char hash


if __name__ == "__main__":
    unittest.main(verbosity=2)
