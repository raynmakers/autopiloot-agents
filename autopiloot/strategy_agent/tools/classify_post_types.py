"""
ClassifyPostTypes tool for categorizing LinkedIn posts into content type taxonomy.
Uses LLM-assisted classification to identify post types with confidence scores.
"""

import os
import sys
import json
import re
import yaml
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class ClassifyPostTypes(BaseTool):
    """
    Classifies LinkedIn posts into content type taxonomy with confidence scores.

    Uses LLM-assisted analysis or heuristic-based classification to categorize posts
    and generate distribution insights for content strategy development.
    """

    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of content items to classify"
    )

    taxonomy: Optional[List[str]] = Field(
        None,
        description="Custom taxonomy for post types (uses default if not provided)"
    )

    model: str = Field(
        "gpt-4o",
        description="LLM model to use for classification (default: gpt-4o)"
    )

    min_text_length: int = Field(
        10,
        description="Minimum text length to attempt classification (default: 10)"
    )

    use_llm: bool = Field(
        True,
        description="Whether to use LLM for classification (fallback to heuristics if False)"
    )

    batch_size: int = Field(
        10,
        description="Number of posts to classify in each LLM batch (default: 10)"
    )

    def _load_settings(self) -> Dict[str, Any]:
        """Load configuration from settings.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def run(self) -> str:
        """
        Classifies posts into content types with confidence scores.

        Returns:
            str: JSON string containing classified items and distribution analysis
                 Format: {
                     "items": [
                         {
                             "id": "urn:li:activity:12345",
                             "post_type": "how_to",
                             "confidence": 0.87,
                             "reasoning": "Contains step-by-step instructions",
                             "secondary_types": ["educational", "actionable"]
                         }
                     ],
                     "distribution": {
                         "how_to": 15,
                         "personal_story": 12,
                         "opinion": 8,
                         "case_study": 5
                     },
                     "analysis": {
                         "total_classified": 40,
                         "high_confidence": 32,
                         "engagement_by_type": {
                             "how_to": 0.75,
                             "personal_story": 0.68
                         },
                         "top_performing_types": ["how_to", "case_study"]
                     },
                     "taxonomy_used": [...],
                     "processing_metadata": {...}
                 }
        """
        try:
            if not self.items:
                return json.dumps({
                    "error": "no_items",
                    "message": "No items provided for classification"
                })

            # Get taxonomy
            taxonomy = self._get_taxonomy()

            # Validate and filter items
            valid_items = self._validate_items(self.items)

            if not valid_items:
                return json.dumps({
                    "error": "no_valid_items",
                    "message": "No items contain sufficient text for classification"
                })

            # Load settings for LLM configuration
            settings = self._load_settings()
            task_config = settings.get('llm', {}).get('tasks', {}).get('strategy_classify_posts', {})
            model = task_config.get('model', self.model)

            # Classify posts
            if self.use_llm:
                classified_items = self._classify_with_llm(valid_items, taxonomy, model)
            else:
                classified_items = self._classify_with_heuristics(valid_items, taxonomy)

            # Calculate distribution
            distribution = self._calculate_distribution(classified_items)

            # Analyze engagement by type
            engagement_analysis = self._analyze_engagement_by_type(classified_items)

            # Generate insights
            analysis = self._generate_analysis(classified_items, distribution, engagement_analysis)

            # Prepare response
            result = {
                "items": classified_items,
                "distribution": distribution,
                "analysis": analysis,
                "taxonomy_used": taxonomy,
                "processing_metadata": {
                    "total_input_items": len(self.items),
                    "valid_items": len(valid_items),
                    "classified_items": len(classified_items),
                    "classification_method": "llm" if self.use_llm else "heuristic",
                    "model": self.model if self.use_llm else "heuristic_rules",
                    "batch_size": self.batch_size,
                    "processed_at": datetime.now(timezone.utc).isoformat()
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "classification_failed",
                "message": str(e),
                "item_count": len(self.items) if self.items else 0,
                "use_llm": self.use_llm,
                "model": self.model
            }
            return json.dumps(error_result)

    def _get_taxonomy(self) -> List[str]:
        """
        Get post type taxonomy for classification.

        Returns:
            List[str]: Post type categories
        """
        if self.taxonomy:
            return self.taxonomy

        # Default LinkedIn post taxonomy
        return [
            "personal_story",      # Personal experiences, journey, lessons learned
            "how_to",             # Step-by-step guides, tutorials, instructional content
            "listicle",           # Numbered lists, bullet points, structured tips
            "opinion",            # Thoughts, perspectives, takes on industry topics
            "case_study",         # Detailed analysis of specific examples or projects
            "announcement",       # News, updates, launches, achievements
            "question",           # Asking for input, polls, discussion starters
            "quote",              # Inspirational quotes, famous sayings
            "behind_scenes",      # Workplace culture, team activities, process insights
            "industry_news",      # Commentary on industry developments
            "motivational",       # Inspiring content, encouragement, mindset
            "educational",        # Teaching concepts, explaining complex topics
            "promotional",        # Product/service promotion, CTAs, sales content
            "networking",         # Connection requests, collaboration invitations
            "celebration",        # Achievements, milestones, congratulations
            "controversial",      # Contrarian views, debate-worthy topics
            "data_insights",      # Statistics, research findings, trend analysis
            "resource_sharing"    # Tools, links, recommendations
        ]

    def _validate_items(self, items: List[Dict]) -> List[Dict]:
        """
        Validate and filter items for classification.

        Args:
            items: Input items

        Returns:
            List[Dict]: Valid items for classification
        """
        valid_items = []

        for item in items:
            # Extract text content
            text = item.get("content", "") or item.get("text", "")

            if not text or len(text.strip()) < self.min_text_length:
                continue

            # Check for links-only posts
            if self._is_links_only(text):
                # Still classify but note it
                item["is_links_only"] = True

            # Add cleaned text
            item["cleaned_text"] = self._clean_text(text)
            valid_items.append(item)

        return valid_items

    def _is_links_only(self, text: str) -> bool:
        """Check if post is primarily links with minimal text."""
        # Remove URLs and check remaining content
        text_without_links = re.sub(r'http[s]?://\S+', '', text)
        text_without_links = re.sub(r'www\.\S+', '', text_without_links)

        remaining_text = text_without_links.strip()
        return len(remaining_text) < 20

    def _clean_text(self, text: str) -> str:
        """Clean text for classification."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        # Remove very short lines that are just formatting
        lines = text.split('\n')
        meaningful_lines = [line.strip() for line in lines if len(line.strip()) > 3]

        return '\n'.join(meaningful_lines)

    def _classify_with_llm(self, items: List[Dict], taxonomy: List[str], model: str = None) -> List[Dict]:
        """
        Classify posts using LLM.

        Args:
            items: Items to classify
            taxonomy: Post type taxonomy
            model: Model to use (optional, uses self.model if not provided)

        Returns:
            List[Dict]: Classified items
        """
        try:
            # Load environment for LLM access
            load_environment()

            # Get OpenAI configuration
            api_key = get_required_env_var("OPENAI_API_KEY", "OpenAI API key for classification")

            # Initialize OpenAI client
            client = self._initialize_openai_client(api_key)

            # Use provided model or fallback to instance model
            llm_model = model or self.model

            classified_items = []

            # Process in batches
            for i in range(0, len(items), self.batch_size):
                batch = items[i:i + self.batch_size]
                batch_results = self._classify_batch_llm(client, batch, taxonomy, llm_model)
                classified_items.extend(batch_results)

            return classified_items

        except Exception as e:
            # Fallback to heuristic classification
            return self._classify_with_heuristics(items, taxonomy)

    def _initialize_openai_client(self, api_key: str):
        """Initialize OpenAI client."""
        try:
            import openai
            return openai.OpenAI(api_key=api_key)
        except ImportError:
            # Return mock client for testing
            return MockOpenAIClient()

    def _classify_batch_llm(self, client, batch: List[Dict], taxonomy: List[str], model: str = None) -> List[Dict]:
        """
        Classify a batch of posts using LLM.

        Args:
            client: OpenAI client
            batch: Batch of items
            taxonomy: Post taxonomy
            model: Model to use (optional, uses self.model if not provided)

        Returns:
            List[Dict]: Classified batch
        """
        # Prepare batch for classification
        posts_text = []
        for i, item in enumerate(batch):
            text = item["cleaned_text"][:500]  # Limit text length
            posts_text.append(f"Post {i+1}: {text}")

        # Create classification prompt
        prompt = self._create_classification_prompt(posts_text, taxonomy)

        try:
            # Check if client is mock
            if hasattr(client, '_is_mock'):
                return self._mock_llm_classification(batch, taxonomy)

            # Use provided model or fallback to instance model
            llm_model = model or self.model

            # Real LLM classification
            response = client.chat.completions.create(
                model=llm_model,
                messages=[
                    {"role": "system", "content": "You are an expert content strategist specializing in LinkedIn post classification."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=1000
            )

            # Parse LLM response
            classifications = self._parse_llm_response(response.choices[0].message.content, len(batch))

            # Apply classifications to items
            for i, item in enumerate(batch):
                if i < len(classifications):
                    item.update(classifications[i])
                else:
                    # Fallback classification
                    item.update({
                        "post_type": "unknown",
                        "confidence": 0.5,
                        "reasoning": "LLM response parsing failed",
                        "secondary_types": []
                    })

            return batch

        except Exception as e:
            # Fallback to heuristic for this batch
            return self._classify_batch_heuristic(batch, taxonomy)

    def _create_classification_prompt(self, posts_text: List[str], taxonomy: List[str]) -> str:
        """Create classification prompt for LLM."""
        taxonomy_str = ", ".join(taxonomy)
        posts_str = "\n\n".join(posts_text)

        prompt = f"""Classify each LinkedIn post into one of these categories: {taxonomy_str}

For each post, provide:
1. Primary category (must be from the list above)
2. Confidence score (0.0-1.0)
3. Brief reasoning (1-2 sentences)
4. Up to 2 secondary categories if applicable

Posts to classify:
{posts_str}

Respond in JSON format:
[
  {{
    "post_type": "category_name",
    "confidence": 0.85,
    "reasoning": "Brief explanation",
    "secondary_types": ["category1", "category2"]
  }}
]"""
        return prompt

    def _parse_llm_response(self, response_text: str, expected_count: int) -> List[Dict]:
        """Parse LLM classification response."""
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
            if json_match:
                classifications = json.loads(json_match.group(0))

                # Validate and clean classifications
                valid_classifications = []
                for i, classification in enumerate(classifications[:expected_count]):
                    if isinstance(classification, dict):
                        valid_classifications.append({
                            "post_type": classification.get("post_type", "unknown"),
                            "confidence": min(max(classification.get("confidence", 0.5), 0.0), 1.0),
                            "reasoning": classification.get("reasoning", "LLM classification"),
                            "secondary_types": classification.get("secondary_types", [])[:2]
                        })

                return valid_classifications

        except Exception:
            pass

        # Fallback if parsing fails
        return [{"post_type": "unknown", "confidence": 0.5, "reasoning": "Parse error", "secondary_types": []}
                for _ in range(expected_count)]

    def _mock_llm_classification(self, batch: List[Dict], taxonomy: List[str]) -> List[Dict]:
        """Mock LLM classification for testing."""
        for item in batch:
            # Simple heuristic-based mock classification
            text = item["cleaned_text"].lower()

            if any(word in text for word in ["how", "step", "guide", "tutorial"]):
                post_type = "how_to"
                confidence = 0.8
            elif any(word in text for word in ["story", "experience", "journey"]):
                post_type = "personal_story"
                confidence = 0.75
            elif any(word in text for word in ["think", "believe", "opinion"]):
                post_type = "opinion"
                confidence = 0.7
            elif "?" in text:
                post_type = "question"
                confidence = 0.85
            else:
                post_type = "educational"
                confidence = 0.6

            item.update({
                "post_type": post_type,
                "confidence": confidence,
                "reasoning": f"Mock classification based on keywords",
                "secondary_types": []
            })

        return batch

    def _classify_with_heuristics(self, items: List[Dict], taxonomy: List[str]) -> List[Dict]:
        """
        Classify posts using heuristic rules.

        Args:
            items: Items to classify
            taxonomy: Post taxonomy

        Returns:
            List[Dict]: Classified items
        """
        classified_items = []

        for item in items:
            text = item["cleaned_text"].lower()

            # Heuristic classification rules
            classification = self._apply_heuristic_rules(text, taxonomy)

            item.update(classification)
            classified_items.append(item)

        return classified_items

    def _classify_batch_heuristic(self, batch: List[Dict], taxonomy: List[str]) -> List[Dict]:
        """Classify batch using heuristics."""
        return self._classify_with_heuristics(batch, taxonomy)

    def _apply_heuristic_rules(self, text: str, taxonomy: List[str]) -> Dict[str, Any]:
        """
        Apply heuristic rules for classification.

        Args:
            text: Post text (lowercase)
            taxonomy: Available categories

        Returns:
            Dict: Classification result
        """
        # Define keyword patterns for each category
        patterns = {
            "how_to": ["how to", "step by step", "guide", "tutorial", "instructions", "here's how"],
            "personal_story": ["my journey", "my experience", "when i", "story", "learned", "journey"],
            "listicle": ["5 ways", "3 tips", "top 10", "list", "• ", "1.", "2.", "3."],
            "opinion": ["i think", "i believe", "in my opinion", "perspective", "take", "view"],
            "question": ["?", "what do you think", "thoughts?", "agree?", "your opinion"],
            "announcement": ["excited to announce", "launching", "proud to share", "news"],
            "case_study": ["case study", "results", "we helped", "project", "analysis"],
            "motivational": ["inspire", "motivation", "never give up", "believe", "dreams"],
            "promotional": ["check out", "learn more", "sign up", "buy", "offer", "discount"],
            "quote": ['"', '"', "'", "said", "quote"],
            "data_insights": ["%", "data shows", "research", "statistics", "study", "survey"],
            "networking": ["connect", "collaboration", "looking for", "hiring", "opportunity"]
        }

        # Score each category
        scores = {}
        for category, keywords in patterns.items():
            if category in taxonomy:
                score = sum(1 for keyword in keywords if keyword in text)
                if score > 0:
                    scores[category] = score

        # Determine primary classification
        if scores:
            primary_type = max(scores.keys(), key=lambda k: scores[k])
            confidence = min(0.9, 0.5 + (scores[primary_type] * 0.1))

            # Get secondary types
            secondary_types = [cat for cat, score in scores.items()
                             if cat != primary_type and score > 0][:2]
        else:
            primary_type = "educational"  # Default fallback
            confidence = 0.3
            secondary_types = []

        return {
            "post_type": primary_type,
            "confidence": round(confidence, 3),
            "reasoning": f"Heuristic classification based on keyword patterns",
            "secondary_types": secondary_types
        }

    def _calculate_distribution(self, items: List[Dict]) -> Dict[str, int]:
        """Calculate post type distribution."""
        distribution = {}
        for item in items:
            post_type = item.get("post_type", "unknown")
            distribution[post_type] = distribution.get(post_type, 0) + 1
        return distribution

    def _analyze_engagement_by_type(self, items: List[Dict]) -> Dict[str, Dict[str, float]]:
        """Analyze engagement patterns by post type."""
        type_engagement = {}

        for item in items:
            post_type = item.get("post_type", "unknown")
            engagement_score = item.get("engagement_score", 0.0)

            if post_type not in type_engagement:
                type_engagement[post_type] = []
            type_engagement[post_type].append(engagement_score)

        # Calculate statistics
        engagement_stats = {}
        for post_type, scores in type_engagement.items():
            if scores:
                engagement_stats[post_type] = {
                    "avg_engagement": round(sum(scores) / len(scores), 4),
                    "max_engagement": round(max(scores), 4),
                    "min_engagement": round(min(scores), 4),
                    "count": len(scores)
                }

        return engagement_stats

    def _generate_analysis(self, items: List[Dict], distribution: Dict[str, int],
                          engagement_analysis: Dict[str, Dict]) -> Dict[str, Any]:
        """Generate comprehensive analysis."""
        total_classified = len(items)
        high_confidence = sum(1 for item in items if item.get("confidence", 0) >= 0.7)

        # Top performing types by engagement
        if engagement_analysis:
            top_performing = sorted(engagement_analysis.items(),
                                  key=lambda x: x[1]["avg_engagement"], reverse=True)
            top_performing_types = [item[0] for item in top_performing[:5]]

            # Engagement by type summary
            engagement_by_type = {ptype: stats["avg_engagement"]
                                for ptype, stats in engagement_analysis.items()}
        else:
            top_performing_types = []
            engagement_by_type = {}

        # Distribution percentages
        distribution_percentages = {}
        if total_classified > 0:
            for post_type, count in distribution.items():
                distribution_percentages[post_type] = round((count / total_classified) * 100, 1)

        return {
            "total_classified": total_classified,
            "high_confidence": high_confidence,
            "high_confidence_rate": round((high_confidence / max(total_classified, 1)) * 100, 1),
            "engagement_by_type": engagement_by_type,
            "top_performing_types": top_performing_types,
            "distribution_percentages": distribution_percentages,
            "most_common_type": max(distribution.keys(), key=distribution.get) if distribution else None,
            "type_diversity": len(distribution)
        }


class MockOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self):
        self._is_mock = True
        self.chat = self.ChatCompletions()

    class ChatCompletions:
        def create(self, **kwargs):
            # Mock response
            class MockChoice:
                class MockMessage:
                    content = '[{"post_type": "how_to", "confidence": 0.8, "reasoning": "Mock classification", "secondary_types": []}, {"post_type": "opinion", "confidence": 0.7, "reasoning": "Mock classification", "secondary_types": []}]'
                message = MockMessage()

            class MockResponse:
                choices = [MockChoice()]

            return MockResponse()


if __name__ == "__main__":
    # Test the tool
    test_items = [
        {
            "id": "post_1",
            "content": "Here's how to build a successful business in 5 steps: 1. Identify market need 2. Create MVP 3. Test with customers 4. Iterate based on feedback 5. Scale operations",
            "engagement_score": 0.85
        },
        {
            "id": "post_2",
            "content": "My journey from corporate to entrepreneur taught me that taking risks is essential for growth. What's your biggest lesson learned?",
            "engagement_score": 0.72
        },
        {
            "id": "post_3",
            "content": "I believe that remote work is the future of business. Companies that adapt will thrive, while others will struggle to retain talent.",
            "engagement_score": 0.63
        },
        {
            "id": "post_4",
            "content": "Excited to announce the launch of our new product! Check it out at our website and let me know what you think.",
            "engagement_score": 0.45
        }
    ]

    tool = ClassifyPostTypes(
        items=test_items,
        use_llm=False,  # Use heuristics for testing
        min_text_length=10
    )

    print("Testing ClassifyPostTypes tool...")
    result = tool.run()
    print(json.dumps(json.loads(result), indent=2))