#!/usr/bin/env python3
"""
Minimal working tests for upsert_drive_docs_to_zep.py
Focuses on achieving code coverage through proper Zep client mocking
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
from datetime import datetime, timezone


class TestUpsertDriveDocsToZepMinimal(unittest.TestCase):
    """Minimal tests for UpsertDriveDocsToZep tool"""

    def test_successful_document_upsert_with_mock_client(self):
        """Test successful document upserting with mock Zep client"""

        # Create agency_swarm modules
        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool

        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        # Create env_loader and loader modules
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-zep-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={
            "zep": {
                "namespace": {
                    "drive": "test_namespace"
                }
            }
        })

        # Create zep_python module structure (will return None for testing)
        zep_python_module = type('Module', (), {})
        zep_python_module.ZepClient = Mock(return_value=None)
        zep_python_module.Document = Mock()

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': zep_python_module
        }

        with patch.dict('sys.modules', mock_modules):
            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            # Execute module
            spec.loader.exec_module(module)

            # Create test documents
            test_documents = [
                {
                    "file_id": "drive_file_123",
                    "extracted_text": "This is a test document with some content for processing.",
                    "metadata": {
                        "name": "Test Document.pdf",
                        "mime_type": "application/pdf",
                        "size": "1024",
                        "modifiedTime": "2025-01-15T10:00:00Z",
                        "owner": "test@example.com",
                        "webViewLink": "https://drive.google.com/file/123"
                    },
                    "text_stats": {
                        "word_count": 50,
                        "paragraph_count": 3
                    },
                    "document_metadata": {
                        "extraction_method": "direct_text"
                    }
                }
            ]

            # Create and run tool
            tool = module.UpsertDriveDocsToZep(
                documents=test_documents,
                namespace="test_namespace",
                batch_size=10,
                chunk_size=1000,
                overwrite_existing=False,
                include_file_metadata=True
            )

            result = tool.run()

            # Verify result
            self.assertIsInstance(result, str)
            result_data = json.loads(result)

            self.assertEqual(result_data["namespace"], "test_namespace")
            self.assertIn("processing_stats", result_data)
            self.assertIn("upsert_results", result_data)
            self.assertIn("summary", result_data)

            # Verify processing stats
            stats = result_data["processing_stats"]
            self.assertEqual(stats["total_input_documents"], 1)
            self.assertEqual(stats["total_chunks_created"], 1)
            self.assertEqual(stats["processing_errors"], 0)

            # Verify mock notice
            self.assertIn("notice", result_data)
            self.assertIn("Mock implementation used", result_data["notice"])

    def test_document_chunking_logic(self):
        """Test document chunking for large content"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        zep_python_module = type('Module', (), {})
        zep_python_module.ZepClient = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': zep_python_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Create test with large content that will be chunked
            large_content = "This is a test sentence. " * 100  # Create content larger than chunk_size
            test_documents = [
                {
                    "file_id": "large_file_456",
                    "extracted_text": large_content,
                    "metadata": {
                        "name": "Large Document.docx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                }
            ]

            tool = module.UpsertDriveDocsToZep(
                documents=test_documents,
                chunk_size=500  # Small chunk size to force chunking
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify chunking occurred
            stats = result_data["processing_stats"]
            self.assertGreater(stats["total_chunks_created"], 1)
            self.assertEqual(stats["chunked_documents"], 1)

    def test_document_type_classification(self):
        """Test document type classification based on file extensions"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        zep_python_module = type('Module', (), {})
        zep_python_module.ZepClient = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': zep_python_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Test different file types
            test_docs = [
                {
                    "file_id": "pdf_file",
                    "extracted_text": "PDF content",
                    "metadata": {"name": "document.pdf"}
                },
                {
                    "file_id": "word_file",
                    "extracted_text": "Word content",
                    "metadata": {"name": "document.docx"}
                },
                {
                    "file_id": "text_file",
                    "extracted_text": "Text content",
                    "metadata": {"name": "document.txt"}
                },
                {
                    "file_id": "csv_file",
                    "extracted_text": "CSV content",
                    "metadata": {"name": "data.csv"}
                },
                {
                    "file_id": "html_file",
                    "extracted_text": "HTML content",
                    "metadata": {"name": "page.html"}
                },
                {
                    "file_id": "unknown_file",
                    "extracted_text": "Unknown content",
                    "metadata": {"name": "file.unknown"}
                }
            ]

            tool = module.UpsertDriveDocsToZep(documents=test_docs)

            # Test the document preparation method directly
            for i, doc in enumerate(test_docs):
                chunk = {"content": doc["extracted_text"], "chunk_index": 0, "chunk_count": 1, "is_complete": True}
                zep_doc = tool._prepare_zep_document(doc, chunk)

                expected_types = ["pdf", "word_document", "text_document", "spreadsheet", "web_document", "unknown"]
                self.assertEqual(zep_doc["metadata"]["document_type"], expected_types[i])

    def test_invalid_documents_handling(self):
        """Test handling of invalid or empty documents"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': type('Module', (), {})
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Test with invalid documents
            invalid_docs = [
                {},  # Missing required fields
                {"file_id": "test", "extracted_text": ""},  # Empty content
                {"file_id": "test", "extracted_text": "[ERROR: Could not extract text]"},  # Error content
                {"extracted_text": "missing file_id"}  # Missing file_id
            ]

            tool = module.UpsertDriveDocsToZep(documents=invalid_docs)
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "no_valid_documents")
            self.assertIn("processing_stats", result_data)
            self.assertEqual(result_data["processing_stats"]["processing_errors"], 4)

    def test_no_documents_provided(self):
        """Test handling when no documents are provided"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': type('Module', (), {})
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.UpsertDriveDocsToZep(documents=[])
            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "no_documents")
            self.assertIn("No documents provided for upserting", result_data["message"])

    def test_zep_client_initialization_fallback(self):
        """Test Zep client initialization with import error fallback"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module
            # No zep_python module - will cause ImportError
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.UpsertDriveDocsToZep(
                documents=[{
                    "file_id": "test_file",
                    "extracted_text": "Test content"
                }]
            )

            # Test the _initialize_zep_client method directly
            client = tool._initialize_zep_client("api_key", "base_url")
            self.assertIsNone(client)  # Should return None due to ImportError

    def test_batch_processing_logic(self):
        """Test batch processing with multiple documents"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(return_value="test-api-key")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        zep_python_module = type('Module', (), {})
        zep_python_module.ZepClient = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': zep_python_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Create multiple documents to test batching
            test_docs = []
            for i in range(7):  # Will create 2 batches with batch_size=5
                test_docs.append({
                    "file_id": f"file_{i}",
                    "extracted_text": f"Content for document {i}"
                })

            tool = module.UpsertDriveDocsToZep(
                documents=test_docs,
                batch_size=5
            )

            result = tool.run()
            result_data = json.loads(result)

            # Verify batch processing
            batch_info = result_data["batch_info"]
            self.assertEqual(batch_info["total_batches"], 2)  # 7 docs / 5 batch_size = 2 batches
            self.assertEqual(batch_info["batch_size"], 5)

            upsert_results = result_data["upsert_results"]
            self.assertEqual(upsert_results["batches_processed"], 2)

    def test_environment_error_handling(self):
        """Test handling of environment configuration errors"""

        agency_swarm_module = type('Module', (), {})
        agency_swarm_tools_module = type('Module', (), {})
        agency_swarm_module.tools = agency_swarm_tools_module

        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        agency_swarm_tools_module.BaseTool = MockBaseTool
        pydantic_module = type('Module', (), {})
        pydantic_module.Field = lambda *args, **kwargs: kwargs.get('default', args[0] if args else None)

        # Mock env_loader to raise exception
        env_loader_module = type('Module', (), {})
        env_loader_module.get_required_env_var = Mock(side_effect=Exception("ZEP_API_KEY not found"))
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value={})

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'env_loader': env_loader_module,
            'loader': loader_module,
            'zep_python': type('Module', (), {})
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/upsert_drive_docs_to_zep.py"
            spec = importlib.util.spec_from_file_location("upsert_drive_docs_to_zep", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.UpsertDriveDocsToZep(
                documents=[{"file_id": "test", "extracted_text": "test"}]
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "upsert_error")
            self.assertIn("ZEP_API_KEY not found", result_data["message"])


if __name__ == '__main__':
    unittest.main()