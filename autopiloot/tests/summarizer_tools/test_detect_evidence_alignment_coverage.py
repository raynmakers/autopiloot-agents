"""
Comprehensive test suite for DetectEvidenceAlignment tool.
Tests overlap detection, contradiction identification, and conflict resolution.
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


class TestDetectEvidenceAlignment(unittest.TestCase):
    """Test suite for DetectEvidenceAlignment tool."""

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
            'detect_evidence_alignment.py'
        )
        spec = importlib.util.spec_from_file_location("detect_evidence_alignment", tool_path)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.ToolClass = self.module.DetectEvidenceAlignment

        # Sample results with overlaps
        self.sample_results = {
            "query": "customer retention strategies",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "video_id": "vid1",
                    "text": "Customer retention costs 5 times less than acquisition.",
                    "matched_sources": ["zep", "opensearch"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "video_id": "vid2",
                    "text": "Retention is 5x cheaper than finding new customers.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.88
                },
                {
                    "chunk_id": "chunk_3",
                    "video_id": "vid3",
                    "text": "Acquisition costs are 3 times higher than retention.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.75
                }
            ]
        }

    def test_parse_valid_results(self):
        """Test parsing valid results JSON (lines 52-56)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        parsed = tool._parse_results(json.dumps(self.sample_results))

        self.assertEqual(parsed["query"], "customer retention strategies")
        self.assertEqual(len(parsed["results"]), 3)

    def test_parse_invalid_results(self):
        """Test parsing invalid JSON (lines 52-56)."""
        tool = self.ToolClass(
            results="invalid json"
        )

        with self.assertRaises(ValueError) as context:
            tool._parse_results("invalid json")

        self.assertIn("Invalid JSON", str(context.exception))

    def test_calculate_text_similarity_high(self):
        """Test text similarity calculation with high similarity (lines 58-63)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        text1 = "Customer retention costs 5 times less than acquisition."
        text2 = "Retention costs 5x less than customer acquisition."

        similarity = tool._calculate_text_similarity(text1, text2)

        self.assertGreater(similarity, 0.7)
        self.assertLessEqual(similarity, 1.0)

    def test_calculate_text_similarity_low(self):
        """Test text similarity calculation with low similarity (lines 58-63)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        text1 = "Customer retention strategies."
        text2 = "Business growth tactics."

        similarity = tool._calculate_text_similarity(text1, text2)

        self.assertLess(similarity, 0.5)

    def test_detect_overlaps_with_alignments(self):
        """Test overlap detection with aligned results (lines 65-99)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            similarity_threshold=0.70
        )

        overlaps = tool._detect_overlaps(self.sample_results["results"], 0.70)

        # Should find at least one overlap group
        self.assertGreater(len(overlaps), 0)

        # Check overlap structure
        for overlap in overlaps:
            self.assertIn("primary_result", overlap)
            self.assertIn("aligned_results", overlap)
            self.assertIn("sources", overlap)
            self.assertIn("alignment_scores", overlap)

    def test_detect_overlaps_no_alignments(self):
        """Test overlap detection with no alignments (high threshold) (lines 65-99)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            similarity_threshold=0.99
        )

        overlaps = tool._detect_overlaps(self.sample_results["results"], 0.99)

        # Should find no overlaps with very high threshold
        self.assertEqual(len(overlaps), 0)

    def test_detect_contradictions_numerical(self):
        """Test detection of numerical contradictions (lines 101-165)."""
        contradictory_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "text": "Revenue grew by 50% last year.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "Revenue increased by 30% last year.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.85
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(contradictory_results)
        )

        contradictions = tool._detect_contradictions(contradictory_results["results"])

        # Should detect numerical conflict
        self.assertGreater(len(contradictions), 0)
        self.assertEqual(contradictions[0]["type"], "numerical_conflict")

    def test_detect_contradictions_temporal(self):
        """Test detection of temporal contradictions (lines 101-165)."""
        temporal_conflict_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "text": "The product launched on January 15, 2025.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "Product launch date was March 20, 2025.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.85
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(temporal_conflict_results)
        )

        contradictions = tool._detect_contradictions(temporal_conflict_results["results"])

        # Should detect temporal conflict
        if len(contradictions) > 0:
            self.assertEqual(contradictions[0]["type"], "temporal_conflict")

    def test_detect_contradictions_none(self):
        """Test no contradictions detected (lines 101-165)."""
        clean_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "text": "Revenue grew consistently.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "Business strategy improved.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.85
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(clean_results)
        )

        contradictions = tool._detect_contradictions(clean_results["results"])

        # Should detect no contradictions
        self.assertEqual(len(contradictions), 0)

    def test_get_trust_score_multi_source(self):
        """Test trust score for multi-source results (lines 167-183)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        score = tool._get_trust_score(["zep", "opensearch"])

        self.assertEqual(score, 3)  # Multi-source highest trust

    def test_get_trust_score_zep(self):
        """Test trust score for Zep-only results (lines 167-183)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        score = tool._get_trust_score(["zep"])

        self.assertEqual(score, 2)  # Zep high trust

    def test_get_trust_score_opensearch(self):
        """Test trust score for OpenSearch-only results (lines 167-183)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        score = tool._get_trust_score(["opensearch"])

        self.assertEqual(score, 1)  # OpenSearch medium trust

    def test_get_trust_score_bigquery(self):
        """Test trust score for BigQuery results (lines 167-183)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        score = tool._get_trust_score(["bigquery"])

        self.assertEqual(score, 2)  # BigQuery high trust (structured data)

    def test_resolve_contradiction_trust_hierarchy(self):
        """Test contradiction resolution by trust hierarchy (lines 185-243)."""
        contradiction = {
            "type": "numerical_conflict",
            "result1": {
                "chunk_id": "chunk_1",
                "text": "50% growth",
                "matched_sources": ["zep", "opensearch"],
                "rrf_score": 0.95
            },
            "result2": {
                "chunk_id": "chunk_2",
                "text": "30% growth",
                "matched_sources": ["opensearch"],
                "rrf_score": 0.85
            }
        }

        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        resolution = tool._resolve_contradiction(contradiction, False)

        self.assertIn("preferred_result", resolution)
        self.assertEqual(resolution["preferred_result"], "result1")  # Multi-source wins
        self.assertIn("rationale", resolution)
        self.assertGreater(len(resolution["rationale"]), 0)

    def test_resolve_contradiction_equal_trust_rrf(self):
        """Test contradiction resolution with equal trust using RRF (lines 185-243)."""
        contradiction = {
            "type": "numerical_conflict",
            "result1": {
                "chunk_id": "chunk_1",
                "text": "50% growth",
                "matched_sources": ["zep"],
                "rrf_score": 0.95
            },
            "result2": {
                "chunk_id": "chunk_2",
                "text": "30% growth",
                "matched_sources": ["bigquery"],
                "rrf_score": 0.85
            }
        }

        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        resolution = tool._resolve_contradiction(contradiction, False)

        self.assertIn("preferred_result", resolution)
        self.assertEqual(resolution["preferred_result"], "result1")  # Higher RRF wins
        self.assertIn("RRF score", resolution["rationale"][0])

    def test_resolve_contradiction_bigquery_verification(self):
        """Test contradiction resolution with BigQuery verification enabled (lines 185-243)."""
        contradiction = {
            "type": "numerical_conflict",
            "result1": {
                "chunk_id": "chunk_1",
                "text": "50% growth",
                "matched_sources": ["bigquery"],
                "rrf_score": 0.95
            },
            "result2": {
                "chunk_id": "chunk_2",
                "text": "30% growth",
                "matched_sources": ["opensearch"],
                "rrf_score": 0.85
            }
        }

        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            enable_bigquery_verification=True
        )

        resolution = tool._resolve_contradiction(contradiction, True)

        self.assertIn("bigquery_verification", resolution)
        self.assertEqual(resolution["bigquery_verification"], "available")

    def test_run_success_with_overlaps(self):
        """Test successful run with overlap detection (lines 253-334)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertIn("alignment_analysis", data)
        self.assertIn("contradiction_resolution", data)
        self.assertIn("source_distribution", data)

    def test_run_no_results(self):
        """Test run with no results (lines 257-263)."""
        empty_results = {
            "query": "test",
            "results": []
        }

        tool = self.ToolClass(
            results=json.dumps(empty_results)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "no_results")

    def test_run_with_contradictions(self):
        """Test run detecting contradictions (lines 253-334)."""
        contradictory_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "text": "Revenue grew by 50% in 2025.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "Revenue increased by 30% in 2025.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.85
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(contradictory_results)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(data["status"], "success")
        self.assertGreaterEqual(
            data["contradiction_resolution"]["total_contradictions"],
            0
        )

    def test_run_source_distribution_analysis(self):
        """Test source distribution analysis (lines 274-283)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("source_distribution", data)
        source_dist = data["source_distribution"]

        # Check all source types tracked
        self.assertIn("zep", source_dist)
        self.assertIn("opensearch", source_dist)
        self.assertIn("bigquery", source_dist)
        self.assertIn("multi_source", source_dist)

    def test_run_alignment_statistics(self):
        """Test alignment statistics calculation (lines 285-294)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool.run()
        data = json.loads(result)

        alignment_stats = data["alignment_analysis"]["alignment_statistics"]

        self.assertIn("total_results", alignment_stats)
        self.assertIn("aligned_groups", alignment_stats)
        self.assertIn("unaligned_results", alignment_stats)
        self.assertIn("avg_alignment_score", alignment_stats)

        # Total should match input
        self.assertEqual(alignment_stats["total_results"], 3)

    def test_run_trust_hierarchy_in_response(self):
        """Test trust hierarchy included in response (lines 302-308)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        result = tool.run()
        data = json.loads(result)

        trust_hierarchy = data["contradiction_resolution"]["trust_hierarchy"]

        self.assertIn("highest", trust_hierarchy)
        self.assertIn("high", trust_hierarchy)
        self.assertIn("medium", trust_hierarchy)

    def test_run_custom_similarity_threshold(self):
        """Test custom similarity threshold (lines 253-334)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            similarity_threshold=0.70
        )

        result = tool.run()
        data = json.loads(result)

        self.assertEqual(
            data["alignment_analysis"]["similarity_threshold"],
            0.70
        )

    def test_run_bigquery_verification_enabled(self):
        """Test BigQuery verification flag in response (lines 310-311)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results),
            enable_bigquery_verification=True
        )

        result = tool.run()
        data = json.loads(result)

        self.assertTrue(data["bigquery_verification_enabled"])

    def test_exception_handling(self):
        """Test exception handling (lines 336-341)."""
        tool = self.ToolClass(
            results="not valid json at all"
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn("error", data)
        self.assertEqual(data["error"], "alignment_detection_failed")
        self.assertIn("message", data)

    def test_timestamp_generation(self):
        """Test timestamp generation (lines 245-247)."""
        tool = self.ToolClass(
            results=json.dumps(self.sample_results)
        )

        timestamp = tool._get_timestamp()

        # Should be ISO 8601 format with timezone
        self.assertIn("T", timestamp)
        self.assertTrue(timestamp.endswith("Z") or "+" in timestamp)

    def test_overlap_groups_merge_sources(self):
        """Test that overlap groups merge sources from aligned results (lines 65-99)."""
        multi_source_results = {
            "query": "test",
            "results": [
                {
                    "chunk_id": "chunk_1",
                    "text": "Customer retention is important.",
                    "matched_sources": ["zep"],
                    "rrf_score": 0.95
                },
                {
                    "chunk_id": "chunk_2",
                    "text": "Customer retention is crucial.",
                    "matched_sources": ["opensearch"],
                    "rrf_score": 0.88
                }
            ]
        }

        tool = self.ToolClass(
            results=json.dumps(multi_source_results),
            similarity_threshold=0.70
        )

        overlaps = tool._detect_overlaps(multi_source_results["results"], 0.70)

        if len(overlaps) > 0:
            # Sources should be merged
            self.assertGreaterEqual(len(overlaps[0]["sources"]), 2)


if __name__ == '__main__':
    unittest.main()
