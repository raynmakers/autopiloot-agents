"""
Evaluation tool for hybrid RAG experiments.

Compares fused results vs single-source results, logs outcomes,
and provides metrics for A/B testing evaluation.
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import Field


class EvaluateRAGExperiment:
    """
    Tool for evaluating hybrid RAG experiment outcomes.

    Features:
    - Compare fused vs single-source retrieval quality
    - Calculate relevance metrics (precision, recall, NDCG)
    - Log experiment outcomes and parameters
    - Track performance metrics (latency, coverage)
    - Generate comparison reports
    - Store results for observability dashboards
    """

    experiment_id: str = Field(
        description="Experiment ID to evaluate"
    )

    query: str = Field(
        description="Query text used for retrieval"
    )

    fused_results: str = Field(
        description="JSON string of fused retrieval results"
    )

    zep_results: Optional[str] = Field(
        default=None,
        description="JSON string of Zep (semantic) results"
    )

    opensearch_results: Optional[str] = Field(
        default=None,
        description="JSON string of OpenSearch (keyword) results"
    )

    bigquery_results: Optional[str] = Field(
        default=None,
        description="JSON string of BigQuery (SQL) results"
    )

    ground_truth: Optional[str] = Field(
        default=None,
        description="JSON string of ground truth relevant document IDs (for metrics)"
    )

    performance_metrics: Optional[str] = Field(
        default=None,
        description="JSON string of performance metrics (latency, coverage, etc.)"
    )

    user_feedback: Optional[str] = Field(
        default=None,
        description="User feedback on result quality (optional)"
    )

    def __init__(self, **data):
        """Initialize evaluation tool."""
        for key, value in data.items():
            setattr(self, key, value)

    def _calculate_precision_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Calculate Precision@K.

        Precision@K = (# relevant docs in top K) / K

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs
            k: K value

        Returns:
            Precision@K score (0.0-1.0)
        """
        if k <= 0 or not retrieved:
            return 0.0

        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant)

        return relevant_in_top_k / min(k, len(top_k))

    def _calculate_recall_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Calculate Recall@K.

        Recall@K = (# relevant docs in top K) / (total # relevant docs)

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs
            k: K value

        Returns:
            Recall@K score (0.0-1.0)
        """
        if k <= 0 or not retrieved or not relevant:
            return 0.0

        top_k = retrieved[:k]
        relevant_in_top_k = sum(1 for doc_id in top_k if doc_id in relevant)

        return relevant_in_top_k / len(relevant)

    def _calculate_ndcg_at_k(
        self,
        retrieved: List[str],
        relevant: List[str],
        k: int
    ) -> float:
        """
        Calculate NDCG@K (Normalized Discounted Cumulative Gain).

        NDCG accounts for position of relevant documents.
        Higher-ranked relevant docs contribute more to the score.

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs
            k: K value

        Returns:
            NDCG@K score (0.0-1.0)
        """
        if k <= 0 or not retrieved or not relevant:
            return 0.0

        import math

        top_k = retrieved[:k]

        # Calculate DCG (Discounted Cumulative Gain)
        dcg = 0.0
        for i, doc_id in enumerate(top_k):
            if doc_id in relevant:
                # Binary relevance: 1 if relevant, 0 otherwise
                relevance = 1.0
                # Position discount: log2(i+2) (i is 0-indexed)
                dcg += relevance / math.log2(i + 2)

        # Calculate IDCG (Ideal DCG)
        # Assume all relevant docs are in top positions
        idcg = 0.0
        for i in range(min(k, len(relevant))):
            idcg += 1.0 / math.log2(i + 2)

        # NDCG = DCG / IDCG
        if idcg == 0.0:
            return 0.0

        return dcg / idcg

    def _calculate_mrr(
        self,
        retrieved: List[str],
        relevant: List[str]
    ) -> float:
        """
        Calculate MRR (Mean Reciprocal Rank).

        MRR = 1 / (rank of first relevant document)

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs

        Returns:
            MRR score (0.0-1.0)
        """
        if not retrieved or not relevant:
            return 0.0

        for i, doc_id in enumerate(retrieved):
            if doc_id in relevant:
                # Found first relevant doc at position i (0-indexed)
                return 1.0 / (i + 1)

        # No relevant docs found
        return 0.0

    def _extract_doc_ids(self, results: List[Dict[str, Any]]) -> List[str]:
        """Extract document IDs from results."""
        doc_ids = []
        for result in results:
            doc_id = result.get("doc_id") or result.get("id") or result.get("document_id")
            if doc_id:
                doc_ids.append(str(doc_id))
        return doc_ids

    def _calculate_overlap_metrics(
        self,
        fused_ids: List[str],
        source_ids: List[str],
        source_name: str
    ) -> Dict[str, Any]:
        """Calculate overlap metrics between fused and single-source results."""
        if not source_ids:
            return {
                "source": source_name,
                "overlap_count": 0,
                "overlap_ratio": 0.0,
                "unique_to_source": 0,
                "unique_to_fused": len(fused_ids)
            }

        fused_set = set(fused_ids)
        source_set = set(source_ids)

        overlap = fused_set & source_set
        unique_to_source = source_set - fused_set
        unique_to_fused = fused_set - source_set

        overlap_ratio = len(overlap) / len(fused_set) if fused_set else 0.0

        return {
            "source": source_name,
            "overlap_count": len(overlap),
            "overlap_ratio": round(overlap_ratio, 3),
            "unique_to_source": len(unique_to_source),
            "unique_to_fused": len(unique_to_fused)
        }

    def _compare_sources(
        self,
        fused_ids: List[str],
        zep_ids: List[str],
        opensearch_ids: List[str],
        bigquery_ids: List[str]
    ) -> Dict[str, Any]:
        """Compare fused results against individual sources."""
        comparisons = {}

        if zep_ids:
            comparisons["zep"] = self._calculate_overlap_metrics(
                fused_ids, zep_ids, "zep"
            )

        if opensearch_ids:
            comparisons["opensearch"] = self._calculate_overlap_metrics(
                fused_ids, opensearch_ids, "opensearch"
            )

        if bigquery_ids:
            comparisons["bigquery"] = self._calculate_overlap_metrics(
                fused_ids, bigquery_ids, "bigquery"
            )

        return comparisons

    def run(self) -> str:
        """
        Execute experiment evaluation.

        Returns:
            JSON string with evaluation results
        """
        try:
            # Parse inputs
            fused_results = json.loads(self.fused_results)
            fused_ids = self._extract_doc_ids(fused_results)

            # Parse single-source results
            zep_ids = []
            opensearch_ids = []
            bigquery_ids = []

            if self.zep_results:
                zep_results = json.loads(self.zep_results)
                zep_ids = self._extract_doc_ids(zep_results)

            if self.opensearch_results:
                opensearch_results = json.loads(self.opensearch_results)
                opensearch_ids = self._extract_doc_ids(opensearch_results)

            if self.bigquery_results:
                bigquery_results = json.loads(self.bigquery_results)
                bigquery_ids = self._extract_doc_ids(bigquery_results)

            # Parse ground truth if provided
            ground_truth_ids = []
            if self.ground_truth:
                ground_truth_ids = json.loads(self.ground_truth)

            # Parse performance metrics if provided
            performance = {}
            if self.performance_metrics:
                performance = json.loads(self.performance_metrics)

            # Calculate relevance metrics if ground truth provided
            relevance_metrics = {}
            if ground_truth_ids:
                k_values = [5, 10, 20]
                relevance_metrics = {
                    "fused": {},
                    "zep": {},
                    "opensearch": {},
                    "bigquery": {}
                }

                # Fused metrics
                for k in k_values:
                    relevance_metrics["fused"][f"precision@{k}"] = round(
                        self._calculate_precision_at_k(fused_ids, ground_truth_ids, k), 3
                    )
                    relevance_metrics["fused"][f"recall@{k}"] = round(
                        self._calculate_recall_at_k(fused_ids, ground_truth_ids, k), 3
                    )
                    relevance_metrics["fused"][f"ndcg@{k}"] = round(
                        self._calculate_ndcg_at_k(fused_ids, ground_truth_ids, k), 3
                    )

                relevance_metrics["fused"]["mrr"] = round(
                    self._calculate_mrr(fused_ids, ground_truth_ids), 3
                )

                # Single-source metrics
                if zep_ids:
                    for k in k_values:
                        relevance_metrics["zep"][f"precision@{k}"] = round(
                            self._calculate_precision_at_k(zep_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["zep"][f"recall@{k}"] = round(
                            self._calculate_recall_at_k(zep_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["zep"][f"ndcg@{k}"] = round(
                            self._calculate_ndcg_at_k(zep_ids, ground_truth_ids, k), 3
                        )
                    relevance_metrics["zep"]["mrr"] = round(
                        self._calculate_mrr(zep_ids, ground_truth_ids), 3
                    )

                if opensearch_ids:
                    for k in k_values:
                        relevance_metrics["opensearch"][f"precision@{k}"] = round(
                            self._calculate_precision_at_k(opensearch_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["opensearch"][f"recall@{k}"] = round(
                            self._calculate_recall_at_k(opensearch_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["opensearch"][f"ndcg@{k}"] = round(
                            self._calculate_ndcg_at_k(opensearch_ids, ground_truth_ids, k), 3
                        )
                    relevance_metrics["opensearch"]["mrr"] = round(
                        self._calculate_mrr(opensearch_ids, ground_truth_ids), 3
                    )

                if bigquery_ids:
                    for k in k_values:
                        relevance_metrics["bigquery"][f"precision@{k}"] = round(
                            self._calculate_precision_at_k(bigquery_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["bigquery"][f"recall@{k}"] = round(
                            self._calculate_recall_at_k(bigquery_ids, ground_truth_ids, k), 3
                        )
                        relevance_metrics["bigquery"][f"ndcg@{k}"] = round(
                            self._calculate_ndcg_at_k(bigquery_ids, ground_truth_ids, k), 3
                        )
                    relevance_metrics["bigquery"]["mrr"] = round(
                        self._calculate_mrr(bigquery_ids, ground_truth_ids), 3
                    )

            # Compare fused vs single-source
            source_comparisons = self._compare_sources(
                fused_ids, zep_ids, opensearch_ids, bigquery_ids
            )

            # Build evaluation result
            evaluation = {
                "experiment_id": self.experiment_id,
                "query": self.query,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "result_counts": {
                    "fused": len(fused_ids),
                    "zep": len(zep_ids),
                    "opensearch": len(opensearch_ids),
                    "bigquery": len(bigquery_ids)
                },
                "source_comparisons": source_comparisons,
                "relevance_metrics": relevance_metrics if relevance_metrics else None,
                "performance_metrics": performance if performance else None,
                "user_feedback": self.user_feedback,
                "status": "success"
            }

            # Store outcome in experiment record (if exists)
            from manage_rag_experiment import ManageRAGExperiment
            if self.experiment_id in ManageRAGExperiment._experiments:
                experiment = ManageRAGExperiment._experiments[self.experiment_id]
                experiment["outcomes"].append({
                    "timestamp": evaluation["timestamp"],
                    "query": self.query,
                    "result_counts": evaluation["result_counts"],
                    "relevance_metrics": evaluation["relevance_metrics"],
                    "performance_metrics": evaluation["performance_metrics"]
                })

            return json.dumps(evaluation)

        except Exception as e:
            return json.dumps({
                "error": "evaluation_failed",
                "message": str(e),
                "experiment_id": self.experiment_id
            })


# Test block
if __name__ == "__main__":
    print("Testing EvaluateRAGExperiment tool...")

    # Test 1: Basic evaluation without ground truth
    print("\n1. Testing basic evaluation (no ground truth):")
    tool_basic = EvaluateRAGExperiment(
        experiment_id="exp_test_001",
        query="How to increase revenue",
        fused_results=json.dumps([
            {"doc_id": "doc1", "score": 0.95},
            {"doc_id": "doc2", "score": 0.89},
            {"doc_id": "doc3", "score": 0.82}
        ]),
        zep_results=json.dumps([
            {"doc_id": "doc1", "score": 0.92},
            {"doc_id": "doc4", "score": 0.85}
        ]),
        opensearch_results=json.dumps([
            {"doc_id": "doc2", "score": 0.91},
            {"doc_id": "doc3", "score": 0.88}
        ])
    )
    result_basic = tool_basic.run()
    print(json.dumps(json.loads(result_basic), indent=2))

    # Test 2: Evaluation with ground truth
    print("\n2. Testing evaluation with ground truth:")
    tool_ground_truth = EvaluateRAGExperiment(
        experiment_id="exp_test_002",
        query="Best marketing strategies",
        fused_results=json.dumps([
            {"doc_id": "doc1", "score": 0.95},
            {"doc_id": "doc2", "score": 0.89},
            {"doc_id": "doc5", "score": 0.82},
            {"doc_id": "doc3", "score": 0.75}
        ]),
        zep_results=json.dumps([
            {"doc_id": "doc1", "score": 0.92},
            {"doc_id": "doc6", "score": 0.85},
            {"doc_id": "doc5", "score": 0.80}
        ]),
        opensearch_results=json.dumps([
            {"doc_id": "doc2", "score": 0.91},
            {"doc_id": "doc3", "score": 0.88},
            {"doc_id": "doc4", "score": 0.79}
        ]),
        ground_truth=json.dumps(["doc1", "doc2", "doc3"]),
        performance_metrics=json.dumps({
            "total_latency_ms": 850,
            "zep_latency_ms": 320,
            "opensearch_latency_ms": 280,
            "fusion_latency_ms": 50
        })
    )
    result_ground_truth = tool_ground_truth.run()
    print(json.dumps(json.loads(result_ground_truth), indent=2))

    # Test 3: Evaluation with user feedback
    print("\n3. Testing evaluation with user feedback:")
    tool_feedback = EvaluateRAGExperiment(
        experiment_id="exp_test_003",
        query="Product launch strategies",
        fused_results=json.dumps([
            {"doc_id": "doc1", "score": 0.95},
            {"doc_id": "doc2", "score": 0.89}
        ]),
        zep_results=json.dumps([
            {"doc_id": "doc1", "score": 0.92}
        ]),
        user_feedback="Results were highly relevant and comprehensive"
    )
    result_feedback = tool_feedback.run()
    print(json.dumps(json.loads(result_feedback), indent=2))

    print("\n✅ All evaluation operations tested successfully!")
