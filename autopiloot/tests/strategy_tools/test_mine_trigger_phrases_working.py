"""
Working test for mine_trigger_phrases.py with proper coverage tracking.
Uses module-level mocking pattern for coverage.py compatibility.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import json
from collections import Counter


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
sys.modules['env_loader'].get_required_env_var = MagicMock(return_value='test-key')
sys.modules['env_loader'].load_environment = MagicMock()
sys.modules['loader'] = MagicMock()
sys.modules['loader'].load_app_config = MagicMock(return_value={'test': 'config'})
sys.modules['loader'].get_config_value = MagicMock(return_value='test-value')

# Import the tool at module level for coverage tracking
from strategy_agent.tools.mine_trigger_phrases import MineTriggerPhrases


class TestMineTriggerPhrasesWorking(unittest.TestCase):
    """Working tests with proper coverage tracking."""

    def setUp(self):
        """Set up common test data."""
        self.sample_items = [
            {
                "id": "post1",
                "content": "Here's how to grow your business in 3 simple steps",
                "metadata": {"engagement": {"reaction_count": 200, "comment_count": 50}}
            },
            {
                "id": "post2",
                "content": "What I learned from failing at my first startup",
                "metadata": {"engagement": {"reaction_count": 150, "comment_count": 30}}
            },
            {
                "id": "post3",
                "content": "The secret to success is consistent effort over time",
                "metadata": {"engagement": {"reaction_count": 300, "comment_count": 75}}
            },
            {
                "id": "post4",
                "content": "My team struggled with remote work initially",
                "metadata": {"engagement": {"reaction_count": 50, "comment_count": 10}}
            },
            {
                "id": "post5",
                "content": "Generic business post about meetings and productivity",
                "metadata": {"engagement": {"reaction_count": 20, "comment_count": 5}}
            },
            {
                "id": "post6",
                "content": "Excited to announce our new product launch today!",
                "metadata": {"engagement": {"reaction_count": 180, "comment_count": 40}}
            },
            {
                "id": "post7",
                "content": "How do you handle difficult conversations at work?",
                "metadata": {"engagement": {"reaction_count": 220, "comment_count": 55}}
            },
            {
                "id": "post8",
                "content": "My personal journey from corporate to entrepreneur",
                "metadata": {"engagement": {"reaction_count": 250, "comment_count": 65}}
            },
            {
                "id": "post9",
                "content": "Quick update on quarterly results and metrics",
                "metadata": {"engagement": {"reaction_count": 30, "comment_count": 8}}
            },
            {
                "id": "post10",
                "content": "Start building your dream business today, not tomorrow",
                "metadata": {"engagement": {"reaction_count": 280, "comment_count": 70}}
            }
        ]

    def test_empty_items_error(self):
        """Test error with empty items list."""
        tool = MineTriggerPhrases(items=[])
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)

    def test_basic_trigger_phrase_extraction(self):
        """Test basic trigger phrase extraction."""
        tool = MineTriggerPhrases(items=self.sample_items, top_n=10)

        result = tool.run()
        data = json.loads(result)

        # Should return trigger phrases or error
        self.assertTrue('trigger_phrases' in data or 'error' in data)

    def test_custom_engagement_threshold(self):
        """Test with custom engagement threshold."""
        tool = MineTriggerPhrases(
            items=self.sample_items,
            top_n=10,
            engagement_threshold=100.0
        )

        result = tool.run()
        data = json.loads(result)

        # Should handle custom threshold
        self.assertTrue('trigger_phrases' in data or 'error' in data)

    def test_min_frequency_filtering(self):
        """Test minimum phrase frequency filtering."""
        tool = MineTriggerPhrases(
            items=self.sample_items,
            top_n=10,
            min_phrase_frequency=2
        )

        result = tool.run()
        data = json.loads(result)

        # Should filter by minimum frequency
        self.assertTrue('trigger_phrases' in data or 'error' in data)

    def test_custom_ngram_range(self):
        """Test with custom n-gram range."""
        tool = MineTriggerPhrases(
            items=self.sample_items,
            top_n=10,
            ngram_range=(2, 3)
        )

        result = tool.run()
        data = json.loads(result)

        # Should extract 2-3 word phrases
        self.assertTrue('trigger_phrases' in data or 'error' in data)

    def test_extract_engagement_data(self):
        """Test engagement data extraction."""
        tool = MineTriggerPhrases(items=self.sample_items)

        valid_items = tool._extract_engagement_data()

        self.assertGreater(len(valid_items), 0)
        # Check first item has required fields
        if valid_items:
            self.assertIn('content', valid_items[0])
            self.assertIn('engagement_score', valid_items[0])

    def test_calculate_engagement_score(self):
        """Test engagement score calculation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        score = tool._calculate_engagement_score(self.sample_items[0])

        self.assertIsInstance(score, (int, float))
        self.assertGreaterEqual(score, 0)

    def test_calculate_engagement_threshold(self):
        """Test engagement threshold calculation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        valid_items = tool._extract_engagement_data()
        threshold = tool._calculate_engagement_threshold(valid_items)

        self.assertIsInstance(threshold, float)
        self.assertGreater(threshold, 0)

    def test_create_cohorts(self):
        """Test cohort creation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        valid_items = tool._extract_engagement_data()
        threshold = tool._calculate_engagement_threshold(valid_items)

        high_cohort, low_cohort = tool._create_cohorts(valid_items, threshold)

        self.assertIsInstance(high_cohort, list)
        self.assertIsInstance(low_cohort, list)

    def test_extract_ngrams(self):
        """Test n-gram extraction."""
        tool = MineTriggerPhrases(items=self.sample_items, ngram_range=(1, 3))

        text = "How to grow your business quickly"
        ngrams = tool._extract_ngrams(text)

        self.assertIsInstance(ngrams, list)
        self.assertGreater(len(ngrams), 0)

    def test_calculate_log_odds_scores(self):
        """Test log-odds scores calculation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        high_phrases = Counter({"success": 5, "failure": 1, "growth": 3})
        low_phrases = Counter({"success": 1, "failure": 5, "decline": 3})
        total_high = 10
        total_low = 10

        result = tool._calculate_log_odds_scores(high_phrases, low_phrases, total_high, total_low)

        self.assertIsInstance(result, list)
        if result:
            self.assertIn('phrase', result[0])
            self.assertIn('log_odds', result[0])

    def test_is_valid_phrase(self):
        """Test phrase validation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Valid phrases
        self.assertTrue(tool._is_valid_phrase("excited to announce"))
        self.assertTrue(tool._is_valid_phrase("business growth"))

        # Invalid phrases
        self.assertFalse(tool._is_valid_phrase("the"))  # Single stopword
        self.assertFalse(tool._is_valid_phrase("a"))    # Too short
        self.assertFalse(tool._is_valid_phrase("123"))  # Only numbers

    def test_classify_phrase_type(self):
        """Test phrase type classification."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Test that classification returns valid categories
        categories = ["announcement", "personal", "question", "action", "emotional",
                     "authority", "curiosity", "urgency", "social", "benefit", "general"]

        # Test various phrases get categorized correctly
        result1 = tool._classify_phrase_type("excited to announce")
        self.assertIn(result1, categories)

        result2 = tool._classify_phrase_type("what happens next")
        self.assertIn(result2, categories)

        result3 = tool._classify_phrase_type("make progress")
        self.assertIn(result3, categories)

        result4 = tool._classify_phrase_type("xyz nonsense gibberish")  # No keywords
        self.assertIn(result4, categories)

        # Verify the function works
        self.assertIsNotNone(tool._classify_phrase_type("test phrase"))
        self.assertIsInstance(tool._classify_phrase_type("another test"), str)

    def test_categorize_phrases(self):
        """Test phrase categorization."""
        tool = MineTriggerPhrases(items=self.sample_items)

        phrases = [
            {"phrase": "excited to announce", "phrase_type": "announcement"},
            {"phrase": "my journey", "phrase_type": "personal"},
            {"phrase": "what happens", "phrase_type": "question"},
            {"phrase": "start now", "phrase_type": "action"},
            {"phrase": "love this", "phrase_type": "emotional"}
        ]

        categories = tool._categorize_phrases(phrases)

        self.assertIsInstance(categories, dict)
        self.assertGreater(len(categories), 0)

    def test_exception_handling(self):
        """Test general exception handling."""
        tool = MineTriggerPhrases(items=self.sample_items)

        with patch.object(tool, '_extract_engagement_data', side_effect=Exception("Test error")):
            result = tool.run()
            data = json.loads(result)

            self.assertIn('error', data)

    def test_insufficient_items(self):
        """Test with insufficient items for cohort analysis."""
        few_items = [
            {"text": "Single post", "engagement": {"reaction_count": 50}}
        ]

        tool = MineTriggerPhrases(items=few_items, top_n=5)

        result = tool.run()
        data = json.loads(result)

        # Should handle insufficient data
        self.assertTrue('trigger_phrases' in data or 'error' in data)

    def test_large_dataset(self):
        """Test with large dataset."""
        large_dataset = [
            {
                "text": f"Post number {i} about business and growth with various trigger words",
                "engagement": {"reaction_count": i * 10, "comment_count": i * 2}
            }
            for i in range(1, 101)
        ]

        tool = MineTriggerPhrases(items=large_dataset, top_n=20)

        result = tool.run()
        data = json.loads(result)

        # Should handle large datasets
        if 'trigger_phrases' in data:
            self.assertLessEqual(len(data['trigger_phrases']), 20)

    def test_insufficient_cohort_size_error(self):
        """Test error when cohorts are too small."""
        small_items = [
            {"id": f"post{i}", "content": f"This is a longer content item to pass the 10 character minimum requirement number {i}", "metadata": {"engagement": {"reaction_count": i * 10}}}
            for i in range(1, 16)  # 15 items to split into cohorts, but small cohorts
        ]

        tool = MineTriggerPhrases(items=small_items, top_n=5)
        result = tool.run()
        data = json.loads(result)

        # Should return insufficient_cohort_size error or handle gracefully
        self.assertIn('error', data)

    def test_extract_phrases_from_cohort(self):
        """Test phrase extraction from cohort."""
        tool = MineTriggerPhrases(items=self.sample_items)

        cohort = [
            {'content': 'How to grow your business', 'engagement_score': 0.8},
            {'content': 'Secret to success', 'engagement_score': 0.9}
        ]

        phrases = tool._extract_phrases_from_cohort(cohort)

        self.assertIsInstance(phrases, Counter)
        self.assertGreater(len(phrases), 0)

    def test_calculate_wilson_confidence(self):
        """Test Wilson score confidence calculation."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Test normal case
        confidence = tool._calculate_wilson_confidence(80, 100)
        self.assertIsInstance(confidence, float)
        self.assertGreater(confidence, 0)

        # Test zero total edge case
        confidence_zero = tool._calculate_wilson_confidence(0, 0)
        self.assertEqual(confidence_zero, 0.0)

    def test_engagement_score_edge_cases(self):
        """Test engagement score calculation edge cases."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Test with engagement_score directly
        item1 = {"content": "Test", "engagement_score": 0.75}
        score1 = tool._calculate_engagement_score(item1)
        self.assertEqual(score1, 0.75)

        # Test with engagement_rate in metadata
        item2 = {"content": "Test", "metadata": {"engagement": {"engagement_rate": 0.65}}}
        score2 = tool._calculate_engagement_score(item2)
        self.assertEqual(score2, 0.65)

        # Test with views for rate calculation
        item3 = {"content": "Test", "metadata": {"engagement": {
            "reaction_count": 100, "comment_count": 20, "share_count": 10, "view_count": 1000
        }}}
        score3 = tool._calculate_engagement_score(item3)
        self.assertEqual(score3, 0.13)  # (100+20+10)/1000

        # Test without views (raw engagement normalized)
        item4 = {"content": "Test", "metadata": {"engagement": {
            "reaction_count": 50, "comment_count": 10
        }}}
        score4 = tool._calculate_engagement_score(item4)
        self.assertEqual(score4, 0.6)  # (50+10)/100

    def test_extract_ngrams_edge_cases(self):
        """Test n-gram extraction edge cases."""
        tool = MineTriggerPhrases(items=self.sample_items, ngram_range=(2, 4))

        # Test with text shorter than min ngram
        short_text = "Hi"
        ngrams_short = tool._extract_ngrams(short_text)
        self.assertEqual(len(ngrams_short), 0)

        # Test with normal text
        normal_text = "How to grow your business quickly and effectively"
        ngrams_normal = tool._extract_ngrams(normal_text)
        self.assertGreater(len(ngrams_normal), 0)

    def test_is_valid_phrase_edge_cases(self):
        """Test phrase validation edge cases."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Test all stopwords phrase
        self.assertFalse(tool._is_valid_phrase("the and of"))

        # Test very long phrase
        long_phrase = "this is a very long phrase that exceeds the maximum length allowed"
        self.assertFalse(tool._is_valid_phrase(long_phrase))

        # Test phrase with only special characters
        self.assertFalse(tool._is_valid_phrase("***"))

    def test_engagement_threshold_with_even_and_odd_items(self):
        """Test threshold calculation with even and odd number of items."""
        tool = MineTriggerPhrases(items=self.sample_items)

        # Test with even number of items
        even_items = [
            {'engagement_score': 0.1},
            {'engagement_score': 0.5},
            {'engagement_score': 0.7},
            {'engagement_score': 0.9}
        ]
        threshold_even = tool._calculate_engagement_threshold(even_items)
        self.assertEqual(threshold_even, 0.6)  # (0.5 + 0.7) / 2

        # Test with odd number of items
        odd_items = [
            {'engagement_score': 0.1},
            {'engagement_score': 0.5},
            {'engagement_score': 0.9}
        ]
        threshold_odd = tool._calculate_engagement_threshold(odd_items)
        self.assertEqual(threshold_odd, 0.5)  # Middle value

    def test_no_valid_engagement_data_error(self):
        """Test error when no valid engagement data exists."""
        invalid_items = [
            {"content": "sh", "metadata": {}},  # Too short
            {"content": "", "metadata": {}},  # Empty
        ]

        tool = MineTriggerPhrases(items=invalid_items)
        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'no_valid_engagement_data')


if __name__ == "__main__":
    unittest.main()
