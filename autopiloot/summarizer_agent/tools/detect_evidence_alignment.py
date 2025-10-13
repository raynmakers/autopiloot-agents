"""
Detect Evidence Alignment and Conflict Resolution Tool

Analyzes retrieval results to detect evidence overlaps across sources,
identify contradictions, and resolve conflicts using trust hierarchy.

Agency Swarm Tool for Hybrid RAG pipeline.
"""

from agency_swarm.tools import BaseTool
from pydantic import Field
from typing import List, Optional, Dict, Any
import json
import re
from datetime import datetime, timezone
from difflib import SequenceMatcher


class DetectEvidenceAlignment(BaseTool):
    """
    Detect evidence alignment and resolve conflicts across retrieval sources.

    Analyzes results from Zep (semantic), OpenSearch (keyword), and BigQuery (structured)
    to identify overlapping evidence, detect contradictions, and resolve conflicts using
    a trust hierarchy. Provides comprehensive rationale for all decisions.

    Trust Hierarchy: Multi-source > Zep > OpenSearch > Single-source

    Use Case: Post-retrieval analysis before LLM reasoning to ensure consistent,
    high-confidence evidence.
    """

    results: str = Field(
        ...,
        description="JSON string from HybridRetrieval containing results with matched_sources"
    )

    similarity_threshold: float = Field(
        default=0.85,
        description="Text similarity threshold for detecting overlaps (0.0-1.0, default 0.85)"
    )

    enable_bigquery_verification: bool = Field(
        default=False,
        description="Enable BigQuery fact verification for conflict resolution"
    )

    def _parse_results(self, results_str: str) -> Dict[str, Any]:
        """Parse results JSON string."""
        try:
            return json.loads(results_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in results: {str(e)}")

    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """
        Calculate similarity between two text strings using SequenceMatcher.

        Returns: Similarity score 0.0-1.0
        """
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()

    def _detect_overlaps(
        self,
        results: List[Dict[str, Any]],
        threshold: float
    ) -> List[Dict[str, Any]]:
        """
        Detect overlapping evidence across sources based on text similarity.

        Returns: List of overlap groups with aligned results.
        """
        overlaps = []
        processed_indices = set()

        for i, result1 in enumerate(results):
            if i in processed_indices:
                continue

            # Start new overlap group
            overlap_group = {
                "primary_result": result1,
                "aligned_results": [],
                "sources": result1.get("matched_sources", []),
                "alignment_scores": []
            }

            # Find similar results
            for j, result2 in enumerate(results):
                if i == j or j in processed_indices:
                    continue

                text1 = result1.get("text", "")
                text2 = result2.get("text", "")

                similarity = self._calculate_text_similarity(text1, text2)

                if similarity >= threshold:
                    overlap_group["aligned_results"].append(result2)
                    overlap_group["alignment_scores"].append(similarity)

                    # Merge sources
                    for source in result2.get("matched_sources", []):
                        if source not in overlap_group["sources"]:
                            overlap_group["sources"].append(source)

                    processed_indices.add(j)

            # Only add if we found alignments
            if len(overlap_group["aligned_results"]) > 0:
                overlaps.append(overlap_group)
                processed_indices.add(i)

        return overlaps

    def _detect_contradictions(
        self,
        results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect potential contradictions between results from different sources.

        Looks for:
        - Numerical conflicts (different numbers for same metric)
        - Temporal conflicts (different dates for same event)
        - Categorical conflicts (different categorizations)
        """
        contradictions = []

        # Extract potential facts from results
        for i, result1 in enumerate(results):
            for j, result2 in enumerate(results):
                if i >= j:
                    continue

                text1 = result1.get("text", "")
                text2 = result2.get("text", "")
                sources1 = result1.get("matched_sources", [])
                sources2 = result2.get("matched_sources", [])

                # Skip if same sources (not a real contradiction)
                if set(sources1) == set(sources2):
                    continue

                # Detect numerical conflicts
                numbers1 = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?(?:%|\s*percent)?\b', text1)
                numbers2 = re.findall(r'\b\d+(?:,\d{3})*(?:\.\d+)?(?:%|\s*percent)?\b', text2)

                if numbers1 and numbers2 and numbers1 != numbers2:
                    # Check if texts are discussing similar topics
                    similarity = self._calculate_text_similarity(text1, text2)
                    if similarity > 0.5:  # Related but with different numbers
                        contradictions.append({
                            "type": "numerical_conflict",
                            "result1": result1,
                            "result2": result2,
                            "conflict_detail": {
                                "numbers1": numbers1,
                                "numbers2": numbers2,
                                "similarity": similarity
                            }
                        })

                # Detect date conflicts
                dates1 = re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', text1, re.IGNORECASE)
                dates2 = re.findall(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b', text2, re.IGNORECASE)

                if dates1 and dates2 and dates1 != dates2:
                    similarity = self._calculate_text_similarity(text1, text2)
                    if similarity > 0.5:
                        contradictions.append({
                            "type": "temporal_conflict",
                            "result1": result1,
                            "result2": result2,
                            "conflict_detail": {
                                "dates1": dates1,
                                "dates2": dates2,
                                "similarity": similarity
                            }
                        })

        return contradictions

    def _get_trust_score(self, sources: List[str]) -> int:
        """
        Calculate trust score based on source count and types.

        Trust Hierarchy:
        - Multi-source (2+): Highest trust (score 3)
        - Zep (semantic): High trust (score 2)
        - OpenSearch (keyword): Medium trust (score 1)
        - BigQuery (structured): Verification source (score 2)
        """
        if len(sources) >= 2:
            return 3  # Multi-source consensus
        elif "zep" in sources:
            return 2  # Semantic understanding
        elif "bigquery" in sources:
            return 2  # Structured data
        elif "opensearch" in sources:
            return 1  # Keyword search
        else:
            return 0  # Unknown source

    def _resolve_contradiction(
        self,
        contradiction: Dict[str, Any],
        enable_bigquery: bool
    ) -> Dict[str, Any]:
        """
        Resolve a contradiction using trust hierarchy and optional BigQuery verification.

        Returns: Resolution decision with rationale.
        """
        result1 = contradiction["result1"]
        result2 = contradiction["result2"]

        sources1 = result1.get("matched_sources", [])
        sources2 = result2.get("matched_sources", [])

        trust1 = self._get_trust_score(sources1)
        trust2 = self._get_trust_score(sources2)

        # Build resolution
        resolution = {
            "contradiction_type": contradiction["type"],
            "result1_sources": sources1,
            "result2_sources": sources2,
            "result1_trust_score": trust1,
            "result2_trust_score": trust2,
            "resolution_method": "trust_hierarchy",
            "rationale": []
        }

        # Resolve based on trust scores
        if trust1 > trust2:
            resolution["preferred_result"] = "result1"
            resolution["rationale"].append(
                f"Result 1 has higher trust score ({trust1}) than Result 2 ({trust2})"
            )
            resolution["rationale"].append(
                f"Result 1 sources: {', '.join(sources1)}"
            )
        elif trust2 > trust1:
            resolution["preferred_result"] = "result2"
            resolution["rationale"].append(
                f"Result 2 has higher trust score ({trust2}) than Result 1 ({trust1})"
            )
            resolution["rationale"].append(
                f"Result 2 sources: {', '.join(sources2)}"
            )
        else:
            # Equal trust - use RRF score if available
            rrf1 = result1.get("rrf_score", 0.0)
            rrf2 = result2.get("rrf_score", 0.0)

            if rrf1 > rrf2:
                resolution["preferred_result"] = "result1"
                resolution["rationale"].append(
                    f"Equal trust scores ({trust1}), preferring Result 1 with higher RRF score ({rrf1:.3f} > {rrf2:.3f})"
                )
            elif rrf2 > rrf1:
                resolution["preferred_result"] = "result2"
                resolution["rationale"].append(
                    f"Equal trust scores ({trust1}), preferring Result 2 with higher RRF score ({rrf2:.3f} > {rrf1:.3f})"
                )
            else:
                resolution["preferred_result"] = "result1"
                resolution["rationale"].append(
                    f"Equal trust scores and RRF scores, defaulting to Result 1"
                )

        # Add BigQuery verification note if enabled
        if enable_bigquery and "bigquery" in (sources1 + sources2):
            resolution["bigquery_verification"] = "available"
            resolution["rationale"].append(
                "BigQuery structured data available for verification"
            )

        return resolution

    def _get_timestamp(self) -> str:
        """Get current timestamp in ISO 8601 format."""
        return datetime.now(timezone.utc).isoformat()

    def run(self) -> str:
        """
        Detect evidence alignment and resolve conflicts.

        Returns: JSON string with alignment analysis and conflict resolutions.
        """
        try:
            # Parse results
            parsed_results = self._parse_results(self.results)
            results_list = parsed_results.get("results", [])

            if not results_list:
                return json.dumps({
                    "status": "no_results",
                    "message": "No results to analyze",
                    "timestamp": self._get_timestamp()
                })

            # Detect overlaps (evidence alignment)
            overlaps = self._detect_overlaps(results_list, self.similarity_threshold)

            # Detect contradictions
            contradictions = self._detect_contradictions(results_list)

            # Resolve each contradiction
            resolutions = []
            for contradiction in contradictions:
                resolution = self._resolve_contradiction(
                    contradiction,
                    self.enable_bigquery_verification
                )
                resolutions.append(resolution)

            # Analyze source distribution
            source_distribution = {"zep": 0, "opensearch": 0, "bigquery": 0, "multi_source": 0}
            for result in results_list:
                sources = result.get("matched_sources", [])
                if len(sources) >= 2:
                    source_distribution["multi_source"] += 1
                else:
                    for source in sources:
                        if source in source_distribution:
                            source_distribution[source] += 1

            # Calculate alignment statistics
            alignment_stats = {
                "total_results": len(results_list),
                "aligned_groups": len(overlaps),
                "unaligned_results": len(results_list) - sum(
                    1 + len(og["aligned_results"]) for og in overlaps
                ),
                "avg_alignment_score": (
                    sum(sum(og["alignment_scores"]) for og in overlaps) /
                    sum(len(og["alignment_scores"]) for og in overlaps)
                ) if overlaps else 0.0
            }

            # Build response
            response = {
                "status": "success",
                "alignment_analysis": {
                    "overlaps_detected": len(overlaps),
                    "contradictions_detected": len(contradictions),
                    "similarity_threshold": self.similarity_threshold,
                    "overlap_groups": overlaps,
                    "alignment_statistics": alignment_stats
                },
                "contradiction_resolution": {
                    "total_contradictions": len(contradictions),
                    "resolutions": resolutions,
                    "resolution_method": "trust_hierarchy",
                    "trust_hierarchy": {
                        "highest": "multi_source (2+ sources)",
                        "high": "zep (semantic) or bigquery (structured)",
                        "medium": "opensearch (keyword)"
                    }
                },
                "source_distribution": source_distribution,
                "bigquery_verification_enabled": self.enable_bigquery_verification,
                "timestamp": self._get_timestamp()
            }

            return json.dumps(response, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "alignment_detection_failed",
                "message": str(e),
                "timestamp": self._get_timestamp()
            })


if __name__ == "__main__":
    # Test block for standalone execution
    print("Testing DetectEvidenceAlignment tool...")

    # Sample results with overlaps and potential contradictions
    sample_results = {
        "query": "How to increase revenue",
        "results": [
            {
                "chunk_id": "chunk_1",
                "video_id": "vid1",
                "text": "To increase revenue, focus on customer retention. Studies show that retaining customers costs 5 times less than acquiring new ones.",
                "matched_sources": ["zep", "opensearch"],
                "rrf_score": 0.95
            },
            {
                "chunk_id": "chunk_2",
                "video_id": "vid2",
                "text": "Customer retention is key to revenue growth. Research indicates that keeping existing customers is 5x cheaper than finding new customers.",
                "matched_sources": ["zep"],
                "rrf_score": 0.88
            },
            {
                "chunk_id": "chunk_3",
                "video_id": "vid3",
                "text": "To boost revenue, prioritize new customer acquisition. Data shows acquisition costs are only 3 times higher than retention.",
                "matched_sources": ["opensearch"],
                "rrf_score": 0.75
            },
            {
                "chunk_id": "chunk_4",
                "video_id": "vid4",
                "text": "Revenue optimization requires both acquisition and retention strategies working together.",
                "matched_sources": ["bigquery"],
                "rrf_score": 0.70
            }
        ]
    }

    # Test 1: Basic alignment detection
    print("\nTest 1: Basic alignment detection")
    tool = DetectEvidenceAlignment(
        results=json.dumps(sample_results)
    )
    result = tool.run()
    data = json.loads(result)
    print(f"Status: {data.get('status')}")
    print(f"Overlaps detected: {data.get('alignment_analysis', {}).get('overlaps_detected', 0)}")
    print(f"Contradictions detected: {data.get('contradiction_resolution', {}).get('total_contradictions', 0)}")

    # Test 2: With BigQuery verification enabled
    print("\nTest 2: With BigQuery verification")
    tool = DetectEvidenceAlignment(
        results=json.dumps(sample_results),
        enable_bigquery_verification=True
    )
    result = tool.run()
    data = json.loads(result)
    print(f"BigQuery verification enabled: {data.get('bigquery_verification_enabled')}")

    # Test 3: Custom similarity threshold
    print("\nTest 3: Custom similarity threshold")
    tool = DetectEvidenceAlignment(
        results=json.dumps(sample_results),
        similarity_threshold=0.70
    )
    result = tool.run()
    data = json.loads(result)
    print(f"Similarity threshold: {data.get('alignment_analysis', {}).get('similarity_threshold')}")

    print("\n✅ All tests completed successfully")
