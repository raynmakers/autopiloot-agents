"""
Test suite for ProcessSummaryWorkflow tool.
Tests end-to-end summary processing workflow with Zep GraphRAG integration.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.ProcessSummaryWorkflow import ProcessSummaryWorkflow
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'ProcessSummaryWorkflow.py'
    )
    spec = importlib.util.spec_from_file_location("ProcessSummaryWorkflow", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    ProcessSummaryWorkflow = module.ProcessSummaryWorkflow


class TestProcessSummaryWorkflow(unittest.TestCase):
    """Test cases for ProcessSummaryWorkflow tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.test_video_metadata = {
            "title": "How to Scale Your Business Without Burnout - Complete Guide",
            "published_at": "2023-09-15T10:30:00Z",
            "channel_id": "UC1234567890"
        }
        
        self.workflow = ProcessSummaryWorkflow(
            video_id="test_video_123",
            transcript_doc_ref="transcripts/test_video_123",
            video_metadata=self.test_video_metadata,
            title="How to Scale Your Business Without Burnout",
            tags=["coaching", "business", "automation", "scaling"]
        )
        
        # Mock responses for each step
        self.mock_summary_result = {
            "bullets": [
                "Focus on systematic customer acquisition",
                "Implement automated sales processes",
                "Build scalable business systems"
            ],
            "key_concepts": [
                "Customer Acquisition Cost optimization",
                "Sales funnel automation",
                "Business process scaling"
            ],
            "prompt_id": "coach_v1_12345678",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        }
        
        self.mock_zep_result = {
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": [
                {"type": "transcript_drive", "ref": "transcripts/test_video_123"}
            ]
        }
        
        self.mock_drive_result = {
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4"
        }
        
        self.mock_firestore_result = {
            "summary_doc_ref": "summaries/test_video_123",
            "zep_doc_id": "summary_test_video_123",
            "rag_refs_count": 1,
            "status": "completed"
        }

    def test_successful_workflow_execution(self):
        """Test successful end-to-end workflow execution."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen, \
             patch.object(self.workflow, '_upsert_to_zep') as mock_zep, \
             patch.object(self.workflow, '_store_to_drive') as mock_drive, \
             patch.object(self.workflow, '_save_enhanced_record') as mock_firestore:
            
            # Mock each step's return value
            mock_gen.return_value = json.dumps(self.mock_summary_result)
            mock_zep.return_value = json.dumps(self.mock_zep_result)
            mock_drive.return_value = json.dumps(self.mock_drive_result)
            mock_firestore.return_value = json.dumps(self.mock_firestore_result)
            
            # Run the workflow
            result = self.workflow.run()
            
            # Parse and validate result
            data = json.loads(result)
            
            self.assertNotIn("error", data)
            self.assertEqual(data["workflow_status"], "completed")
            self.assertEqual(len(data["steps_completed"]), 4)
            self.assertIn("summary_generation", data["steps_completed"])
            self.assertIn("zep_upsert", data["steps_completed"])
            self.assertIn("drive_storage", data["steps_completed"])
            self.assertIn("firestore_record", data["steps_completed"])
            
            # Check final references
            refs = data["final_references"]
            self.assertEqual(refs["summary_doc_ref"], "summaries/test_video_123")
            self.assertEqual(refs["zep_doc_id"], "summary_test_video_123")
            self.assertEqual(refs["zep_collection"], "autopiloot_guidelines")
            self.assertEqual(refs["short_drive_id"], "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4")
            self.assertEqual(len(refs["rag_refs"]), 1)
            
            # Verify all steps were called
            mock_gen.assert_called_once()
            mock_zep.assert_called_once()
            mock_drive.assert_called_once()
            mock_firestore.assert_called_once()

    def test_workflow_failure_at_summary_generation(self):
        """Test workflow failure at summary generation step."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen:
            
            # Mock summary generation failure
            mock_gen.return_value = json.dumps({
                "error": "Failed to load transcript document",
                "bullets": None,
                "key_concepts": None
            })
            
            # Run the workflow
            result = self.workflow.run()
            
            # Parse and validate result
            data = json.loads(result)
            
            self.assertIn("error", data)
            self.assertIn("Summary generation failed", data["error"])
            self.assertEqual(data["workflow_status"], "failed")
            self.assertEqual(len(data["steps_completed"]), 1)  # Only summary_generation attempted

    def test_workflow_failure_at_zep_upsert(self):
        """Test workflow failure at Zep upsert step."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen, \
             patch.object(self.workflow, '_upsert_to_zep') as mock_zep:
            
            # Mock successful summary generation
            mock_gen.return_value = json.dumps(self.mock_summary_result)
            
            # Mock Zep upsert failure
            mock_zep.return_value = json.dumps({
                "error": "Zep API connection failed",
                "zep_doc_id": None
            })
            
            # Run the workflow
            result = self.workflow.run()
            
            # Parse and validate result
            data = json.loads(result)
            
            self.assertIn("error", data)
            self.assertIn("Zep upsert failed", data["error"])
            self.assertEqual(data["workflow_status"], "failed")
            self.assertEqual(len(data["steps_completed"]), 2)  # summary_generation and zep_upsert attempted

    def test_workflow_failure_at_drive_storage(self):
        """Test workflow failure at Drive storage step."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen, \
             patch.object(self.workflow, '_upsert_to_zep') as mock_zep, \
             patch.object(self.workflow, '_store_to_drive') as mock_drive:
            
            # Mock successful steps
            mock_gen.return_value = json.dumps(self.mock_summary_result)
            mock_zep.return_value = json.dumps(self.mock_zep_result)
            
            # Mock Drive storage failure
            mock_drive.return_value = json.dumps({
                "error": "Google Drive quota exceeded",
                "short_drive_id": None
            })
            
            # Run the workflow
            result = self.workflow.run()
            
            # Parse and validate result
            data = json.loads(result)
            
            self.assertIn("error", data)
            self.assertIn("Drive storage failed", data["error"])
            self.assertEqual(data["workflow_status"], "failed")
            self.assertEqual(len(data["steps_completed"]), 3)

    def test_workflow_failure_at_firestore_record(self):
        """Test workflow failure at Firestore record creation step."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen, \
             patch.object(self.workflow, '_upsert_to_zep') as mock_zep, \
             patch.object(self.workflow, '_store_to_drive') as mock_drive, \
             patch.object(self.workflow, '_save_enhanced_record') as mock_firestore:
            
            # Mock successful steps
            mock_gen.return_value = json.dumps(self.mock_summary_result)
            mock_zep.return_value = json.dumps(self.mock_zep_result)
            mock_drive.return_value = json.dumps(self.mock_drive_result)
            
            # Mock Firestore record failure
            mock_firestore.return_value = json.dumps({
                "error": "Firestore transaction failed",
                "summary_doc_ref": None
            })
            
            # Run the workflow
            result = self.workflow.run()
            
            # Parse and validate result
            data = json.loads(result)
            
            self.assertIn("error", data)
            self.assertIn("Firestore record creation failed", data["error"])
            self.assertEqual(data["workflow_status"], "failed")
            self.assertEqual(len(data["steps_completed"]), 4)  # All steps attempted

    def test_build_rag_references(self):
        """Test RAG references building functionality."""
        rag_refs = self.workflow._build_rag_references()
        
        self.assertIsInstance(rag_refs, list)
        self.assertGreater(len(rag_refs), 0)
        
        # Check transcript reference is included
        transcript_ref = next((ref for ref in rag_refs if ref["type"] == "transcript_drive"), None)
        self.assertIsNotNone(transcript_ref)
        self.assertEqual(transcript_ref["ref"], "transcripts/test_video_123")

    @patch('summarizer_agent.tools.ProcessSummaryWorkflow.get_required_env_var')
    def test_validate_workflow_requirements(self, mock_get_required):
        """Test workflow requirements validation."""
        # Mock missing environment variable
        mock_get_required.side_effect = Exception("Environment variable not found")
        
        with self.assertRaises(RuntimeError) as context:
            self.workflow._validate_workflow_requirements()
        
        self.assertIn("Missing required environment variables", str(context.exception))

    def test_workflow_step_data_flow(self):
        """Test that data flows correctly between workflow steps."""
        with patch.object(self.workflow, '_generate_short_summary') as mock_gen, \
             patch.object(self.workflow, '_upsert_to_zep') as mock_zep, \
             patch.object(self.workflow, '_store_to_drive') as mock_drive, \
             patch.object(self.workflow, '_save_enhanced_record') as mock_firestore:
            
            # Mock each step's return value
            mock_gen.return_value = json.dumps(self.mock_summary_result)
            mock_zep.return_value = json.dumps(self.mock_zep_result)
            mock_drive.return_value = json.dumps(self.mock_drive_result)
            mock_firestore.return_value = json.dumps(self.mock_firestore_result)
            
            # Run the workflow
            result = self.workflow.run()
            
            # Verify data was passed correctly between steps
            
            # Check Zep upsert received summary data
            zep_call_args = mock_zep.call_args[0][0]  # First argument (short_summary)
            self.assertEqual(zep_call_args["prompt_id"], "coach_v1_12345678")
            self.assertEqual(len(zep_call_args["bullets"]), 3)
            
            # Check Drive storage received summary data
            drive_call_args = mock_drive.call_args[0][0]  # First argument (short_summary)
            self.assertEqual(len(drive_call_args["key_concepts"]), 3)
            
            # Check Firestore record received all references
            firestore_call_args = mock_firestore.call_args
            refs_arg = firestore_call_args[0][1]  # zep_data argument
            self.assertEqual(refs_arg["zep_doc_id"], "summary_test_video_123")

    def test_workflow_with_empty_tags(self):
        """Test workflow execution with empty tags list."""
        workflow = ProcessSummaryWorkflow(
            video_id="test_video_123",
            transcript_doc_ref="transcripts/test_video_123",
            video_metadata=self.test_video_metadata,
            title="Test Video",
            tags=[]  # Empty tags
        )
        
        # Should not raise any errors during initialization
        self.assertEqual(len(workflow.tags), 0)

    def test_workflow_with_minimal_metadata(self):
        """Test workflow execution with minimal video metadata."""
        minimal_metadata = {
            "title": "Basic Video",
            "published_at": "",
            "channel_id": ""
        }
        
        workflow = ProcessSummaryWorkflow(
            video_id="test_video_123",
            transcript_doc_ref="transcripts/test_video_123",
            video_metadata=minimal_metadata
        )
        
        # Should handle minimal metadata gracefully
        self.assertEqual(workflow.video_metadata["title"], "Basic Video")
        self.assertEqual(workflow.video_metadata["published_at"], "")


if __name__ == '__main__':
    unittest.main()