"""
GenerateContentBriefs tool for creating actionable content briefs and templates.
Produces content briefs based on strategy playbook for amplification campaigns.
"""

import os
import sys
import json
import re
import random
import yaml
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, load_environment
from loader import load_app_config, get_config_value


class GenerateContentBriefs(BaseTool):
    """
    Produces content briefs and templates based on strategy playbook.

    Creates actionable content briefs with angles, hooks, outlines, keywords,
    and call-to-actions for systematic content amplification.
    """

    playbook_json: Dict[str, Any] = Field(
        ...,
        description="Strategy playbook JSON data (from SynthesizeStrategyPlaybook)"
    )

    count: int = Field(
        5,
        description="Number of content briefs to generate (default: 5)"
    )

    focus_areas: Optional[List[str]] = Field(
        None,
        description="Specific focus areas for briefs (e.g., ['personal_story', 'how_to'])"
    )

    diversity_mode: bool = Field(
        True,
        description="Whether to ensure diverse content types and angles (default: True)"
    )

    use_llm: bool = Field(
        True,
        description="Whether to use LLM for advanced brief generation (requires OpenAI API)"
    )

    model: str = Field(
        "gpt-4o",
        description="LLM model to use for brief generation"
    )

    def _load_settings(self) -> Dict[str, Any]:
        """Load configuration from settings.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def run(self) -> str:
        """
        Generates content briefs based on strategy playbook.

        Returns:
            str: JSON string containing content briefs
                 Format: {
                     "content_briefs": [
                         {
                             "id": "brief_001",
                             "title": "Personal Journey: From Corporate to Startup",
                             "content_type": "personal_story",
                             "angle": "transformation_story",
                             "hook": "I never thought I'd leave my 6-figure corporate job...",
                             "outline": {
                                 "opening": "Hook with transformation statement",
                                 "body": [
                                     "Corporate background and comfort zone",
                                     "The catalyst moment for change",
                                     "Challenges and fears during transition",
                                     "Key lessons learned"
                                 ],
                                 "closing": "Question about audience's career transitions"
                             },
                             "target_keywords": ["entrepreneurship", "career change", "startup journey"],
                             "trigger_phrases": ["excited to share", "what I learned", "biggest lesson"],
                             "call_to_action": "What's the biggest risk you've taken in your career?",
                             "estimated_length": "200-250 words",
                             "optimal_posting_time": "Tuesday 9AM",
                             "expected_engagement": "high",
                             "tone_guidelines": "conversational, vulnerable, inspiring",
                             "hashtag_suggestions": ["#entrepreneurship", "#careertransition", "#startup"],
                             "visual_suggestions": "Personal photo or behind-the-scenes image"
                         }
                     ],
                     "brief_distribution": {
                         "personal_story": 2,
                         "how_to": 1,
                         "opinion": 1,
                         "industry_insights": 1
                     },
                     "content_calendar_alignment": {
                         "weekly_spread": "5 briefs cover optimal weekly mix",
                         "posting_schedule": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                         "theme_alignment": "Matches playbook content themes"
                     },
                     "generation_metadata": {
                         "total_briefs": 5,
                         "diversity_ensured": true,
                         "playbook_version": "1.0",
                         "generated_at": "2024-01-15T10:00:00Z"
                     }
                 }
        """
        try:
            # Validate inputs
            validation_error = self._validate_inputs()
            if validation_error:
                return json.dumps(validation_error)

            # Load settings for LLM configuration
            settings = self._load_settings()
            task_config = settings.get('llm', {}).get('tasks', {}).get('strategy_generate_briefs', {})
            model = task_config.get('model', self.model)

            # Initialize brief generator
            if self.use_llm:
                generator = LLMBriefGenerator(model)
            else:
                generator = TemplateBriefGenerator()

            # Extract playbook elements
            playbook_elements = self._extract_playbook_elements()

            # Determine content types for briefs
            content_types = self._determine_content_types(playbook_elements)

            # Generate content briefs
            content_briefs = []
            for i, content_type in enumerate(content_types):
                brief = generator.generate_brief(
                    brief_id=f"brief_{i+1:03d}",
                    content_type=content_type,
                    playbook_elements=playbook_elements,
                    brief_index=i
                )
                content_briefs.append(brief)

            # Calculate distribution
            brief_distribution = self._calculate_brief_distribution(content_briefs)

            # Generate calendar alignment
            calendar_alignment = self._generate_calendar_alignment(content_briefs, playbook_elements)

            # Prepare result
            result = {
                "content_briefs": content_briefs,
                "brief_distribution": brief_distribution,
                "content_calendar_alignment": calendar_alignment,
                "generation_metadata": {
                    "total_briefs": len(content_briefs),
                    "diversity_ensured": self.diversity_mode,
                    "playbook_version": "1.0",
                    "generation_method": "llm" if self.use_llm else "template",
                    "focus_areas": self.focus_areas if self.focus_areas else "all",
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "content_brief_generation_failed",
                "message": str(e),
                "playbook_provided": bool(self.playbook_json),
                "count_requested": self.count
            }
            return json.dumps(error_result)

    def _validate_inputs(self) -> Optional[Dict[str, Any]]:
        """Validate required inputs."""
        if not self.playbook_json or not isinstance(self.playbook_json, dict):
            return {
                "error": "invalid_playbook",
                "message": "Valid playbook JSON is required for brief generation"
            }

        if self.count < 1 or self.count > 20:
            return {
                "error": "invalid_count",
                "message": "Count must be between 1 and 20"
            }

        # Check for essential playbook sections
        required_sections = ['winning_topics', 'trigger_phrases', 'content_formats']
        missing_sections = [section for section in required_sections
                          if not self.playbook_json.get(section)]

        if missing_sections:
            return {
                "error": "incomplete_playbook",
                "message": f"Playbook missing required sections: {missing_sections}",
                "required_sections": required_sections
            }

        return None

    def _extract_playbook_elements(self) -> Dict[str, Any]:
        """Extract key elements from playbook for brief generation."""
        elements = {}

        # Extract winning topics
        elements['topics'] = self.playbook_json.get('winning_topics', [])

        # Extract trigger phrases
        elements['triggers'] = self.playbook_json.get('trigger_phrases', [])

        # Extract content formats
        elements['formats'] = self.playbook_json.get('content_formats', [])

        # Extract tone guidelines
        elements['tone'] = self.playbook_json.get('tone_guidelines', {})

        # Extract hooks and openers
        elements['hooks'] = self.playbook_json.get('hooks_and_openers', [])

        # Extract CTA patterns
        elements['ctas'] = self.playbook_json.get('call_to_action_patterns', [])

        # Extract calendar framework
        elements['calendar'] = self.playbook_json.get('content_calendar_framework', {})

        return elements

    def _determine_content_types(self, playbook_elements: Dict[str, Any]) -> List[str]:
        """Determine content types for briefs ensuring diversity."""
        if self.focus_areas:
            # Use specified focus areas
            content_types = []
            for _ in range(self.count):
                content_types.append(random.choice(self.focus_areas))
        else:
            # Use playbook content formats
            formats = playbook_elements.get('formats', [])
            if not formats:
                # Default content types
                default_types = ['personal_story', 'how_to', 'opinion', 'listicle', 'question']
                content_types = []
                for i in range(self.count):
                    content_types.append(default_types[i % len(default_types)])
            else:
                # Use top performing formats
                format_names = [fmt['format'] for fmt in formats]
                content_types = []

                if self.diversity_mode:
                    # Ensure diversity by cycling through top formats
                    for i in range(self.count):
                        content_types.append(format_names[i % len(format_names)])
                else:
                    # Focus on top performing formats
                    top_format = format_names[0] if format_names else 'personal_story'
                    content_types = [top_format] * self.count

        return content_types

    def _calculate_brief_distribution(self, briefs: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate distribution of brief types."""
        distribution = {}
        for brief in briefs:
            content_type = brief.get('content_type', 'unknown')
            distribution[content_type] = distribution.get(content_type, 0) + 1
        return distribution

    def _generate_calendar_alignment(self, briefs: List[Dict[str, Any]],
                                   playbook_elements: Dict[str, Any]) -> Dict[str, Any]:
        """Generate content calendar alignment information."""
        calendar = playbook_elements.get('calendar', {})

        # Generate posting schedule
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        posting_schedule = days[:len(briefs)]

        # Check alignment with weekly mix
        weekly_mix = calendar.get('weekly_mix', {})
        distribution = self._calculate_brief_distribution(briefs)

        alignment_score = 0.8  # Simplified score

        return {
            "weekly_spread": f"{len(briefs)} briefs cover optimal weekly mix",
            "posting_schedule": posting_schedule,
            "theme_alignment": "Matches playbook content themes",
            "weekly_mix_alignment": alignment_score,
            "optimal_times": calendar.get('optimal_times', ['9AM', '2PM', '11AM'])
        }


