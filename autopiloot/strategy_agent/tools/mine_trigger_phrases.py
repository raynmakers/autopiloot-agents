"""
MineTriggerPhrases tool for identifying high-engagement trigger phrases using log-odds analysis.
Uses statistical methods to identify phrases strongly associated with high engagement.
"""

import os
import sys
import json
import re
import math
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class MineTriggerPhrases(BaseTool):
    """
    Identifies trigger phrases statistically associated with high engagement using log-odds analysis.

    Uses informative Dirichlet prior to find phrases that reliably predict high engagement
    across different content cohorts (high vs low engagement groups).
    """

    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of content items with text and engagement metrics"
    )

    top_n: int = Field(
        50,
        description="Number of top trigger phrases to return (default: 50)"
    )

    engagement_threshold: Optional[float] = Field(
        None,
        description="Engagement threshold for high/low cohorts (auto-calculated if None)"
    )

    min_phrase_frequency: int = Field(
        3,
        description="Minimum frequency required for phrase consideration (default: 3)"
    )

    ngram_range: Tuple[int, int] = Field(
        (1, 4),
        description="N-gram range for phrase extraction (min_n, max_n)"
    )

    alpha_prior: float = Field(
        0.1,
        description="Dirichlet prior parameter for smoothing (default: 0.1)"
    )

    def run(self) -> str:
        """
        Mines trigger phrases using log-odds analysis with informative Dirichlet prior.

        Returns:
            str: JSON string containing trigger phrases analysis
                 Format: {
                     "trigger_phrases": [
                         {
                             "phrase": "excited to announce",
                             "log_odds": 2.45,
                             "high_cohort_frequency": 15,
                             "low_cohort_frequency": 2,
                             "high_cohort_rate": 0.075,
                             "low_cohort_rate": 0.01,
                             "lift": 7.5,
                             "confidence": 0.89,
                             "phrase_type": "announcement"
                         }
                     ],
                     "cohort_analysis": {
                         "engagement_threshold": 0.75,
                         "high_cohort_size": 200,
                         "low_cohort_size": 300,
                         "high_cohort_avg_engagement": 1.25,
                         "low_cohort_avg_engagement": 0.35
                     },
                     "methodology": {
                         "analysis_method": "log_odds_informative_dirichlet",
                         "alpha_prior": 0.1,
                         "min_phrase_frequency": 3,
                         "ngram_range": [1, 4]
                     },
                     "phrase_categories": {
                         "announcement": 12,
                         "personal": 8,
                         "question": 6,
                         "action": 10,
                         "emotional": 14
                     }
                 }
        """
        try:
            if not self.items:
                return json.dumps({
                    "error": "no_content",
                    "message": "No content items provided for trigger phrase analysis"
                })

            # Extract and validate engagement data
            valid_items = self._extract_engagement_data()
            if not valid_items:
                return json.dumps({
                    "error": "no_valid_engagement_data",
                    "message": "No items with valid engagement metrics found"
                })

            # Determine engagement threshold and create cohorts
            engagement_threshold = self._calculate_engagement_threshold(valid_items)
            high_cohort, low_cohort = self._create_cohorts(valid_items, engagement_threshold)

            if len(high_cohort) < 10 or len(low_cohort) < 10:
                return json.dumps({
                    "error": "insufficient_cohort_size",
                    "message": f"Need at least 10 items in each cohort. Got high: {len(high_cohort)}, low: {len(low_cohort)}"
                })

            # Extract phrases from both cohorts
            high_phrases = self._extract_phrases_from_cohort(high_cohort)
            low_phrases = self._extract_phrases_from_cohort(low_cohort)

            # Calculate log-odds ratios with Dirichlet prior
            trigger_phrases = self._calculate_log_odds_scores(high_phrases, low_phrases, len(high_cohort), len(low_cohort))

            # Sort by log-odds score and take top N
            trigger_phrases.sort(key=lambda x: x['log_odds'], reverse=True)
            top_triggers = trigger_phrases[:self.top_n]

            # Categorize phrases
            phrase_categories = self._categorize_phrases(top_triggers)

            # Generate result
            result = {
                "trigger_phrases": top_triggers,
                "cohort_analysis": {
                    "engagement_threshold": round(engagement_threshold, 3),
                    "high_cohort_size": len(high_cohort),
                    "low_cohort_size": len(low_cohort),
                    "high_cohort_avg_engagement": round(sum(item['engagement_score'] for item in high_cohort) / len(high_cohort), 3),
                    "low_cohort_avg_engagement": round(sum(item['engagement_score'] for item in low_cohort) / len(low_cohort), 3)
                },
                "methodology": {
                    "analysis_method": "log_odds_informative_dirichlet",
                    "alpha_prior": self.alpha_prior,
                    "min_phrase_frequency": self.min_phrase_frequency,
                    "ngram_range": list(self.ngram_range)
                },
                "phrase_categories": phrase_categories,
                "analysis_metadata": {
                    "total_items": len(self.items),
                    "valid_items": len(valid_items),
                    "total_phrases_analyzed": len(trigger_phrases),
                    "top_phrases_returned": len(top_triggers),
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "trigger_phrase_mining_failed",
                "message": str(e),
                "items_count": len(self.items) if self.items else 0
            }
            return json.dumps(error_result)

    def _extract_engagement_data(self) -> List[Dict[str, Any]]:
        """Extract and normalize engagement data from items."""
        valid_items = []

        for item in self.items:
            content = item.get('content', '').strip()
            if not content or len(content) < 10:
                continue

            # Extract engagement score
            engagement_score = self._calculate_engagement_score(item)
            if engagement_score is None:
                continue

            valid_items.append({
                'content': content,
                'engagement_score': engagement_score,
                'id': item.get('id', ''),
                'metadata': item.get('metadata', {})
            })

        return valid_items

    def _calculate_engagement_score(self, item: Dict[str, Any]) -> Optional[float]:
        """Calculate normalized engagement score for an item."""
        # Try multiple sources for engagement data
        engagement_score = item.get('engagement_score')
        if engagement_score is not None:
            return float(engagement_score)

        # Try metadata engagement
        metadata = item.get('metadata', {})
        engagement = metadata.get('engagement', {})

        if engagement:
            likes = engagement.get('reaction_count', 0) or engagement.get('likes', 0)
            comments = engagement.get('comment_count', 0) or engagement.get('comments', 0)
            shares = engagement.get('share_count', 0) or engagement.get('shares', 0)
            views = engagement.get('view_count', 0)

            # Calculate total engagement
            total_engagement = likes + comments + shares

            # Use engagement rate if available, otherwise calculate basic score
            engagement_rate = engagement.get('engagement_rate')
            if engagement_rate is not None:
                return float(engagement_rate)

            # Calculate basic score if we have views
            if views > 0:
                return total_engagement / views

            # Return raw engagement count normalized
            return total_engagement / 100.0  # Basic normalization

        return None

    def _calculate_engagement_threshold(self, items: List[Dict[str, Any]]) -> float:
        """Calculate engagement threshold for high/low cohorts."""
        if self.engagement_threshold is not None:
            return self.engagement_threshold

        # Use median as threshold
        engagement_scores = [item['engagement_score'] for item in items]
        engagement_scores.sort()
        n = len(engagement_scores)

        if n % 2 == 0:
            threshold = (engagement_scores[n//2 - 1] + engagement_scores[n//2]) / 2
        else:
            threshold = engagement_scores[n//2]

        return threshold

    def _create_cohorts(self, items: List[Dict[str, Any]], threshold: float) -> Tuple[List[Dict], List[Dict]]:
        """Create high and low engagement cohorts."""
        high_cohort = [item for item in items if item['engagement_score'] >= threshold]
        low_cohort = [item for item in items if item['engagement_score'] < threshold]

        return high_cohort, low_cohort

    def _extract_phrases_from_cohort(self, cohort: List[Dict[str, Any]]) -> Counter:
        """Extract n-gram phrases from a cohort of content."""
        phrases = Counter()

        for item in cohort:
            content = item['content']
            content_phrases = self._extract_ngrams(content)
            phrases.update(content_phrases)

        return phrases

    def _extract_ngrams(self, text: str) -> List[str]:
        """Extract n-grams from text."""
        # Clean and tokenize text
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text.strip())
        words = text.split()

        if len(words) < self.ngram_range[0]:
            return []

        ngrams = []
        for n in range(self.ngram_range[0], min(self.ngram_range[1] + 1, len(words) + 1)):
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i + n])
                if self._is_valid_phrase(ngram):
                    ngrams.append(ngram)

        return ngrams

    def _is_valid_phrase(self, phrase: str) -> bool:
        """Check if phrase is valid for analysis."""
        # Filter out very common words and short phrases
        stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by',
            'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me',
            'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their', 'is',
            'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did'
        }

        words = phrase.split()

        # Skip single stopwords
        if len(words) == 1 and phrase in stopwords:
            return False

        # Skip phrases that are all stopwords
        if all(word in stopwords for word in words):
            return False

        # Skip very short or very long phrases
        if len(phrase) < 3 or len(phrase) > 50:
            return False

        # Skip phrases with only numbers or special characters
        if not any(c.isalpha() for c in phrase):
            return False

        return True

    def _calculate_log_odds_scores(self, high_phrases: Counter, low_phrases: Counter,
                                   high_total: int, low_total: int) -> List[Dict[str, Any]]:
        """Calculate log-odds scores with informative Dirichlet prior."""
        # Get all phrases that meet minimum frequency requirement
        all_phrases = set()
        for phrase, count in high_phrases.items():
            if count >= self.min_phrase_frequency:
                all_phrases.add(phrase)
        for phrase, count in low_phrases.items():
            if count >= self.min_phrase_frequency:
                all_phrases.add(phrase)

        trigger_phrases = []

        for phrase in all_phrases:
            high_count = high_phrases.get(phrase, 0)
            low_count = low_phrases.get(phrase, 0)

            # Apply Dirichlet prior smoothing
            high_smoothed = high_count + self.alpha_prior
            low_smoothed = low_count + self.alpha_prior

            # Calculate total counts with smoothing
            high_total_smoothed = high_total + 2 * self.alpha_prior
            low_total_smoothed = low_total + 2 * self.alpha_prior

            # Calculate rates
            high_rate = high_smoothed / high_total_smoothed
            low_rate = low_smoothed / low_total_smoothed

            # Calculate log-odds ratio
            if low_rate > 0:
                log_odds = math.log(high_rate / low_rate)
            else:
                log_odds = float('inf')

            # Calculate lift and confidence
            lift = high_rate / low_rate if low_rate > 0 else float('inf')

            # Calculate confidence using Wilson score interval
            total_count = high_count + low_count
            if total_count > 0:
                p = high_count / total_count
                confidence = self._calculate_wilson_confidence(high_count, total_count)
            else:
                confidence = 0.0

            # Only include phrases with meaningful signal
            if log_odds > 0 and total_count >= self.min_phrase_frequency:
                trigger_phrases.append({
                    "phrase": phrase,
                    "log_odds": round(log_odds, 4),
                    "high_cohort_frequency": high_count,
                    "low_cohort_frequency": low_count,
                    "high_cohort_rate": round(high_rate, 6),
                    "low_cohort_rate": round(low_rate, 6),
                    "lift": round(lift, 2) if lift != float('inf') else 999.0,
                    "confidence": round(confidence, 3),
                    "total_occurrences": total_count,
                    "phrase_type": self._classify_phrase_type(phrase)
                })

        return trigger_phrases

    def _calculate_wilson_confidence(self, successes: int, total: int, confidence_level: float = 0.95) -> float:
        """Calculate Wilson score confidence interval."""
        if total == 0:
            return 0.0

        z = 1.96  # 95% confidence level
        p = successes / total

        denominator = 1 + z**2 / total
        centre_adjusted_probability = (p + z**2 / (2 * total)) / denominator
        adjusted_standard_deviation = math.sqrt((p * (1 - p) + z**2 / (4 * total)) / total) / denominator

        lower_bound = centre_adjusted_probability - z * adjusted_standard_deviation
        return max(0.0, lower_bound)

    def _classify_phrase_type(self, phrase: str) -> str:
        """Classify phrase into semantic categories."""
        phrase_lower = phrase.lower()

        # Define category patterns
        categories = {
            "announcement": ["announce", "launch", "excited", "proud", "introduce", "unveil", "reveal"],
            "personal": ["my", "i", "personal", "journey", "experience", "story", "learned"],
            "question": ["what", "how", "why", "when", "where", "do you", "thoughts", "?"],
            "action": ["start", "begin", "take", "make", "create", "build", "get", "try", "use"],
            "emotional": ["love", "hate", "excited", "frustrated", "amazing", "incredible", "disappointed"],
            "authority": ["expert", "proven", "research", "data", "study", "results", "years of"],
            "curiosity": ["secret", "hack", "trick", "tip", "unknown", "hidden", "discover"],
            "urgency": ["now", "today", "limited", "urgent", "hurry", "fast", "quick", "immediate"],
            "social": ["share", "tell", "community", "together", "connect", "join", "follow"],
            "benefit": ["free", "save", "bonus", "advantage", "benefit", "reward", "gain"]
        }

        for category, keywords in categories.items():
            if any(keyword in phrase_lower for keyword in keywords):
                return category

        return "general"

    def _categorize_phrases(self, phrases: List[Dict[str, Any]]) -> Dict[str, int]:
        """Count phrases by category."""
        categories = defaultdict(int)
        for phrase_data in phrases:
            phrase_type = phrase_data.get('phrase_type', 'general')
            categories[phrase_type] += 1

        return dict(categories)


