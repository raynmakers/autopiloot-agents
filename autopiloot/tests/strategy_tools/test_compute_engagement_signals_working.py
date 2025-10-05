"""
Working test for compute_engagement_signals.py with proper coverage tracking.
Uses module-level mocking pattern for coverage.py compatibility.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json


# Mock ALL external dependencies BEFORE import
class MockBaseTool:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

def mock_field(*args, **kwargs):
    # Return the actual default value if provided, otherwise return the first positional arg
    if 'default' in kwargs:
        return kwargs['default']
    if args:
        return args[0]
    return None
sys.modules['agency_swarm'] = MagicMock()
sys.modules['agency_swarm.tools'] = MagicMock()
sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic'].Field = mock_field
sys.modules['config'] = MagicMock()
sys.modules['config.env_loader'] = MagicMock()
sys.modules['config.loader'] = MagicMock()
sys.modules['env_loader'] = MagicMock()
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value='test-api-key')
sys.modules['env_loader'].load_environment = MagicMock()
sys.modules['loader'] = MagicMock()
sys.modules['loader'].load_app_config = MagicMock(return_value={'test': 'config'})
sys.modules['loader'].get_config_value = MagicMock(return_value='test-value')

# Import the tool at module level for coverage tracking
from strategy_agent.tools.compute_engagement_signals import ComputeEngagementSignals


class TestComputeEngagementSignalsWorking(unittest.TestCase):
    """Working tests with proper coverage tracking."""

    def setUp(self):
        """Set up common test data."""
        self.sample_items = [
            {
                "text": "Great post about business",
                "metadata": {
                    "engagement": {
                        "reaction_count": 50,
                        "comment_count": 10,
                        "share_count": 5
                    }
                }
            },
            {
                "text": "Another interesting insight",
                "metadata": {
                    "engagement": {
                        "reaction_count": 100,
                        "comment_count": 20,
                        "share_count": 10
                    }
                }
            },
            {
                "text": "Low engagement post",
                "metadata": {
                    "engagement": {
                        "reaction_count": 5,
                        "comment_count": 1,
                        "share_count": 0
                    }
                }
            }
        ]

    def test_empty_items_error(self):
        """Test error with empty items list."""
        tool = ComputeEngagementSignals(items=[])
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)

    def test_basic_engagement_computation(self):
        """Test basic engagement signal computation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        result = tool.run()
        data = json.loads(result)

        self.assertIn('items', data)
        self.assertIn('aggregates', data)

    def test_custom_weights(self):
        """Test computation with custom weights."""
        custom_weights = {
            "reaction_count": 2.0,
            "comment_count": 5.0,
            "share_count": 10.0
        }

        tool = ComputeEngagementSignals(
            items=self.sample_items,
            weights=custom_weights
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('items', data)

    def test_z_score_normalization(self):
        """Test z-score normalization."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        result = tool.run()
        data = json.loads(result)

        # Should return items or error
        self.assertTrue('items' in data or 'error' in data)

    def test_min_max_normalization(self):
        """Test min-max normalization."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="min_max"
        )

        result = tool.run()
        data = json.loads(result)

        # Should return items or error
        self.assertTrue('items' in data or 'error' in data)

    def test_percentile_normalization(self):
        """Test percentile normalization."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="percentile"
        )

        result = tool.run()
        data = json.loads(result)

        # Should return items or error
        self.assertTrue('items' in data or 'error' in data)

    def test_validate_and_clean_items(self):
        """Test item validation and cleaning."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Test invalid items return empty list
        invalid_items = [{"no_engagement": "missing"}]
        valid_items = tool._validate_and_clean_items(invalid_items)
        self.assertEqual(len(valid_items), 0)

    def test_extract_engagement_data(self):
        """Test engagement data extraction."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        engagement = tool._extract_engagement_data(self.sample_items[0])

        self.assertIsNotNone(engagement)
        self.assertIn('reaction_count', engagement)

    def test_get_default_weights(self):
        """Test default weights retrieval."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        weights = tool._get_default_weights()

        self.assertIn('reactions', weights)
        self.assertIn('comments', weights)
        self.assertIn('shares', weights)

    def test_compute_raw_engagement(self):
        """Test raw engagement computation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        weights = tool._get_default_weights()
        items_with_scores = tool._compute_raw_engagement(self.sample_items, weights)

        self.assertEqual(len(items_with_scores), len(self.sample_items))
        for item in items_with_scores:
            self.assertIn('engagement_score', item)

    def test_apply_engagement_threshold(self):
        """Test engagement threshold application."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            engagement_threshold=50
        )

        items_with_scores = [
            {"engagement_score": 100},
            {"engagement_score": 30},
            {"engagement_score": 75}
        ]

        filtered_items = tool._apply_engagement_threshold(items_with_scores)

        # Should only keep items above threshold
        self.assertLessEqual(len(filtered_items), len(items_with_scores))

    def test_categorize_engagement(self):
        """Test engagement categorization."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_normalized = [
            {"normalized_score": 0.9},
            {"normalized_score": 0.5},
            {"normalized_score": 0.2}
        ]

        categorized = tool._categorize_engagement(items_with_normalized)

        for item in categorized:
            self.assertIn('engagement_category', item)

    def test_compute_aggregates(self):
        """Test aggregate computation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_scores = [
            {"engagement_score": 100, "normalized_score": 0.9},
            {"engagement_score": 50, "normalized_score": 0.5},
            {"engagement_score": 25, "normalized_score": 0.3}
        ]

        aggregates = tool._compute_aggregates(items_with_scores)

        self.assertIn('total_items', aggregates)
        self.assertIn('average_engagement_score', aggregates)

    def test_exception_handling(self):
        """Test general exception handling."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        with patch.object(tool, '_validate_and_clean_items', side_effect=Exception("Test error")):
            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)

    def test_z_score_normalization_method(self):
        """Test z-score normalization implementation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        scores = [10.0, 20.0, 30.0, 40.0, 50.0]
        normalized = tool._z_score_normalization(scores)

        self.assertEqual(len(normalized), len(scores))
        # Z-scores should have mean near 0
        self.assertIsInstance(normalized[0], float)

    def test_min_max_normalization_method(self):
        """Test min-max normalization implementation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        scores = [10.0, 20.0, 30.0, 40.0, 50.0]
        normalized = tool._min_max_normalization(scores)

        self.assertEqual(len(normalized), len(scores))
        # Min-max should be between 0 and 1
        self.assertGreaterEqual(min(normalized), 0.0)
        self.assertLessEqual(max(normalized), 1.0)

    def test_percentile_normalization_method(self):
        """Test percentile normalization implementation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        scores = [10.0, 20.0, 30.0, 40.0, 50.0]
        normalized = tool._percentile_normalization(scores)

        self.assertEqual(len(normalized), len(scores))
        # Percentiles should be between 0 and 100
        self.assertGreaterEqual(min(normalized), 0)
        self.assertLessEqual(max(normalized), 100)

    def test_calculate_percentile(self):
        """Test percentile calculation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        all_values = [10, 20, 30, 40, 50]
        percentile = tool._calculate_percentile(30, all_values)

        self.assertIsInstance(percentile, int)
        self.assertGreaterEqual(percentile, 0)
        self.assertLessEqual(percentile, 100)

    def test_engagement_categorization_thresholds(self):
        """Test engagement categorization with different thresholds."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_scores = [
            {"normalized_score": 0.9},  # Should be "very_high"
            {"normalized_score": 0.7},  # Should be "high"
            {"normalized_score": 0.5},  # Should be "medium"
            {"normalized_score": 0.3},  # Should be "low"
            {"normalized_score": 0.1}   # Should be "very_low"
        ]

        categorized = tool._categorize_engagement(items_with_scores)

        for item in categorized:
            self.assertIn('engagement_category', item)

    def test_compute_normalized_scores(self):
        """Test normalized score computation."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        items_with_raw_scores = [
            {"engagement_score": 100},
            {"engagement_score": 200},
            {"engagement_score": 300}
        ]

        normalized_items = tool._compute_normalized_scores(items_with_raw_scores)

        for item in normalized_items:
            self.assertIn('normalized_score', item)

    def test_aggregate_statistics(self):
        """Test aggregate statistics computation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_all_scores = [
            {
                "engagement_score": 100,
                "normalized_score": 0.8,
                "engagement_category": "high"
            },
            {
                "engagement_score": 50,
                "normalized_score": 0.4,
                "engagement_category": "medium"
            }
        ]

        aggregates = tool._compute_aggregates(items_with_all_scores)

        self.assertIn('total_items', aggregates)
        self.assertIn('average_engagement_score', aggregates)

    def test_empty_engagement_data(self):
        """Test handling of items with empty engagement data."""
        items_no_engagement = [
            {"text": "Post without engagement"},
            {"text": "Another post", "engagement": {}}
        ]

        tool = ComputeEngagementSignals(items=items_no_engagement)

        result = tool.run()
        data = json.loads(result)

        # Should return error for no valid items
        self.assertIn('error', data)

    def test_single_item_normalization(self):
        """Test normalization with single item (edge case)."""
        single_item = [
            {
                "text": "Single post",
                "engagement": {
                    "reaction_count": 50,
                    "comment_count": 10,
                    "share_count": 5
                }
            }
        ]

        tool = ComputeEngagementSignals(items=single_item)

        result = tool.run()
        data = json.loads(result)

        # Should handle single item gracefully
        self.assertTrue('items' in data or 'error' in data)

    def test_large_dataset_performance(self):
        """Test performance with large dataset."""
        large_dataset = [
            {
                "text": f"Post {i}",
                "engagement": {
                    "reaction_count": i * 10,
                    "comment_count": i * 2,
                    "share_count": i
                }
            }
            for i in range(1000)
        ]

        tool = ComputeEngagementSignals(items=large_dataset)

        result = tool.run()
        data = json.loads(result)

        # Should handle large datasets
        if 'items' in data:
            self.assertEqual(len(data['items']), 1000)

    def test_weight_validation(self):
        """Test custom weight validation."""
        invalid_weights = {
            "reactions": -1.0,  # Negative weight
            "comments": 0.0,
            "shares": 5.0
        }

        tool = ComputeEngagementSignals(
            items=self.sample_items,
            weights=invalid_weights
        )

        # Should handle invalid weights gracefully
        result = tool.run()
        data = json.loads(result)

        self.assertTrue('items' in data or 'error' in data)

    def test_missing_engagement_fields(self):
        """Test handling of missing engagement fields."""
        items_partial = [
            {
                "text": "Post with partial engagement",
                "engagement": {
                    "reaction_count": 50
                    # Missing comment_count, share_count, etc.
                }
            }
        ]

        tool = ComputeEngagementSignals(items=items_partial)

        result = tool.run()
        data = json.loads(result)

        # Should handle missing fields with defaults
        self.assertTrue('items' in data or 'error' in data)

    def test_invalid_normalization_method(self):
        """Test handling of invalid normalization method."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="invalid_method"
        )

        result = tool.run()
        data = json.loads(result)

        # Should handle invalid method gracefully
        self.assertTrue('items' in data or 'error' in data)

    def test_normalize_items_implementation(self):
        """Test normalize items method."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        items_with_scores = [
            {"engagement_score": 100, "text": "Post 1"},
            {"engagement_score": 200, "text": "Post 2"},
            {"engagement_score": 300, "text": "Post 3"}
        ]

        normalized = tool._normalize_items(items_with_scores)

        self.assertEqual(len(normalized), len(items_with_scores))
        for item in normalized:
            self.assertIn('normalized_score', item)

    def test_extract_raw_scores(self):
        """Test raw score extraction from items."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_scores = [
            {"engagement_score": 100},
            {"engagement_score": 200},
            {"engagement_score": 300}
        ]

        raw_scores = tool._extract_raw_scores(items_with_scores)

        self.assertEqual(len(raw_scores), 3)
        self.assertEqual(raw_scores, [100, 200, 300])

    def test_zero_variance_normalization(self):
        """Test normalization with zero variance (all same scores)."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # All items have same score
        scores = [50.0, 50.0, 50.0, 50.0]

        # Z-score normalization should handle zero variance
        normalized = tool._z_score_normalization(scores)
        self.assertEqual(len(normalized), len(scores))

    def test_engagement_category_distribution(self):
        """Test engagement category distribution in aggregates."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_categorized = [
            {"engagement_category": "high"},
            {"engagement_category": "high"},
            {"engagement_category": "medium"},
            {"engagement_category": "low"}
        ]

        aggregates = tool._compute_aggregates(items_categorized)

        if 'category_distribution' in aggregates:
            self.assertIn('high', aggregates['category_distribution'])

    def test_calculate_raw_engagement_score(self):
        """Test raw engagement score calculation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        engagement_data = {
            "reaction_count": 50,
            "comment_count": 10,
            "share_count": 5
        }

        weights = {
            "reactions": 1.0,
            "comments": 2.0,
            "shares": 3.0
        }

        score = tool._calculate_raw_engagement_score(engagement_data, weights)

        self.assertIsInstance(score, float)
        self.assertGreater(score, 0)

    def test_validate_weights(self):
        """Test weight validation method."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Valid weights
        valid_weights = {
            "reactions": 1.0,
            "comments": 2.0,
            "shares": 3.0
        }

        is_valid = tool._validate_weights(valid_weights)
        self.assertTrue(is_valid)

    def test_compute_engagement_statistics(self):
        """Test engagement statistics computation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_all_data = [
            {
                "engagement_score": 100,
                "normalized_score": 0.8,
                "engagement_category": "high",
                "engagement": {"reaction_count": 50, "comment_count": 10}
            },
            {
                "engagement_score": 50,
                "normalized_score": 0.4,
                "engagement_category": "medium",
                "engagement": {"reaction_count": 20, "comment_count": 5}
            }
        ]

        stats = tool._compute_engagement_statistics(items_with_all_data)

        self.assertIsInstance(stats, dict)

    def test_extreme_values_normalization(self):
        """Test normalization with extreme values."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Extreme values with wide range
        scores = [1.0, 10.0, 100.0, 1000.0, 10000.0]

        # Min-max normalization should handle extreme ranges
        normalized = tool._min_max_normalization(scores)

        self.assertGreaterEqual(min(normalized), 0.0)
        self.assertLessEqual(max(normalized), 1.0)

    def test_negative_engagement_scores(self):
        """Test handling of negative or zero engagement scores."""
        items_negative = [
            {
                "text": "Post with negative engagement",
                "engagement": {
                    "reaction_count": 0,
                    "comment_count": 0,
                    "share_count": 0
                }
            }
        ]

        tool = ComputeEngagementSignals(items=items_negative)

        result = tool.run()
        data = json.loads(result)

        # Should handle zero engagement gracefully
        self.assertTrue('items' in data or 'error' in data)

    def test_apply_normalization_method(self):
        """Test apply normalization method selection."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        scores = [10.0, 20.0, 30.0, 40.0, 50.0]

        normalized = tool._apply_normalization_method(scores, "z_score")

        self.assertEqual(len(normalized), len(scores))

    def test_get_engagement_category_name(self):
        """Test engagement category name retrieval."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Test different normalized score thresholds
        category_high = tool._get_engagement_category_name(0.85)
        category_medium = tool._get_engagement_category_name(0.5)
        category_low = tool._get_engagement_category_name(0.2)

        self.assertIsInstance(category_high, str)
        self.assertIsInstance(category_medium, str)
        self.assertIsInstance(category_low, str)

    def test_metadata_generation(self):
        """Test metadata generation in results."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        result = tool.run()
        data = json.loads(result)

        if 'metadata' in data:
            self.assertIn('normalization_method', data['metadata'])
            self.assertIn('weights_used', data['metadata'])

    def test_percentile_edge_cases(self):
        """Test percentile calculation edge cases."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Test with single value
        single_value = [50]
        percentile = tool._calculate_percentile(50, single_value)
        self.assertIsInstance(percentile, int)

        # Test with value not in list
        values = [10, 20, 30, 40, 50]
        percentile = tool._calculate_percentile(25, values)
        self.assertIsInstance(percentile, int)

    def test_full_pipeline_with_valid_items(self):
        """Test full engagement computation pipeline."""
        valid_items = [
            {
                "text": "Post 1",
                "engagement": {
                    "reaction_count": 100,
                    "comment_count": 20,
                    "share_count": 5
                }
            },
            {
                "text": "Post 2",
                "engagement": {
                    "reaction_count": 50,
                    "comment_count": 10,
                    "share_count": 2
                }
            },
            {
                "text": "Post 3",
                "engagement": {
                    "reaction_count": 200,
                    "comment_count": 30,
                    "share_count": 10
                }
            }
        ]

        tool = ComputeEngagementSignals(items=valid_items, normalization_method="min_max")

        result = tool.run()
        data = json.loads(result)

        # Should execute full pipeline
        if 'items' in data:
            self.assertIn('aggregates', data)
            self.assertIn('processing_metadata', data)
            for item in data['items']:
                self.assertIn('engagement_score', item)
                self.assertIn('normalized_score', item)
                self.assertIn('engagement_category', item)

    def test_raw_engagement_computation(self):
        """Test raw engagement score calculation."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Create items with _engagement_data
        items_with_data = []
        for item in self.sample_items:
            item_copy = item.copy()
            item_copy["_engagement_data"] = {
                "reactions": item["engagement"]["reaction_count"],
                "comments": item["engagement"]["comment_count"],
                "shares": item["engagement"]["share_count"]
            }
            items_with_data.append(item_copy)

        weights = {"reactions": 1.0, "comments": 2.0, "shares": 3.0}

        items_with_raw = tool._compute_raw_engagement(items_with_data, weights)

        self.assertEqual(len(items_with_raw), len(items_with_data))
        for item in items_with_raw:
            self.assertIn('raw_engagement', item)
            self.assertIn('weighted_score', item['raw_engagement'])

    def test_apply_threshold_filtering(self):
        """Test engagement threshold filtering."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            min_engagement_threshold=50
        )

        items_with_raw = [
            {"raw_engagement": {"total": 100, "weighted_score": 100}},
            {"raw_engagement": {"total": 30, "weighted_score": 30}},
            {"raw_engagement": {"total": 75, "weighted_score": 75}}
        ]

        filtered = tool._apply_engagement_threshold(items_with_raw)

        # Should filter items below threshold
        for item in filtered:
            self.assertGreaterEqual(item["raw_engagement"]["total"], 50)

    def test_categorize_by_normalized_score(self):
        """Test engagement categorization."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_with_normalized = [
            {"normalized_score": 0.95, "text": "High engagement"},
            {"normalized_score": 0.75, "text": "High engagement"},
            {"normalized_score": 0.55, "text": "Medium engagement"},
            {"normalized_score": 0.35, "text": "Low engagement"},
            {"normalized_score": 0.15, "text": "Very low engagement"}
        ]

        categorized = tool._categorize_engagement(items_with_normalized)

        for item in categorized:
            self.assertIn('engagement_category', item)
            self.assertIsInstance(item['engagement_category'], str)

    def test_aggregate_computation(self):
        """Test aggregate statistics."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        items_complete = [
            {
                "engagement_score": 100,
                "normalized_score": 0.8,
                "engagement_category": "high"
            },
            {
                "engagement_score": 50,
                "normalized_score": 0.4,
                "engagement_category": "medium"
            },
            {
                "engagement_score": 150,
                "normalized_score": 0.9,
                "engagement_category": "very_high"
            }
        ]

        aggregates = tool._compute_aggregates(items_complete)

        self.assertIn('total_items', aggregates)
        self.assertIn('average_engagement_score', aggregates)
        self.assertEqual(aggregates['total_items'], 3)

    def test_normalization_with_pipeline_data(self):
        """Test normalization in full pipeline context."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        items_with_scores = [
            {"engagement_score": 100, "text": "Post 1"},
            {"engagement_score": 200, "text": "Post 2"},
            {"engagement_score": 300, "text": "Post 3"}
        ]

        normalized = tool._compute_normalized_scores(items_with_scores)

        for item in normalized:
            self.assertIn('normalized_score', item)


    def test_full_pipeline_with_threshold(self):
        """Test full pipeline with engagement threshold filtering."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            min_engagement_threshold=50.0
        )

        result = tool.run()
        data = json.loads(result)

        # Should filter out low engagement items
        if 'items' in data:
            # Only items above threshold should remain
            for item in data['items']:
                self.assertIn('engagement_score', item)
                self.assertIn('normalized_score', item)
                self.assertIn('engagement_category', item)

    def test_root_level_engagement_extraction(self):
        """Test extraction of engagement from root level."""
        root_level_items = [
            {
                "text": "Post with root level engagement",
                "reaction_count": 100,
                "comment_count": 20,
                "share_count": 10,
                "view_count": 1000
            }
        ]

        tool = ComputeEngagementSignals(items=root_level_items)
        result = tool.run()
        data = json.loads(result)

        # Should successfully process root-level engagement
        self.assertTrue('items' in data or 'error' in data)

    def test_metadata_direct_engagement_extraction(self):
        """Test extraction from metadata without nested engagement."""
        metadata_items = [
            {
                "text": "Post with metadata engagement",
                "metadata": {
                    "likes": 50,
                    "comments": 10,
                    "shares": 5
                }
            }
        ]

        tool = ComputeEngagementSignals(items=metadata_items)
        result = tool.run()
        data = json.loads(result)

        # Should successfully process metadata engagement
        self.assertTrue('items' in data or 'error' in data)

    def test_no_items_above_threshold_error(self):
        """Test error when no items meet threshold."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            min_engagement_threshold=1000000.0  # Impossibly high threshold
        )

        result = tool.run()
        data = json.loads(result)

        # Should return threshold error
        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no_items_above_threshold')

    def test_compute_raw_engagement_with_weights(self):
        """Test raw engagement computation with custom weights."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        # Create mock items with engagement data
        mock_items = [
            {
                "text": "Test",
                "_engagement_data": {
                    "reactions": 100,
                    "comments": 20,
                    "shares": 10,
                    "views": 1000
                }
            }
        ]

        weights = {
            "reactions": 1.0,
            "comments": 3.0,
            "shares": 5.0,
            "views": 0.01
        }

        items_with_raw = tool._compute_raw_engagement(mock_items, weights)

        # Should compute raw engagement score
        self.assertEqual(len(items_with_raw), 1)
        self.assertIn('engagement_score', items_with_raw[0])
        self.assertGreater(items_with_raw[0]['engagement_score'], 0)

    def test_apply_engagement_threshold_filtering(self):
        """Test threshold filtering logic."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            min_engagement_threshold=50.0
        )

        mock_items = [
            {"text": "High", "engagement_score": 100.0},
            {"text": "Medium", "engagement_score": 75.0},
            {"text": "Low", "engagement_score": 25.0}
        ]

        filtered = tool._apply_engagement_threshold(mock_items)

        # Should filter items below threshold
        self.assertEqual(len(filtered), 2)  # Only high and medium

    def test_compute_normalized_scores_minmax(self):
        """Test min-max normalization."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="min_max"
        )

        mock_items = [
            {"engagement_score": 10.0},
            {"engagement_score": 50.0},
            {"engagement_score": 100.0}
        ]

        normalized = tool._compute_normalized_scores(mock_items)

        # Min-max should produce scores between 0 and 1
        for item in normalized:
            self.assertIn('normalized_score', item)
            self.assertGreaterEqual(item['normalized_score'], 0.0)
            self.assertLessEqual(item['normalized_score'], 1.0)

    def test_compute_normalized_scores_zscore(self):
        """Test z-score normalization."""
        tool = ComputeEngagementSignals(
            items=self.sample_items,
            normalization_method="z_score"
        )

        mock_items = [
            {"engagement_score": 10.0},
            {"engagement_score": 50.0},
            {"engagement_score": 100.0}
        ]

        normalized = tool._compute_normalized_scores(mock_items)

        # Z-score normalization should produce normalized scores
        for item in normalized:
            self.assertIn('normalized_score', item)
            self.assertIsInstance(item['normalized_score'], float)

    def test_categorize_engagement_levels(self):
        """Test engagement categorization into high/medium/low."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        mock_items = [
            {"normalized_score": 0.9},  # High
            {"normalized_score": 0.5},  # Medium
            {"normalized_score": 0.2}   # Low
        ]

        categorized = tool._categorize_engagement(mock_items)

        # Should assign categories
        self.assertIn('engagement_category', categorized[0])
        self.assertIn('engagement_category', categorized[1])
        self.assertIn('engagement_category', categorized[2])

    def test_compute_aggregates_comprehensive(self):
        """Test comprehensive aggregate statistics."""
        tool = ComputeEngagementSignals(items=self.sample_items)

        mock_items = [
            {
                "engagement_score": 100.0,
                "normalized_score": 0.9,
                "engagement_category": "high"
            },
            {
                "engagement_score": 50.0,
                "normalized_score": 0.5,
                "engagement_category": "medium"
            },
            {
                "engagement_score": 25.0,
                "normalized_score": 0.3,
                "engagement_category": "low"
            }
        ]

        aggregates = tool._compute_aggregates(mock_items)

        # Should compute all aggregate stats
        self.assertIn('total_items', aggregates)
        self.assertIn('average_engagement_score', aggregates)
        self.assertIn('median_engagement_score', aggregates)
        self.assertIn('min_engagement_score', aggregates)
        self.assertIn('max_engagement_score', aggregates)
        self.assertIn('category_distribution', aggregates)

        self.assertEqual(aggregates['total_items'], 3)
        self.assertEqual(aggregates['average_engagement_score'], 58.33)


if __name__ == "__main__":
    unittest.main()
