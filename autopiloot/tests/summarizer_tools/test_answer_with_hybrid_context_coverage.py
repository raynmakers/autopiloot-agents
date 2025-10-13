"""
Comprehensive test suite for AnswerWithHybridContext tool.
Tests LLM-powered Q&A with hybrid retrieval, context balancing, evidence alignment, and structured outputs.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch
from collections import defaultdict

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools

# Mock openai
mock_openai = MagicMock()
sys.modules['openai'] = mock_openai

# Mock opensearchpy (dependency of hybrid_retrieval)
mock_opensearchpy = MagicMock()
sys.modules['opensearchpy'] = mock_opensearchpy

# Mock httpx (dependency of hybrid_retrieval)
mock_httpx = MagicMock()
sys.modules['httpx'] = mock_httpx

# Mock tiktoken
mock_tiktoken = MagicMock()
sys.modules['tiktoken'] = mock_tiktoken


class TestAnswerWithHybridContext(unittest.TestCase):
    """Test suite for AnswerWithHybridContext tool."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tool after mocks are in place
        import importlib.util
        tool_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'answer_with_hybrid_context.py'
        )
        spec = importlib.util.spec_from_file_location("answer_with_hybrid_context", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.AnswerWithHybridContext

        # Sample test data
        self.test_query = "How do I hire A-players for my SaaS business?"
        self.mock_retrieval_results = [
            {
                "chunk_id": "vid1_chunk_1",
                "video_id": "vid1",
                "title": "Hiring Best Practices",
                "channel_id": "UC123",
                "text": "To hire A-players, focus on attitude over aptitude. Look for self-starters who demonstrate ownership.",
                "tokens": 20,
                "rrf_score": 0.0196,
                "matched_sources": ["zep", "opensearch"],
                "source_count": 2
            },
            {
                "chunk_id": "vid1_chunk_2",
                "video_id": "vid1",
                "title": "Hiring Best Practices",
                "channel_id": "UC123",
                "text": "Use structured interviews with behavioral questions. Ask candidates to describe specific past situations.",
                "tokens": 18,
                "rrf_score": 0.0180,
                "matched_sources": ["zep"],
                "source_count": 1
            },
            {
                "chunk_id": "vid2_chunk_1",
                "video_id": "vid2",
                "title": "Building High-Performance Teams",
                "channel_id": "UC123",
                "text": "Implement a rigorous screening process. Top performers typically have a track record of achievement.",
                "tokens": 19,
                "rrf_score": 0.0165,
                "matched_sources": ["opensearch"],
                "source_count": 1
            }
        ]

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    def test_successful_answer_generation(self, mock_open, mock_yaml_load):
        """Test successful answer generation with citations (lines 195-270)."""
        # Mock settings
        mock_yaml_load.return_value = {
            'llm': {
                'tasks': {
                    'rag_answer_question': {
                        'model': 'gpt-4o',
                        'temperature': 0.2,
                        'max_output_tokens': 2000,
                        'prompt_id': 'rag_qa_v1'
                    }
                }
            }
        }

        # Mock HybridRetrieval
        mock_retrieval_result = {
            "query": self.test_query,
            "results": self.mock_retrieval_results,
            "result_count": 3,
            "sources": {"zep": True, "opensearch": True},
            "source_counts": {"zep": 2, "opensearch": 2},
            "weights": {"semantic": 0.6, "keyword": 0.4},
            "status": "success"
        }

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "answer": "To hire A-players, focus on attitude over aptitude [1]. Use structured interviews with behavioral questions [2].",
            "citations": [
                {
                    "citation_number": 1,
                    "chunk_id": "vid1_chunk_1",
                    "video_id": "vid1",
                    "video_title": "Hiring Best Practices",
                    "source_type": "multi_source"
                },
                {
                    "citation_number": 2,
                    "chunk_id": "vid1_chunk_2",
                    "video_id": "vid1",
                    "video_title": "Hiring Best Practices",
                    "source_type": "semantic"
                }
            ],
            "confidence": "high",
            "limitations": "None identified"
        })
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1500
        mock_response.usage.completion_tokens = 300
        mock_response.usage.total_tokens = 1800

        mock_openai.OpenAI.return_value.chat.completions.create.return_value = mock_response

        # Create tool and mock HybridRetrieval import
        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps(mock_retrieval_result)
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=10,
                max_tokens_per_source=4000
            )

            result = tool.run()
            data = json.loads(result)

        # Assertions
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['query'], self.test_query)
        self.assertIn('answer', data)
        self.assertIn('citations', data)
        self.assertGreater(len(data['citations']), 0)
        self.assertIn('evidence_quality', data)
        self.assertIn('confidence', data['evidence_quality'])

    @patch.dict(os.environ, {})
    def test_missing_openai_api_key(self):
        """Test error when OPENAI_API_KEY is missing (lines 217-221)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'configuration_error')
        self.assertIn('OPENAI_API_KEY', data['message'])

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    def test_retrieval_failure(self, mock_open, mock_yaml_load):
        """Test handling of retrieval failures (lines 244-250)."""
        # Mock settings
        mock_yaml_load.return_value = {
            'llm': {'tasks': {'rag_answer_question': {'model': 'gpt-4o'}}}
        }

        # Mock failed retrieval
        mock_retrieval_result = {
            "error": "no_search_sources",
            "message": "Neither Zep nor OpenSearch configured",
            "query": self.test_query
        }

        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps(mock_retrieval_result)
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=10
            )

            result = tool.run()
            data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'retrieval_failed')

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    def test_no_results_from_retrieval(self, mock_open, mock_yaml_load):
        """Test handling when retrieval returns zero results (lines 252-262)."""
        # Mock settings
        mock_yaml_load.return_value = {
            'llm': {'tasks': {'rag_answer_question': {'model': 'gpt-4o'}}}
        }

        # Mock empty retrieval results
        mock_retrieval_result = {
            "query": self.test_query,
            "results": [],
            "result_count": 0,
            "sources": {"zep": True, "opensearch": True},
            "source_counts": {"zep": 0, "opensearch": 0},
            "status": "success"
        }

        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps(mock_retrieval_result)
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=10
            )

            result = tool.run()
            data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no_results')
        self.assertIn('retrieval_metadata', data)

    def test_estimate_tokens(self):
        """Test token estimation method (lines 77-83)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        # Test with known text
        text = "This is a test sentence with approximately twenty tokens in it for testing purposes."
        estimated_tokens = tool._estimate_tokens(text)

        # Should estimate ~21 tokens (84 chars / 4)
        self.assertGreater(estimated_tokens, 15)
        self.assertLess(estimated_tokens, 30)

    def test_balance_context_per_source(self):
        """Test context balancing to prevent single-source bias (lines 85-130)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        # Test with mixed results
        balanced_results, source_tokens = tool._balance_context_per_source(
            self.mock_retrieval_results,
            max_tokens_per_source=50
        )

        # Should return balanced results
        self.assertGreater(len(balanced_results), 0)
        self.assertLessEqual(len(balanced_results), len(self.mock_retrieval_results))

        # Check token counts are tracked
        self.assertIn("zep", source_tokens)
        self.assertIn("opensearch", source_tokens)
        self.assertIn("both", source_tokens)

        # Multi-source chunks should be prioritized
        multi_source_chunks = [r for r in balanced_results if r.get("source_count", 1) > 1]
        self.assertGreater(len(multi_source_chunks), 0)

    def test_balance_context_prevents_overflow(self):
        """Test that context balancing respects token limits (lines 114-124)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        # Create results that would exceed limit
        large_results = []
        for i in range(10):
            large_results.append({
                "chunk_id": f"chunk_{i}",
                "video_id": "vid1",
                "title": "Test Video",
                "text": "x" * 400,  # ~100 tokens each
                "tokens": 100,
                "rrf_score": 0.01 * (10 - i),
                "matched_sources": ["zep"],
                "source_count": 1
            })

        # Set limit to 250 tokens (should allow ~2-3 chunks)
        balanced_results, source_tokens = tool._balance_context_per_source(
            large_results,
            max_tokens_per_source=250
        )

        # Should respect limit
        self.assertLessEqual(source_tokens["zep"], 250)

    def test_detect_evidence_overlaps(self):
        """Test detection of multi-source evidence (lines 132-166)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        overlap_info = tool._detect_evidence_overlaps(self.mock_retrieval_results)

        # Should detect multi-source chunks
        self.assertEqual(overlap_info["multi_source_count"], 1)  # One chunk has both sources
        self.assertEqual(overlap_info["zep_only_count"], 1)
        self.assertEqual(overlap_info["opensearch_only_count"], 1)
        self.assertIn("vid1_chunk_1", overlap_info["high_confidence_chunks"])
        self.assertGreater(overlap_info["confidence_ratio"], 0.0)

    def test_resolve_conflicts_with_trust_hierarchy(self):
        """Test conflict resolution using trust hierarchy (lines 168-193)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        # Test high confidence scenario (>50% multi-source)
        high_confidence_results = [
            {"chunk_id": "c1", "matched_sources": ["zep", "opensearch"], "source_count": 2},
            {"chunk_id": "c2", "matched_sources": ["zep", "opensearch"], "source_count": 2}
        ]
        guidance = tool._resolve_conflicts_with_trust_hierarchy(high_confidence_results)
        self.assertIn("HIGH CONFIDENCE", guidance)

        # Test moderate confidence scenario (25-50% multi-source)
        moderate_confidence_results = [
            {"chunk_id": "c1", "matched_sources": ["zep", "opensearch"], "source_count": 2},
            {"chunk_id": "c2", "matched_sources": ["zep"], "source_count": 1},
            {"chunk_id": "c3", "matched_sources": ["opensearch"], "source_count": 1}
        ]
        guidance = tool._resolve_conflicts_with_trust_hierarchy(moderate_confidence_results)
        self.assertIn("MODERATE CONFIDENCE", guidance)

        # Test low confidence scenario (<25% multi-source)
        low_confidence_results = [
            {"chunk_id": "c1", "matched_sources": ["zep"], "source_count": 1},
            {"chunk_id": "c2", "matched_sources": ["opensearch"], "source_count": 1},
            {"chunk_id": "c3", "matched_sources": ["zep"], "source_count": 1},
            {"chunk_id": "c4", "matched_sources": ["opensearch"], "source_count": 1}
        ]
        guidance = tool._resolve_conflicts_with_trust_hierarchy(low_confidence_results)
        self.assertIn("LOW CONFIDENCE", guidance)

    def test_build_context_prompt(self):
        """Test prompt construction with balanced context (lines 195-240)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        overlap_info = tool._detect_evidence_overlaps(self.mock_retrieval_results)
        trust_guidance = tool._resolve_conflicts_with_trust_hierarchy(self.mock_retrieval_results)

        prompt = tool._build_context_prompt(
            query=self.test_query,
            results=self.mock_retrieval_results,
            overlap_info=overlap_info,
            trust_guidance=trust_guidance
        )

        # Prompt should include key elements
        self.assertIn(self.test_query, prompt)
        self.assertIn("QUESTION:", prompt)
        self.assertIn("CONTEXT", prompt)
        self.assertIn("INSTRUCTIONS:", prompt)

        # Should include confidence markers
        self.assertIn("🔵🔴", prompt)  # Multi-source marker
        self.assertIn("🔵", prompt)    # Zep marker
        self.assertIn("🔴", prompt)    # OpenSearch marker

        # Should include all chunk information
        for result in self.mock_retrieval_results:
            self.assertIn(result["chunk_id"], prompt)
            self.assertIn(result["text"], prompt)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    def test_structured_output_schema_enforcement(self, mock_open, mock_yaml_load):
        """Test that LLM is called with proper JSON schema (lines 290-320)."""
        # Mock settings
        mock_yaml_load.return_value = {
            'llm': {
                'tasks': {
                    'rag_answer_question': {
                        'model': 'gpt-4o',
                        'temperature': 0.2,
                        'max_output_tokens': 2000,
                        'prompt_id': 'rag_qa_v1'
                    }
                }
            }
        }

        # Mock retrieval
        mock_retrieval_result = {
            "query": self.test_query,
            "results": self.mock_retrieval_results,
            "result_count": 3,
            "sources": {"zep": True, "opensearch": True},
            "source_counts": {"zep": 2, "opensearch": 2},
            "weights": {"semantic": 0.6, "keyword": 0.4},
            "status": "success"
        }

        # Mock OpenAI response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "answer": "Test answer",
            "citations": [],
            "confidence": "moderate",
            "limitations": "Limited context available"
        })
        mock_response.usage = MagicMock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 200
        mock_response.usage.total_tokens = 1200

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps(mock_retrieval_result)
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=10
            )

            result = tool.run()

        # Verify OpenAI was called with structured output format
        call_args = mock_client.chat.completions.create.call_args
        self.assertIn('response_format', call_args[1])
        self.assertEqual(call_args[1]['response_format']['type'], 'json_schema')
        self.assertIn('json_schema', call_args[1]['response_format'])

    def test_channel_filter_passed_to_retrieval(self):
        """Test that channel_id filter is passed to HybridRetrieval (lines 233)."""
        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps({"error": "test"})
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=5,
                channel_id="UC123"
            )

            try:
                tool.run()
            except:
                pass

            # Verify HybridRetrieval was instantiated with channel_id
            call_kwargs = mock_hr_class.call_args[1]
            self.assertEqual(call_kwargs['channel_id'], "UC123")

    def test_date_filters_passed_to_retrieval(self):
        """Test that date range filters are passed to HybridRetrieval (lines 233)."""
        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_instance = MagicMock()
            mock_hr_instance.run.return_value = json.dumps({"error": "test"})
            mock_hr_class.return_value = mock_hr_instance

            tool = self.ToolClass(
                query=self.test_query,
                top_k=5,
                min_published_date="2025-01-01T00:00:00Z",
                max_published_date="2025-12-31T23:59:59Z"
            )

            try:
                tool.run()
            except:
                pass

            # Verify date filters were passed
            call_kwargs = mock_hr_class.call_args[1]
            self.assertEqual(call_kwargs['min_published_date'], "2025-01-01T00:00:00Z")
            self.assertEqual(call_kwargs['max_published_date'], "2025-12-31T23:59:59Z")

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test_key'})
    @patch('yaml.safe_load')
    @patch('builtins.open', create=True)
    def test_exception_handling(self, mock_open, mock_yaml_load):
        """Test general exception handling (lines 325-330)."""
        # Mock settings
        mock_yaml_load.return_value = {
            'llm': {'tasks': {'rag_answer_question': {'model': 'gpt-4o'}}}
        }

        # Mock HybridRetrieval to raise exception
        with patch.object(self.module, 'HybridRetrieval') as mock_hr_class:
            mock_hr_class.side_effect = Exception("Test exception")

            tool = self.ToolClass(
                query=self.test_query,
                top_k=10
            )

            result = tool.run()
            data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'generation_failed')
        self.assertIn('Test exception', data['message'])


if __name__ == '__main__':
    unittest.main()
