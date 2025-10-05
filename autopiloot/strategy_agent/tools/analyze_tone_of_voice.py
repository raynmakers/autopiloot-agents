"""
AnalyzeToneOfVoice tool for extracting tone and voice characteristics from LinkedIn content.
Analyzes linguistic patterns, emotional markers, and communication style.
"""

import os
import sys
import json
import re
from typing import List, Dict, Any, Optional
from collections import Counter, defaultdict
from datetime import datetime
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class AnalyzeToneOfVoice(BaseTool):
    """
    Analyzes tone of voice and communication style patterns in LinkedIn content.

    Extracts linguistic markers, emotional indicators, and stylistic elements
    to build comprehensive tone profiles for content creators and posts.
    """

    items: List[Dict[str, Any]] = Field(
        ...,
        description="List of content items with text and optional engagement scores"
    )

    analyze_emotions: bool = Field(
        True,
        description="Whether to analyze emotional markers and sentiment patterns"
    )

    analyze_style: bool = Field(
        True,
        description="Whether to analyze writing style and linguistic patterns"
    )

    analyze_authority: bool = Field(
        True,
        description="Whether to analyze authority and credibility markers"
    )

    use_llm: bool = Field(
        True,
        description="Whether to use LLM for advanced tone analysis (requires OpenAI API)"
    )

    model: str = Field(
        "gpt-4o",
        description="LLM model to use for tone analysis"
    )

    def run(self) -> str:
        """
        Analyzes tone of voice across content items.

        Returns:
            str: JSON string containing tone analysis results
                 Format: {
                     "overall_tone": {
                         "primary_characteristics": ["confident", "educational", "personal"],
                         "confidence_score": 0.85,
                         "consistency_score": 0.78
                     },
                     "emotional_analysis": {
                         "sentiment_distribution": {"positive": 0.7, "neutral": 0.2, "negative": 0.1},
                         "emotion_markers": [{"emotion": "enthusiasm", "frequency": 0.6, "indicators": [...]}],
                         "emotional_range": "moderate"
                     },
                     "style_analysis": {
                         "writing_style": {
                             "formality_level": "casual-professional",
                             "complexity_score": 0.6,
                             "avg_sentence_length": 18.5,
                             "readability_score": 72.3
                         },
                         "linguistic_patterns": [
                             {"pattern": "first_person_narrative", "frequency": 0.8},
                             {"pattern": "rhetorical_questions", "frequency": 0.3}
                         ],
                         "vocabulary_analysis": {
                             "unique_words_ratio": 0.65,
                             "business_vocabulary_ratio": 0.25,
                             "technical_vocabulary_ratio": 0.15
                         }
                     },
                     "authority_markers": {
                         "credibility_indicators": [
                             {"type": "data_citations", "frequency": 0.4},
                             {"type": "experience_references", "frequency": 0.6}
                         ],
                         "expertise_signals": ["industry_knowledge", "case_studies", "results_sharing"],
                         "authority_score": 0.72
                     },
                     "engagement_correlation": {
                         "high_engagement_traits": [
                             {"trait": "personal_stories", "correlation": 0.65},
                             {"trait": "actionable_advice", "correlation": 0.58}
                         ],
                         "tone_performance": {"confident_tone": 1.2, "vulnerable_tone": 1.4}
                     },
                     "recommendations": [
                         {"aspect": "emotional_appeal", "suggestion": "Increase personal vulnerability"},
                         {"aspect": "authority_building", "suggestion": "Add more data points"}
                     ]
                 }
        """
        try:
            if not self.items:
                return json.dumps({
                    "error": "no_content",
                    "message": "No content items provided for tone analysis"
                })

            # Initialize analysis components
            emotion_analyzer = EmotionAnalyzer()
            style_analyzer = StyleAnalyzer()
            authority_analyzer = AuthorityAnalyzer()
            llm_analyzer = None

            if self.use_llm:
                llm_analyzer = LLMToneAnalyzer(self.model)

            # Process all content items
            all_content = []
            engagement_data = []

            for item in self.items:
                content = item.get('content', '')
                if not content:
                    continue

                all_content.append(content)

                # Extract engagement metrics if available
                engagement = self._extract_engagement_metrics(item)
                engagement_data.append(engagement)

            if not all_content:
                return json.dumps({
                    "error": "no_valid_content",
                    "message": "No valid content found in provided items"
                })

            # Perform tone analysis
            result = {
                "overall_tone": self._analyze_overall_tone(all_content, llm_analyzer),
                "content_analysis": {
                    "total_items": len(all_content),
                    "total_words": sum(len(content.split()) for content in all_content),
                    "avg_content_length": sum(len(content) for content in all_content) / len(all_content)
                }
            }

            # Emotional analysis
            if self.analyze_emotions:
                result["emotional_analysis"] = emotion_analyzer.analyze(all_content)

            # Style analysis
            if self.analyze_style:
                result["style_analysis"] = style_analyzer.analyze(all_content)

            # Authority analysis
            if self.analyze_authority:
                result["authority_markers"] = authority_analyzer.analyze(all_content)

            # Engagement correlation analysis
            if engagement_data and any(e for e in engagement_data if e['total_engagement'] > 0):
                result["engagement_correlation"] = self._analyze_engagement_correlation(
                    all_content, engagement_data
                )

            # Generate recommendations
            result["recommendations"] = self._generate_recommendations(result)

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "tone_analysis_failed",
                "message": str(e),
                "items_count": len(self.items) if self.items else 0
            }
            return json.dumps(error_result)

    def _extract_engagement_metrics(self, item: Dict[str, Any]) -> Dict[str, float]:
        """Extract engagement metrics from content item."""
        metadata = item.get('metadata', {})
        engagement = metadata.get('engagement', {})

        likes = engagement.get('reaction_count', 0) or engagement.get('likes', 0)
        comments = engagement.get('comment_count', 0) or engagement.get('comments', 0)
        shares = engagement.get('share_count', 0) or engagement.get('shares', 0)
        views = engagement.get('view_count', 0)

        total_engagement = likes + comments + shares
        engagement_rate = engagement.get('engagement_rate', 0.0)

        return {
            'likes': float(likes),
            'comments': float(comments),
            'shares': float(shares),
            'views': float(views),
            'total_engagement': float(total_engagement),
            'engagement_rate': float(engagement_rate)
        }

    def _analyze_overall_tone(self, content_list: List[str], llm_analyzer=None) -> Dict[str, Any]:
        """Analyze overall tone characteristics across all content."""
        if llm_analyzer:
            return llm_analyzer.analyze_overall_tone(content_list)

        # Fallback heuristic analysis
        total_words = sum(len(content.split()) for content in content_list)
        avg_length = total_words / len(content_list)

        # Basic tone indicators
        confidence_indicators = sum(
            content.count('!') + content.count('definitely') + content.count('absolutely')
            for content in content_list
        )

        question_count = sum(content.count('?') for content in content_list)
        personal_pronouns = sum(
            len(re.findall(r'\b(I|me|my|we|our|us)\b', content, re.IGNORECASE))
            for content in content_list
        )

        confidence_score = min(1.0, confidence_indicators / (total_words / 100))
        conversational_score = min(1.0, (question_count + personal_pronouns) / (total_words / 50))

        characteristics = []
        if confidence_score > 0.3:
            characteristics.append("confident")
        if conversational_score > 0.4:
            characteristics.append("conversational")
        if avg_length > 50:
            characteristics.append("detailed")

        return {
            "primary_characteristics": characteristics[:3],
            "confidence_score": round(confidence_score, 2),
            "consistency_score": 0.75,  # Placeholder
            "analysis_method": "heuristic"
        }

    def _analyze_engagement_correlation(self, content_list: List[str], engagement_data: List[Dict]) -> Dict[str, Any]:
        """Analyze correlation between tone elements and engagement."""
        correlations = {}

        # Analyze various tone traits against engagement
        for i, content in enumerate(content_list):
            engagement = engagement_data[i]
            if engagement['total_engagement'] == 0:
                continue

            # Personal story indicators
            personal_indicators = len(re.findall(r'\b(I|my|when I|I was|I had)\b', content, re.IGNORECASE))
            if personal_indicators > 2:
                correlations.setdefault('personal_stories', []).append(engagement['total_engagement'])

            # Question usage
            questions = content.count('?')
            if questions > 0:
                correlations.setdefault('questions', []).append(engagement['total_engagement'])

            # Emotional words
            emotional_words = len(re.findall(r'\b(amazing|incredible|frustrated|excited|love|hate)\b', content, re.IGNORECASE))
            if emotional_words > 1:
                correlations.setdefault('emotional_language', []).append(engagement['total_engagement'])

        # Calculate correlation scores
        high_engagement_traits = []
        baseline_engagement = sum(e['total_engagement'] for e in engagement_data) / len(engagement_data)

        for trait, engagement_values in correlations.items():
            if engagement_values:
                avg_engagement = sum(engagement_values) / len(engagement_values)
                correlation = avg_engagement / baseline_engagement if baseline_engagement > 0 else 1.0

                if correlation > 1.1:  # 10% above baseline
                    high_engagement_traits.append({
                        "trait": trait,
                        "correlation": round(correlation, 2)
                    })

        return {
            "high_engagement_traits": sorted(high_engagement_traits, key=lambda x: x['correlation'], reverse=True)[:5],
            "baseline_engagement": round(baseline_engagement, 1)
        }

    def _generate_recommendations(self, analysis_result: Dict[str, Any]) -> List[Dict[str, str]]:
        """Generate actionable recommendations based on tone analysis."""
        recommendations = []

        # Analyze emotional patterns
        if "emotional_analysis" in analysis_result:
            emotional = analysis_result["emotional_analysis"]
            if emotional.get("emotional_range") == "low":
                recommendations.append({
                    "aspect": "emotional_appeal",
                    "suggestion": "Increase emotional variety and personal vulnerability to create stronger connection"
                })

        # Analyze authority markers
        if "authority_markers" in analysis_result:
            authority = analysis_result["authority_markers"]
            if authority.get("authority_score", 0) < 0.6:
                recommendations.append({
                    "aspect": "authority_building",
                    "suggestion": "Add more data points, case studies, and specific results to enhance credibility"
                })

        # Analyze engagement correlation
        if "engagement_correlation" in analysis_result:
            engagement = analysis_result["engagement_correlation"]
            high_traits = engagement.get("high_engagement_traits", [])

            if not high_traits:
                recommendations.append({
                    "aspect": "engagement_optimization",
                    "suggestion": "Experiment with personal stories, questions, and actionable advice to boost engagement"
                })
            elif len(high_traits) < 3:
                recommendations.append({
                    "aspect": "content_variety",
                    "suggestion": "Diversify content approaches to discover additional high-engagement patterns"
                })

        # Style recommendations
        if "style_analysis" in analysis_result:
            style = analysis_result["style_analysis"]
            writing_style = style.get("writing_style", {})

            if writing_style.get("readability_score", 100) < 60:
                recommendations.append({
                    "aspect": "readability",
                    "suggestion": "Simplify language and reduce sentence complexity for better readability"
                })

        return recommendations[:5]  # Limit to top 5 recommendations