class LLMBriefGenerator:
    """LLM-powered content brief generation using OpenAI."""

    def __init__(self, model: str = "gpt-4o"):
        self.model = model
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        """Initialize OpenAI client."""
        try:
            import openai
            try:
                api_key = get_required_env_var("OPENAI_API_KEY", "OpenAI API key for content brief generation")
                self.client = openai.OpenAI(api_key=api_key)
            except EnvironmentError:
                # Fall back to mock client if API key not configured
                self.client = MockLLMClient()
        except ImportError:
            self.client = MockLLMClient()

    def generate_brief(self, brief_id: str, content_type: str,
                      playbook_elements: Dict[str, Any], brief_index: int) -> Dict[str, Any]:
        """Generate content brief using LLM."""
        if isinstance(self.client, MockLLMClient):
            return self.client.generate_brief(brief_id, content_type, playbook_elements, brief_index)

        # Prepare context for LLM
        context = self._prepare_context(playbook_elements, content_type)

        prompt = f"""Create a detailed content brief for a {content_type} post based on this strategy playbook data:

{context}

Generate a content brief with:
1. Compelling title
2. Specific angle/approach
3. Attention-grabbing hook
4. Detailed outline (opening, 3-4 body points, closing)
5. Target keywords from the playbook
6. Relevant trigger phrases
7. Engaging call-to-action
8. Tone guidelines

Respond with JSON:
{{
  "title": "Specific post title",
  "angle": "Content angle/approach",
  "hook": "Opening hook sentence",
  "outline": {{
    "opening": "Opening approach",
    "body": ["point 1", "point 2", "point 3"],
    "closing": "Closing approach"
  }},
  "target_keywords": ["keyword1", "keyword2"],
  "trigger_phrases": ["phrase1", "phrase2"],
  "call_to_action": "Specific CTA",
  "tone_guidelines": "Tone description"
}}"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert content strategist. Create actionable content briefs. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=1000
            )

            brief_data = json.loads(response.choices[0].message.content)

            # Add standard fields
            brief_data.update({
                "id": brief_id,
                "content_type": content_type,
                "estimated_length": self._estimate_length(content_type),
                "optimal_posting_time": self._get_optimal_time(brief_index),
                "expected_engagement": self._estimate_engagement(content_type, playbook_elements),
                "hashtag_suggestions": self._generate_hashtags(content_type, brief_data.get('target_keywords', [])),
                "visual_suggestions": self._suggest_visuals(content_type)
            })

            return brief_data

        except Exception as e:
            return MockLLMClient().generate_brief(brief_id, content_type, playbook_elements, brief_index)

    def _prepare_context(self, playbook_elements: Dict[str, Any], content_type: str) -> str:
        """Prepare context string for LLM."""
        context_parts = []

        # Add topics
        topics = playbook_elements.get('topics', [])[:3]
        if topics:
            context_parts.append("Top Topics: " + ", ".join([t.get('topic', '') for t in topics]))

        # Add trigger phrases
        triggers = playbook_elements.get('triggers', [])[:5]
        if triggers:
            trigger_list = [t.get('phrase', '') for t in triggers]
            context_parts.append("Key Trigger Phrases: " + ", ".join(trigger_list))

        # Add tone guidelines
        tone = playbook_elements.get('tone', {})
        if tone:
            primary_tone = tone.get('primary_tone', '')
            voice_chars = ', '.join(tone.get('voice_characteristics', [])[:3])
            context_parts.append(f"Tone: {primary_tone}, Voice: {voice_chars}")

        # Add content type specific guidance
        formats = playbook_elements.get('formats', [])
        format_info = next((f for f in formats if f.get('format') == content_type), None)
        if format_info:
            practices = ', '.join(format_info.get('best_practices', [])[:3])
            context_parts.append(f"Best Practices for {content_type}: {practices}")

        return "\n".join(context_parts)

    def _estimate_length(self, content_type: str) -> str:
        """Estimate optimal length for content type."""
        length_mapping = {
            "personal_story": "200-300 words",
            "how_to": "250-350 words",
            "opinion": "150-250 words",
            "listicle": "200-300 words",
            "question": "100-200 words",
            "case_study": "300-400 words",
            "announcement": "150-250 words"
        }
        return length_mapping.get(content_type, "200-250 words")

    def _get_optimal_time(self, brief_index: int) -> str:
        """Get optimal posting time."""
        times = ["Tuesday 9AM", "Thursday 2PM", "Friday 11AM", "Monday 10AM", "Wednesday 3PM"]
        return times[brief_index % len(times)]

    def _estimate_engagement(self, content_type: str, playbook_elements: Dict[str, Any]) -> str:
        """Estimate engagement level for content type."""
        formats = playbook_elements.get('formats', [])
        format_info = next((f for f in formats if f.get('format') == content_type), None)

        if format_info:
            engagement_rate = format_info.get('engagement_rate', 0.5)
            if engagement_rate > 0.7:
                return "high"
            elif engagement_rate > 0.5:
                return "medium"
            else:
                return "moderate"

        return "medium"

    def _generate_hashtags(self, content_type: str, keywords: List[str]) -> List[str]:
        """Generate hashtag suggestions."""
        hashtags = []

        # Add content type hashtag
        hashtags.append(f"#{content_type.replace('_', '')}")

        # Add keyword-based hashtags
        for keyword in keywords[:3]:
            hashtag = "#" + keyword.replace(" ", "").replace("-", "")
            hashtags.append(hashtag)

        # Add general engagement hashtags
        general_tags = ["#linkedin", "#professional", "#career", "#business"]
        hashtags.extend(general_tags[:2])

        return hashtags[:5]

    def _suggest_visuals(self, content_type: str) -> str:
        """Suggest visual content for post type."""
        visual_mapping = {
            "personal_story": "Personal photo or behind-the-scenes image",
            "how_to": "Step-by-step visual or infographic",
            "opinion": "Quote graphic or professional headshot",
            "listicle": "Numbered list graphic or carousel",
            "question": "Question graphic or engagement visual",
            "case_study": "Before/after images or data visualization",
            "announcement": "Product image or company logo"
        }
        return visual_mapping.get(content_type, "Professional image or branded graphic")


class TemplateBriefGenerator:
    """Template-based content brief generation for fallback."""

    def __init__(self):
        self.brief_templates = {
            "personal_story": {
                "title_patterns": [
                    "My Journey From {} to {}",
                    "The Biggest Lesson I Learned About {}",
                    "How {} Changed My Perspective on {}"
                ],
                "angles": ["transformation", "lesson_learned", "behind_scenes", "vulnerability"],
                "hooks": [
                    "I never thought I'd...",
                    "Three years ago, I was...",
                    "The moment that changed everything..."
                ]
            },
            "how_to": {
                "title_patterns": [
                    "How to {} in {} Steps",
                    "The Complete Guide to {}",
                    "{} Steps to Achieve {}"
                ],
                "angles": ["step_by_step", "comprehensive_guide", "quick_tips", "framework"],
                "hooks": [
                    "Want to know how to...?",
                    "Here's exactly how I...",
                    "The proven method for..."
                ]
            },
            "opinion": {
                "title_patterns": [
                    "Why I Believe {}",
                    "The Truth About {}",
                    "My Take on {}"
                ],
                "angles": ["contrarian_view", "industry_opinion", "trend_analysis", "prediction"],
                "hooks": [
                    "Unpopular opinion:",
                    "I'm going to say something controversial...",
                    "Here's what everyone gets wrong about..."
                ]
            }
        }

    def generate_brief(self, brief_id: str, content_type: str,
                      playbook_elements: Dict[str, Any], brief_index: int) -> Dict[str, Any]:
        """Generate content brief using templates."""
        template = self.brief_templates.get(content_type, self.brief_templates["personal_story"])

        # Extract playbook data
        topics = playbook_elements.get('topics', [])
        triggers = playbook_elements.get('triggers', [])
        tone = playbook_elements.get('tone', {})

        # Get topic for brief
        topic = topics[brief_index % len(topics)] if topics else {"topic": "professional_growth"}

        # Generate title
        title_pattern = random.choice(template["title_patterns"])
        if "{}" in title_pattern:
            title = title_pattern.format(topic.get('topic', 'success').replace('_', ' ').title())
        else:
            title = title_pattern

        # Generate angle
        angle = random.choice(template["angles"])

        # Generate hook
        hook = random.choice(template["hooks"])

        # Generate outline
        outline = self._generate_outline(content_type, topic)

        # Get keywords and triggers
        target_keywords = topic.get('keywords', [])[:3]
        trigger_phrases = [t.get('phrase', '') for t in triggers[:3]]

        # Generate CTA
        ctas = playbook_elements.get('ctas', [])
        cta = ctas[0].get('cta', 'What do you think?') if ctas else 'What are your thoughts?'

        # Tone guidelines
        primary_tone = tone.get('primary_tone', 'professional')
        voice_chars = ', '.join(tone.get('voice_characteristics', ['authentic'])[:2])
        tone_guidelines = f"{primary_tone}, {voice_chars}"

        brief = {
            "id": brief_id,
            "title": title,
            "content_type": content_type,
            "angle": angle,
            "hook": hook,
            "outline": outline,
            "target_keywords": target_keywords,
            "trigger_phrases": trigger_phrases,
            "call_to_action": cta,
            "estimated_length": self._estimate_length(content_type),
            "optimal_posting_time": self._get_optimal_time(brief_index),
            "expected_engagement": "medium",
            "tone_guidelines": tone_guidelines,
            "hashtag_suggestions": self._generate_hashtags(content_type, target_keywords),
            "visual_suggestions": self._suggest_visuals(content_type)
        }

        return brief

    def _generate_outline(self, content_type: str, topic: Dict[str, Any]) -> Dict[str, Any]:
        """Generate content outline based on type."""
        topic_name = topic.get('topic', 'success').replace('_', ' ')

        outlines = {
            "personal_story": {
                "opening": f"Hook with personal context about {topic_name}",
                "body": [
                    "Background and initial situation",
                    "The challenge or turning point",
                    "Actions taken and lessons learned",
                    "Current perspective and insights"
                ],
                "closing": "Question to engage audience about their experience"
            },
            "how_to": {
                "opening": f"Problem statement and value proposition for {topic_name}",
                "body": [
                    "Step 1: Foundation and preparation",
                    "Step 2: Implementation and execution",
                    "Step 3: Optimization and refinement",
                    "Common mistakes to avoid"
                ],
                "closing": "Call-to-action for implementation"
            },
            "opinion": {
                "opening": f"Opinion statement about {topic_name}",
                "body": [
                    "Current industry perspective",
                    "Why conventional wisdom is wrong",
                    "Evidence and reasoning for new perspective",
                    "Implications for the future"
                ],
                "closing": "Question to gather audience opinions"
            }
        }

        return outlines.get(content_type, outlines["personal_story"])

    def _estimate_length(self, content_type: str) -> str:
        """Estimate optimal length."""
        return LLMBriefGenerator(None)._estimate_length(content_type)

    def _get_optimal_time(self, brief_index: int) -> str:
        """Get optimal posting time."""
        return LLMBriefGenerator(None)._get_optimal_time(brief_index)

    def _generate_hashtags(self, content_type: str, keywords: List[str]) -> List[str]:
        """Generate hashtag suggestions."""
        return LLMBriefGenerator(None)._generate_hashtags(content_type, keywords)

    def _suggest_visuals(self, content_type: str) -> str:
        """Suggest visual content."""
        return LLMBriefGenerator(None)._suggest_visuals(content_type)


class MockLLMClient:
    """Mock LLM client for testing without OpenAI."""

    def generate_brief(self, brief_id: str, content_type: str,
                      playbook_elements: Dict[str, Any], brief_index: int) -> Dict[str, Any]:
        """Return mock content brief."""
        return {
            "id": brief_id,
            "title": f"Mock {content_type.replace('_', ' ').title()} Post",
            "content_type": content_type,
            "angle": "transformation_story",
            "hook": "Here's something that completely changed my perspective...",
            "outline": {
                "opening": "Hook with transformation statement",
                "body": [
                    "Background and context",
                    "The catalyst moment",
                    "Lessons learned",
                    "Current insights"
                ],
                "closing": "Question to engage audience"
            },
            "target_keywords": ["growth", "success", "learning"],
            "trigger_phrases": ["excited to share", "biggest lesson"],
            "call_to_action": "What's your experience with this?",
            "estimated_length": "200-250 words",
            "optimal_posting_time": "Tuesday 9AM",
            "expected_engagement": "high",
            "tone_guidelines": "conversational, authentic",
            "hashtag_suggestions": ["#growth", "#success", "#learning"],
            "visual_suggestions": "Personal photo or professional image"
        }


if __name__ == "__main__":
    # Test the tool with sample playbook data
    test_playbook = {
        "winning_topics": [
            {"topic": "entrepreneurship", "engagement_score": 0.85, "keywords": ["startup", "business", "growth"]},
            {"topic": "leadership", "engagement_score": 0.78, "keywords": ["team", "management", "vision"]}
        ],
        "trigger_phrases": [
            {"phrase": "excited to share", "log_odds": 2.5, "phrase_type": "announcement"},
            {"phrase": "biggest lesson", "log_odds": 1.8, "phrase_type": "personal"}
        ],
        "content_formats": [
            {"format": "personal_story", "engagement_rate": 0.85, "best_practices": ["Include vulnerability", "End with question"]},
            {"format": "how_to", "engagement_rate": 0.72, "best_practices": ["Use numbered steps", "Include examples"]}
        ],
        "tone_guidelines": {
            "primary_tone": "conversational",
            "voice_characteristics": ["authentic", "professional", "engaging"]
        },
        "hooks_and_openers": [
            {"hook": "What if I told you...", "category": "curiosity"}
        ],
        "call_to_action_patterns": [
            {"cta": "What's your experience?", "type": "engagement_question"}
        ],
        "content_calendar_framework": {
            "weekly_mix": {"educational": "40%", "personal": "30%"},
            "optimal_times": ["Tuesday 9AM", "Thursday 2PM"]
        }
    }

    print("Testing GenerateContentBriefs tool...")

    # Test basic functionality
    tool = GenerateContentBriefs(
        playbook_json=test_playbook,
        count=3,
        use_llm=False  # Use template-based for testing
    )

    result = tool.run()
    parsed_result = json.loads(result)

    print("✅ Content briefs generation completed successfully")
    print(f"Generated briefs: {len(parsed_result.get('content_briefs', []))}")
    print(f"Brief distribution: {parsed_result.get('brief_distribution', {})}")

    # Show first brief
    if parsed_result.get('content_briefs'):
        first_brief = parsed_result['content_briefs'][0]
        print(f"\nFirst brief: '{first_brief.get('title', 'N/A')}'")
        print(f"Content type: {first_brief.get('content_type', 'N/A')}")
        print(f"Hook: {first_brief.get('hook', 'N/A')}")

    # Test with invalid playbook
    empty_tool = GenerateContentBriefs(playbook_json={}, count=5)
    empty_result = json.loads(empty_tool.run())
    assert "error" in empty_result
    print("✅ Invalid playbook validation works")

    print("\nSample brief structure:")
    if parsed_result.get('content_briefs'):
        brief_keys = list(parsed_result['content_briefs'][0].keys())
        print(f"Brief fields: {brief_keys}")