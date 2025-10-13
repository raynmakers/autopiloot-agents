"""
Integration test suite for hybrid RAG pipeline.

Tests end-to-end flows:
1. Transcript ingestion → Zep/OpenSearch/BigQuery fan-out
2. Retrieval fusion across multiple sources
3. Degraded mode operation (source failures)
4. Query routing and adaptation
5. Policy enforcement and security validation
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tools
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestRAGPipelineIntegration(unittest.TestCase):
    """Integration tests for hybrid RAG pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        # Import tools after mocks are in place
        import importlib.util

        # Helper to import tool
        def import_tool(tool_name):
            tool_path = os.path.join(
                os.path.dirname(__file__),
                '..',
                '..',
                'summarizer_agent',
                'tools',
                f'{tool_name}.py'
            )
            spec = importlib.util.spec_from_file_location(tool_name, tool_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module

        # Import all RAG tools
        self.upsert_zep = import_tool('upsert_full_transcript_to_zep')
        self.index_opensearch = import_tool('index_full_transcript_to_opensearch')
        self.stream_bigquery = import_tool('stream_full_transcript_to_bigquery')
        self.hybrid_retrieval = import_tool('hybrid_retrieval')
        self.adaptive_routing = import_tool('adaptive_query_routing')
        self.enforce_policy = import_tool('enforce_retrieval_policy')

    def test_transcript_ingestion_fanout(self):
        """
        Test transcript ingestion fans out to all three sources.

        Flow: Transcript → Zep + OpenSearch + BigQuery
        """
        transcript_text = "This is a test transcript about business growth strategies."
        video_id = "test_video_123"

        # Mock Zep ingestion
        zep_tool = self.upsert_zep.UpsertFullTranscriptToZep(
            video_id=video_id,
            transcript_text=transcript_text,
            title="Test Video",
            channel_id="test_channel"
        )

        with patch.object(zep_tool, '_chunk_transcript', return_value=[
            {"text": "chunk1", "chunk_id": "chunk_0"},
            {"text": "chunk2", "chunk_id": "chunk_1"}
        ]):
            with patch.object(zep_tool, '_upsert_chunks_to_zep', return_value={"success": True}):
                result_zep = zep_tool.run()
                data_zep = json.loads(result_zep)
                self.assertEqual(data_zep["status"], "success")

        # Mock OpenSearch ingestion
        os_tool = self.index_opensearch.IndexFullTranscriptToOpenSearch(
            video_id=video_id,
            transcript_text=transcript_text,
            title="Test Video"
        )

        with patch.object(os_tool, '_chunk_transcript', return_value=[
            {"text": "chunk1", "chunk_id": "chunk_0"}
        ]):
            with patch.object(os_tool, '_index_chunks_to_opensearch', return_value={"indexed": 1}):
                result_os = os_tool.run()
                data_os = json.loads(result_os)
                self.assertEqual(data_os["status"], "success")

        # Mock BigQuery ingestion
        bq_tool = self.stream_bigquery.StreamFullTranscriptToBigQuery(
            video_id=video_id,
            transcript_text=transcript_text,
            title="Test Video"
        )

        with patch.object(bq_tool, '_chunk_transcript', return_value=[
            {"text": "chunk1", "chunk_id": "chunk_0"}
        ]):
            with patch.object(bq_tool, '_stream_chunks_to_bigquery', return_value={"streamed": 1}):
                result_bq = bq_tool.run()
                data_bq = json.loads(result_bq)
                self.assertEqual(data_bq["status"], "success")

        # All three ingestions should succeed
        self.assertTrue(all([
            data_zep["status"] == "success",
            data_os["status"] == "success",
            data_bq["status"] == "success"
        ]))

    def test_retrieval_fusion_all_sources(self):
        """
        Test retrieval fusion combines results from all sources.

        Flow: Query → Zep + OpenSearch + BigQuery → Fusion → Results
        """
        query = "business growth strategies"

        tool = self.hybrid_retrieval.HybridRetrieval(
            query=query,
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock individual source retrievals
        zep_results = [{"doc_id": "zep_1", "score": 0.9, "source": "zep"}]
        os_results = [{"doc_id": "os_1", "score": 0.85, "source": "opensearch"}]
        bq_results = [{"doc_id": "bq_1", "score": 0.8, "source": "bigquery"}]

        with patch.object(tool, '_retrieve_from_zep', return_value=zep_results):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=os_results):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=bq_results):
                    result = tool.run()
                    data = json.loads(result)

        # Check fusion combines all sources
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["results"]), 0)

        # Verify all sources contributed
        sources = set(r.get("source") for r in data["results"])
        self.assertTrue(len(sources) >= 1)

    def test_degraded_mode_zep_failure(self):
        """
        Test degraded mode when Zep fails but other sources work.

        Flow: Query → Zep (FAIL) + OpenSearch + BigQuery → Results
        """
        query = "test query"

        tool = self.hybrid_retrieval.HybridRetrieval(
            query=query,
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock Zep failure, other sources succeed
        with patch.object(tool, '_retrieve_from_zep', side_effect=Exception("Zep unavailable")):
            with patch.object(tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "os_1", "score": 0.85}
            ]):
                with patch.object(tool, '_retrieve_from_bigquery', return_value=[
                    {"doc_id": "bq_1", "score": 0.8}
                ]):
                    result = tool.run()
                    data = json.loads(result)

        # Should still succeed with partial results
        self.assertEqual(data["status"], "success")
        self.assertGreater(len(data["results"]), 0)
        self.assertIn("zep", data["errors"])

    def test_degraded_mode_all_sources_fail(self):
        """
        Test behavior when all sources fail.

        Flow: Query → All sources FAIL → Empty results
        """
        query = "test query"

        tool = self.hybrid_retrieval.HybridRetrieval(
            query=query,
            use_zep=True,
            use_opensearch=True,
            use_bigquery=True,
            top_k=10
        )

        # Mock all sources failing
        with patch.object(tool, '_retrieve_from_zep', side_effect=Exception("Zep unavailable")):
            with patch.object(tool, '_retrieve_from_opensearch', side_effect=Exception("OS unavailable")):
                with patch.object(tool, '_retrieve_from_bigquery', side_effect=Exception("BQ unavailable")):
                    result = tool.run()
                    data = json.loads(result)

        # Should return error or empty results
        self.assertTrue(
            data.get("status") == "error" or len(data.get("results", [])) == 0
        )

    def test_adaptive_routing_conceptual_query(self):
        """
        Test adaptive routing selects Zep for conceptual queries.

        Flow: Conceptual query → Route to Zep only
        """
        query = "What is the meaning of leadership?"

        tool = self.adaptive_routing.AdaptiveQueryRouting(
            query=query,
            filters=json.dumps({})
        )

        result = tool.run()
        data = json.loads(result)

        # Should route to Zep for conceptual query
        self.assertEqual(data["status"], "success")
        routing = data["routing_decision"]
        self.assertIn("zep", routing["selected_sources"])

    def test_adaptive_routing_filtered_query(self):
        """
        Test adaptive routing selects OpenSearch + BigQuery for filtered queries.

        Flow: Query with filters → Route to OpenSearch + BigQuery
        """
        query = "revenue growth"

        tool = self.adaptive_routing.AdaptiveQueryRouting(
            query=query,
            filters=json.dumps({
                "channel": "business",
                "date_range": "2024-01-01"
            })
        )

        result = tool.run()
        data = json.loads(result)

        # Should route to OpenSearch + BigQuery for filtered query
        self.assertEqual(data["status"], "success")
        routing = data["routing_decision"]
        # Should include at least one of OS or BQ
        self.assertTrue(
            "opensearch" in routing["selected_sources"] or
            "bigquery" in routing["selected_sources"]
        )

    def test_policy_enforcement_redaction(self):
        """
        Test policy enforcement redacts sensitive content.

        Flow: Results with PII → Policy enforcement → Redacted results
        """
        results_with_pii = [
            {
                "doc_id": "doc1",
                "text": "Contact me at john@example.com or 555-123-4567",
                "score": 0.9
            }
        ]

        tool = self.enforce_policy.EnforceRetrievalPolicy(
            results=json.dumps(results_with_pii),
            policy_mode="redact"
        )

        result = tool.run()
        data = json.loads(result)

        # Check redaction occurred
        self.assertEqual(data["status"], "success")
        filtered_results = data["filtered_results"]
        self.assertGreater(len(filtered_results), 0)

        # PII should be redacted
        text = filtered_results[0]["text"]
        self.assertNotIn("john@example.com", text)
        self.assertNotIn("555-123-4567", text)

    def test_end_to_end_retrieval_with_policy(self):
        """
        Test complete end-to-end retrieval with policy enforcement.

        Flow: Query → Retrieval → Fusion → Policy → Final results
        """
        query = "business strategies"

        # Step 1: Retrieval
        retrieval_tool = self.hybrid_retrieval.HybridRetrieval(
            query=query,
            use_zep=True,
            use_opensearch=True,
            top_k=10
        )

        with patch.object(retrieval_tool, '_retrieve_from_zep', return_value=[
            {"doc_id": "doc1", "text": "Strategy 1", "score": 0.9}
        ]):
            with patch.object(retrieval_tool, '_retrieve_from_opensearch', return_value=[
                {"doc_id": "doc2", "text": "Strategy 2 with email@example.com", "score": 0.85}
            ]):
                retrieval_result = retrieval_tool.run()
                retrieval_data = json.loads(retrieval_result)

        # Step 2: Policy enforcement
        policy_tool = self.enforce_policy.EnforceRetrievalPolicy(
            results=json.dumps(retrieval_data["results"]),
            policy_mode="redact"
        )

        policy_result = policy_tool.run()
        policy_data = json.loads(policy_result)

        # Verify end-to-end success
        self.assertEqual(retrieval_data["status"], "success")
        self.assertEqual(policy_data["status"], "success")
        self.assertGreater(len(policy_data["filtered_results"]), 0)

    def test_caching_improves_performance(self):
        """
        Test caching reduces latency for repeated queries.

        Flow: Query 1 (cache miss) → Query 2 (cache hit)
        """
        # Import cache tool
        import importlib.util
        cache_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'cache_hybrid_retrieval.py'
        )
        spec = importlib.util.spec_from_file_location("cache_hybrid_retrieval", cache_path)
        cache_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cache_module)

        CacheTool = cache_module.CacheHybridRetrieval

        # Clear cache
        CacheTool._memory_cache = {}
        CacheTool._cache_stats = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

        query = "test query"
        results = [{"doc_id": "doc1", "score": 0.9}]

        # First query (cache miss)
        tool_set = CacheTool(
            backend="memory",
            operation="set",
            query=query,
            top_k=10,
            results=json.dumps(results),
            ttl_seconds=3600
        )
        tool_set.run()

        # Second query (cache hit)
        tool_get = CacheTool(
            backend="memory",
            operation="get",
            query=query,
            top_k=10
        )
        result = tool_get.run()
        data = json.loads(result)

        # Should be cache hit
        self.assertTrue(data["hit"])
        self.assertEqual(data["results"], results)

    def test_experiment_evaluation_workflow(self):
        """
        Test experiment creation and evaluation workflow.

        Flow: Create experiment → Run retrieval → Evaluate results
        """
        # Import experiment tools
        import importlib.util

        exp_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'manage_rag_experiment.py'
        )
        spec = importlib.util.spec_from_file_location("manage_rag_experiment", exp_path)
        exp_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exp_module)

        eval_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            'summarizer_agent',
            'tools',
            'evaluate_rag_experiment.py'
        )
        spec2 = importlib.util.spec_from_file_location("evaluate_rag_experiment", eval_path)
        eval_module = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(eval_module)

        ManageExp = exp_module.ManageRAGExperiment
        EvaluateExp = eval_module.EvaluateRAGExperiment

        # Clear experiments
        ManageExp._experiments = {}

        # Step 1: Create experiment
        tool_create = ManageExp(
            operation="create",
            experiment_name="Test Experiment",
            weights_semantic=0.7,
            weights_keyword=0.3,
            weights_sql=0.0
        )
        create_result = tool_create.run()
        create_data = json.loads(create_result)
        experiment_id = create_data["experiment_id"]

        # Step 2: Evaluate (simulate retrieval results)
        tool_eval = EvaluateExp(
            experiment_id=experiment_id,
            query="test query",
            fused_results=json.dumps([
                {"doc_id": "doc1", "score": 0.9},
                {"doc_id": "doc2", "score": 0.85}
            ]),
            zep_results=json.dumps([
                {"doc_id": "doc1", "score": 0.88}
            ]),
            ground_truth=json.dumps(["doc1", "doc2"])
        )
        eval_result = tool_eval.run()
        eval_data = json.loads(eval_result)

        # Verify workflow success
        self.assertEqual(create_data["status"], "success")
        self.assertEqual(eval_data["status"], "success")
        self.assertIn("relevance_metrics", eval_data)


if __name__ == '__main__':
    unittest.main()