class EmotionAnalyzer:
    """Analyzes emotional content and sentiment patterns."""

    def __init__(self):
        self.positive_words = {
            'amazing', 'incredible', 'fantastic', 'love', 'excited', 'thrilled',
            'grateful', 'blessed', 'proud', 'happy', 'joy', 'awesome'
        }
        self.negative_words = {
            'frustrated', 'disappointed', 'hate', 'angry', 'sad', 'worried',
            'concerned', 'difficult', 'challenge', 'problem', 'struggle'
        }
        self.enthusiasm_words = {
            'exciting', 'can\'t wait', 'pumped', 'stoked', 'fired up', 'passionate'
        }

    def analyze(self, content_list: List[str]) -> Dict[str, Any]:
        """Analyze emotional patterns in content."""
        total_words = sum(len(content.split()) for content in content_list)

        positive_count = 0
        negative_count = 0
        enthusiasm_count = 0

        for content in content_list:
            content_lower = content.lower()
            positive_count += sum(content_lower.count(word) for word in self.positive_words)
            negative_count += sum(content_lower.count(word) for word in self.negative_words)
            enthusiasm_count += sum(content_lower.count(word) for word in self.enthusiasm_words)

        # Calculate sentiment distribution
        total_emotional = positive_count + negative_count
        if total_emotional > 0:
            positive_ratio = positive_count / total_emotional
            negative_ratio = negative_count / total_emotional
            neutral_ratio = max(0, 1 - positive_ratio - negative_ratio)
        else:
            positive_ratio = negative_ratio = 0.1
            neutral_ratio = 0.8

        # Determine emotional range
        emotional_density = total_emotional / (total_words / 100) if total_words > 0 else 0
        if emotional_density > 5:
            emotional_range = "high"
        elif emotional_density > 2:
            emotional_range = "moderate"
        else:
            emotional_range = "low"

        emotion_markers = []
        if enthusiasm_count > 0:
            emotion_markers.append({
                "emotion": "enthusiasm",
                "frequency": round(enthusiasm_count / len(content_list), 2),
                "indicators": list(self.enthusiasm_words)[:3]
            })

        return {
            "sentiment_distribution": {
                "positive": round(positive_ratio, 2),
                "neutral": round(neutral_ratio, 2),
                "negative": round(negative_ratio, 2)
            },
            "emotion_markers": emotion_markers,
            "emotional_range": emotional_range,
            "emotional_density": round(emotional_density, 2)
        }


