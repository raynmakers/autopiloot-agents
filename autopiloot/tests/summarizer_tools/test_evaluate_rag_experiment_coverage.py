"""
Comprehensive test suite for EvaluateRAGExperiment tool.
Tests relevance metrics calculation, source comparison, and evaluation reporting.
Target: 80%+ coverage with success paths, error paths, and edge cases.
"""

import unittest
import json
import sys
import os
from unittest.mock import Mock, MagicMock, patch

# Mock agency_swarm before importing tool
mock_agency_swarm = MagicMock()
mock_base_tool = MagicMock()
mock_agency_swarm.tools.BaseTool = mock_base_tool
sys.modules['agency_swarm'] = mock_agency_swarm
sys.modules['agency_swarm.tools'] = mock_agency_swarm.tools


class TestEvaluateRAGExperiment(unittest.TestCase):
    """Test suite for EvaluateRAGExperiment tool."""

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
            'evaluate_rag_experiment.py'
        )
        spec = importlib.util.spec_from_file_location("evaluate_rag_experiment", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.EvaluateRAGExperiment

    def test_precision_at_k_perfect(self):
        """Test precision@K with perfect results."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        precision = tool._calculate_precision_at_k(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc2", "doc3"],
            k=3
        )

        self.assertEqual(precision, 1.0)

    def test_precision_at_k_half(self):
        """Test precision@K with 50% relevant."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        precision = tool._calculate_precision_at_k(
            retrieved=["doc1", "doc2", "doc3", "doc4"],
            relevant=["doc1", "doc3"],
            k=4
        )

        self.assertEqual(precision, 0.5)

    def test_precision_at_k_zero(self):
        """Test precision@K with no relevant results."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        precision = tool._calculate_precision_at_k(
            retrieved=["doc1", "doc2"],
            relevant=["doc3", "doc4"],
            k=2
        )

        self.assertEqual(precision, 0.0)

    def test_recall_at_k_perfect(self):
        """Test recall@K with all relevant documents retrieved."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        recall = tool._calculate_recall_at_k(
            retrieved=["doc1", "doc2", "doc3", "doc4"],
            relevant=["doc1", "doc2"],
            k=4
        )

        self.assertEqual(recall, 1.0)

    def test_recall_at_k_partial(self):
        """Test recall@K with partial retrieval."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        recall = tool._calculate_recall_at_k(
            retrieved=["doc1", "doc5"],
            relevant=["doc1", "doc2", "doc3"],
            k=2
        )

        # 1 out of 3 relevant docs retrieved
        self.assertAlmostEqual(recall, 1.0 / 3.0, places=2)

    def test_recall_at_k_zero(self):
        """Test recall@K with no relevant results."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        recall = tool._calculate_recall_at_k(
            retrieved=["doc1", "doc2"],
            relevant=["doc3", "doc4"],
            k=2
        )

        self.assertEqual(recall, 0.0)

    def test_ndcg_at_k_perfect(self):
        """Test NDCG@K with perfect ranking."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        ndcg = tool._calculate_ndcg_at_k(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1", "doc2", "doc3"],
            k=3
        )

        self.assertEqual(ndcg, 1.0)

    def test_ndcg_at_k_partial(self):
        """Test NDCG@K with partial relevance."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        ndcg = tool._calculate_ndcg_at_k(
            retrieved=["doc1", "doc4", "doc2"],
            relevant=["doc1", "doc2"],
            k=3
        )

        # NDCG should be > 0 but < 1
        self.assertGreater(ndcg, 0.0)
        self.assertLess(ndcg, 1.0)

    def test_ndcg_at_k_zero(self):
        """Test NDCG@K with no relevant results."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        ndcg = tool._calculate_ndcg_at_k(
            retrieved=["doc1", "doc2"],
            relevant=["doc3", "doc4"],
            k=2
        )

        self.assertEqual(ndcg, 0.0)

    def test_mrr_first_position(self):
        """Test MRR with relevant document at first position."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        mrr = tool._calculate_mrr(
            retrieved=["doc1", "doc2", "doc3"],
            relevant=["doc1"]
        )

        self.assertEqual(mrr, 1.0)

    def test_mrr_second_position(self):
        """Test MRR with relevant document at second position."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        mrr = tool._calculate_mrr(
            retrieved=["doc5", "doc1", "doc3"],
            relevant=["doc1"]
        )

        self.assertEqual(mrr, 0.5)

    def test_mrr_no_relevant(self):
        """Test MRR with no relevant documents."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        mrr = tool._calculate_mrr(
            retrieved=["doc1", "doc2"],
            relevant=["doc3"]
        )

        self.assertEqual(mrr, 0.0)

    def test_extract_doc_ids(self):
        """Test document ID extraction from results."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        results = [
            {"doc_id": "doc1", "score": 0.9},
            {"id": "doc2", "score": 0.8},
            {"document_id": "doc3", "score": 0.7}
        ]

        doc_ids = tool._extract_doc_ids(results)

        self.assertEqual(doc_ids, ["doc1", "doc2", "doc3"])

    def test_evaluate_without_ground_truth(self):
        """Test evaluation without ground truth (no relevance metrics)."""
        tool = self.ToolClass(
            experiment_id="exp_test_001",
            query="Test query",
            fused_results=json.dumps([
                {"doc_id": "doc1", "score": 0.95},
                {"doc_id": "doc2", "score": 0.89}
            ]),
            zep_results=json.dumps([
                {"doc_id": "doc1", "score": 0.92}
            ]),
            opensearch_results=json.dumps([
                {"doc_id": "doc2", "score": 0.91}
            ])
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["experiment_id"], "exp_test_001")
        self.assertIsNone(data["relevance_metrics"])
        self.assertIn("source_comparisons", data)

    def test_evaluate_with_ground_truth(self):
        """Test evaluation with ground truth (calculate metrics)."""
        tool = self.ToolClass(
            experiment_id="exp_test_002",
            query="Test query",
            fused_results=json.dumps([
                {"doc_id": "doc1", "score": 0.95},
                {"doc_id": "doc2", "score": 0.89},
                {"doc_id": "doc5", "score": 0.82}
            ]),
            zep_results=json.dumps([
                {"doc_id": "doc1", "score": 0.92},
                {"doc_id": "doc6", "score": 0.85}
            ]),
            ground_truth=json.dumps(["doc1", "doc2"])
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["relevance_metrics"])
        self.assertIn("fused", data["relevance_metrics"])
        self.assertIn("zep", data["relevance_metrics"])
        self.assertIn("precision@5", data["relevance_metrics"]["fused"])
        self.assertIn("recall@5", data["relevance_metrics"]["fused"])
        self.assertIn("ndcg@5", data["relevance_metrics"]["fused"])
        self.assertIn("mrr", data["relevance_metrics"]["fused"])

    def test_evaluate_with_performance_metrics(self):
        """Test evaluation with performance metrics."""
        tool = self.ToolClass(
            experiment_id="exp_test_003",
            query="Test query",
            fused_results=json.dumps([{"doc_id": "doc1"}]),
            performance_metrics=json.dumps({
                "total_latency_ms": 850,
                "zep_latency_ms": 320,
                "opensearch_latency_ms": 280
            })
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertIsNotNone(data["performance_metrics"])
        self.assertEqual(data["performance_metrics"]["total_latency_ms"], 850)

    def test_evaluate_with_user_feedback(self):
        """Test evaluation with user feedback."""
        tool = self.ToolClass(
            experiment_id="exp_test_004",
            query="Test query",
            fused_results=json.dumps([{"doc_id": "doc1"}]),
            user_feedback="Results were highly relevant"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user_feedback"], "Results were highly relevant")

    def test_source_comparison_metrics(self):
        """Test source comparison overlap metrics."""
        tool = self.ToolClass(
            experiment_id="exp_test_005",
            query="Test query",
            fused_results=json.dumps([
                {"doc_id": "doc1", "score": 0.95},
                {"doc_id": "doc2", "score": 0.89},
                {"doc_id": "doc3", "score": 0.82}
            ]),
            zep_results=json.dumps([
                {"doc_id": "doc1", "score": 0.92},
                {"doc_id": "doc4", "score": 0.85}
            ])
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("source_comparisons", data)
        self.assertIn("zep", data["source_comparisons"])

        zep_comp = data["source_comparisons"]["zep"]
        self.assertEqual(zep_comp["source"], "zep")
        self.assertEqual(zep_comp["overlap_count"], 1)  # Only doc1 overlaps
        self.assertGreater(zep_comp["overlap_ratio"], 0.0)

    def test_result_counts(self):
        """Test result count tracking."""
        tool = self.ToolClass(
            experiment_id="exp_test_006",
            query="Test query",
            fused_results=json.dumps([{"doc_id": "doc1"}, {"doc_id": "doc2"}]),
            zep_results=json.dumps([{"doc_id": "doc1"}]),
            opensearch_results=json.dumps([{"doc_id": "doc2"}, {"doc_id": "doc3"}]),
            bigquery_results=json.dumps([{"doc_id": "doc4"}])
        )

        result = tool.run()
        data = json.loads(result)

        counts = data["result_counts"]
        self.assertEqual(counts["fused"], 2)
        self.assertEqual(counts["zep"], 1)
        self.assertEqual(counts["opensearch"], 2)
        self.assertEqual(counts["bigquery"], 1)

    def test_timestamp_generation(self):
        """Test timestamp generation in evaluation."""
        tool = self.ToolClass(
            experiment_id="exp_test_007",
            query="Test query",
            fused_results=json.dumps([{"doc_id": "doc1"}])
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("timestamp", data)
        self.assertTrue(data["timestamp"].endswith("Z"))

    def test_exception_handling(self):
        """Test exception handling in run method."""
        tool = self.ToolClass(
            experiment_id="exp_test_008",
            query="Test query",
            fused_results="invalid json {"  # Invalid JSON
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "evaluation_failed")

    def test_overlap_metrics_no_overlap(self):
        """Test overlap metrics with no overlap."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        metrics = tool._calculate_overlap_metrics(
            fused_ids=["doc1", "doc2"],
            source_ids=["doc3", "doc4"],
            source_name="test_source"
        )

        self.assertEqual(metrics["overlap_count"], 0)
        self.assertEqual(metrics["overlap_ratio"], 0.0)

    def test_overlap_metrics_complete_overlap(self):
        """Test overlap metrics with 100% overlap."""
        tool = self.ToolClass(
            experiment_id="test",
            query="test",
            fused_results=json.dumps([])
        )

        metrics = tool._calculate_overlap_metrics(
            fused_ids=["doc1", "doc2"],
            source_ids=["doc1", "doc2"],
            source_name="test_source"
        )

        self.assertEqual(metrics["overlap_count"], 2)
        self.assertEqual(metrics["overlap_ratio"], 1.0)

    def test_compare_multiple_sources(self):
        """Test comparison across multiple sources."""
        tool = self.ToolClass(
            experiment_id="exp_test_009",
            query="Test query",
            fused_results=json.dumps([
                {"doc_id": "doc1"},
                {"doc_id": "doc2"},
                {"doc_id": "doc3"}
            ]),
            zep_results=json.dumps([{"doc_id": "doc1"}]),
            opensearch_results=json.dumps([{"doc_id": "doc2"}]),
            bigquery_results=json.dumps([{"doc_id": "doc3"}])
        )

        result = tool.run()
        data = json.loads(result)

        comparisons = data["source_comparisons"]
        self.assertIn("zep", comparisons)
        self.assertIn("opensearch", comparisons)
        self.assertIn("bigquery", comparisons)


if __name__ == '__main__':
    unittest.main()
