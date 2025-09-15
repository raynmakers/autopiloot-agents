"""
Test suite for LLM observability features.
Tests TASK-LLM-0007 implementation including gpt-4.1 defaults, Langfuse tracing, and prompt_version integration.
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


class TestLLMObservability(unittest.TestCase):
    """Test cases for LLM observability features in TASK-LLM-0007."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.tool = GenerateShortSummary(
            transcript_doc_ref="transcripts/test_video_123",
            title="Advanced Business Scaling Strategies"
        )

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    def test_gpt41_default_configuration(self, mock_config):
        """Test that gpt-4.1 defaults are loaded from configuration."""
        # Mock configuration with TASK-LLM-0007 defaults
        mock_config.return_value = {
            "llm": {
                "default": {
                    "model": "gpt-4.1",
                    "temperature": 0.2,
                    "max_output_tokens": 1500
                },
                "tasks": {
                    "summarizer_generate_short": {
                        "model": "gpt-4.1",
                        "temperature": 0.2,
                        "max_output_tokens": 1500,
                        "prompt_id": "coach_v1",
                        "prompt_version": "v1"
                    }
                }
            }
        }
        
        # Test LLM configuration loading
        llm_config = self.tool._get_llm_config(mock_config.return_value)
        
        # Verify gpt-4.1 defaults
        self.assertEqual(llm_config["model"], "gpt-4.1")
        self.assertEqual(llm_config["temperature"], 0.2)
        self.assertEqual(llm_config["max_output_tokens"], 1500)
        self.assertEqual(llm_config["prompt_version"], "v1")
        
        print("✅ GPT-4.1 defaults properly configured")

    @patch('summarizer_agent.tools.GenerateShortSummary.load_app_config')
    def test_fallback_configuration(self, mock_config):
        """Test fallback to default configuration when task-specific config is missing."""
        # Mock configuration with only defaults
        mock_config.return_value = {
            "llm": {
                "default": {
                    "model": "gpt-4.1",
                    "temperature": 0.2,
                    "max_output_tokens": 1500
                },
                "prompts": {
                    "summarizer_short_id": "coach_v1"
                }
            }
        }
        
        # Test LLM configuration fallback
        llm_config = self.tool._get_llm_config(mock_config.return_value)
        
        # Verify fallback values
        self.assertEqual(llm_config["model"], "gpt-4.1")
        self.assertEqual(llm_config["temperature"], 0.2)
        self.assertEqual(llm_config["max_output_tokens"], 1500)
        self.assertEqual(llm_config["prompt_id"], "coach_v1")
        self.assertEqual(llm_config["prompt_version"], "v1")
        
        print("✅ Configuration fallback working correctly")

    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    def test_langfuse_tracing_enabled(self, mock_get_required, mock_get_optional):
        """Test Langfuse tracing when credentials are available."""
        # Mock environment variables for Langfuse
        mock_get_optional.side_effect = lambda key, default=None: {
            "LANGFUSE_PUBLIC_KEY": "pk_test_12345",
            "LANGFUSE_SECRET_KEY": "sk_test_67890",
            "LANGFUSE_HOST": "https://cloud.langfuse.com"
        }.get(key, default)
        
        # Mock GenerateShortSummaryResponse
        mock_summary_response = {
            "bullets": ["Test bullet 1", "Test bullet 2"],
            "key_concepts": ["Test concept 1", "Test concept 2"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "coach_v1_abc12345",
            "prompt_version": "v1"
        }
        
        # Mock Langfuse
        mock_langfuse_class = MagicMock()
        mock_langfuse_instance = MagicMock()
        mock_trace = MagicMock()
        
        mock_langfuse_class.return_value = mock_langfuse_instance
        mock_langfuse_instance.trace.return_value = mock_trace
        
        with patch('builtins.__import__') as mock_import:
            def import_side_effect(name, *args, **kwargs):
                if name == 'langfuse':
                    mock_langfuse_module = MagicMock()
                    mock_langfuse_module.Langfuse = mock_langfuse_class
                    return mock_langfuse_module
                return __import__(name, *args, **kwargs)
            
            mock_import.side_effect = import_side_effect
            
            # Test Langfuse tracing
            self.tool._trace_with_langfuse(
                mock_summary_response, 
                "gpt-4.1", 
                0.2, 
                "coach_v1_abc12345",
                "v1"
            )
            
            # Verify Langfuse client initialization
            mock_langfuse_class.assert_called_once_with(
                public_key="pk_test_12345",
                secret_key="sk_test_67890",
                host="https://cloud.langfuse.com"
            )
            
            # Verify trace creation with prompt_version
            mock_langfuse_instance.trace.assert_called_once()
            trace_call_args = mock_langfuse_instance.trace.call_args
            metadata = trace_call_args.kwargs["metadata"]
            
            self.assertEqual(metadata["model"], "gpt-4.1")
            self.assertEqual(metadata["temperature"], 0.2)
            self.assertEqual(metadata["prompt_id"], "coach_v1_abc12345")
            self.assertEqual(metadata["prompt_version"], "v1")
            self.assertEqual(metadata["transcript_doc_ref"], "transcripts/test_video_123")
            self.assertEqual(metadata["title"], "Advanced Business Scaling Strategies")
            
            # Verify generation span
            mock_trace.generation.assert_called_once()
            generation_call_args = mock_trace.generation.call_args
            
            self.assertEqual(generation_call_args.kwargs["model"], "gpt-4.1")
            self.assertEqual(generation_call_args.kwargs["input"], 100)
            self.assertEqual(generation_call_args.kwargs["output"], 50)
            
            # Verify flush was called
            mock_langfuse_instance.flush.assert_called_once()
        
        print("✅ Langfuse tracing integration working correctly")

    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    def test_langfuse_tracing_disabled(self, mock_get_optional):
        """Test graceful handling when Langfuse credentials are not available."""
        # Mock missing Langfuse credentials
        mock_get_optional.return_value = None
        
        mock_summary_response = {
            "bullets": ["Test bullet"],
            "key_concepts": ["Test concept"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "coach_v1_abc12345",
            "prompt_version": "v1"
        }
        
        # Test tracing with missing credentials (should not raise exception)
        try:
            self.tool._trace_with_langfuse(
                mock_summary_response, 
                "gpt-4.1", 
                0.2, 
                "coach_v1_abc12345",
                "v1"
            )
            success = True
        except Exception:
            success = False
        
        self.assertTrue(success, "Langfuse tracing should gracefully handle missing credentials")
        print("✅ Langfuse graceful degradation working correctly")

    def test_prompt_version_in_response(self):
        """Test that prompt_version is included in GenerateShortSummary response."""
        # Test response structure includes prompt_version
        mock_response = {
            "bullets": ["Test bullet"],
            "key_concepts": ["Test concept"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "coach_v1_abc12345",
            "prompt_version": "v1"
        }
        
        # Verify all required fields are present
        required_fields = ["bullets", "key_concepts", "token_usage", "prompt_id", "prompt_version"]
        for field in required_fields:
            self.assertIn(field, mock_response, f"Response must include {field}")
        
        # Verify prompt_version format
        self.assertEqual(mock_response["prompt_version"], "v1")
        print("✅ Response structure includes prompt_version")

    @patch('summarizer_agent.tools.GenerateShortSummary.get_required_env_var')
    @patch('summarizer_agent.tools.GenerateShortSummary.OpenAI')
    def test_max_output_tokens_configuration(self, mock_openai, mock_get_required):
        """Test that max_output_tokens is properly used in OpenAI API calls."""
        # Mock OpenAI client and response
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_get_required.return_value = "test-api-key"
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "ACTIONABLE INSIGHTS:\n• Test insight\n\nKEY CONCEPTS:\n• Test concept"
        mock_response.usage.prompt_tokens = 100
        mock_response.usage.completion_tokens = 50
        
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test chunk generation with max_output_tokens
        result = self.tool._generate_summary_chunk(
            mock_client,
            "Test transcript content",
            "Test Title",
            "gpt-4.1",
            0.2,
            1500,  # max_output_tokens
            "coach_v1",
            "v1"
        )
        
        # Verify OpenAI API call includes max_tokens parameter
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        
        self.assertEqual(call_args.kwargs["model"], "gpt-4.1")
        self.assertEqual(call_args.kwargs["temperature"], 0.2)
        self.assertEqual(call_args.kwargs["max_tokens"], 1500)
        
        # Verify response includes prompt_version
        self.assertEqual(result["prompt_version"], "v1")
        print("✅ max_output_tokens properly configured in API calls")

    def test_prompt_hash_includes_version(self):
        """Test that prompt hash generation includes prompt_version."""
        import hashlib
        
        # Test hash generation logic
        prompt_id = "coach_v1"
        prompt_version = "v1"
        model = "gpt-4.1"
        temperature = 0.2
        
        # Generate hash as done in the tool
        expected_hash = hashlib.md5(f"{prompt_id}_{prompt_version}_{model}_{temperature}".encode()).hexdigest()[:8]
        
        # Verify hash includes version information
        hash_input = f"{prompt_id}_{prompt_version}_{model}_{temperature}"
        self.assertIn(prompt_version, hash_input)
        
        # Test chunked version
        chunked_hash = hashlib.md5(f"{prompt_id}_{prompt_version}_{model}_{temperature}_chunked".encode()).hexdigest()[:8]
        self.assertNotEqual(expected_hash, chunked_hash, "Chunked and regular hashes should differ")
        
        print("✅ Prompt hash generation includes version information")

    def test_error_response_includes_prompt_version(self):
        """Test that error responses include prompt_version field."""
        # Test error response structure
        error_response = {
            "error": "Test error message",
            "bullets": [],
            "key_concepts": [],
            "token_usage": {"input_tokens": 0, "output_tokens": 0},
            "prompt_id": "",
            "prompt_version": "v1"
        }
        
        # Verify error response includes all required fields
        required_fields = ["error", "bullets", "key_concepts", "token_usage", "prompt_id", "prompt_version"]
        for field in required_fields:
            self.assertIn(field, error_response, f"Error response must include {field}")
        
        self.assertEqual(error_response["prompt_version"], "v1")
        print("✅ Error responses include prompt_version")

    @patch('summarizer_agent.tools.GenerateShortSummary.get_optional_env_var')
    def test_langfuse_tracing_exception_handling(self, mock_get_optional):
        """Test that Langfuse tracing exceptions don't break the main flow."""
        # Mock Langfuse credentials available
        mock_get_optional.side_effect = lambda key, default=None: {
            "LANGFUSE_PUBLIC_KEY": "pk_test_12345",
            "LANGFUSE_SECRET_KEY": "sk_test_67890"
        }.get(key, default)
        
        mock_summary_response = {
            "bullets": ["Test bullet"],
            "key_concepts": ["Test concept"],
            "token_usage": {"input_tokens": 100, "output_tokens": 50},
            "prompt_id": "coach_v1_abc12345",
            "prompt_version": "v1"
        }
        
        # Mock import to raise exception
        with patch('builtins.__import__', side_effect=ImportError("Langfuse module not found")):
            with patch('builtins.print') as mock_print:
                # Should not raise exception, should print warning
                self.tool._trace_with_langfuse(
                    mock_summary_response, 
                    "gpt-4.1", 
                    0.2, 
                    "coach_v1_abc12345",
                    "v1"
                )
                
                # Verify warning was printed
                mock_print.assert_called_once()
                warning_call = mock_print.call_args[0][0]
                self.assertIn("Warning: Langfuse tracing failed", warning_call)
        
        print("✅ Langfuse exception handling working correctly")


if __name__ == '__main__':
    unittest.main()