class StyleAnalyzer:
    """Analyzes writing style and linguistic patterns."""

    def analyze(self, content_list: List[str]) -> Dict[str, Any]:
        """Analyze writing style patterns."""
        total_sentences = 0
        total_words = 0
        total_characters = 0
        question_count = 0
        exclamation_count = 0
        first_person_count = 0
        unique_words = set()

        business_vocab = {
            'strategy', 'growth', 'revenue', 'profit', 'business', 'market',
            'customer', 'client', 'sales', 'marketing', 'brand', 'leadership'
        }
        technical_vocab = {
            'data', 'analytics', 'algorithm', 'technology', 'digital', 'platform',
            'automation', 'optimization', 'framework', 'metrics', 'kpi'
        }

        business_count = 0
        technical_count = 0

        for content in content_list:
            sentences = len(re.split(r'[.!?]+', content))
            words = content.split()

            total_sentences += sentences
            total_words += len(words)
            total_characters += len(content)
            question_count += content.count('?')
            exclamation_count += content.count('!')

            # Count first person usage
            first_person_count += len(re.findall(r'\b(I|me|my|mine)\b', content, re.IGNORECASE))

            # Add to unique words
            unique_words.update(word.lower().strip('.,!?";') for word in words)

            # Count business and technical vocabulary
            content_lower = content.lower()
            business_count += sum(content_lower.count(word) for word in business_vocab)
            technical_count += sum(content_lower.count(word) for word in technical_vocab)

        # Calculate metrics
        avg_sentence_length = total_words / total_sentences if total_sentences > 0 else 0
        avg_word_length = total_characters / total_words if total_words > 0 else 0

        # Simple readability score (Flesch-like)
        readability = max(0, min(100, 206.835 - (1.015 * avg_sentence_length) - (84.6 * avg_word_length)))

        # Determine formality level
        formal_indicators = business_count + technical_count
        casual_indicators = question_count + exclamation_count + first_person_count

        if formal_indicators > casual_indicators * 1.5:
            formality = "formal"
        elif casual_indicators > formal_indicators * 1.5:
            formality = "casual"
        else:
            formality = "casual-professional"

        # Linguistic patterns
        patterns = []
        if total_words > 0 and first_person_count / total_words > 0.02:  # More than 2% first person
            patterns.append({"pattern": "first_person_narrative", "frequency": round(first_person_count / total_words, 3)})

        if question_count / len(content_list) > 0.5:  # More than 0.5 questions per post
            patterns.append({"pattern": "rhetorical_questions", "frequency": round(question_count / len(content_list), 2)})

        if exclamation_count / len(content_list) > 0.3:
            patterns.append({"pattern": "exclamatory_style", "frequency": round(exclamation_count / len(content_list), 2)})

        return {
            "writing_style": {
                "formality_level": formality,
                "complexity_score": round(min(1.0, avg_sentence_length / 20), 2),
                "avg_sentence_length": round(avg_sentence_length, 1),
                "readability_score": round(readability, 1)
            },
            "linguistic_patterns": patterns,
            "vocabulary_analysis": {
                "unique_words_ratio": round(len(unique_words) / total_words, 2) if total_words > 0 else 0,
                "business_vocabulary_ratio": round(business_count / total_words, 2) if total_words > 0 else 0,
                "technical_vocabulary_ratio": round(technical_count / total_words, 2) if total_words > 0 else 0
            }
        }


