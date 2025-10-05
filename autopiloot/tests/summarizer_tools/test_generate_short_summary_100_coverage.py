"""
Comprehensive test suite for GenerateShortSummary tool - targeting 100% coverage.
Tests all paths including LLM integration, transcript retrieval, and parsing logic.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, MagicMock, patch

# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'google': MagicMock(),
    'google.cloud': MagicMock(),
    'google.cloud.firestore': MagicMock(),
    'openai': MagicMock(),
}

# Apply mocks
# First set up the mocks in sys.modules (without context manager to keep them persistent)
sys.modules.update(mock_modules)
# Mock BaseTool and Field
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    return kwargs.get('default', None)

sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'].Field = mock_field

# Import using direct file import to avoid module import errors
import importlib.util
tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'summarizer_agent', 'tools', 'generate_short_summary.py')
spec = importlib.util.spec_from_file_location("generate_short_summary", tool_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

# Register the module so patches can find it
sys.modules['generate_short_summary'] = module
GenerateShortSummary = module.GenerateShortSummary


class TestGenerateShortSummary100Coverage(unittest.TestCase):
    """Comprehensive test suite for GenerateShortSummary achieving 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_transcript_ref = "transcripts/test_video_123"
        self.test_title = "How to Build a Successful Business"

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project',
        'LLM_MODEL': 'gpt-4o',
        'LLM_TEMPERATURE': '0.3'
    })
    @patch('generate_short_summary.OpenAI')
    @patch('generate_short_summary.firestore')
    def test_successful_summary_generation(self, mock_firestore, mock_openai_class):
        """Test successful summary generation with proper parsing (lines 45-139)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript document
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        # Mock video document
        mock_video_doc = MagicMock()
        mock_video_doc.exists = True

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
ACTIONABLE INSIGHTS:
• Build a strong team foundation
• Focus on customer retention
• Implement scalable processes

KEY CONCEPTS:
• Product-market fit
• Customer acquisition cost
• Lifetime value
"""
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        result = tool.run()
        data = json.loads(result)

        # Verify result structure
        self.assertIn('bullets', data)
        self.assertIn('key_concepts', data)
        self.assertIn('prompt_id', data)
        self.assertIn('token_usage', data)
        self.assertIn('video_id', data)

        # Verify parsed content
        self.assertEqual(len(data['bullets']), 3)
        self.assertEqual(len(data['key_concepts']), 3)
        self.assertEqual(data['video_id'], 'test_video_123')

    @patch.dict(os.environ, {}, clear=True)
    def test_missing_openai_api_key(self):
        """Test error when OPENAI_API_KEY is missing (lines 33-37)."""
        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        with self.assertRaises(ValueError) as context:
            tool.run()

        self.assertIn("OPENAI_API_KEY", str(context.exception))

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}, clear=True)
    def test_missing_gcp_project_id(self):
        """Test error when GCP_PROJECT_ID is missing (lines 38-39)."""
        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        with self.assertRaises(ValueError) as context:
            tool.run()

        self.assertIn("GCP_PROJECT_ID", str(context.exception))

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('generate_short_summary.firestore')
    def test_transcript_does_not_exist(self, mock_firestore):
        """Test error when transcript doesn't exist (lines 54-55)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript does NOT exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = False

        mock_db.document.return_value.get.return_value = mock_transcript_doc

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        with self.assertRaises(RuntimeError) as context:
            tool.run()

        self.assertIn("does not exist", str(context.exception))

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('generate_short_summary.firestore')
    def test_video_does_not_exist(self, mock_firestore):
        """Test error when video doesn't exist (lines 64-65)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock transcript exists
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        # Mock video does NOT exist
        mock_video_doc = MagicMock()
        mock_video_doc.exists = False

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        with self.assertRaises(RuntimeError) as context:
            tool.run()

        self.assertIn("does not exist", str(context.exception))

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project',
        'LLM_MODEL': 'gpt-4',
        'LLM_TEMPERATURE': '0.5'
    })
    @patch('generate_short_summary.OpenAI')
    @patch('generate_short_summary.firestore')
    def test_custom_llm_configuration(self, mock_firestore, mock_openai_class):
        """Test custom LLM model and temperature configuration (lines 42-43)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock documents exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = """
ACTIONABLE INSIGHTS:
• Test insight

KEY CONCEPTS:
• Test concept
"""
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        tool.run()

        # Verify LLM was called with custom config
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        self.assertEqual(call_kwargs['model'], 'gpt-4')
        self.assertEqual(call_kwargs['temperature'], 0.5)

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('generate_short_summary.OpenAI')
    @patch('generate_short_summary.firestore')
    def test_summary_without_sections(self, mock_firestore, mock_openai_class):
        """Test handling summary response without proper sections (lines 112-124)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock documents exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Mock OpenAI response without proper formatting
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Just some plain text without sections"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        result = tool.run()
        data = json.loads(result)

        # Should return empty lists when sections not found
        self.assertEqual(len(data['bullets']), 0)
        self.assertEqual(len(data['key_concepts']), 0)

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('generate_short_summary.OpenAI')
    @patch('generate_short_summary.firestore')
    def test_openai_api_failure(self, mock_firestore, mock_openai_class):
        """Test handling of OpenAI API failures (lines 141-142)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock documents exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Mock OpenAI failure
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        with self.assertRaises(RuntimeError) as context:
            tool.run()

        self.assertIn("Failed to generate short summary", str(context.exception))

    @patch.dict(os.environ, {
        'OPENAI_API_KEY': 'test-key',
        'GCP_PROJECT_ID': 'test-project'
    })
    @patch('generate_short_summary.OpenAI')
    @patch('generate_short_summary.firestore')
    def test_prompt_construction(self, mock_firestore, mock_openai_class):
        """Test that prompt is properly constructed with title and transcript (lines 72-93)."""
        # Mock Firestore client
        mock_db = MagicMock()
        mock_firestore.Client.return_value = mock_db

        # Mock documents exist
        mock_transcript_doc = MagicMock()
        mock_transcript_doc.exists = True
        mock_transcript_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'drive_id_txt': 'drive_123'
        }

        mock_video_doc = MagicMock()
        mock_video_doc.exists = True

        def mock_document(doc_ref):
            mock_ref = MagicMock()
            if 'transcripts' in doc_ref:
                mock_ref.get.return_value = mock_transcript_doc
            return mock_ref

        mock_db.document.side_effect = mock_document
        mock_db.collection.return_value.document.return_value.get.return_value = mock_video_doc

        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "ACTIONABLE INSIGHTS:\nKEY CONCEPTS:"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50

        mock_client.chat.completions.create.return_value = mock_response

        tool = GenerateShortSummary(
            transcript_doc_ref=self.test_transcript_ref,
            title=self.test_title
        )

        tool.run()

        # Verify prompt contains title
        call_args = mock_client.chat.completions.create.call_args[1]
        messages = call_args['messages']
        user_message = messages[1]['content']

        self.assertIn(self.test_title, user_message)
        self.assertIn("ACTIONABLE INSIGHTS", user_message)
        self.assertIn("KEY CONCEPTS", user_message)


if __name__ == '__main__':
    unittest.main()
