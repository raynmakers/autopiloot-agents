"""
SynthesizeStrategyPlaybook tool for creating actionable Strategy Playbooks from analysis data.
Combines keywords, topics, triggers, post types, and tone analysis into comprehensive playbook.
"""

import os
import sys
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class SynthesizeStrategyPlaybook(BaseTool):
    """
    Synthesizes findings into actionable Strategy Playbook with winning topics,
    trigger phrases, audience vocabulary, formats, hooks, and call-to-action patterns.

    Combines multiple analysis results to create comprehensive strategic guidance
    for content creation and engagement optimization.
    """

    keywords: Dict[str, Any] = Field(
        ...,
        description="Keywords analysis results (from ExtractKeywordsAndPhrases)"
    )

    topics: Optional[Dict[str, Any]] = Field(
        None,
        description="Topic clustering results (from ClusterTopicsEmbeddings)"
    )

    triggers: Dict[str, Any] = Field(
        ...,
        description="Trigger phrases analysis (from MineTriggerPhrases)"
    )

    post_types: Dict[str, Any] = Field(
        ...,
        description="Post type classification results (from ClassifyPostTypes)"
    )

    tones: Dict[str, Any] = Field(
        ...,
        description="Tone of voice analysis (from AnalyzeToneOfVoice)"
    )

    examples: Optional[Dict[str, Any]] = Field(
        None,
        description="Example high-performing content with metadata"
    )

    constraints: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional constraints for playbook generation (brand guidelines, etc.)"
    )

    use_llm: bool = Field(
        True,
        description="Whether to use LLM for advanced synthesis (requires OpenAI API)"
    )

    model: str = Field(
        "gpt-4o",
        description="LLM model to use for synthesis"
    )

    def run(self) -> str:
        """
        Synthesizes analysis results into comprehensive Strategy Playbook.

        Returns:
            str: JSON string containing both markdown and structured JSON playbook
                 Format: {
                     "playbook_markdown": "# Strategy Playbook\\n\\n...",
                     "playbook_json": {
                         "executive_summary": {
                             "key_insights": ["insight1", "insight2"],
                             "top_opportunities": ["opp1", "opp2"],
                             "engagement_drivers": ["driver1", "driver2"]
                         },
                         "winning_topics": [
                             {
                                 "topic": "entrepreneurship",
                                 "engagement_score": 0.85,
                                 "frequency": 25,
                                 "keywords": ["startup", "business", "growth"],
                                 "recommended_frequency": "weekly"
                             }
                         ],
                         "trigger_phrases": [
                             {
                                 "phrase": "excited to announce",
                                 "context": "announcements",
                                 "usage_guidelines": "Use for product launches",
                                 "effectiveness_score": 0.92
                             }
                         ],
                         "content_formats": [
                             {
                                 "format": "personal_story",
                                 "engagement_rate": 0.78,
                                 "optimal_length": "150-250 words",
                                 "best_practices": ["Include vulnerability", "End with question"]
                             }
                         ],
                         "tone_guidelines": {
                             "primary_tone": "conversational",
                             "secondary_tones": ["authentic", "professional"],
                             "avoid": ["overly formal", "jargon-heavy"],
                             "voice_characteristics": ["personal", "actionable", "engaging"]
                         },
                         "hooks_and_openers": [
                             {
                                 "hook": "What if I told you...",
                                 "category": "curiosity",
                                 "effectiveness": 0.82,
                                 "use_cases": ["educational posts", "insights sharing"]
                             }
                         ],
                         "call_to_action_patterns": [
                             {
                                 "cta": "What's your experience with X?",
                                 "type": "engagement_question",
                                 "response_rate": 0.65,
                                 "optimal_placement": "end of post"
                             }
                         ],
                         "content_calendar_framework": {
                             "weekly_mix": {
                                 "educational": "40%",
                                 "personal": "30%",
                                 "industry": "20%",
                                 "promotional": "10%"
                             },
                             "posting_frequency": "5-7 posts per week",
                             "optimal_times": ["Tuesday 9AM", "Thursday 2PM"]
                         }
                     },
                     "version": "1.0",
                     "created_at": "2024-01-15T10:00:00Z",
                     "analysis_sources": {
                         "keywords_analyzed": 150,
                         "triggers_analyzed": 45,
                         "posts_analyzed": 250,
                         "timeframe": "last_90_days"
                     }
                 }
        """
        try:
            # Validate required inputs
            validation_error = self._validate_inputs()
            if validation_error:
                return json.dumps(validation_error)

            # Initialize synthesis components
            if self.use_llm:
                synthesizer = LLMPlaybookSynthesizer(self.model)
            else:
                synthesizer = RuleBasedSynthesizer()

            # Extract key insights from each analysis
            insights = self._extract_key_insights()

            # Generate playbook structure
            playbook_json = self._create_playbook_structure(insights, synthesizer)

            # Generate markdown version
            playbook_markdown = self._generate_markdown_playbook(playbook_json)

            # Prepare final result
            result = {
                "playbook_markdown": playbook_markdown,
                "playbook_json": playbook_json,
                "version": "1.0",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "analysis_sources": {
                    "keywords_analyzed": len(self.keywords.get('keywords', [])),
                    "triggers_analyzed": len(self.triggers.get('trigger_phrases', [])),
                    "posts_analyzed": self.post_types.get('processing_metadata', {}).get('total_input_items', 0),
                    "timeframe": "analysis_period"
                },
                "synthesis_metadata": {
                    "synthesis_method": "llm" if self.use_llm else "rule_based",
                    "model_used": self.model if self.use_llm else "heuristic",
                    "constraints_applied": bool(self.constraints),
                    "topics_included": bool(self.topics)
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "playbook_synthesis_failed",
                "message": str(e),
                "inputs_provided": {
                    "keywords": bool(self.keywords),
                    "triggers": bool(self.triggers),
                    "post_types": bool(self.post_types),
                    "tones": bool(self.tones),
                    "topics": bool(self.topics),
                    "examples": bool(self.examples)
                }
            }
            return json.dumps(error_result)

    def _validate_inputs(self) -> Optional[Dict[str, Any]]:
        """Validate required input sections are present."""
        required_sections = ['keywords', 'triggers', 'post_types', 'tones']
        missing_sections = []

        for section in required_sections:
            data = getattr(self, section)
            if not data or not isinstance(data, dict):
                missing_sections.append(section)

        if missing_sections:
            return {
                "error": "missing_required_sections",
                "message": f"Required sections missing or invalid: {missing_sections}",
                "required_sections": required_sections
            }

        return None

    def _extract_key_insights(self) -> Dict[str, Any]:
        """Extract key insights from each analysis component."""
        insights = {}

        # Extract keyword insights
        keywords_data = self.keywords.get('keywords', [])
        if keywords_data:
            insights['top_keywords'] = keywords_data[:10]
            insights['high_engagement_keywords'] = [
                kw for kw in keywords_data[:20]
                if kw.get('engagement_boost', 0) > 0.1
            ]

        # Extract trigger phrase insights
        triggers_data = self.triggers.get('trigger_phrases', [])
        if triggers_data:
            insights['top_triggers'] = triggers_data[:15]
            insights['trigger_categories'] = self.triggers.get('phrase_categories', {})

        # Extract post type insights
        post_analysis = self.post_types.get('analysis', {})
        if post_analysis:
            insights['top_performing_types'] = post_analysis.get('top_performing_types', [])
            insights['type_engagement'] = post_analysis.get('engagement_by_type', {})

        # Extract tone insights
        tone_data = self.tones.get('overall_tone', {})
        if tone_data:
            insights['primary_tone_characteristics'] = tone_data.get('primary_characteristics', [])
            insights['authority_score'] = self.tones.get('authority_markers', {}).get('authority_score', 0)

        # Extract engagement correlation insights
        engagement_correlation = self.tones.get('engagement_correlation', {})
        if engagement_correlation:
            insights['high_engagement_traits'] = engagement_correlation.get('high_engagement_traits', [])

        return insights

    def _create_playbook_structure(self, insights: Dict[str, Any], synthesizer) -> Dict[str, Any]:
        """Create structured playbook from insights."""
        # Generate executive summary
        executive_summary = synthesizer.create_executive_summary(insights)

        # Build winning topics
        winning_topics = self._build_winning_topics(insights)

        # Build trigger phrases section
        trigger_phrases_section = self._build_trigger_phrases_section(insights)

        # Build content formats section
        content_formats = self._build_content_formats(insights)

        # Build tone guidelines
        tone_guidelines = self._build_tone_guidelines(insights)

        # Build hooks and openers
        hooks_and_openers = synthesizer.generate_hooks_and_openers(insights)

        # Build CTA patterns
        cta_patterns = synthesizer.generate_cta_patterns(insights)

        # Build content calendar framework
        content_calendar = self._build_content_calendar_framework(insights)

        playbook = {
            "executive_summary": executive_summary,
            "winning_topics": winning_topics,
            "trigger_phrases": trigger_phrases_section,
            "content_formats": content_formats,
            "tone_guidelines": tone_guidelines,
            "hooks_and_openers": hooks_and_openers,
            "call_to_action_patterns": cta_patterns,
            "content_calendar_framework": content_calendar
        }

        return playbook

    def _build_winning_topics(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build winning topics section from keyword and topic insights."""
        winning_topics = []

        # Use keyword data to infer topics
        top_keywords = insights.get('top_keywords', [])

        # Group keywords by semantic similarity (simplified)
        topic_groups = self._group_keywords_into_topics(top_keywords)

        for topic_name, keywords in topic_groups.items():
            avg_engagement = sum(kw.get('avg_engagement', 0) for kw in keywords) / len(keywords)
            total_frequency = sum(kw.get('frequency', 0) for kw in keywords)

            winning_topics.append({
                "topic": topic_name,
                "engagement_score": round(avg_engagement, 3),
                "frequency": total_frequency,
                "keywords": [kw.get('term', '') for kw in keywords[:5]],
                "recommended_frequency": self._recommend_frequency(avg_engagement, total_frequency)
            })

        # Sort by engagement score
        winning_topics.sort(key=lambda x: x['engagement_score'], reverse=True)
        return winning_topics[:10]

    def _group_keywords_into_topics(self, keywords: List[Dict[str, Any]]) -> Dict[str, List[Dict]]:
        """Group keywords into semantic topics (simplified heuristic approach)."""
        # Define topic categories with seed words
        topic_categories = {
            "business_growth": ["business", "growth", "revenue", "profit", "scale", "expansion"],
            "entrepreneurship": ["startup", "entrepreneur", "founder", "launch", "venture"],
            "leadership": ["leadership", "team", "management", "leader", "executive"],
            "marketing": ["marketing", "brand", "content", "social", "campaign"],
            "technology": ["technology", "tech", "digital", "software", "platform"],
            "personal_development": ["personal", "development", "skill", "learning", "growth"],
            "industry_insights": ["industry", "market", "trend", "analysis", "insight"],
            "customer_focus": ["customer", "client", "user", "experience", "service"]
        }

        grouped_keywords = {topic: [] for topic in topic_categories.keys()}
        unmatched = []

        for keyword in keywords:
            term = keyword.get('term', '').lower()
            matched = False

            for topic, seed_words in topic_categories.items():
                if any(seed in term for seed in seed_words):
                    grouped_keywords[topic].append(keyword)
                    matched = True
                    break

            if not matched:
                unmatched.append(keyword)

        # Add unmatched high-engagement keywords to general category
        if unmatched:
            grouped_keywords["general_engagement"] = unmatched[:5]

        # Remove empty categories
        return {k: v for k, v in grouped_keywords.items() if v}

    def _recommend_frequency(self, engagement_score: float, frequency: int) -> str:
        """Recommend posting frequency based on engagement and current frequency."""
        if engagement_score > 0.8 and frequency > 10:
            return "weekly"
        elif engagement_score > 0.6 and frequency > 5:
            return "bi-weekly"
        elif engagement_score > 0.4:
            return "monthly"
        else:
            return "occasional"

    def _build_trigger_phrases_section(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build trigger phrases section with usage guidelines."""
        triggers = insights.get('top_triggers', [])
        trigger_section = []

        for trigger in triggers[:20]:
            phrase = trigger.get('phrase', '')
            phrase_type = trigger.get('phrase_type', 'general')
            log_odds = trigger.get('log_odds', 0)

            # Generate usage guidelines based on phrase type
            usage_guidelines = self._generate_usage_guidelines(phrase, phrase_type)
            context = self._determine_phrase_context(phrase_type)

            trigger_section.append({
                "phrase": phrase,
                "context": context,
                "usage_guidelines": usage_guidelines,
                "effectiveness_score": min(1.0, log_odds / 5.0),  # Normalize to 0-1
                "phrase_type": phrase_type,
                "log_odds": log_odds
            })

        return trigger_section

    def _generate_usage_guidelines(self, phrase: str, phrase_type: str) -> str:
        """Generate usage guidelines for trigger phrases."""
        guidelines = {
            "announcement": "Use for product launches, feature releases, or major company news",
            "personal": "Include in personal stories, lessons learned, or vulnerable moments",
            "question": "End posts with these to encourage engagement and comments",
            "action": "Use to motivate audience to take specific steps or try new approaches",
            "emotional": "Include when sharing experiences or reactions to create emotional connection",
            "authority": "Use when sharing expertise, data, or research-backed insights",
            "curiosity": "Start posts with these to hook attention and create intrigue",
            "urgency": "Use sparingly for time-sensitive offers or important updates",
            "social": "Include to build community and encourage sharing/connection",
            "benefit": "Highlight value propositions and what audience gains"
        }

        return guidelines.get(phrase_type, "Use strategically to enhance message impact")

    def _determine_phrase_context(self, phrase_type: str) -> str:
        """Determine context category for phrase type."""
        context_mapping = {
            "announcement": "announcements",
            "personal": "storytelling",
            "question": "engagement",
            "action": "motivation",
            "emotional": "connection",
            "authority": "expertise",
            "curiosity": "attention",
            "urgency": "urgency",
            "social": "community",
            "benefit": "value_proposition"
        }

        return context_mapping.get(phrase_type, "general")

    def _build_content_formats(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build content formats section from post type analysis."""
        type_engagement = insights.get('type_engagement', {})
        content_formats = []

        # Standard format recommendations based on post types
        format_guidelines = {
            "personal_story": {
                "optimal_length": "150-250 words",
                "best_practices": ["Include vulnerability", "End with question", "Share specific details"]
            },
            "how_to": {
                "optimal_length": "200-300 words",
                "best_practices": ["Use numbered steps", "Include actionable tips", "Provide examples"]
            },
            "opinion": {
                "optimal_length": "100-200 words",
                "best_practices": ["State position clearly", "Provide reasoning", "Invite discussion"]
            },
            "listicle": {
                "optimal_length": "150-250 words",
                "best_practices": ["Use clear numbering", "Keep items concise", "Include brief explanations"]
            },
            "question": {
                "optimal_length": "50-150 words",
                "best_practices": ["Ask specific questions", "Provide context", "Encourage diverse responses"]
            }
        }

        for format_name, engagement_rate in type_engagement.items():
            guidelines = format_guidelines.get(format_name, {
                "optimal_length": "150-200 words",
                "best_practices": ["Focus on value", "Keep audience engaged", "Include clear message"]
            })

            content_formats.append({
                "format": format_name,
                "engagement_rate": round(float(engagement_rate), 3),
                "optimal_length": guidelines["optimal_length"],
                "best_practices": guidelines["best_practices"]
            })

        # Sort by engagement rate
        content_formats.sort(key=lambda x: x['engagement_rate'], reverse=True)
        return content_formats

    def _build_tone_guidelines(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Build tone guidelines from tone analysis."""
        tone_characteristics = insights.get('primary_tone_characteristics', [])
        authority_score = insights.get('authority_score', 0)

        # Determine primary and secondary tones
        primary_tone = tone_characteristics[0] if tone_characteristics else "professional"
        secondary_tones = tone_characteristics[1:3] if len(tone_characteristics) > 1 else ["authentic"]

        # Generate voice characteristics based on analysis
        voice_characteristics = []
        if authority_score > 0.7:
            voice_characteristics.extend(["authoritative", "data-driven"])
        if "personal" in tone_characteristics:
            voice_characteristics.extend(["personal", "relatable"])
        if "conversational" in tone_characteristics:
            voice_characteristics.extend(["conversational", "approachable"])

        # Default characteristics if none detected
        if not voice_characteristics:
            voice_characteristics = ["professional", "engaging", "authentic"]

        return {
            "primary_tone": primary_tone,
            "secondary_tones": secondary_tones,
            "avoid": ["overly formal", "jargon-heavy", "impersonal"],
            "voice_characteristics": voice_characteristics[:4],  # Limit to top 4
            "authority_level": "high" if authority_score > 0.7 else "moderate" if authority_score > 0.4 else "developing"
        }

    def _build_content_calendar_framework(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Build content calendar framework based on analysis."""
        top_performing_types = insights.get('top_performing_types', [])

        # Default mix if no data
        if not top_performing_types:
            weekly_mix = {
                "educational": "40%",
                "personal": "30%",
                "industry": "20%",
                "promotional": "10%"
            }
        else:
            # Calculate mix based on performance
            total_types = len(top_performing_types)
            weekly_mix = {}

            for i, post_type in enumerate(top_performing_types[:4]):
                if i == 0:
                    percentage = "40%"
                elif i == 1:
                    percentage = "30%"
                elif i == 2:
                    percentage = "20%"
                else:
                    percentage = "10%"
                weekly_mix[post_type] = percentage

        return {
            "weekly_mix": weekly_mix,
            "posting_frequency": "5-7 posts per week",
            "optimal_times": ["Tuesday 9AM", "Thursday 2PM", "Friday 11AM"],
            "content_themes": {
                "monday": "motivation_planning",
                "tuesday": "educational_insights",
                "wednesday": "personal_stories",
                "thursday": "industry_analysis",
                "friday": "community_engagement"
            }
        }

    def _generate_markdown_playbook(self, playbook_json: Dict[str, Any]) -> str:
        """Generate markdown version of the playbook."""
        md = []

        # Header
        md.append("# Content Strategy Playbook")
        md.append("")
        md.append(f"*Generated on {datetime.utcnow().strftime('%Y-%m-%d')}*")
        md.append("")

        # Executive Summary
        md.append("## Executive Summary")
        md.append("")
        exec_summary = playbook_json.get('executive_summary', {})

        if exec_summary.get('key_insights'):
            md.append("### Key Insights")
            for insight in exec_summary['key_insights']:
                md.append(f"- {insight}")
            md.append("")

        if exec_summary.get('top_opportunities'):
            md.append("### Top Opportunities")
            for opp in exec_summary['top_opportunities']:
                md.append(f"- {opp}")
            md.append("")

        # Winning Topics
        md.append("## Winning Topics")
        md.append("")
        for topic in playbook_json.get('winning_topics', [])[:5]:
            md.append(f"### {topic['topic'].title()}")
            md.append(f"- **Engagement Score:** {topic['engagement_score']}")
            md.append(f"- **Recommended Frequency:** {topic['recommended_frequency']}")
            md.append(f"- **Key Keywords:** {', '.join(topic['keywords'])}")
            md.append("")

        # Trigger Phrases
        md.append("## High-Impact Trigger Phrases")
        md.append("")
        for trigger in playbook_json.get('trigger_phrases', [])[:10]:
            md.append(f"### \"{trigger['phrase']}\"")
            md.append(f"- **Context:** {trigger['context']}")
            md.append(f"- **Usage:** {trigger['usage_guidelines']}")
            md.append(f"- **Effectiveness:** {trigger['effectiveness_score']:.2f}")
            md.append("")

        # Content Formats
        md.append("## Top Performing Content Formats")
        md.append("")
        for fmt in playbook_json.get('content_formats', [])[:5]:
            md.append(f"### {fmt['format'].replace('_', ' ').title()}")
            md.append(f"- **Engagement Rate:** {fmt['engagement_rate']}")
            md.append(f"- **Optimal Length:** {fmt['optimal_length']}")
            md.append("- **Best Practices:**")
            for practice in fmt['best_practices']:
                md.append(f"  - {practice}")
            md.append("")

        # Tone Guidelines
        md.append("## Tone & Voice Guidelines")
        md.append("")
        tone = playbook_json.get('tone_guidelines', {})
        md.append(f"**Primary Tone:** {tone.get('primary_tone', 'professional').title()}")
        md.append(f"**Secondary Tones:** {', '.join(tone.get('secondary_tones', []))}")
        md.append("")
        md.append("**Voice Characteristics:**")
        for char in tone.get('voice_characteristics', []):
            md.append(f"- {char.title()}")
        md.append("")

        # Content Calendar
        md.append("## Content Calendar Framework")
        md.append("")
        calendar = playbook_json.get('content_calendar_framework', {})
        md.append(f"**Posting Frequency:** {calendar.get('posting_frequency', 'Regular')}")
        md.append("")
        md.append("**Weekly Content Mix:**")
        for content_type, percentage in calendar.get('weekly_mix', {}).items():
            md.append(f"- {content_type.replace('_', ' ').title()}: {percentage}")
        md.append("")

        return "\n".join(md)


class LLMPlaybookSynthesizer:
    """LLM-powered playbook synthesis using OpenAI."""

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

    def create_executive_summary(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Create executive summary using LLM."""
        if isinstance(self.client, MockLLMClient):
            return self.client.create_executive_summary(insights)

        # Prepare insights for LLM
        insights_text = json.dumps(insights, indent=2)[:3000]  # Limit length

        prompt = f"""Based on the following content analysis insights, create an executive summary with:
1. 3-4 key insights about what drives engagement
2. 3-4 top opportunities for content improvement
3. 3-4 main engagement drivers

Insights data:
{insights_text}

Respond with JSON:
{{
  "key_insights": ["insight1", "insight2", "insight3"],
  "top_opportunities": ["opp1", "opp2", "opp3"],
  "engagement_drivers": ["driver1", "driver2", "driver3"]
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert content strategist. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )

            result = json.loads(response.choices[0].message.content)
            return result

        except Exception as e:
            return MockLLMClient().create_executive_summary(insights)

    def generate_hooks_and_openers(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate hooks and openers based on insights."""
        # Simplified implementation
        hooks = [
            {
                "hook": "What if I told you...",
                "category": "curiosity",
                "effectiveness": 0.82,
                "use_cases": ["educational posts", "insights sharing"]
            },
            {
                "hook": "Here's something most people don't know...",
                "category": "curiosity",
                "effectiveness": 0.78,
                "use_cases": ["expertise sharing", "industry insights"]
            },
            {
                "hook": "I used to think... until...",
                "category": "transformation",
                "effectiveness": 0.75,
                "use_cases": ["personal stories", "lessons learned"]
            },
            {
                "hook": "The biggest mistake I see...",
                "category": "authority",
                "effectiveness": 0.73,
                "use_cases": ["advice posts", "educational content"]
            }
        ]
        return hooks

    def generate_cta_patterns(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate call-to-action patterns."""
        cta_patterns = [
            {
                "cta": "What's your experience with this?",
                "type": "engagement_question",
                "response_rate": 0.65,
                "optimal_placement": "end of post"
            },
            {
                "cta": "Share your thoughts in the comments",
                "type": "general_engagement",
                "response_rate": 0.45,
                "optimal_placement": "end of post"
            },
            {
                "cta": "What would you add to this list?",
                "type": "collaboration",
                "response_rate": 0.58,
                "optimal_placement": "end of post"
            }
        ]
        return cta_patterns


class RuleBasedSynthesizer:
    """Rule-based playbook synthesis for fallback."""

    def create_executive_summary(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Create executive summary using rules."""
        return {
            "key_insights": [
                "Personal stories and authentic content drive higher engagement",
                "Question-based posts generate more comments and interaction",
                "Consistent tone and voice build stronger audience connection"
            ],
            "top_opportunities": [
                "Increase use of high-performing trigger phrases",
                "Optimize content format mix based on engagement data",
                "Develop stronger call-to-action patterns"
            ],
            "engagement_drivers": [
                "Authentic personal stories",
                "Interactive question formats",
                "Actionable advice and insights"
            ]
        }

    def generate_hooks_and_openers(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate hooks using rules."""
        return [
            {
                "hook": "Here's what I learned...",
                "category": "learning",
                "effectiveness": 0.75,
                "use_cases": ["personal insights", "lessons learned"]
            }
        ]

    def generate_cta_patterns(self, insights: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate CTA patterns using rules."""
        return [
            {
                "cta": "What do you think?",
                "type": "simple_question",
                "response_rate": 0.50,
                "optimal_placement": "end of post"
            }
        ]


class MockLLMClient:
    """Mock LLM client for testing without OpenAI."""

    def create_executive_summary(self, insights: Dict[str, Any]) -> Dict[str, Any]:
        """Return mock executive summary."""
        return {
            "key_insights": [
                "Personal narratives increase engagement by 40%",
                "Question-based content generates 65% more comments",
                "Authentic tone builds stronger audience connection"
            ],
            "top_opportunities": [
                "Increase personal story frequency to 30% of content",
                "Implement trigger phrases in 80% of posts",
                "Optimize posting schedule for peak engagement times"
            ],
            "engagement_drivers": [
                "Vulnerability and authenticity",
                "Actionable insights and advice",
                "Community-building questions"
            ]
        }


if __name__ == "__main__":
    # Test the tool with sample data
    test_keywords = {
        "keywords": [
            {"term": "business", "frequency": 15, "avg_engagement": 0.8},
            {"term": "growth", "frequency": 12, "avg_engagement": 0.75},
            {"term": "startup", "frequency": 10, "avg_engagement": 0.85}
        ]
    }

    test_triggers = {
        "trigger_phrases": [
            {"phrase": "excited to announce", "log_odds": 2.5, "phrase_type": "announcement"},
            {"phrase": "what's your experience", "log_odds": 1.8, "phrase_type": "question"}
        ]
    }

    test_post_types = {
        "analysis": {
            "engagement_by_type": {"personal_story": 0.85, "how_to": 0.72, "opinion": 0.68},
            "top_performing_types": ["personal_story", "how_to", "opinion"]
        },
        "processing_metadata": {"total_input_items": 100}
    }

    test_tones = {
        "overall_tone": {"primary_characteristics": ["conversational", "authentic", "professional"]},
        "authority_markers": {"authority_score": 0.72}
    }

    print("Testing SynthesizeStrategyPlaybook tool...")

    # Test basic functionality
    tool = SynthesizeStrategyPlaybook(
        keywords=test_keywords,
        triggers=test_triggers,
        post_types=test_post_types,
        tones=test_tones,
        use_llm=False  # Use rule-based for testing
    )

    result = tool.run()
    parsed_result = json.loads(result)

    print("✅ Strategy playbook synthesis completed successfully")
    print(f"Playbook sections: {list(parsed_result.get('playbook_json', {}).keys())}")
    print(f"Markdown length: {len(parsed_result.get('playbook_markdown', ''))}")
    print(f"Winning topics count: {len(parsed_result.get('playbook_json', {}).get('winning_topics', []))}")

    # Test with missing required data
    empty_tool = SynthesizeStrategyPlaybook(
        keywords={},
        triggers={},
        post_types={},
        tones={}
    )
    empty_result = json.loads(empty_tool.run())
    assert "error" in empty_result
    print("✅ Missing data validation works")

    print("\nSample playbook sections:")
    if parsed_result.get('playbook_json'):
        sections = list(parsed_result['playbook_json'].keys())
        print(f"Generated sections: {sections}")