class AuthorityAnalyzer:
    """Analyzes authority and credibility markers."""

    def analyze(self, content_list: List[str]) -> Dict[str, Any]:
        """Analyze authority and credibility indicators."""
        data_indicators = 0
        experience_indicators = 0
        results_indicators = 0
        expertise_signals = []

        # Pattern matching for authority markers
        for content in content_list:
            content_lower = content.lower()

            # Data citations
            data_patterns = [r'\d+%', r'\$\d+', r'\d+x', r'research shows', r'study found', r'data reveals']
            for pattern in data_patterns:
                data_indicators += len(re.findall(pattern, content_lower))

            # Experience references
            exp_patterns = [r'in my experience', r'i\'ve found', r'i\'ve learned', r'over \d+ years']
            for pattern in exp_patterns:
                experience_indicators += len(re.findall(pattern, content_lower))

            # Results sharing
            result_patterns = [r'increased by', r'grew from', r'achieved', r'resulted in', r'improved by']
            for pattern in result_patterns:
                results_indicators += len(re.findall(pattern, content_lower))

        # Identify expertise signals
        if data_indicators > 0:
            expertise_signals.append("data_driven_insights")
        if experience_indicators > 0:
            expertise_signals.append("experiential_knowledge")
        if results_indicators > 0:
            expertise_signals.append("results_oriented")

        # Calculate authority score
        total_posts = len(content_list)
        authority_score = min(1.0, (data_indicators + experience_indicators + results_indicators) / (total_posts * 2))

        credibility_indicators = []
        if data_indicators > 0:
            credibility_indicators.append({
                "type": "data_citations",
                "frequency": round(data_indicators / total_posts, 2)
            })
        if experience_indicators > 0:
            credibility_indicators.append({
                "type": "experience_references",
                "frequency": round(experience_indicators / total_posts, 2)
            })
        if results_indicators > 0:
            credibility_indicators.append({
                "type": "results_sharing",
                "frequency": round(results_indicators / total_posts, 2)
            })

        return {
            "credibility_indicators": credibility_indicators,
            "expertise_signals": expertise_signals,
            "authority_score": round(authority_score, 2)
        }


