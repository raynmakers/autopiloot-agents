#!/usr/bin/env python3
"""
Minimal working tests for save_drive_ingestion_record.py
Focuses on achieving code coverage through proper Firestore mocking
"""

import unittest
import json
import sys
import os
from unittest.mock import patch, Mock
import importlib.util
from datetime import datetime, timezone


class TestSaveDriveIngestionRecordMinimal(unittest.TestCase):
    """Minimal tests for SaveDriveIngestionRecord tool"""

    def test_successful_audit_record_save(self):
        """Test successful saving of audit record to Firestore"""

        # Create proper nested module structure for Google Cloud
        google_module = type('Module', (), {})
        google_cloud_module = type('Module', (), {})
        firestore_module = type('Module', (), {})

        google_module.cloud = google_cloud_module
        google_cloud_module.firestore = firestore_module

        # Create mock Firestore client and operations
        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_collection = Mock()
        mock_doc_ref.set = Mock()
        mock_collection.document.return_value = mock_doc_ref
        mock_client.collection.return_value = mock_collection

        firestore_module.Client = Mock(return_value=mock_client)
        firestore_module.SERVER_TIMESTAMP = "server_timestamp"

        # Create other needed modules
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
        env_loader_module.get_required_env_var = Mock(return_value="test-project-id")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.cloud': google_cloud_module,
            'google.cloud.firestore': firestore_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            # Load module
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/save_drive_ingestion_record.py"
            spec = importlib.util.spec_from_file_location("save_drive_ingestion_record", module_path)
            module = importlib.util.module_from_spec(spec)

            # Execute module
            spec.loader.exec_module(module)

            # Create and run tool with test data
            tool = module.SaveDriveIngestionRecord(
                run_id="test_run_123",
                namespace="test_namespace",
                targets_processed=[
                    {
                        "id": "file_123",
                        "type": "file",
                        "name": "Test Document.pdf",
                        "files_found": 1,
                        "files_processed": 1,
                        "errors": []
                    }
                ],
                ingestion_stats={
                    "files_discovered": 1,
                    "files_processed": 1,
                    "text_extraction_count": 1,
                    "zep_upserted": 1,
                    "chunks_created": 5,
                    "bytes_processed": 1024000
                },
                processing_duration_seconds=15.5,
                sync_interval_minutes=30
            )

            result = tool.run()

            # Verify result
            self.assertIsInstance(result, str)
            result_data = json.loads(result)

            self.assertEqual(result_data["status"], "saved")
            self.assertIn("audit_record_id", result_data)
            self.assertIn("firestore_document_path", result_data)
            self.assertIn("record_summary", result_data)

            # Verify Firestore operations were called
            mock_client.collection.assert_called()
            mock_doc_ref.set.assert_called()

            # Verify record summary content
            summary = result_data["record_summary"]
            self.assertEqual(summary["namespace"], "test_namespace")
            self.assertEqual(summary["files_discovered"], 1)
            self.assertEqual(summary["files_processed"], 1)
            self.assertEqual(summary["zep_documents_upserted"], 1)

    def test_audit_record_preparation(self):
        """Test preparation of comprehensive audit record"""

        # Create modules
        google_module = type('Module', (), {})
        google_cloud_module = type('Module', (), {})
        firestore_module = type('Module', (), {})

        google_module.cloud = google_cloud_module
        google_cloud_module.firestore = firestore_module

        # We don't need to actually call Firestore for this test
        firestore_module.Client = Mock()
        firestore_module.SERVER_TIMESTAMP = "server_timestamp"

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
        env_loader_module.get_required_env_var = Mock(return_value="test-project-id")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.cloud': google_cloud_module,
            'google.cloud.firestore': firestore_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/save_drive_ingestion_record.py"
            spec = importlib.util.spec_from_file_location("save_drive_ingestion_record", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Create tool with comprehensive test data
            tool = module.SaveDriveIngestionRecord(
                run_id="test_run_456",
                namespace="test_namespace",
                targets_processed=[
                    {
                        "id": "folder_123",
                        "type": "folder",
                        "name": "Test Folder",
                        "files_found": 5,
                        "files_processed": 4,
                        "errors": ["permission_error"]
                    }
                ],
                ingestion_stats={
                    "files_discovered": 5,
                    "files_processed": 4,
                    "text_extraction_count": 4,
                    "zep_upserted": 3,
                    "chunks_created": 20,
                    "bytes_processed": 5120000
                },
                errors=[
                    {
                        "type": "permission_error",
                        "severity": "warning",
                        "message": "Access denied to file"
                    },
                    {
                        "type": "processing_error",
                        "severity": "critical",
                        "message": "Failed to extract text"
                    }
                ],
                processing_duration_seconds=45.2,
                checkpoint_data={"last_modified": "2025-01-15T10:00:00Z"},
                sync_interval_minutes=60
            )

            # Test the _prepare_audit_record method
            record_id = "test_record_789"
            audit_record = tool._prepare_audit_record(record_id)

            # Verify record structure
            self.assertEqual(audit_record["record_id"], record_id)
            self.assertEqual(audit_record["run_id"], "test_run_456")
            self.assertEqual(audit_record["namespace"], "test_namespace")
            self.assertEqual(audit_record["agent_type"], "drive_agent")

            # Verify summary statistics
            summary = audit_record["summary"]
            self.assertEqual(summary["targets_configured"], 1)
            self.assertEqual(summary["files_discovered"], 5)
            self.assertEqual(summary["files_processed"], 4)
            self.assertEqual(summary["success_rate_percent"], 80.0)  # 4/5 * 100

            # Verify performance metrics
            performance = audit_record["performance"]
            self.assertEqual(performance["processing_duration_seconds"], 45.2)
            self.assertEqual(performance["sync_interval_minutes"], 60)
            self.assertAlmostEqual(performance["avg_file_processing_seconds"], 45.2 / 4, places=2)

            # Verify error tracking
            errors = audit_record["errors"]
            self.assertEqual(errors["total_errors"], 2)
            self.assertEqual(errors["critical_errors"], 1)
            self.assertIn("permission_error", errors["error_types"])
            self.assertIn("processing_error", errors["error_types"])

            # Verify checkpoint data
            self.assertEqual(audit_record["checkpoint"]["last_modified"], "2025-01-15T10:00:00Z")

            # Verify metadata
            metadata = audit_record["metadata"]
            self.assertEqual(metadata["status"], "completed_with_errors")  # Due to critical error

    def test_error_handling_no_critical_errors(self):
        """Test status determination when no critical errors present"""

        google_module = type('Module', (), {})
        google_cloud_module = type('Module', (), {})
        firestore_module = type('Module', (), {})

        google_module.cloud = google_cloud_module
        google_cloud_module.firestore = firestore_module

        firestore_module.Client = Mock()
        firestore_module.SERVER_TIMESTAMP = "server_timestamp"

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
        env_loader_module.get_required_env_var = Mock(return_value="test-project-id")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.cloud': google_cloud_module,
            'google.cloud.firestore': firestore_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/save_drive_ingestion_record.py"
            spec = importlib.util.spec_from_file_location("save_drive_ingestion_record", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Create tool with no critical errors
            tool = module.SaveDriveIngestionRecord(
                run_id="test_run_clean",
                namespace="test_namespace",
                targets_processed=[],
                ingestion_stats={"files_discovered": 0, "files_processed": 0},
                errors=[
                    {
                        "type": "warning",
                        "severity": "warning",
                        "message": "Minor issue"
                    }
                ]
            )

            record_id = "test_record_clean"
            audit_record = tool._prepare_audit_record(record_id)

            # Should be completed since no critical errors
            self.assertEqual(audit_record["metadata"]["status"], "completed")
            self.assertEqual(audit_record["errors"]["critical_errors"], 0)

    def test_firestore_save_failure(self):
        """Test handling of Firestore save failure"""

        google_module = type('Module', (), {})
        google_cloud_module = type('Module', (), {})
        firestore_module = type('Module', (), {})

        google_module.cloud = google_cloud_module
        google_cloud_module.firestore = firestore_module

        # Mock Firestore client to raise exception
        mock_client = Mock()
        mock_client.collection.side_effect = Exception("Firestore connection failed")
        firestore_module.Client = Mock(return_value=mock_client)

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
        env_loader_module.get_required_env_var = Mock(return_value="test-project-id")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.cloud': google_cloud_module,
            'google.cloud.firestore': firestore_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/save_drive_ingestion_record.py"
            spec = importlib.util.spec_from_file_location("save_drive_ingestion_record", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            tool = module.SaveDriveIngestionRecord(
                run_id="test_run_fail",
                namespace="test_namespace",
                targets_processed=[],
                ingestion_stats={"files_discovered": 0}
            )

            result = tool.run()
            result_data = json.loads(result)

            self.assertEqual(result_data["error"], "save_failed")
            self.assertIn("Failed to save Drive ingestion record", result_data["message"])
            self.assertIn("Firestore connection failed", result_data["message"])

    def test_zero_files_processing_edge_case(self):
        """Test edge case with zero files discovered and processed"""

        google_module = type('Module', (), {})
        google_cloud_module = type('Module', (), {})
        firestore_module = type('Module', (), {})

        google_module.cloud = google_cloud_module
        google_cloud_module.firestore = firestore_module

        mock_client = Mock()
        mock_doc_ref = Mock()
        mock_collection = Mock()
        mock_doc_ref.set = Mock()
        mock_collection.document.return_value = mock_doc_ref
        mock_client.collection.return_value = mock_collection

        firestore_module.Client = Mock(return_value=mock_client)
        firestore_module.SERVER_TIMESTAMP = "server_timestamp"

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
        env_loader_module.get_required_env_var = Mock(return_value="test-project-id")
        env_loader_module.load_environment = Mock()

        loader_module = type('Module', (), {})
        loader_module.load_app_config = Mock(return_value={})
        loader_module.get_config_value = Mock(return_value=None)

        mock_modules = {
            'agency_swarm': agency_swarm_module,
            'agency_swarm.tools': agency_swarm_tools_module,
            'pydantic': pydantic_module,
            'google': google_module,
            'google.cloud': google_cloud_module,
            'google.cloud.firestore': firestore_module,
            'env_loader': env_loader_module,
            'loader': loader_module
        }

        with patch.dict('sys.modules', mock_modules):
            module_path = "/Users/maarten/Projects/16 - autopiloot/agents/autopiloot/drive_agent/tools/save_drive_ingestion_record.py"
            spec = importlib.util.spec_from_file_location("save_drive_ingestion_record", module_path)
            module = importlib.util.module_from_spec(spec)

            spec.loader.exec_module(module)

            # Test with zero files
            tool = module.SaveDriveIngestionRecord(
                run_id="test_run_zero",
                namespace="empty_namespace",
                targets_processed=[],
                ingestion_stats={
                    "files_discovered": 0,
                    "files_processed": 0,
                    "text_extraction_count": 0,
                    "zep_upserted": 0,
                    "chunks_created": 0,
                    "bytes_processed": 0
                }
            )

            audit_record = tool._prepare_audit_record("test_record_zero")

            # Verify success rate calculation with zero files
            self.assertEqual(audit_record["summary"]["success_rate_percent"], 0.0)
            self.assertEqual(audit_record["summary"]["files_discovered"], 0)
            self.assertEqual(audit_record["summary"]["files_processed"], 0)

            # Verify performance metrics handle division by zero
            performance = audit_record["performance"]
            self.assertIsNone(performance["avg_file_processing_seconds"])
            self.assertIsNone(performance["files_per_minute"])


if __name__ == '__main__':
    unittest.main()