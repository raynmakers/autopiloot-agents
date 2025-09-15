"""
Test suite for GenerateShortSummary tool.
Tests LLM configuration loading, adaptive chunking, Langfuse integration, and summary generation.
"""

import unittest
import json
import os
from unittest.mock import patch, MagicMock, Mock
import sys

# Add the parent directories to sys.path to import the tool
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from summarizer_agent.tools.GenerateShortSummary import GenerateShortSummary
except ImportError:
    # Alternative import path if direct import fails
    import importlib.util
    tool_path = os.path.join(
        os.path.dirname(__file__), 
        '..', 
        'summarizer_agent', 
        'tools', 
        'GenerateShortSummary.py'
    )
    spec = importlib.util.spec_from_file_location("GenerateShortSummary", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    GenerateShortSummary = module.GenerateShortSummary


class TestGenerateShortSummary(unittest.TestCase):
    """Test cases for GenerateShortSummary tool."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = GenerateShortSummary(
            transcript_doc_ref="transcripts/test_video_123",
            title="Building a 7-Figure Business: Key Strategies"
        )
        
        # Sample transcript text for testing
        self.sample_transcript = """
        Welcome to today's episode where we discuss the key strategies for building a successful business.
        First, you need to focus on customer acquisition. The most important thing is to understand your customer's pain points.
        Second, you should implement a systematic approach to sales. This means having a clear sales process.
        Third, you need to build systems that scale. Automation is crucial for growth.
        Remember, consistency beats perfection every time. 
        The key frameworks we'll cover today include the AIDA model for marketing and the SaaS metrics that matter.
        """
        
        # Sample LLM response
        self.sample_llm_response = """
        ACTIONABLE INSIGHTS:
        • Focus on understanding customer pain points before developing solutions
        • Implement a systematic sales process with clear stages and metrics
        • Build automated systems that can scale without constant manual intervention
        • Prioritize consistency over perfection in execution
        • Track key SaaS metrics to measure business performance
        • Use the AIDA model to structure marketing campaigns

        KEY CONCEPTS:
        • Customer acquisition cost optimization
        • Systematic sales process design
        • Business automation and scaling
        • AIDA marketing framework
        • SaaS performance metrics
        """

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.OpenAI')
    @patch('summarizer_agent.tools.GenerateShortSummary.firestore.Client')
    def test_successful_summary_generation(self, mock_firestore, mock_openai, mock_get_optional, mock_get_required, mock_config):
        """Test successful summary generation with proper configuration."""
        # Mock configuration
        mock_config.return_value = {
            "llm": {
                "tasks": {
                    "summarizer_generate_short": {
                        "model": "gpt-4.1",
                        "temperature": 0.2,
                        "prompt_id": "coach_v1"
                    }
                }
            }
        }
        
        # Mock environment variables
        mock_get_required.return_value = "test-api-key"
        mock_get_optional.side_effect = lambda key, default="": ""  # No Langfuse keys
        
        # Mock Firestore client and document
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            'video_id': 'test_video_123',
            'full_text': self.sample_transcript
        }
        mock_db.document.return_value.get.return_value = mock_doc
        
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = self.sample_llm_response
        mock_response.usage.prompt_tokens = 500
        mock_response.usage.completion_tokens = 200
        mock_client.chat.completions.create.return_value = mock_response
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertNotIn("error", data)
        self.assertIn("bullets", data)
        self.assertIn("key_concepts", data)
        self.assertIn("token_usage", data)
        self.assertIn("prompt_id", data)
        
        # Validate structure
        self.assertIsInstance(data["bullets"], list)
        self.assertIsInstance(data["key_concepts"], list)
        self.assertGreater(len(data["bullets"]), 0)
        self.assertGreater(len(data["key_concepts"]), 0)
        
        # Validate token usage
        self.assertEqual(data["token_usage"]["input_tokens"], 500)
        self.assertEqual(data["token_usage"]["output_tokens"], 200)
        
        # Validate prompt ID format
        self.assertTrue(data["prompt_id"].startswith("coach_v1"))

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    def test_fallback_to_default_config(self, mock_get_optional, mock_get_required, mock_config):
        """Test fallback to default LLM configuration when task-specific config is missing."""
        # Mock configuration without task-specific settings
        mock_config.return_value = {
            "llm": {
                "default": {
                    "model": "gpt-4.1",
                    "temperature": 0.3
                },
                "prompts": {
                    "summarizer_short_id": "default_prompt"
                }
            }
        }
        
        mock_get_required.return_value = "test-api-key"
        mock_get_optional.return_value = ""
        
        # Test _get_llm_config method
        config = self.tool._get_llm_config(mock_config.return_value)
        
        self.assertEqual(config["model"], "gpt-4.1")
        self.assertEqual(config["temperature"], 0.3)
        self.assertEqual(config["prompt_id"], "default_prompt")

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.firestore.Client')
    def test_transcript_not_found(self, mock_firestore, mock_get_optional, mock_get_required, mock_config):
        """Test handling when transcript document doesn't exist."""
        # Mock configuration
        mock_config.return_value = {
            "llm": {
                "default": {"model": "gpt-4.1", "temperature": 0.2},
                "prompts": {"summarizer_short_id": "coach_v1"}
            }
        }
        
        mock_get_required.return_value = "test-api-key"
        mock_get_optional.return_value = ""
        
        # Mock Firestore client with non-existent document
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        
        mock_doc = MagicMock()
        mock_doc.exists = False
        mock_db.document.return_value.get.return_value = mock_doc
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("does not exist", data["error"])
        self.assertEqual(data["bullets"], [])
        self.assertEqual(data["key_concepts"], [])

    @patch('summarizer_agent.tools.GenerateShortSummary.tiktoken.encoding_for_model')
    def test_adaptive_chunking(self, mock_encoding):
        """Test adaptive chunking for long transcripts."""
        # Mock encoding
        mock_enc = MagicMock()
        mock_enc.encode.return_value = list(range(100))  # 100 tokens per call
        mock_encoding.return_value = mock_enc
        
        # Create a long transcript
        long_transcript = "This is a test sentence. " * 1000  # Very long transcript
        
        # Test chunking
        chunks = self.tool._chunk_transcript(long_transcript, mock_enc, 500)
        
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            self.assertIsInstance(chunk, str)
            self.assertGreater(len(chunk), 0)

    def test_parse_summary_response(self):
        """Test parsing of structured LLM response."""
        # Test parsing
        bullets, concepts = self.tool._parse_summary_response(self.sample_llm_response)
        
        # Validate bullets
        self.assertGreater(len(bullets), 0)
        self.assertIn("Focus on understanding customer pain points", bullets[0])
        
        # Validate concepts
        self.assertGreater(len(concepts), 0)
        self.assertIn("Customer acquisition cost optimization", concepts[0])

    def test_deduplicate_items(self):
        """Test deduplication functionality."""
        items_with_duplicates = [
            "Focus on customer needs",
            "Build automated systems",
            "focus on customer needs",  # Duplicate (case insensitive)
            "Track key metrics",
            "Build automated systems",  # Exact duplicate
            ""  # Empty item
        ]
        
        deduplicated = self.tool._deduplicate_items(items_with_duplicates)
        
        self.assertEqual(len(deduplicated), 3)
        self.assertIn("Focus on customer needs", deduplicated)
        self.assertIn("Build automated systems", deduplicated)
        self.assertIn("Track key metrics", deduplicated)

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.OpenAI')
    @patch('summarizer_agent.tools.GenerateShortSummary.firestore.Client')
    def test_openai_api_error(self, mock_firestore, mock_openai, mock_get_optional, mock_get_required, mock_config):
        """Test handling of OpenAI API errors."""
        # Mock configuration
        mock_config.return_value = {
            "llm": {"default": {"model": "gpt-4.1", "temperature": 0.2}, "prompts": {"summarizer_short_id": "coach_v1"}}
        }
        
        mock_get_required.return_value = "test-api-key"
        mock_get_optional.return_value = ""
        
        # Mock Firestore
        mock_db = MagicMock()
        mock_firestore.return_value = mock_db
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {'video_id': 'test', 'full_text': self.sample_transcript}
        mock_db.document.return_value.get.return_value = mock_doc
        
        # Mock OpenAI client to raise exception
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # Run the tool
        result = self.tool.run()
        
        # Parse and validate result
        data = json.loads(result)
        
        self.assertIn("error", data)
        self.assertIn("API Error", data["error"])

    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    def test_langfuse_integration_disabled(self, mock_get_optional):
        """Test that Langfuse integration is skipped when keys are not provided."""
        # Mock missing Langfuse keys
        mock_get_optional.return_value = ""
        
        # Create mock response
        mock_response = {
            "bullets": ["Test bullet"],
            "key_concepts": ["Test concept"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "test_prompt"
        }
        
        # Test that this doesn't raise an exception
        try:
            self.tool._trace_with_langfuse(mock_response, "gpt-4.1", 0.2, "coach_v1")
            # Should complete without error
        except Exception as e:
            self.fail(f"Langfuse tracing should not fail when keys are missing: {e}")

    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    @patch('builtins.__import__')
    def test_langfuse_integration_enabled(self, mock_import, mock_get_optional):
        """Test Langfuse integration when properly configured."""
        # Mock Langfuse keys
        def mock_env_var(key, default=""):
            if key == "LANGFUSE_PUBLIC_KEY":
                return "test-public-key"
            elif key == "LANGFUSE_SECRET_KEY":
                return "test-secret-key"
            elif key == "LANGFUSE_HOST":
                return "https://cloud.langfuse.com"
            return default
        
        mock_get_optional.side_effect = mock_env_var
        
        # Mock Langfuse import and client
        mock_langfuse_module = MagicMock()
        mock_langfuse_class = MagicMock()
        mock_langfuse_module.Langfuse = mock_langfuse_class
        
        def mock_import_side_effect(name, *args, **kwargs):
            if name == 'langfuse':
                return mock_langfuse_module
            return __import__(name, *args, **kwargs)
        
        mock_import.side_effect = mock_import_side_effect
        
        mock_langfuse = MagicMock()
        mock_langfuse_class.return_value = mock_langfuse
        mock_trace = MagicMock()
        mock_langfuse.trace.return_value = mock_trace
        
        # Create mock response
        mock_response = {
            "bullets": ["Test bullet"],
            "key_concepts": ["Test concept"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "test_prompt"
        }
        
        # Test Langfuse integration
        self.tool._trace_with_langfuse(mock_response, "gpt-4.1", 0.2, "coach_v1")
        
        # Verify Langfuse was called
        mock_langfuse_class.assert_called_once()
        mock_langfuse.trace.assert_called_once()
        mock_trace.generation.assert_called_once()
        mock_langfuse.flush.assert_called_once()

    def test_create_summary_prompt(self):
        """Test summary prompt creation."""
        prompt = self.tool._create_summary_prompt(self.sample_transcript, "Test Title")
        
        self.assertIn("Test Title", prompt)
        self.assertIn("ACTIONABLE INSIGHTS:", prompt)
        self.assertIn("KEY CONCEPTS:", prompt)
        self.assertIn(self.sample_transcript, prompt)

    def test_config_with_minimal_settings(self):
        """Test LLM config extraction with minimal settings."""
        minimal_config = {}
        
        config = self.tool._get_llm_config(minimal_config)
        
        # Should use defaults
        self.assertEqual(config["model"], "gpt-4.1")
        self.assertEqual(config["temperature"], 0.2)
        self.assertEqual(config["prompt_id"], "coach_v1")


if __name__ == '__main__':
    unittest.main()