"""
Comprehensive test suite for ProcessSummaryWorkflow - targeting 100% coverage.
Tests the complete 4-step workflow orchestration with proper mocking.
"""

import sys
import os
import json
import unittest
from unittest.mock import MagicMock, patch, Mock

# Create properly configured mock modules
mock_env_loader = MagicMock()
mock_env_loader.get_required_env_var = MagicMock(return_value="mock_value")
mock_env_loader.get_optional_env_var = MagicMock(return_value="mock_value")

mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'env_loader': mock_env_loader,
    'openai': MagicMock(),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'googleapiclient': MagicMock(),
    'googleapiclient.discovery': MagicMock(),
    'googleapiclient.http': MagicMock(),
    'google.oauth2': MagicMock(),
    'google.oauth2.service_account': MagicMock(),
}

# First set up the mocks in sys.modules (without context manager to keep them persistent)
sys.modules.update(mock_modules)

class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field

# Import the tool - this will work because we're patching at the test method level
from summarizer_agent.tools import process_summary_workflow


class TestProcessSummaryWorkflowComprehensive(unittest.TestCase):
    """Comprehensive test suite achieving 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_video_id = "test_video_123"
        self.test_transcript_ref = "transcripts/test_video_123"
        self.test_video_metadata = {
            "title": "How to Scale Your Business",
            "published_at": "2023-09-15T10:00:00Z",
            "channel_id": "UC1234567890"
        }
        self.test_tags = ["coaching", "business", "automation"]

    @patch('summarizer_agent.tools.process_summary_workflow.SaveSummaryRecordEnhanced')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortSummaryToDrive')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_successful_complete_workflow(self, mock_gen, mock_zep, mock_drive, mock_record):
        """Test successful workflow execution through all 4 steps (lines 75-148)."""
        # Mock Step 1: GenerateShortSummary - must return the exact fields the tool expects
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1", "Insight 2", "Insight 3"],
            "key_concepts": ["Concept A", "Concept B"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300},
            "video_id": self.test_video_id
        })

        # Mock Step 2: StoreShortInZep - must return zep_doc_id, collection, rag_refs
        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": [
                {"type": "transcript_drive", "ref": self.test_transcript_ref}
            ]
        })

        # Mock Step 3: StoreShortSummaryToDrive - must return short_drive_id
        mock_drive_instance = MagicMock()
        mock_drive.return_value = mock_drive_instance
        mock_drive_instance.run.return_value = json.dumps({
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4"
        })

        # Mock Step 4: SaveSummaryRecordEnhanced - must return summary_doc_ref
        mock_record_instance = MagicMock()
        mock_record.return_value = mock_record_instance
        mock_record_instance.run.return_value = json.dumps({
            "summary_doc_ref": f"summaries/{self.test_video_id}"
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata,
            title="How to Scale Your Business",
            tags=self.test_tags
        )

        result = tool.run()
        data = json.loads(result)

        # Verify workflow completion
        self.assertEqual(data['workflow_status'], 'completed')
        self.assertEqual(len(data['steps_completed']), 4)
        self.assertIn('summary_generation', data['steps_completed'])
        self.assertIn('zep_upsert', data['steps_completed'])
        self.assertIn('drive_storage', data['steps_completed'])
        self.assertIn('firestore_record', data['steps_completed'])

        # Verify final references
        self.assertIn('final_references', data)
        refs = data['final_references']
        self.assertEqual(refs['summary_doc_ref'], f"summaries/{self.test_video_id}")
        self.assertEqual(refs['zep_doc_id'], "summary_test_video_123")
        self.assertEqual(refs['short_drive_id'], "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4")

    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_summary_generation_failure(self, mock_gen):
        """Test workflow failure at step 1 - summary generation (lines 84-91, 150-156)."""
        # Mock summary generation failure
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "error": "Failed to generate summary",
            "message": "Transcript not found"
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error response
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertEqual(len(data['steps_completed']), 1)  # Only summary_generation attempted

    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_zep_upsert_failure(self, mock_gen, mock_zep):
        """Test workflow failure at step 2 - Zep upsert (lines 102-109, 150-156)."""
        # Mock successful summary generation
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        # Mock Zep upsert failure
        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "error": "Zep API error",
            "message": "Connection timeout"
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error at step 2
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertEqual(len(data['steps_completed']), 2)  # summary_generation and zep_upsert attempted
        self.assertIn('summary_generation', data['steps_completed'])

    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortSummaryToDrive')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_drive_storage_failure(self, mock_gen, mock_zep, mock_drive):
        """Test workflow failure at step 3 - Drive storage (lines 113-120, 150-156)."""
        # Mock successful steps 1 and 2
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": []
        })

        # Mock Drive storage failure
        mock_drive_instance = MagicMock()
        mock_drive.return_value = mock_drive_instance
        mock_drive_instance.run.return_value = json.dumps({
            "error": "Drive API error",
            "message": "Quota exceeded"
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error at step 3
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertEqual(len(data['steps_completed']), 3)

    @patch('summarizer_agent.tools.process_summary_workflow.SaveSummaryRecordEnhanced')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortSummaryToDrive')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_firestore_record_failure(self, mock_gen, mock_zep, mock_drive, mock_record):
        """Test workflow failure at step 4 - Firestore record (lines 124-136, 150-156)."""
        # Mock successful steps 1-3
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": []
        })

        mock_drive_instance = MagicMock()
        mock_drive.return_value = mock_drive_instance
        mock_drive_instance.run.return_value = json.dumps({
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4"
        })

        # Mock Firestore record failure
        mock_record_instance = MagicMock()
        mock_record.return_value = mock_record_instance
        mock_record_instance.run.return_value = json.dumps({
            "error": "Firestore error",
            "message": "Permission denied"
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error at step 4
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertEqual(len(data['steps_completed']), 4)

    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_generate_short_summary_helper(self, mock_gen):
        """Test _generate_short_summary helper method (lines 158-174)."""
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata,
            title="Custom Title"
        )

        # Call the helper method directly via run (which calls it)
        result = tool.run()

        # Verify GenerateShortSummary was called with correct parameters
        mock_gen.assert_called_once()
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['transcript_doc_ref'], self.test_transcript_ref)
        self.assertEqual(call_kwargs['title'], "Custom Title")

    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_generate_short_summary_uses_metadata_title(self, mock_gen):
        """Test _generate_short_summary uses video_metadata title when title empty (line 168)."""
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata,
            title=""  # Empty title
        )

        result = tool.run()

        # Verify title from video_metadata was used
        call_kwargs = mock_gen.call_args[1]
        self.assertEqual(call_kwargs['title'], self.test_video_metadata['title'])

    def test_build_rag_references(self):
        """Test _build_rag_references helper method (lines 275-293)."""
        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        rag_refs = tool._build_rag_references()

        # Verify RAG references structure
        self.assertIsInstance(rag_refs, list)
        self.assertEqual(len(rag_refs), 1)
        self.assertEqual(rag_refs[0]['type'], 'transcript_drive')
        self.assertEqual(rag_refs[0]['ref'], self.test_transcript_ref)

    @patch('summarizer_agent.tools.process_summary_workflow.get_required_env_var')
    def test_validate_workflow_requirements_success(self, mock_get_env):
        """Test _validate_workflow_requirements with all vars present (lines 295-317)."""
        # Mock all required env vars are present
        mock_get_env.return_value = "mock_value"

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        # Should not raise exception
        tool._validate_workflow_requirements()

        # Verify all required vars were checked
        self.assertEqual(mock_get_env.call_count, 4)

    @patch('summarizer_agent.tools.process_summary_workflow.get_required_env_var')
    def test_validate_workflow_requirements_missing_vars(self, mock_get_env):
        """Test _validate_workflow_requirements with missing vars (lines 316-317)."""
        # Mock missing environment variables
        mock_get_env.side_effect = Exception("Missing variable")

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        with self.assertRaises(RuntimeError) as context:
            tool._validate_workflow_requirements()

        self.assertIn("Missing required environment variables", str(context.exception))

    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_exception_handling_in_run(self, mock_gen):
        """Test exception handling in main run method (lines 150-156)."""
        # Mock an unexpected exception
        mock_gen.side_effect = Exception("Unexpected error")

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify error is caught and returned
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertIn('Unexpected error', data['error'])

    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortSummaryToDrive')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_store_to_drive_exception_handling(self, mock_gen, mock_zep, mock_drive):
        """Test _store_to_drive exception handling (lines 222-223)."""
        # Mock successful steps 1 and 2
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": []
        })

        # Mock Drive tool initialization failure
        mock_drive.side_effect = Exception("Drive tool initialization failed")

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify exception was caught and error returned
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertIn('Failed to store to Drive', data['error'])

    @patch('summarizer_agent.tools.process_summary_workflow.SaveSummaryRecordEnhanced')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortSummaryToDrive')
    @patch('summarizer_agent.tools.process_summary_workflow.StoreShortInZep')
    @patch('summarizer_agent.tools.process_summary_workflow.GenerateShortSummary')
    def test_save_enhanced_record_exception_handling(self, mock_gen, mock_zep, mock_drive, mock_record):
        """Test _save_enhanced_record exception handling (lines 272-273)."""
        # Mock successful steps 1-3
        mock_gen_instance = MagicMock()
        mock_gen.return_value = mock_gen_instance
        mock_gen_instance.run.return_value = json.dumps({
            "bullets": ["Insight 1"],
            "key_concepts": ["Concept A"],
            "prompt_id": "coach_v1_12345",
            "token_usage": {"input_tokens": 1500, "output_tokens": 300}
        })

        mock_zep_instance = MagicMock()
        mock_zep.return_value = mock_zep_instance
        mock_zep_instance.run.return_value = json.dumps({
            "zep_doc_id": "summary_test_video_123",
            "collection": "autopiloot_guidelines",
            "rag_refs": []
        })

        mock_drive_instance = MagicMock()
        mock_drive.return_value = mock_drive_instance
        mock_drive_instance.run.return_value = json.dumps({
            "short_drive_id": "1BvGjZqX5YK8H3mP9QnRtS7Ua2VwE4"
        })

        # Mock Firestore record tool initialization failure
        mock_record.side_effect = Exception("Record tool initialization failed")

        tool = process_summary_workflow.ProcessSummaryWorkflow(
            video_id=self.test_video_id,
            transcript_doc_ref=self.test_transcript_ref,
            video_metadata=self.test_video_metadata
        )

        result = tool.run()
        data = json.loads(result)

        # Verify exception was caught and error returned
        self.assertIn('error', data)
        self.assertEqual(data['workflow_status'], 'failed')
        self.assertIn('Failed to save enhanced record', data['error'])


if __name__ == '__main__':
    unittest.main()