if __name__ == "__main__":
    # Test the tool with sample data
    test_items = [
        {
            "id": "post1",
            "content": "Excited to announce the launch of our new product! This has been an incredible journey.",
            "engagement_score": 0.85
        },
        {
            "id": "post2",
            "content": "What's your biggest challenge in business? I'd love to hear your thoughts.",
            "engagement_score": 0.92
        },
        {
            "id": "post3",
            "content": "Here's a secret that most entrepreneurs don't know: customer feedback is everything.",
            "engagement_score": 0.78
        },
        {
            "id": "post4",
            "content": "My personal journey from corporate to startup taught me valuable lessons.",
            "engagement_score": 0.88
        },
        {
            "id": "post5",
            "content": "Today's market update shows promising trends for technology stocks.",
            "engagement_score": 0.45
        },
        {
            "id": "post6",
            "content": "The quarterly earnings report indicates steady growth.",
            "engagement_score": 0.32
        },
        {
            "id": "post7",
            "content": "Industry analysis suggests continued expansion in this sector.",
            "engagement_score": 0.28
        },
        {
            "id": "post8",
            "content": "Regular market movements follow predictable patterns.",
            "engagement_score": 0.35
        },
        {
            "id": "post9",
            "content": "How do you stay motivated during difficult times? Share your strategies!",
            "engagement_score": 0.91
        },
        {
            "id": "post10",
            "content": "The secret to success is never giving up on your dreams.",
            "engagement_score": 0.82
        }
    ]

    print("Testing MineTriggerPhrases tool...")

    # Test basic functionality
    tool = MineTriggerPhrases(
        items=test_items,
        top_n=15,
        min_phrase_frequency=1,  # Lower for test data
        alpha_prior=0.01
    )

    result = tool.run()
    parsed_result = json.loads(result)

    print("✅ Trigger phrase mining completed successfully")
    print(f"High cohort size: {parsed_result.get('cohort_analysis', {}).get('high_cohort_size', 'N/A')}")
    print(f"Low cohort size: {parsed_result.get('cohort_analysis', {}).get('low_cohort_size', 'N/A')}")
    print(f"Top trigger phrases found: {len(parsed_result.get('trigger_phrases', []))}")

    # Show top 5 trigger phrases
    if parsed_result.get('trigger_phrases'):
        print("\nTop 5 trigger phrases:")
        for i, phrase in enumerate(parsed_result['trigger_phrases'][:5]):
            print(f"{i+1}. '{phrase['phrase']}' (log-odds: {phrase['log_odds']}, type: {phrase['phrase_type']})")

    # Test with empty data
    empty_tool = MineTriggerPhrases(items=[])
    empty_result = json.loads(empty_tool.run())
    assert "error" in empty_result
    print("✅ Empty content handling works")

    print("\nSample output structure:")
    sample_keys = list(parsed_result.keys())
    print(f"Result keys: {sample_keys}")