"""
Comprehensive test for upsert_to_zep_group tool to achieve maximum coverage.
"""

import unittest
import os
import sys
import json
import importlib.util
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone


class TestUpsertToZepGroupComprehensive(unittest.TestCase):
    """Comprehensive test for UpsertToZepGroup tool."""

    @classmethod
    def setUpClass(cls):
        """Set up test class with proper mocking and imports."""
        # Define all mock modules
        mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'zep_python': MagicMock(),
        }

        # Mock Pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        with patch.dict('sys.modules', mock_modules):
            # Create mock BaseTool
            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
            sys.modules['pydantic'].Field = mock_field

            # Import using importlib for proper coverage
            tool_path = os.path.join(os.path.dirname(__file__), '..', '..',
                                   'linkedin_agent', 'tools', 'upsert_to_zep_group.py')
            spec = importlib.util.spec_from_file_location("upsert_to_zep_group", tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            cls.UpsertToZepGroup = module.UpsertToZepGroup

    def setUp(self):
        """Set up test fixtures."""
        # Sample LinkedIn entities
        self.sample_entities = [
            {
                "id": "urn:li:activity:12345",
                "content_hash": "abc123def456",
                "type": "post",
                "text": "Great insights about business strategy and growth mindset",
                "author": {
                    "name": "John Doe",
                    "headline": "Business Coach & Strategy Consultant",
                    "profile_url": "https://linkedin.com/in/johndoe"
                },
                "created_at": "2024-01-15T10:00:00Z",
                "normalized_at": "2024-01-15T10:05:00Z",
                "metrics": {
                    "likes": 150,
                    "comments": 25,
                    "shares": 10,
                    "engagement_rate": 0.05
                },
                "media": [
                    {"type": "image", "url": "https://example.com/image.jpg"}
                ]
            },
            {
                "id": "urn:li:comment:67890",
                "content_hash": "def789ghi012",
                "type": "comment",
                "text": "This is very insightful, thank you for sharing!",
                "author": {
                    "name": "Jane Smith",
                    "headline": "Marketing Director",
                    "profile_url": "https://linkedin.com/in/janesmith"
                },
                "created_at": "2024-01-15T11:00:00Z",
                "normalized_at": "2024-01-15T11:05:00Z",
                "parent_post_id": "urn:li:activity:12345",
                "metrics": {
                    "likes": 5,
                    "comments": 0,
                    "is_reply": True,
                    "engagement_rate": 0.01
                }
            }
        ]

    def test_successful_upsert_with_custom_group_name(self):
        """Test successful upsert with custom group name (lines 56-78, 91-128)."""
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment') as mock_load_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_get_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_get_config, \
             patch.dict('os.environ', {'ZEP_BASE_URL': 'https://test.api.com'}):

            mock_get_env.return_value = "test-api-key"
            mock_get_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "test_linkedin",
                "linkedin.zep.collection_name": "test_collection"
            }.get(key, default)

            tool = self.UpsertToZepGroup(
                entities=self.sample_entities,
                group_name="custom_group_name",
                content_type="posts",
                batch_size=50
            )

            # Mock Zep client methods
            mock_client = Mock()
            mock_client._is_mock = True
            tool._initialize_zep_client = Mock(return_value=mock_client)
            tool._create_or_find_group = Mock(return_value={
                "group_id": "custom_group_name",
                "created": False,
                "collection": "test_collection"
            })
            tool._batch_upsert_documents = Mock(return_value={
                "upserted": 2,
                "skipped": 0,
                "errors": 0,
                "error_details": []
            })

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["group_id"], "custom_group_name")
            self.assertEqual(result_data["upsert_results"]["upserted"], 2)
            self.assertIn("metadata", result_data)
            self.assertEqual(result_data["metadata"]["content_type"], "posts")

    def test_upsert_with_empty_entities_list(self):
        """Test handling of empty entities list (lines 91-96)."""
        tool = self.UpsertToZepGroup(
            entities=[],
            content_type="posts"
        )

        # Mock the load_environment function within the tool module
        with patch.object(tool.__class__.__module__, 'load_environment', create=True):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "no_entities")
            self.assertIn("No entities provided", result_data["message"])

    def test_exception_handling_in_run_method(self):
        """Test exception handling in main run method (lines 130-137)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            content_type="mixed"
        )

        # Force an exception by mocking load_environment to raise
        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment',
                  side_effect=Exception("Environment loading failed")):
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "zep_upsert_failed")
            self.assertIn("Environment loading failed", result_data["message"])
            self.assertEqual(result_data["entity_count"], 2)
            self.assertEqual(result_data["content_type"], "mixed")

    def test_initialize_zep_client_with_import_error(self):
        """Test Zep client initialization with import error (lines 150-155)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        with patch('linkedin_agent.tools.upsert_to_zep_group.ZepClient',
                  side_effect=ImportError("zep_python not available")):
            client = tool._initialize_zep_client("test-key", "https://test.com")

            self.assertTrue(hasattr(client, '_is_mock'))
            self.assertTrue(hasattr(client, 'group'))

    def test_initialize_zep_client_success(self):
        """Test successful Zep client initialization (lines 150-152)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_zep_client = Mock()
        with patch('linkedin_agent.tools.upsert_to_zep_group.ZepClient',
                  return_value=mock_zep_client):
            client = tool._initialize_zep_client("test-key", "https://test.com")

            self.assertEqual(client, mock_zep_client)

    def test_determine_group_name_with_custom_name(self):
        """Test group name determination with custom name (lines 167-168)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            group_name="custom_test_group"
        )

        result = tool._determine_group_name("linkedin")
        self.assertEqual(result, "custom_test_group")

    def test_determine_group_name_with_profile_identifier(self):
        """Test group name with profile identifier (lines 171-175)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            profile_identifier="@Alex Hormozi",
            content_type="posts"
        )

        result = tool._determine_group_name("linkedin")
        self.assertEqual(result, "linkedin_alex_hormozi_posts")

    def test_determine_group_name_with_special_chars_in_profile(self):
        """Test group name with special characters in profile identifier (lines 173-174)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            profile_identifier="@test-user_123!@#$%",
            content_type="comments"
        )

        result = tool._determine_group_name("prefix")
        self.assertEqual(result, "prefix_testuser_123_comments")

    def test_determine_group_name_with_hash_fallback(self):
        """Test group name generation with hash fallback (lines 177-181)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            content_type="mixed"
        )

        result = tool._determine_group_name("linkedin")
        self.assertTrue(result.startswith("linkedin_"))
        self.assertTrue(result.endswith("_mixed"))
        # Hash should be 8 characters long
        hash_part = result.replace("linkedin_", "").replace("_mixed", "")
        self.assertEqual(len(hash_part), 8)

    def test_create_or_find_group_existing_group(self):
        """Test finding existing group (lines 196-202)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        mock_group = Mock()
        mock_client.group.get.return_value = mock_group

        result = tool._create_or_find_group(mock_client, "test_group", "test_collection")

        self.assertEqual(result["group_id"], "test_group")
        self.assertFalse(result["created"])
        self.assertEqual(result["collection"], "test_collection")

    def test_create_or_find_group_create_new(self):
        """Test creating new group (lines 204-220)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            content_type="posts"
        )

        mock_client = Mock()
        mock_client.group.get.side_effect = Exception("Group not found")
        mock_created_group = Mock()
        mock_client.group.add.return_value = mock_created_group

        result = tool._create_or_find_group(mock_client, "new_group", "test_collection")

        self.assertEqual(result["group_id"], "new_group")
        self.assertTrue(result["created"])
        self.assertEqual(result["collection"], "test_collection")

        # Verify group.add was called with correct parameters
        mock_client.group.add.assert_called_once()
        call_args = mock_client.group.add.call_args
        self.assertEqual(call_args[1]["group_id"], "new_group")
        self.assertIn("LinkedIn Content", call_args[1]["name"])
        self.assertIn("posts", call_args[1]["description"])

    def test_create_or_find_group_fallback_mock(self):
        """Test group creation fallback to mock behavior (lines 221-228)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        mock_client.group.get.side_effect = Exception("Group not found")
        mock_client.group.add.side_effect = Exception("Creation failed")

        result = tool._create_or_find_group(mock_client, "test_group", "test_collection")

        self.assertEqual(result["group_id"], "test_group")
        self.assertTrue(result["created"])
        self.assertTrue(result.get("mock", False))

    def test_prepare_documents_complete_entity(self):
        """Test document preparation with complete entity data (lines 242-296)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        documents = tool._prepare_documents(self.sample_entities)

        self.assertEqual(len(documents), 2)

        # Check first document (post)
        post_doc = documents[0]
        self.assertEqual(post_doc["id"], "urn:li:activity:12345")
        self.assertEqual(post_doc["content"], "Great insights about business strategy and growth mindset")

        metadata = post_doc["metadata"]
        self.assertEqual(metadata["type"], "post")
        self.assertEqual(metadata["author_name"], "John Doe")
        self.assertEqual(metadata["likes"], 150)
        self.assertTrue(metadata["has_media"])
        self.assertEqual(metadata["media_types"], ["image"])

        # Check second document (comment)
        comment_doc = documents[1]
        self.assertEqual(comment_doc["metadata"]["type"], "comment")
        self.assertEqual(comment_doc["metadata"]["parent_post_id"], "urn:li:activity:12345")
        self.assertTrue(comment_doc["metadata"]["is_reply"])

    def test_prepare_documents_empty_text_skipped(self):
        """Test skipping entities without text content (lines 244-246)."""
        entities_with_empty = [
            {"id": "test1", "text": ""},
            {"id": "test2"},  # No text field
            {"id": "test3", "text": "Valid content"}
        ]

        tool = self.UpsertToZepGroup(entities=entities_with_empty)
        documents = tool._prepare_documents(entities_with_empty)

        self.assertEqual(len(documents), 1)
        self.assertEqual(documents[0]["content"], "Valid content")

    def test_prepare_documents_minimal_entity(self):
        """Test document preparation with minimal entity data (lines 248-256)."""
        minimal_entity = [{"text": "Simple content"}]

        tool = self.UpsertToZepGroup(entities=minimal_entity)
        documents = tool._prepare_documents(minimal_entity)

        self.assertEqual(len(documents), 1)
        doc = documents[0]
        self.assertEqual(doc["content"], "Simple content")

        metadata = doc["metadata"]
        self.assertEqual(metadata["id"], "")
        self.assertEqual(metadata["type"], "unknown")
        self.assertEqual(metadata["source"], "linkedin")

    def test_prepare_documents_entity_without_author(self):
        """Test document preparation without author information (lines 258-265)."""
        entity_no_author = [{
            "id": "test123",
            "text": "Content without author",
            "metrics": {"likes": 5}
        }]

        tool = self.UpsertToZepGroup(entities=entity_no_author)
        documents = tool._prepare_documents(entity_no_author)

        metadata = documents[0]["metadata"]
        self.assertNotIn("author_name", metadata)
        self.assertEqual(metadata["likes"], 5)

    def test_prepare_documents_entity_without_metrics(self):
        """Test document preparation without metrics information (lines 267-275)."""
        entity_no_metrics = [{
            "id": "test456",
            "text": "Content without metrics",
            "author": {"name": "Test User"}
        }]

        tool = self.UpsertToZepGroup(entities=entity_no_metrics)
        documents = tool._prepare_documents(entity_no_metrics)

        metadata = documents[0]["metadata"]
        self.assertEqual(metadata["author_name"], "Test User")
        self.assertNotIn("likes", metadata)

    def test_prepare_documents_non_comment_type(self):
        """Test document preparation for non-comment types (lines 277-282)."""
        post_entity = [{
            "id": "post123",
            "text": "This is a post",
            "type": "post"
        }]

        tool = self.UpsertToZepGroup(entities=post_entity)
        documents = tool._prepare_documents(post_entity)

        metadata = documents[0]["metadata"]
        self.assertNotIn("parent_post_id", metadata)
        self.assertNotIn("is_reply", metadata)

    def test_prepare_documents_entity_without_media(self):
        """Test document preparation without media (lines 284-287)."""
        entity_no_media = [{
            "id": "test789",
            "text": "Content without media"
        }]

        tool = self.UpsertToZepGroup(entities=entity_no_media)
        documents = tool._prepare_documents(entity_no_media)

        metadata = documents[0]["metadata"]
        self.assertNotIn("has_media", metadata)
        self.assertNotIn("media_types", metadata)

    def test_prepare_documents_with_empty_media_list(self):
        """Test document preparation with empty media list."""
        entity_empty_media = [{
            "id": "test999",
            "text": "Content with empty media",
            "media": []
        }]

        tool = self.UpsertToZepGroup(entities=entity_empty_media)
        documents = tool._prepare_documents(entity_empty_media)

        metadata = documents[0]["metadata"]
        self.assertNotIn("has_media", metadata)

    def test_batch_upsert_documents_single_batch(self):
        """Test batch upsert with single batch (lines 319-332)."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            batch_size=50
        )

        mock_client = Mock()
        documents = [
            {"id": "doc1", "content": "Content 1", "metadata": {}},
            {"id": "doc2", "content": "Content 2", "metadata": {}}
        ]

        mock_batch_result = {
            "upserted": 2,
            "skipped": 0,
            "errors": 0,
            "error_details": []
        }
        tool._upsert_batch = Mock(return_value=mock_batch_result)

        result = tool._batch_upsert_documents(mock_client, "test_group", documents)

        self.assertEqual(result["upserted"], 2)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertEqual(len(result["error_details"]), 0)

    def test_batch_upsert_documents_multiple_batches(self):
        """Test batch upsert with multiple batches."""
        tool = self.UpsertToZepGroup(
            entities=self.sample_entities,
            batch_size=1  # Force multiple batches
        )

        mock_client = Mock()
        documents = [
            {"id": "doc1", "content": "Content 1", "metadata": {}},
            {"id": "doc2", "content": "Content 2", "metadata": {}}
        ]

        mock_batch_result = {
            "upserted": 1,
            "skipped": 0,
            "errors": 0
        }
        tool._upsert_batch = Mock(return_value=mock_batch_result)

        result = tool._batch_upsert_documents(mock_client, "test_group", documents)

        self.assertEqual(result["upserted"], 2)  # 2 batches x 1 upserted each
        self.assertEqual(tool._upsert_batch.call_count, 2)

    def test_batch_upsert_documents_batch_exception(self):
        """Test batch upsert with batch exception (lines 333-339)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        documents = [{"id": "doc1", "content": "Content 1", "metadata": {}}]

        tool._upsert_batch = Mock(side_effect=Exception("Batch failed"))

        result = tool._batch_upsert_documents(mock_client, "test_group", documents)

        self.assertEqual(result["errors"], 1)
        self.assertEqual(len(result["error_details"]), 1)
        self.assertIn("Batch failed", result["error_details"][0]["error"])

    def test_batch_upsert_documents_with_error_details(self):
        """Test batch upsert accumulating error details (lines 330-331)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        documents = [{"id": "doc1", "content": "Content 1", "metadata": {}}]

        mock_batch_result = {
            "upserted": 0,
            "skipped": 0,
            "errors": 1,
            "error_details": [{"error": "Individual document error"}]
        }
        tool._upsert_batch = Mock(return_value=mock_batch_result)

        result = tool._batch_upsert_documents(mock_client, "test_group", documents)

        self.assertEqual(result["errors"], 1)
        self.assertEqual(len(result["error_details"]), 1)
        self.assertIn("Individual document error", result["error_details"][0]["error"])

    def test_upsert_batch_with_mock_client(self):
        """Test single batch upsert with mock client (lines 356-363)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        mock_client._is_mock = True

        batch = [{"id": "doc1", "content": "Content", "metadata": {}}]
        result = tool._upsert_batch(mock_client, "test_group", batch)

        self.assertEqual(result["upserted"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["errors"], 0)
        self.assertTrue(result.get("mock", False))

    def test_upsert_batch_with_real_client_success(self):
        """Test single batch upsert with real Zep client (lines 365-384)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        # Mock real Zep client (without _is_mock attribute)
        mock_client = Mock()
        del mock_client._is_mock  # Ensure no _is_mock attribute

        # Mock Document class and upsert result
        mock_document_class = Mock()
        mock_zep_doc = Mock()
        mock_document_class.return_value = mock_zep_doc
        mock_client.group.add_documents.return_value = {"added": 1}

        batch = [{"id": "doc1", "content": "Content", "metadata": {"key": "value"}}]

        with patch('linkedin_agent.tools.upsert_to_zep_group.Document',
                  mock_document_class):
            result = tool._upsert_batch(mock_client, "test_group", batch)

        self.assertEqual(result["upserted"], 1)
        self.assertEqual(result["errors"], 0)
        mock_client.group.add_documents.assert_called_once()

    def test_upsert_batch_with_real_client_exception(self):
        """Test single batch upsert with real client exception (lines 386-392)."""
        tool = self.UpsertToZepGroup(entities=self.sample_entities)

        mock_client = Mock()
        del mock_client._is_mock  # Real client simulation

        batch = [{"id": "doc1", "content": "Content", "metadata": {}}]

        with patch('linkedin_agent.tools.upsert_to_zep_group.Document',
                  side_effect=Exception("Document creation failed")):
            result = tool._upsert_batch(mock_client, "test_group", batch)

        self.assertEqual(result["upserted"], 0)
        self.assertEqual(result["errors"], 1)
        self.assertIn("Document creation failed", result["error_details"][0])

    def test_mock_zep_client_initialization(self):
        """Test MockZepClient class (lines 395-400)."""
        from importlib import reload
        import sys
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..',
                               'linkedin_agent', 'tools', 'upsert_to_zep_group.py')
        spec = importlib.util.spec_from_file_location("upsert_to_zep_group", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mock_client = module.MockZepClient()
        self.assertTrue(mock_client._is_mock)
        self.assertIsNotNone(mock_client.group)

    def test_mock_group_client_methods(self):
        """Test MockGroupClient methods (lines 406-414)."""
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..',
                               'linkedin_agent', 'tools', 'upsert_to_zep_group.py')
        spec = importlib.util.spec_from_file_location("upsert_to_zep_group", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        mock_group = module.MockGroupClient()

        # Test get method raises exception
        with self.assertRaises(Exception):
            mock_group.get("test_group")

        # Test add method
        result = mock_group.add("test_group", "Test Name", "Description", {})
        self.assertEqual(result["id"], "test_group")
        self.assertEqual(result["name"], "Test Name")

        # Test add_documents method
        result = mock_group.add_documents("test_group", ["doc1", "doc2"])
        self.assertEqual(result["added"], 2)

    def test_integration_with_profile_identifier_and_batching(self):
        """Test complete integration with profile identifier and batching."""
        # Create more entities to test batching
        large_entities = []
        for i in range(75):  # More than one batch
            large_entities.append({
                "id": f"urn:li:activity:{i}",
                "text": f"Content {i}",
                "type": "post",
                "metrics": {"likes": i}
            })

        with patch('linkedin_agent.tools.upsert_to_zep_group.load_environment') as mock_load_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_required_env_var') as mock_get_env, \
             patch('linkedin_agent.tools.upsert_to_zep_group.get_config_value') as mock_get_config:

            mock_get_env.return_value = "test-api-key"
            mock_get_config.side_effect = lambda key, default: {
                "linkedin.zep.group_prefix": "linkedin",
                "linkedin.zep.collection_name": "linkedin_content"
            }.get(key, default)

            tool = self.UpsertToZepGroup(
                entities=large_entities,
                profile_identifier="alex_hormozi",
                content_type="posts",
                batch_size=30
            )

            # Mock all dependencies
            mock_client = Mock()
            mock_client._is_mock = True
            tool._initialize_zep_client = Mock(return_value=mock_client)
            tool._create_or_find_group = Mock(return_value={
                "group_id": "linkedin_alex_hormozi_posts",
                "created": True,
                "collection": "linkedin_content"
            })
            tool._batch_upsert_documents = Mock(return_value={
                "upserted": 75,
                "skipped": 0,
                "errors": 0,
                "error_details": []
            })

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["group_id"], "linkedin_alex_hormozi_posts")
            self.assertEqual(result_data["upsert_results"]["upserted"], 75)
            self.assertEqual(result_data["batch_info"]["total_batches"], 3)  # 75 / 30 = 2.5 -> 3 batches
            self.assertEqual(result_data["batch_info"]["batch_size"], 30)
            self.assertEqual(result_data["batch_info"]["total_documents"], 75)


if __name__ == '__main__':
    unittest.main()