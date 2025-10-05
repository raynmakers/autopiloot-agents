#!/usr/bin/env python3
"""
Working coverage test for upsert_drive_docs_to_zep.py
Uses proper import strategy to ensure actual source code execution for coverage measurement
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
from datetime import datetime, timezone


class TestUpsertDriveDocsToZepCoverageWorking(unittest.TestCase):
    """Working tests for UpsertDriveDocsToZep tool that properly measure coverage"""

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

        # Create datetime and hashlib mocks
        datetime_module = type('Module', (), {})
        datetime_module.datetime = datetime
        datetime_module.timezone = timezone

        hashlib_module = type('Module', (), {})
        mock_hasher = Mock()
        mock_hasher.hexdigest.return_value = 'mock_hash_123'
        hashlib_module.sha256 = Mock(return_value=mock_hasher)

        # Set up environment and config loader mocks
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value='test-api-key')
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={
            'zep': {'namespace': 'test_namespace'}
        })

        # Apply all mocks to sys.modules
        sys.modules['agency_swarm'] = agency_swarm_module
        sys.modules['agency_swarm.tools'] = agency_swarm_tools_module
        sys.modules['pydantic'] = pydantic_module
        sys.modules['datetime'] = datetime_module
        sys.modules['hashlib'] = hashlib_module
        sys.modules['env_loader'] = env_loader_module
        sys.modules['loader'] = loader_module

        # Now import the actual module directly using importlib
        tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'drive_agent', 'tools', 'upsert_drive_docs_to_zep.py')
        spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", tool_path)
        module = importlib.util.module_from_spec(spec)

        # Execute module
        spec.loader.exec_module(module)

        return module.UpsertDriveDocsToZep

    def test_successful_single_document_upsert(self):
        """Test successful single document upsert"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Create tool with single document
        documents = [{
            'file_id': 'test_file_123',
            'name': 'Test Document.pdf',
            'content': 'This is test document content for indexing.',
            'mime_type': 'application/pdf',
            'modified_time': '2023-01-01T10:00:00Z'
        }]

        tool = UpsertDriveDocsToZep(documents=documents)

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('success', result_data)
        self.assertTrue(result_data['success'])
        self.assertIn('upserted_count', result_data)
        self.assertEqual(result_data['upserted_count'], 1)

    def test_multiple_documents_upsert(self):
        """Test multiple documents upsert"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Create tool with multiple documents
        documents = [
            {
                'file_id': 'file_1',
                'name': 'Document 1.txt',
                'content': 'Content of first document.',
                'mime_type': 'text/plain',
                'modified_time': '2023-01-01T10:00:00Z'
            },
            {
                'file_id': 'file_2',
                'name': 'Document 2.docx',
                'content': 'Content of second document.',
                'mime_type': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'modified_time': '2023-01-02T10:00:00Z'
            }
        ]

        tool = UpsertDriveDocsToZep(documents=documents)

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('success', result_data)
        self.assertIn('upserted_count', result_data)
        self.assertEqual(result_data['upserted_count'], 2)

    def test_empty_documents_list(self):
        """Test empty documents list handling"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Create tool with empty documents list
        tool = UpsertDriveDocsToZep(documents=[])

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('success', result_data)
        self.assertIn('upserted_count', result_data)
        self.assertEqual(result_data['upserted_count'], 0)

    def test_document_with_metadata(self):
        """Test document with additional metadata"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Create tool with document containing metadata
        documents = [{
            'file_id': 'meta_file_123',
            'name': 'Meta Document.pdf',
            'content': 'Document with metadata for testing.',
            'mime_type': 'application/pdf',
            'modified_time': '2023-01-01T10:00:00Z',
            'size': 1024,
            'owners': ['user@example.com'],
            'parents': ['parent_folder_id']
        }]

        tool = UpsertDriveDocsToZep(
            documents=documents,
            namespace='custom_namespace'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('success', result_data)
        self.assertTrue(result_data['success'])

    def test_custom_namespace(self):
        """Test custom namespace parameter"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        documents = [{
            'file_id': 'namespace_test',
            'name': 'Namespace Test.txt',
            'content': 'Testing custom namespace.',
            'mime_type': 'text/plain',
            'modified_time': '2023-01-01T10:00:00Z'
        }]

        tool = UpsertDriveDocsToZep(
            documents=documents,
            namespace='test_custom_namespace'
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify results
        self.assertIn('success', result_data)

    def test_batch_size_parameter(self):
        """Test batch size parameter for coverage"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Create multiple documents to test batching
        documents = []
        for i in range(5):
            documents.append({
                'file_id': f'batch_file_{i}',
                'name': f'Batch Document {i}.txt',
                'content': f'Content of batch document {i}.',
                'mime_type': 'text/plain',
                'modified_time': '2023-01-01T10:00:00Z'
            })

        tool = UpsertDriveDocsToZep(
            documents=documents,
            batch_size=2
        )

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify batching worked
        self.assertIn('success', result_data)
        self.assertEqual(result_data['upserted_count'], 5)

    def test_document_content_variations(self):
        """Test various document content types"""
        UpsertDriveDocsToZep = self._setup_mocks_and_import()

        # Test different content scenarios
        documents = [
            {
                'file_id': 'empty_content',
                'name': 'Empty.txt',
                'content': '',
                'mime_type': 'text/plain',
                'modified_time': '2023-01-01T10:00:00Z'
            },
            {
                'file_id': 'long_content',
                'name': 'Long.txt',
                'content': 'A' * 1000,  # Long content
                'mime_type': 'text/plain',
                'modified_time': '2023-01-01T10:00:00Z'
            }
        ]

        tool = UpsertDriveDocsToZep(documents=documents)

        # Execute the test
        result = tool.run()
        result_data = json.loads(result)

        # Verify handling of different content types
        self.assertIn('success', result_data)


if __name__ == "__main__":
    unittest.main()