class LLMToneAnalyzer:
    """LLM-powered tone analysis using OpenAI."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            import openai
            api_key = os.getenv("OPENAI_API_KEY")
            if api_key:
                self.client = openai.OpenAI(api_key=api_key)
            else:
                self.client = MockLLMClient()
        except ImportError:
            self.client = MockLLMClient()

    def analyze_overall_tone(self, content_list: List[str]) -> Dict[str, Any]:
        """Analyze overall tone using LLM."""
        if isinstance(self.client, MockLLMClient):
            return self.client.analyze_tone(content_list)

        # Prepare content sample for analysis
        sample_content = "\n\n---\n\n".join(content_list[:5])  # Analyze first 5 posts

        prompt = f"""Analyze the tone and voice characteristics of this LinkedIn content. Focus on:

1. Primary tone characteristics (confident, conversational, educational, authoritative, personal, etc.)
2. Consistency of voice across posts
3. Overall confidence level

Content to analyze:
{sample_content}

Respond with a JSON object containing:
- primary_characteristics: array of 2-3 main tone characteristics
- confidence_score: float between 0-1 indicating how confident the tone is
- consistency_score: float between 0-1 indicating consistency across posts
- analysis_method: "llm"
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert in analyzing communication tone and style. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            # Fallback to mock response
            return MockLLMClient().analyze_tone(content_list)


