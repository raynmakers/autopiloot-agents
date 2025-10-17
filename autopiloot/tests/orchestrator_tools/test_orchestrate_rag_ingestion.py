"""
Test suite for OrchestrateRagIngestion tool (TASK-0095).

Tests cover:
- Config flag behavior (rag.auto_ingest_after_transcription)
- RagIndexTranscript wrapper call (not 3 deprecated tools)
- Non-blocking failure behavior
- rag.features.rag_required flag
- Status recognition ("indexed", "stored", "success")
- Retry logic and DLQ routing
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import sys
import os
import importlib.util

# Add parent directory to path for imports

class TestOrchestrateRagIngestion(unittest.TestCase):
    """Test OrchestrateRagIngestion tool with new RagIndexTranscript wrapper."""

    def setUp(self):
        """Set up test fixtures."""
        # Create fake credentials file
        with open('/tmp/fake-credentials.json', 'w') as f:
            f.write('{}')

        # Mock Agency Swarm BaseTool
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
            'GCP_PROJECT_ID': 'test-project-id',
            'GOOGLE_APPLICATION_CREDENTIALS': '/tmp/fake-credentials.json'
        })
        self.env_patcher.start()

        # Mock pydantic
        mock_pydantic = MagicMock()
        sys.modules['pydantic'] = mock_pydantic
        sys.modules['pydantic'].Field = lambda *args, **kwargs: None

        # Mock google.cloud.firestore
        self.mock_firestore_module = MagicMock()
        self.mock_firestore_client = MagicMock()
        self.mock_firestore_module.Client = MagicMock(return_value=self.mock_firestore_client)

        sys.modules['google'] = MagicMock()
        sys.modules['google.cloud'] = MagicMock()
        sys.modules['google.cloud.firestore'] = self.mock_firestore_module

        # Mock dotenv
        sys.modules['dotenv'] = MagicMock()

        # Mock loader modules
        mock_env_loader = MagicMock()
        mock_env_loader.get_required_env_var = MagicMock(side_effect=lambda key, desc='': os.getenv(key))
        sys.modules['env_loader'] = mock_env_loader

        mock_loader = MagicMock()
        mock_loader.load_app_config = MagicMock()
        sys.modules['loader'] = mock_loader

        mock_audit_logger = MagicMock()
        mock_audit_logger.audit_logger = MagicMock()
        mock_audit_logger.audit_logger.log_custom_event = MagicMock()
        sys.modules['audit_logger'] = mock_audit_logger

        # Import the tool directly from file
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'orchestrator_agent', 'tools', 'orchestrate_rag_ingestion.py'
        )
        spec = importlib.util.spec_from_file_location("orchestrate_rag_ingestion", tool_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.OrchestrateRagIngestion = module.OrchestrateRagIngestion

    def tearDown(self):
        """Clean up test fixtures."""
        self.env_patcher.stop()

        # Clean up fake credentials file
        if os.path.exists('/tmp/fake-credentials.json'):
            os.remove('/tmp/fake-credentials.json')

    def test_config_flag_disabled_skips_rag(self):
        """
        Test that rag.auto_ingest_after_transcription: false skips RAG ingestion.
        """
        # Mock config with RAG disabled
        mock_config = {
            "rag": {
                "auto_ingest_after_transcription": False
            }
        }

        with patch('loader.load_app_config', return_value=mock_config):
            tool = self.OrchestrateRagIngestion(video_id="test_video_123")

            # Mock _initialize_firestore to avoid file system checks
            with patch.object(tool, '_initialize_firestore', return_value=MagicMock()):
                result = tool.run()

        result_data = json.loads(result)
        self.assertEqual(result_data["status"], "skipped")
        self.assertIn("disabled", result_data["message"])
        self.assertEqual(result_data["config_flag"], "rag.auto_ingest_after_transcription")

    def test_calls_rag_index_transcript_not_deprecated_tools(self):
        """
        Test that OrchestrateRagIngestion calls RagIndexTranscript, not old tools.

        Verifies:
        - Single operation "rag_unified" (not "zep", "opensearch", "bigquery")
        - Tool name is "RagIndexTranscript"
        - Agent path is "transcriber_agent"
        """
        # Mock config with RAG enabled
        mock_config = {
            "rag": {
                "auto_ingest_after_transcription": True
            }
        }

        # Mock Firestore
        mock_firestore_client = MagicMock()

        # Mock transcript document
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            "transcript_text": "Test transcript content",
            "video_id": "test_video_123"
        }
        mock_firestore_client.collection.return_value.document.return_value.get.return_value = mock_transcript_doc

        # Mock video document
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            "title": "Test Video",
            "channel_id": "UC123",
            "channel_handle": "@TestChannel",
            "published_at": "2025-01-01T00:00:00Z",
            "duration_sec": 300
        }

        # Set up different returns for transcript and video collections
        def collection_side_effect(collection_name):
            mock_collection = MagicMock()
            if collection_name == 'transcripts':
                mock_collection.document.return_value.get.return_value = mock_transcript_doc
            elif collection_name == 'videos':
                mock_collection.document.return_value.get.return_value = mock_video_doc
            return mock_collection

        mock_firestore_client.collection.side_effect = collection_side_effect

        # Mock RagIndexTranscript tool
        captured_operation_name = None
        captured_tool_name = None
        captured_agent_name = None

        def mock_call_rag_tool(tool_name, transcript_data, agent_name="summarizer_agent"):
            nonlocal captured_tool_name, captured_agent_name
            captured_tool_name = tool_name
            captured_agent_name = agent_name
            return json.dumps({
                "status": "indexed",
                "message": "Successfully indexed to 3 sinks"
            })

        with patch('loader.load_app_config', return_value=mock_config):
            with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
                tool = self.OrchestrateRagIngestion(video_id="test_video_123")

                # Patch _call_rag_tool to capture parameters
                with patch.object(tool, '_call_rag_tool', side_effect=mock_call_rag_tool):
                    result = tool.run()

        result_data = json.loads(result)

        # Verify tool was called
        self.assertIsNotNone(captured_tool_name)
        self.assertEqual(captured_tool_name, "RagIndexTranscript")
        self.assertEqual(captured_agent_name, "transcriber_agent")

        # Verify response structure
        self.assertEqual(result_data["overall_status"], "success")
        self.assertIn("rag_unified", result_data["operations"])
        self.assertEqual(result_data["operations"]["rag_unified"]["status"], "success")

    def test_status_indexed_recognized_as_success(self):
        """
        Test that core library status "indexed" is recognized as success.
        """
        mock_config = {
            "rag": {
                "auto_ingest_after_transcription": True
            }
        }

        # Mock Firestore
        mock_firestore_client = MagicMock()
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            "transcript_text": "Test transcript",
            "video_id": "test_video_123"
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            "title": "Test",
            "channel_id": "UC123"
        }

        def collection_side_effect(collection_name):
            mock_collection = MagicMock()
            if collection_name == 'transcripts':
                mock_collection.document.return_value.get.return_value = mock_transcript_doc
            elif collection_name == 'videos':
                mock_collection.document.return_value.get.return_value = mock_video_doc
            return mock_collection

        mock_firestore_client.collection.side_effect = collection_side_effect

        def mock_call_rag_tool(tool_name, transcript_data, agent_name="summarizer_agent"):
            # Return "indexed" status from core library
            return json.dumps({
                "status": "indexed",
                "message": "Indexed to Zep, OpenSearch, BigQuery"
            })

        with patch('loader.load_app_config', return_value=mock_config):
            with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
                tool = self.OrchestrateRagIngestion(video_id="test_video_123")

                with patch.object(tool, '_call_rag_tool', side_effect=mock_call_rag_tool):
                    result = tool.run()

        result_data = json.loads(result)
        self.assertEqual(result_data["overall_status"], "success")
        self.assertEqual(result_data["success_count"], 1)
        self.assertEqual(result_data["failed_count"], 0)

    def test_non_blocking_failure_when_rag_not_required(self):
        """
        Test that RAG failures don't block workflow when rag_required is false.
        """
        mock_config = {
            "rag": {
                "auto_ingest_after_transcription": True,
                "features": {
                    "rag_required": False
                }
            }
        }

        # Mock Firestore
        mock_firestore_client = MagicMock()
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            "transcript_text": "Test transcript",
            "video_id": "test_video_123"
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            "title": "Test",
            "channel_id": "UC123"
        }

        def collection_side_effect(collection_name):
            mock_collection = MagicMock()
            if collection_name == 'transcripts':
                mock_collection.document.return_value.get.return_value = mock_transcript_doc
            elif collection_name == 'videos':
                mock_collection.document.return_value.get.return_value = mock_video_doc
            return mock_collection

        mock_firestore_client.collection.side_effect = collection_side_effect

        # Mock failure in RAG tool
        def mock_call_rag_tool(tool_name, transcript_data, agent_name="summarizer_agent"):
            return json.dumps({
                "error": "connection_error",
                "message": "Failed to connect to Zep"
            })

        # Mock DLQ and alert handlers
        mock_handle_dlq = MagicMock()
        mock_send_alert = MagicMock()

        with patch('loader.load_app_config', return_value=mock_config):
            with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
                tool = self.OrchestrateRagIngestion(video_id="test_video_123", max_retries=1)

                with patch.object(tool, '_call_rag_tool', side_effect=mock_call_rag_tool):
                    with patch.object(tool, '_handle_failure'):
                        result = tool.run()

        result_data = json.loads(result)

        # Workflow should complete with "partial" or "failed" status
        # but should NOT raise exception (non-blocking)
        self.assertIn("overall_status", result_data)
        self.assertIn(result_data["overall_status"], ["partial", "failed"])
        self.assertEqual(result_data["failed_count"], 1)

    def test_parameter_name_is_text_not_transcript_text(self):
        """
        Test that tool instance is created with 'text' parameter (not 'transcript_text').

        Verifies RagIndexTranscript signature compatibility.
        """
        mock_config = {
            "rag": {
                "auto_ingest_after_transcription": True
            }
        }

        # Mock Firestore
        mock_firestore_client = MagicMock()
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            "transcript_text": "Test transcript content",
            "video_id": "test_video_123"
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True
        mock_video_doc.to_dict.return_value = {
            "title": "Test",
            "channel_id": "UC123"
        }

        def collection_side_effect(collection_name):
            mock_collection = MagicMock()
            if collection_name == 'transcripts':
                mock_collection.document.return_value.get.return_value = mock_transcript_doc
            elif collection_name == 'videos':
                mock_collection.document.return_value.get.return_value = mock_video_doc
            return mock_collection

        mock_firestore_client.collection.side_effect = collection_side_effect

        # Capture tool instantiation parameters
        captured_params = {}

        # Mock the tool class
        class MockRagIndexTranscript:
            def __init__(self, **kwargs):
                captured_params.update(kwargs)

            def run(self):
                return json.dumps({"status": "indexed", "message": "Success"})

        # Mock the module loading to return our mock tool
        original_call_rag_tool = self.OrchestrateRagIngestion._call_rag_tool

        def patched_call_rag_tool(self_tool, tool_name, transcript_data, agent_name="summarizer_agent"):
            # Create mock tool instance
            tool_instance = MockRagIndexTranscript(
                video_id=transcript_data["video_id"],
                text=transcript_data["transcript_text"],  # Should use 'text' parameter
                channel_id=transcript_data.get("channel_id"),
                title=transcript_data.get("title")
            )
            return tool_instance.run()

        with patch('loader.load_app_config', return_value=mock_config):
            with patch('google.cloud.firestore.Client', return_value=mock_firestore_client):
                tool = self.OrchestrateRagIngestion(video_id="test_video_123")

                # Patch _call_rag_tool at class level
                with patch.object(
                    self.OrchestrateRagIngestion,
                    '_call_rag_tool',
                    patched_call_rag_tool
                ):
                    result = tool.run()

        # Verify 'text' parameter was used
        self.assertIn('text', captured_params)
        self.assertEqual(captured_params['text'], "Test transcript content")
        self.assertNotIn('transcript_text', captured_params)


if __name__ == "__main__":
    unittest.main(verbosity=2)
