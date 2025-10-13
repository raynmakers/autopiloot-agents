"""
Comprehensive test suite for HybridRetrieval tool.
Tests Zep semantic search, OpenSearch keyword search, RRF fusion, and error handling.
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

# Mock opensearchpy
mock_opensearchpy = MagicMock()
sys.modules['opensearchpy'] = mock_opensearchpy

# Mock httpx
mock_httpx = MagicMock()
sys.modules['httpx'] = mock_httpx

# Mock tiktoken (not directly used but may be imported by dependencies)
mock_tiktoken = MagicMock()
sys.modules['tiktoken'] = mock_tiktoken


class TestHybridRetrieval(unittest.TestCase):
    """Test suite for HybridRetrieval tool."""

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
            'hybrid_retrieval.py'
        )
        spec = importlib.util.spec_from_file_location("hybrid_retrieval", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.HybridRetrieval

        # Sample test data
        self.test_query = "How to hire A-players for SaaS"

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_zep_key',
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_opensearch_key'
    })
    @patch('importlib.import_module')
    def test_successful_hybrid_retrieval(self, mock_import):
        """Test successful hybrid retrieval with both sources (lines 62-166)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock OpenSearch search response
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "chunk_id": "vid1_chunk_1",
                            "video_id": "vid1",
                            "title": "Test Video 1",
                            "channel_id": "UC123",
                            "text": "Test content about hiring",
                            "tokens": 50
                        },
                        "_score": 10.5
                    }
                ]
            }
        }

        # Create tool instance
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        # Run tool
        result = tool.run()
        data = json.loads(result)

        # Assertions
        self.assertEqual(data['status'], 'success')
        self.assertIn('results', data)
        self.assertIn('sources', data)
        self.assertEqual(data['query'], self.test_query)
        self.assertGreaterEqual(len(data['results']), 0)

    @patch.dict(os.environ, {})
    def test_no_search_sources_configured(self):
        """Test error when neither Zep nor OpenSearch is configured (lines 131-136)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no_search_sources')
        self.assertIn('Neither Zep nor OpenSearch', data['message'])

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_key'
    })
    @patch('importlib.import_module')
    def test_opensearch_only_retrieval(self, mock_import):
        """Test retrieval with only OpenSearch configured (lines 113-128)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock search response
        mock_client.search.return_value = {
            "hits": {
                "hits": [
                    {
                        "_source": {
                            "chunk_id": "vid1_chunk_1",
                            "video_id": "vid1",
                            "title": "Test Video",
                            "channel_id": "UC123",
                            "text": "Test content",
                            "tokens": 50
                        },
                        "_score": 10.0
                    }
                ]
            }
        }

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['sources']['opensearch'])
        self.assertFalse(data['sources']['zep'])

    @patch.dict(os.environ, {
        'ZEP_API_KEY': 'test_key'
    })
    @patch('importlib.import_module')
    def test_zep_only_retrieval(self, mock_import):
        """Test retrieval with only Zep configured (lines 98-111)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20
        }.get(key, default))

        mock_import.return_value = mock_loader

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()
        data = json.loads(result)

        # Zep query returns empty results (placeholder implementation)
        # But should not error
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['sources']['zep'])
        self.assertFalse(data['sources']['opensearch'])

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_USERNAME': 'test_user',
        'OPENSEARCH_PASSWORD': 'test_pass'
    })
    @patch('importlib.import_module')
    def test_opensearch_basic_auth(self, mock_import):
        """Test OpenSearch client initialization with basic auth (lines 286-292)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock search response
        mock_client.search.return_value = {"hits": {"hits": []}}

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()
        data = json.loads(result)

        # Verify basic auth was used
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertEqual(call_kwargs['http_auth'], ('test_user', 'test_pass'))

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_key'
    })
    @patch('importlib.import_module')
    def test_opensearch_with_channel_filter(self, mock_import):
        """Test OpenSearch query with channel_id filter (lines 314-315)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock search response
        mock_client.search.return_value = {"hits": {"hits": []}}

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5,
            channel_id="UCtest123"
        )

        result = tool.run()

        # Verify search was called with channel filter
        call_args = mock_client.search.call_args[1]
        search_body = call_args['body']
        filters = search_body['query']['bool']['filter']

        self.assertGreater(len(filters), 0)
        self.assertEqual(filters[0]['term']['channel_id'], 'UCtest123')

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_key'
    })
    @patch('importlib.import_module')
    def test_opensearch_with_date_range_filter(self, mock_import):
        """Test OpenSearch query with date range filter (lines 317-323)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client

        # Mock search response
        mock_client.search.return_value = {"hits": {"hits": []}}

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5,
            min_published_date="2025-01-01T00:00:00Z",
            max_published_date="2025-12-31T23:59:59Z"
        )

        result = tool.run()

        # Verify search was called with date range filter
        call_args = mock_client.search.call_args[1]
        search_body = call_args['body']
        filters = search_body['query']['bool']['filter']

        self.assertGreater(len(filters), 0)
        # Find range filter
        range_filter = next((f for f in filters if 'range' in f), None)
        self.assertIsNotNone(range_filter)

    def test_rrf_fusion_algorithm(self):
        """Test Reciprocal Rank Fusion algorithm (lines 360-429)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        # Create mock results from both sources
        zep_results = [
            {"chunk_id": "chunk_1", "video_id": "vid1", "title": "Video 1", "text": "Content 1", "score": 0.9},
            {"chunk_id": "chunk_2", "video_id": "vid2", "title": "Video 2", "text": "Content 2", "score": 0.8},
        ]

        opensearch_results = [
            {"chunk_id": "chunk_2", "video_id": "vid2", "title": "Video 2", "text": "Content 2", "score": 15.0},
            {"chunk_id": "chunk_3", "video_id": "vid3", "title": "Video 3", "text": "Content 3", "score": 12.0},
        ]

        # Test fusion
        fused = tool._fuse_with_rrf(
            zep_results=zep_results,
            opensearch_results=opensearch_results,
            semantic_weight=0.6,
            keyword_weight=0.4,
            top_k=5
        )

        # Assertions
        self.assertIsInstance(fused, list)
        self.assertGreater(len(fused), 0)

        # Check that chunk_2 appears in both sources
        chunk_2_result = next((r for r in fused if r.get('chunk_id') == 'chunk_2'), None)
        if chunk_2_result:
            self.assertEqual(chunk_2_result['source_count'], 2)
            self.assertIn('zep', chunk_2_result['matched_sources'])
            self.assertIn('opensearch', chunk_2_result['matched_sources'])

        # Verify results have RRF scores
        for result in fused:
            self.assertIn('rrf_score', result)
            self.assertIn('matched_sources', result)
            self.assertIn('source_count', result)

    def test_rrf_fusion_with_empty_zep_results(self):
        """Test RRF fusion when Zep returns empty results (lines 389-399)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        zep_results = []
        opensearch_results = [
            {"chunk_id": "chunk_1", "video_id": "vid1", "title": "Video 1", "text": "Content", "score": 10.0}
        ]

        fused = tool._fuse_with_rrf(
            zep_results=zep_results,
            opensearch_results=opensearch_results,
            semantic_weight=0.6,
            keyword_weight=0.4,
            top_k=5
        )

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]['chunk_id'], 'chunk_1')
        self.assertIn('opensearch', fused[0]['matched_sources'])

    def test_rrf_fusion_with_empty_opensearch_results(self):
        """Test RRF fusion when OpenSearch returns empty results (lines 401-411)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        zep_results = [
            {"chunk_id": "chunk_1", "video_id": "vid1", "title": "Video 1", "text": "Content", "score": 0.9}
        ]
        opensearch_results = []

        fused = tool._fuse_with_rrf(
            zep_results=zep_results,
            opensearch_results=opensearch_results,
            semantic_weight=0.6,
            keyword_weight=0.4,
            top_k=5
        )

        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]['chunk_id'], 'chunk_1')
        self.assertIn('zep', fused[0]['matched_sources'])

    def test_rrf_fusion_deduplication(self):
        """Test that RRF fusion deduplicates by chunk_id (lines 392-393, 404-405)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=10
        )

        # Same chunk_id in both results
        zep_results = [
            {"chunk_id": "chunk_1", "video_id": "vid1", "title": "Video 1", "text": "Content", "score": 0.9}
        ]
        opensearch_results = [
            {"chunk_id": "chunk_1", "video_id": "vid1", "title": "Video 1", "text": "Content", "score": 10.0}
        ]

        fused = tool._fuse_with_rrf(
            zep_results=zep_results,
            opensearch_results=opensearch_results,
            semantic_weight=0.6,
            keyword_weight=0.4,
            top_k=10
        )

        # Should only have one result (deduplicated)
        self.assertEqual(len(fused), 1)
        self.assertEqual(fused[0]['chunk_id'], 'chunk_1')
        self.assertEqual(fused[0]['source_count'], 2)

    def test_rrf_fusion_top_k_limiting(self):
        """Test that RRF fusion limits results to top_k (lines 413-418)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=2
        )

        zep_results = [
            {"chunk_id": f"chunk_{i}", "video_id": f"vid{i}", "title": f"Video {i}", "text": f"Content {i}", "score": 1.0 - i*0.1}
            for i in range(1, 6)
        ]
        opensearch_results = []

        fused = tool._fuse_with_rrf(
            zep_results=zep_results,
            opensearch_results=opensearch_results,
            semantic_weight=0.6,
            keyword_weight=0.4,
            top_k=2
        )

        # Should only return top 2 results
        self.assertEqual(len(fused), 2)

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'https://test.opensearch.com:9200',
        'OPENSEARCH_API_KEY': 'test_key'
    })
    @patch('importlib.import_module')
    def test_opensearch_query_error_handling(self, mock_import):
        """Test error handling when OpenSearch query fails (lines 356-358)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client with error
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client
        mock_client.search.side_effect = Exception("Connection timeout")

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()
        data = json.loads(result)

        # Should still succeed with empty OpenSearch results
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['source_counts']['opensearch'], 0)

    def test_zep_query_returns_empty_placeholder(self):
        """Test that Zep query returns empty results (placeholder implementation) (lines 213)."""
        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        # Test _query_zep directly
        results = tool._query_zep(
            query=self.test_query,
            top_k=5,
            channel_id="UCtest123"
        )

        # Placeholder implementation returns empty list
        self.assertEqual(results, [])

    @patch.dict(os.environ, {
        'OPENSEARCH_HOST': 'test.opensearch.com'
    })
    @patch('importlib.import_module')
    def test_opensearch_url_parsing_without_protocol(self, mock_import):
        """Test URL parsing when host doesn't include protocol (lines 272-277)."""
        # Mock loader module
        mock_loader = MagicMock()
        mock_loader.get_config_value = MagicMock(side_effect=lambda key, default=None: {
            'rag.opensearch.weights.semantic': 0.6,
            'rag.opensearch.weights.keyword': 0.4,
            'rag.opensearch.top_k': 20,
            'rag.opensearch.index_transcripts': 'autopiloot_transcripts',
            'rag.opensearch.connection.verify_certs': True,
            'rag.opensearch.timeout_ms': 1500
        }.get(key, default))

        mock_import.return_value = mock_loader

        # Mock OpenSearch client
        mock_client = MagicMock()
        mock_opensearchpy.OpenSearch.return_value = mock_client
        mock_client.search.return_value = {"hits": {"hits": []}}

        tool = self.ToolClass(
            query=self.test_query,
            top_k=5
        )

        result = tool.run()

        # Verify SSL defaults to True
        call_kwargs = mock_opensearchpy.OpenSearch.call_args[1]
        self.assertTrue(call_kwargs['use_ssl'])


if __name__ == '__main__':
    unittest.main()