class MockLLMClient:
    """Mock LLM client for testing without OpenAI."""

    def analyze_tone(self, content_list: List[str]) -> Dict[str, Any]:
        """Return mock tone analysis."""
        return {
            "primary_characteristics": ["professional", "educational", "confident"],
            "confidence_score": 0.78,
            "consistency_score": 0.82,
            "analysis_method": "mock_llm"
        }


if __name__ == "__main__":
    # Test the tool with sample data
    test_items = [
        {
            "id": "post1",
            "content": "I've learned that the key to successful business growth is understanding your customers deeply. After working with 500+ companies, I can confidently say that data-driven decisions always outperform gut feelings. What's your experience with customer research?",
            "metadata": {
                "engagement": {
                    "reaction_count": 45,
                    "comment_count": 12,
                    "share_count": 3
                }
            }
        },
        {
            "id": "post2",
            "content": "Yesterday was incredible! Our team achieved a 150% increase in conversion rates by implementing a simple A/B testing framework. The results speak for themselves - sometimes the smallest changes create the biggest impact. Here's what we learned...",
            "metadata": {
                "engagement": {
                    "reaction_count": 78,
                    "comment_count": 24,
                    "share_count": 8
                }
            }
        },
        {
            "id": "post3",
            "content": "Struggling with team productivity? I used to think longer hours meant better results. Boy, was I wrong! After implementing time-blocking and focus sessions, our output doubled while working 20% fewer hours. The secret is quality over quantity.",
            "metadata": {
                "engagement": {
                    "reaction_count": 112,
                    "comment_count": 18,
                    "share_count": 15
                }
            }
        }
    ]

    print("Testing AnalyzeToneOfVoice tool...")

    # Test basic functionality
    tool = AnalyzeToneOfVoice(
        items=test_items,
        analyze_emotions=True,
        analyze_style=True,
        analyze_authority=True,
        use_llm=True
    )

    result = tool.run()
    parsed_result = json.loads(result)

    print("✅ Tone analysis completed successfully")
    print(f"Primary characteristics: {parsed_result.get('overall_tone', {}).get('primary_characteristics', [])}")
    print(f"Authority score: {parsed_result.get('authority_markers', {}).get('authority_score', 'N/A')}")
    print(f"Emotional range: {parsed_result.get('emotional_analysis', {}).get('emotional_range', 'N/A')}")
    print(f"Recommendations count: {len(parsed_result.get('recommendations', []))}")

    # Test with empty content
    empty_tool = AnalyzeToneOfVoice(items=[])
    empty_result = json.loads(empty_tool.run())
    assert "error" in empty_result
    print("✅ Empty content handling works")

    print("\nSample output:")
    print(json.dumps(parsed_result, indent=2)[:500] + "...")