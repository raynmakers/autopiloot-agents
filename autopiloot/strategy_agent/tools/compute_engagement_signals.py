"""
ComputeEngagementSignals tool for calculating normalized engagement scores and metrics.
Processes LinkedIn content items to generate engagement scores and aggregate statistics.
"""

import json
import math
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from agency_swarm.tools import BaseTool
from pydantic import Field


class ComputeEngagementSignals(BaseTool):
    """
    Computes normalized engagement signals and scores for LinkedIn content items.

    Calculates weighted engagement scores per item and generates aggregate statistics
    for strategic analysis and content optimization insights.
    """

    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of content items with engagement metrics (from fetch_corpus_from_zep)"
    )

    weights: Optional[Dict[str, float]] = Field(
        None,
        description="Custom weights for engagement types (e.g., {'likes': 1.0, 'comments': 3.0, 'shares': 5.0})"
    )

    min_engagement_threshold: float = Field(
        0.0,
        description="Minimum engagement threshold to include items in analysis (default: 0)"
    )

    normalization_method: str = Field(
        "z_score",
        description="Normalization method: 'z_score', 'min_max', or 'percentile' (default: z_score)"
    )

    def run(self) -> str:
        """
        Computes engagement signals and normalized scores for content items.

        Returns:
            str: JSON string containing items with engagement scores and aggregates
                 Format: {
                     "items": [
                         {
                             "id": "urn:li:activity:12345",
                             "engagement_score": 0.85,
                             "raw_engagement": {
                                 "reactions": 150,
                                 "comments": 25,
                                 "shares": 5,
                                 "total": 180
                             },
                             "normalized_engagement": {
                                 "reactions_norm": 0.7,
                                 "comments_norm": 0.9,
                                 "shares_norm": 0.3,
                                 "percentile": 85
                             },
                             "engagement_category": "high"
                         }
                     ],
                     "aggregates": {
                         "total_items": 100,
                         "mean_engagement": 0.45,
                         "median_engagement": 0.42,
                         "std_engagement": 0.25,
                         "distribution": {
                             "high": 15,
                             "medium": 60,
                             "low": 25
                         },
                         "top_performers": [...],
                         "engagement_trends": {...}
                     },
                     "processing_metadata": {
                         "weights_used": {...},
                         "normalization_method": "z_score",
                         "threshold_applied": 0.0,
                         "computed_at": "2024-01-15T12:00:00Z"
                     }
                 }
        """
        try:
            if not self.items:
                return json.dumps({
                    "error": "no_items",
                    "message": "No items provided for engagement analysis"
                })

            # Set default weights if not provided
            weights = self._get_default_weights() if not self.weights else self.weights

            # Validate and clean items
            valid_items = self._validate_and_clean_items(self.items)

            if not valid_items:
                return json.dumps({
                    "error": "no_valid_items",
                    "message": "No items contain valid engagement metrics"
                })

            # Compute raw engagement metrics
            items_with_raw = self._compute_raw_engagement(valid_items, weights)

            # Apply engagement threshold filter
            filtered_items = self._apply_engagement_threshold(items_with_raw)

            if not filtered_items:
                return json.dumps({
                    "error": "no_items_above_threshold",
                    "message": f"No items meet minimum engagement threshold of {self.min_engagement_threshold}"
                })

            # Compute normalized engagement scores
            items_with_scores = self._compute_normalized_scores(filtered_items)

            # Categorize engagement levels
            items_with_categories = self._categorize_engagement(items_with_scores)

            # Compute aggregate statistics
            aggregates = self._compute_aggregates(items_with_categories)

            # Prepare response
            result = {
                "items": items_with_categories,
                "aggregates": aggregates,
                "processing_metadata": {
                    "weights_used": weights,
                    "normalization_method": self.normalization_method,
                    "threshold_applied": self.min_engagement_threshold,
                    "total_input_items": len(self.items),
                    "valid_items": len(valid_items),
                    "items_above_threshold": len(filtered_items),
                    "computed_at": datetime.utcnow().isoformat() + "Z"
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "engagement_computation_failed",
                "message": str(e),
                "item_count": len(self.items) if self.items else 0,
                "weights": self.weights,
                "threshold": self.min_engagement_threshold
            }
            return json.dumps(error_result)

    def _get_default_weights(self) -> Dict[str, float]:
        """
        Get default weights for different engagement types.

        Returns:
            Dict[str, float]: Default engagement weights
        """
        return {
            "reactions": 1.0,     # Likes, loves, celebrates, etc.
            "comments": 3.0,      # Comments are more valuable than likes
            "shares": 5.0,        # Shares indicate strong engagement
            "views": 0.1,         # Views are least valuable but good for reach
            "saves": 4.0,         # Saves indicate high value content
            "clicks": 2.0         # Link clicks show strong interest
        }

    def _validate_and_clean_items(self, items: List[Dict]) -> List[Dict]:
        """
        Validate and clean items for engagement computation.

        Args:
            items: Raw items from corpus

        Returns:
            List[Dict]: Valid items with engagement metrics
        """
        valid_items = []

        for item in items:
            # Extract engagement data from different possible structures
            engagement_data = self._extract_engagement_data(item)

            if engagement_data and any(engagement_data.values()):
                # Add cleaned engagement data to item
                cleaned_item = item.copy()
                cleaned_item["_engagement_data"] = engagement_data
                valid_items.append(cleaned_item)

        return valid_items

    def _extract_engagement_data(self, item: Dict) -> Optional[Dict[str, int]]:
        """
        Extract engagement metrics from various item structures.

        Args:
            item: Content item

        Returns:
            Dict[str, int]: Extracted engagement metrics or None
        """
        engagement = {}

        # Try to get from metadata.engagement first
        if "metadata" in item and "engagement" in item["metadata"]:
            meta_eng = item["metadata"]["engagement"]
            engagement["reactions"] = meta_eng.get("reaction_count", 0) or meta_eng.get("likes", 0)
            engagement["comments"] = meta_eng.get("comment_count", 0) or meta_eng.get("comments", 0)
            engagement["shares"] = meta_eng.get("share_count", 0) or meta_eng.get("shares", 0)
            engagement["views"] = meta_eng.get("view_count", 0) or meta_eng.get("views", 0)

        # Try to get from metadata directly
        elif "metadata" in item:
            metadata = item["metadata"]
            engagement["reactions"] = metadata.get("likes", 0) or metadata.get("reaction_count", 0)
            engagement["comments"] = metadata.get("comments", 0) or metadata.get("comment_count", 0)
            engagement["shares"] = metadata.get("shares", 0) or metadata.get("share_count", 0)
            engagement["views"] = metadata.get("views", 0) or metadata.get("view_count", 0)

        # Try to get from root level
        else:
            engagement["reactions"] = item.get("likes", 0) or item.get("reaction_count", 0)
            engagement["comments"] = item.get("comments", 0) or item.get("comment_count", 0)
            engagement["shares"] = item.get("shares", 0) or item.get("share_count", 0)
            engagement["views"] = item.get("views", 0) or item.get("view_count", 0)

        # Convert to integers and handle None values
        for key, value in engagement.items():
            engagement[key] = int(value) if value is not None else 0

        return engagement if any(engagement.values()) else None

    def _compute_raw_engagement(self, items: List[Dict], weights: Dict[str, float]) -> List[Dict]:
        """
        Compute raw engagement scores using provided weights.

        Args:
            items: Valid items with engagement data
            weights: Engagement type weights

        Returns:
            List[Dict]: Items with raw engagement scores
        """
        items_with_raw = []

        for item in items:
            engagement_data = item["_engagement_data"]

            # Calculate weighted engagement score
            raw_score = 0.0
            for eng_type, count in engagement_data.items():
                weight = weights.get(eng_type, 0.0)
                raw_score += count * weight

            # Calculate total unweighted engagement
            total_engagement = sum(engagement_data.values())

            # Add raw engagement information
            item_copy = item.copy()
            item_copy["raw_engagement"] = {
                **engagement_data,
                "total": total_engagement,
                "weighted_score": raw_score
            }

            items_with_raw.append(item_copy)

        return items_with_raw

    def _apply_engagement_threshold(self, items: List[Dict]) -> List[Dict]:
        """
        Filter items based on minimum engagement threshold.

        Args:
            items: Items with raw engagement scores

        Returns:
            List[Dict]: Items meeting threshold requirements
        """
        if self.min_engagement_threshold <= 0:
            return items

        filtered = []
        for item in items:
            total_engagement = item["raw_engagement"]["total"]
            if total_engagement >= self.min_engagement_threshold:
                filtered.append(item)

        return filtered

    def _compute_normalized_scores(self, items: List[Dict]) -> List[Dict]:
        """
        Compute normalized engagement scores based on selected method.

        Args:
            items: Items with raw engagement scores

        Returns:
            List[Dict]: Items with normalized engagement scores
        """
        if not items:
            return items

        # Extract raw scores for normalization
        raw_scores = [item["raw_engagement"]["weighted_score"] for item in items]

        if self.normalization_method == "z_score":
            normalized_scores = self._z_score_normalization(raw_scores)
        elif self.normalization_method == "min_max":
            normalized_scores = self._min_max_normalization(raw_scores)
        elif self.normalization_method == "percentile":
            normalized_scores = self._percentile_normalization(raw_scores)
        else:
            # Default to z_score
            normalized_scores = self._z_score_normalization(raw_scores)

        # Add normalized scores to items
        items_with_scores = []
        for i, item in enumerate(items):
            item_copy = item.copy()
            item_copy["engagement_score"] = normalized_scores[i]

            # Add detailed normalization info
            item_copy["normalized_engagement"] = {
                "score": normalized_scores[i],
                "percentile": self._calculate_percentile(raw_scores[i], raw_scores),
                "raw_score": item["raw_engagement"]["weighted_score"],
                "method": self.normalization_method
            }

            items_with_scores.append(item_copy)

        return items_with_scores

    def _z_score_normalization(self, scores: List[float]) -> List[float]:
        """Z-score normalization (mean=0, std=1)."""
        if len(scores) <= 1:
            return [0.5] * len(scores)

        mean_score = sum(scores) / len(scores)
        variance = sum((x - mean_score) ** 2 for x in scores) / len(scores)
        std_score = math.sqrt(variance) if variance > 0 else 1

        # Normalize to 0-1 range by applying sigmoid to z-scores
        normalized = []
        for score in scores:
            z_score = (score - mean_score) / std_score
            # Apply sigmoid to map to 0-1 range
            sigmoid_score = 1 / (1 + math.exp(-z_score))
            normalized.append(round(sigmoid_score, 4))

        return normalized

    def _min_max_normalization(self, scores: List[float]) -> List[float]:
        """Min-max normalization to 0-1 range."""
        if not scores:
            return []

        min_score = min(scores)
        max_score = max(scores)

        if min_score == max_score:
            return [0.5] * len(scores)

        normalized = []
        for score in scores:
            norm_score = (score - min_score) / (max_score - min_score)
            normalized.append(round(norm_score, 4))

        return normalized

    def _percentile_normalization(self, scores: List[float]) -> List[float]:
        """Percentile-based normalization."""
        sorted_scores = sorted(scores)

        normalized = []
        for score in scores:
            # Find percentile rank
            rank = sum(1 for s in sorted_scores if s <= score)
            percentile = rank / len(sorted_scores)
            normalized.append(round(percentile, 4))

        return normalized

    def _calculate_percentile(self, value: float, all_values: List[float]) -> int:
        """Calculate percentile rank of a value."""
        if not all_values:
            return 50

        rank = sum(1 for v in all_values if v <= value)
        percentile = int((rank / len(all_values)) * 100)
        return percentile

    def _categorize_engagement(self, items: List[Dict]) -> List[Dict]:
        """
        Categorize items into engagement levels (high, medium, low).

        Args:
            items: Items with engagement scores

        Returns:
            List[Dict]: Items with engagement categories
        """
        items_with_categories = []

        for item in items:
            score = item["engagement_score"]

            # Define thresholds for categories
            if score >= 0.75:
                category = "high"
            elif score >= 0.4:
                category = "medium"
            else:
                category = "low"

            item_copy = item.copy()
            item_copy["engagement_category"] = category
            items_with_categories.append(item_copy)

        return items_with_categories

    def _compute_aggregates(self, items: List[Dict]) -> Dict[str, Any]:
        """
        Compute aggregate statistics across all items.

        Args:
            items: Items with engagement scores and categories

        Returns:
            Dict: Aggregate statistics
        """
        if not items:
            return {}

        scores = [item["engagement_score"] for item in items]
        raw_scores = [item["raw_engagement"]["weighted_score"] for item in items]

        # Basic statistics
        mean_score = sum(scores) / len(scores)
        median_score = sorted(scores)[len(scores) // 2]

        # Standard deviation
        variance = sum((x - mean_score) ** 2 for x in scores) / len(scores)
        std_score = math.sqrt(variance)

        # Category distribution
        categories = [item["engagement_category"] for item in items]
        distribution = {
            "high": categories.count("high"),
            "medium": categories.count("medium"),
            "low": categories.count("low")
        }

        # Top performers (top 10%)
        top_count = max(1, len(items) // 10)
        top_performers = sorted(items, key=lambda x: x["engagement_score"], reverse=True)[:top_count]
        top_performer_ids = [item["id"] for item in top_performers]

        # Engagement type breakdown
        total_reactions = sum(item["raw_engagement"]["reactions"] for item in items)
        total_comments = sum(item["raw_engagement"]["comments"] for item in items)
        total_shares = sum(item["raw_engagement"]["shares"] for item in items)

        aggregates = {
            "total_items": len(items),
            "mean_engagement": round(mean_score, 4),
            "median_engagement": round(median_score, 4),
            "std_engagement": round(std_score, 4),
            "min_engagement": round(min(scores), 4),
            "max_engagement": round(max(scores), 4),
            "distribution": distribution,
            "distribution_percentages": {
                cat: round((count / len(items)) * 100, 1)
                for cat, count in distribution.items()
            },
            "top_performers": top_performer_ids,
            "engagement_breakdown": {
                "total_reactions": total_reactions,
                "total_comments": total_comments,
                "total_shares": total_shares,
                "avg_reactions_per_item": round(total_reactions / len(items), 2),
                "avg_comments_per_item": round(total_comments / len(items), 2),
                "avg_shares_per_item": round(total_shares / len(items), 2)
            },
            "quality_indicators": {
                "high_engagement_rate": round(distribution["high"] / len(items), 3),
                "comment_to_reaction_ratio": round(total_comments / max(total_reactions, 1), 3),
                "share_rate": round(total_shares / max(total_reactions + total_comments, 1), 3)
            }
        }

        return aggregates


if __name__ == "__main__":
    # Test the tool
    test_items = [
        {
            "id": "urn:li:activity:1",
            "content": "Test post 1",
            "metadata": {
                "engagement": {
                    "reaction_count": 100,
                    "comment_count": 15,
                    "share_count": 5,
                    "view_count": 1000
                }
            }
        },
        {
            "id": "urn:li:activity:2",
            "content": "Test post 2",
            "metadata": {
                "likes": 200,
                "comments": 30,
                "shares": 10,
                "views": 2000
            }
        },
        {
            "id": "urn:li:activity:3",
            "content": "Test post 3",
            "metadata": {
                "engagement": {
                    "reaction_count": 50,
                    "comment_count": 8,
                    "share_count": 2
                }
            }
        }
    ]

    tool = ComputeEngagementSignals(
        items=test_items,
        weights={"reactions": 1.0, "comments": 3.0, "shares": 5.0},
        min_engagement_threshold=10,
        normalization_method="z_score"
    )

    print("Testing ComputeEngagementSignals tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))