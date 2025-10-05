"""
Comprehensive test suite for GenerateContentBriefs - targeting 100% coverage.
Single consolidated file replacing all fragmented test files.
"""

import sys
import os
import json
import unittest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

# Mock external dependencies before imports
mock_modules = {
    'agency_swarm': MagicMock(),
    'agency_swarm.tools': MagicMock(),
    'pydantic': MagicMock(),
    'openai': MagicMock(),
}

# Apply mocks
with patch.dict('sys.modules', mock_modules):
    # Mock BaseTool and Field
    class MockBaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    def mock_field(*args, **kwargs):
        return kwargs.get('default', None)

    sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool
    sys.modules['pydantic'].Field = mock_field

    # Mock env_loader and loader modules
    mock_env_loader = MagicMock()
    mock_loader = MagicMock()
    sys.modules['env_loader'] = mock_env_loader
    sys.modules['loader'] = mock_loader

    # Import using direct file import
    import importlib.util
    tool_path = os.path.join(os.path.dirname(__file__), '..', '..', 'strategy_agent', 'tools', 'generate_content_briefs.py')
    spec = importlib.util.spec_from_file_location("generate_content_briefs", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    GenerateContentBriefs = module.GenerateContentBriefs
    LLMBriefGenerator = module.LLMBriefGenerator
    TemplateBriefGenerator = module.TemplateBriefGenerator
    MockLLMClient = module.MockLLMClient


class TestGenerateContentBriefs100Coverage(unittest.TestCase):
    """Comprehensive test suite achieving 100% coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.valid_playbook = {
            "winning_topics": [
                {"topic": "entrepreneurship", "engagement_score": 0.85, "keywords": ["startup", "business"]},
                {"topic": "leadership", "engagement_score": 0.78, "keywords": ["team", "management"]}
            ],
            "trigger_phrases": [
                {"phrase": "excited to share", "log_odds": 2.5, "phrase_type": "announcement"},
                {"phrase": "biggest lesson", "log_odds": 1.8, "phrase_type": "personal"}
            ],
            "content_formats": [
                {"format": "personal_story", "engagement_rate": 0.85, "best_practices": ["vulnerability", "question"]},
                {"format": "how_to", "engagement_rate": 0.72, "best_practices": ["numbered steps"]}
            ],
            "tone_guidelines": {
                "primary_tone": "conversational",
                "voice_characteristics": ["authentic", "professional"]
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

    def test_successful_brief_generation_template_mode(self):
        """Test successful brief generation with template generator (lines 116-166)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=3,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # Verify structure
        self.assertIn('content_briefs', data)
        self.assertIn('brief_distribution', data)
        self.assertIn('content_calendar_alignment', data)
        self.assertIn('generation_metadata', data)

        # Verify briefs generated
        self.assertEqual(len(data['content_briefs']), 3)
        self.assertEqual(data['generation_metadata']['total_briefs'], 3)
        self.assertEqual(data['generation_metadata']['generation_method'], 'template')

    def test_successful_brief_generation_llm_mode(self):
        """Test successful brief generation with LLM mode (line 124)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=2,
            use_llm=True
        )

        result = tool.run()
        data = json.loads(result)

        # Should use MockLLMClient since OpenAI not available
        self.assertIn('content_briefs', data)
        self.assertEqual(len(data['content_briefs']), 2)
        self.assertEqual(data['generation_metadata']['generation_method'], 'llm')

    def test_invalid_playbook_validation(self):
        """Test validation with invalid playbook (lines 177-183)."""
        tool = GenerateContentBriefs(
            playbook_json=None,
            count=5
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid_playbook')

    def test_invalid_count_validation(self):
        """Test validation with invalid count (lines 185-189)."""
        # Count too low
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=0
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid_count')

        # Count too high
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=25
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'invalid_count')

    def test_missing_required_sections(self):
        """Test validation with incomplete playbook (lines 191-201)."""
        incomplete_playbook = {
            "winning_topics": [],
            # Missing: trigger_phrases, content_formats
        }

        tool = GenerateContentBriefs(
            playbook_json=incomplete_playbook,
            count=3
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'incomplete_playbook')
        self.assertIn('required_sections', data)

    def test_extract_playbook_elements(self):
        """Test playbook element extraction (lines 205-230)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=2,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # Verify briefs use playbook elements
        brief = data['content_briefs'][0]
        self.assertIn('target_keywords', brief)
        self.assertIn('trigger_phrases', brief)
        self.assertIn('tone_guidelines', brief)

    def test_determine_content_types_with_focus_areas(self):
        """Test content type determination with focus areas (lines 232-238)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=5,
            focus_areas=['personal_story', 'how_to'],
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # All briefs should use focus areas
        for brief in data['content_briefs']:
            self.assertIn(brief['content_type'], ['personal_story', 'how_to'])

    def test_determine_content_types_from_formats(self):
        """Test content type determination from playbook formats (lines 240-256)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=4,
            diversity_mode=True,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # Should cycle through available formats
        self.assertEqual(len(data['content_briefs']), 4)

    def test_diversity_mode_disabled(self):
        """Test diversity mode disabled uses top format (lines 257-260)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=3,
            diversity_mode=False,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # All briefs should use same top format
        content_types = [brief['content_type'] for brief in data['content_briefs']]
        self.assertEqual(len(set(content_types)), 1)  # Only one unique type

    def test_calculate_brief_distribution(self):
        """Test brief distribution calculation (lines 264-270)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=5,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # Verify distribution matches generated briefs
        distribution = data['brief_distribution']
        total_in_distribution = sum(distribution.values())
        self.assertEqual(total_in_distribution, 5)

    def test_generate_calendar_alignment(self):
        """Test calendar alignment generation (lines 272-293)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=3,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        alignment = data['content_calendar_alignment']
        self.assertIn('weekly_spread', alignment)
        self.assertIn('posting_schedule', alignment)
        self.assertIn('theme_alignment', alignment)
        self.assertEqual(len(alignment['posting_schedule']), 3)

    def test_exception_handling(self):
        """Test exception handling returns error (lines 168-175)."""
        # Create playbook that will cause error during processing
        bad_playbook = {
            "winning_topics": "not_a_list",  # Wrong type
            "trigger_phrases": [],
            "content_formats": []
        }

        tool = GenerateContentBriefs(
            playbook_json=bad_playbook,
            count=2,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        self.assertIn('error', data)
        self.assertEqual(data['error'], 'content_brief_generation_failed')

    def test_template_brief_generator_initialization(self):
        """Test TemplateBriefGenerator initialization (lines 481-525)."""
        generator = TemplateBriefGenerator()

        # Verify templates exist
        self.assertIn('personal_story', generator.brief_templates)
        self.assertIn('how_to', generator.brief_templates)
        self.assertIn('opinion', generator.brief_templates)

        # Verify template structure
        template = generator.brief_templates['personal_story']
        self.assertIn('title_patterns', template)
        self.assertIn('angles', template)
        self.assertIn('hooks', template)

    def test_template_brief_generation(self):
        """Test template brief generation (lines 527-587)."""
        generator = TemplateBriefGenerator()
        playbook_elements = {
            'topics': [{'topic': 'entrepreneurship', 'keywords': ['startup', 'growth']}],
            'triggers': [{'phrase': 'excited to share'}],
            'tone': {'primary_tone': 'conversational', 'voice_characteristics': ['authentic']},
            'ctas': [{'cta': 'What do you think?'}]
        }

        brief = generator.generate_brief(
            brief_id='test_001',
            content_type='personal_story',
            playbook_elements=playbook_elements,
            brief_index=0
        )

        # Verify brief structure
        self.assertEqual(brief['id'], 'test_001')
        self.assertEqual(brief['content_type'], 'personal_story')
        self.assertIn('title', brief)
        self.assertIn('angle', brief)
        self.assertIn('hook', brief)
        self.assertIn('outline', brief)
        self.assertIn('target_keywords', brief)

    def test_template_outline_generation(self):
        """Test template outline generation (lines 589-626)."""
        generator = TemplateBriefGenerator()

        topic = {'topic': 'leadership', 'keywords': ['team', 'vision']}

        outline = generator._generate_outline('how_to', topic)

        # Verify outline structure
        self.assertIn('opening', outline)
        self.assertIn('body', outline)
        self.assertIn('closing', outline)
        self.assertIsInstance(outline['body'], list)
        self.assertGreater(len(outline['body']), 0)

    def test_template_utility_methods(self):
        """Test template generator utility methods (lines 628-642)."""
        generator = TemplateBriefGenerator()

        # Test _estimate_length
        length = generator._estimate_length('personal_story')
        self.assertIsInstance(length, str)
        self.assertIn('words', length)

        # Test _get_optimal_time
        time = generator._get_optimal_time(0)
        self.assertIsInstance(time, str)

        # Test _generate_hashtags
        hashtags = generator._generate_hashtags('personal_story', ['growth', 'success'])
        self.assertIsInstance(hashtags, list)
        self.assertGreater(len(hashtags), 0)

        # Test _suggest_visuals
        visual = generator._suggest_visuals('personal_story')
        self.assertIsInstance(visual, str)

    def test_llm_brief_generator_with_mock_client(self):
        """Test LLM brief generator falls back to mock (lines 296-314)."""
        generator = LLMBriefGenerator(model='gpt-4o')

        # Should use MockLLMClient
        self.assertIsInstance(generator.client, MockLLMClient)

    def test_mock_llm_client_generation(self):
        """Test MockLLMClient brief generation (lines 645-676)."""
        mock_client = MockLLMClient()
        playbook_elements = {'topics': [], 'triggers': [], 'tone': {}}

        brief = mock_client.generate_brief(
            brief_id='mock_001',
            content_type='how_to',
            playbook_elements=playbook_elements,
            brief_index=0
        )

        # Verify mock brief structure
        self.assertEqual(brief['id'], 'mock_001')
        self.assertEqual(brief['content_type'], 'how_to')
        self.assertIn('title', brief)
        self.assertIn('outline', brief)
        self.assertIn('target_keywords', brief)

    def test_llm_estimate_length(self):
        """Test LLM generator estimate length (lines 415-426)."""
        generator = LLMBriefGenerator()

        length = generator._estimate_length('case_study')
        self.assertEqual(length, '300-400 words')

        length = generator._estimate_length('unknown_type')
        self.assertEqual(length, '200-250 words')

    def test_llm_get_optimal_time(self):
        """Test LLM generator optimal time (lines 428-431)."""
        generator = LLMBriefGenerator()

        time1 = generator._get_optimal_time(0)
        time2 = generator._get_optimal_time(5)

        self.assertIsInstance(time1, str)
        self.assertIsInstance(time2, str)
        # Should cycle through times
        self.assertEqual(time1, time2)

    def test_llm_estimate_engagement(self):
        """Test LLM generator engagement estimation (lines 433-447)."""
        generator = LLMBriefGenerator()

        playbook_elements = {
            'formats': [
                {'format': 'personal_story', 'engagement_rate': 0.85},
                {'format': 'how_to', 'engagement_rate': 0.55},
                {'format': 'opinion', 'engagement_rate': 0.45}
            ]
        }

        # High engagement
        engagement = generator._estimate_engagement('personal_story', playbook_elements)
        self.assertEqual(engagement, 'high')

        # Medium engagement
        engagement = generator._estimate_engagement('how_to', playbook_elements)
        self.assertEqual(engagement, 'medium')

        # Moderate engagement
        engagement = generator._estimate_engagement('opinion', playbook_elements)
        self.assertEqual(engagement, 'moderate')

        # Unknown type
        engagement = generator._estimate_engagement('unknown', playbook_elements)
        self.assertEqual(engagement, 'medium')

    def test_llm_generate_hashtags(self):
        """Test LLM generator hashtag generation (lines 449-465)."""
        generator = LLMBriefGenerator()

        hashtags = generator._generate_hashtags('personal_story', ['growth', 'success', 'mindset'])

        self.assertIsInstance(hashtags, list)
        self.assertLessEqual(len(hashtags), 5)
        # Should include content type hashtag
        self.assertIn('#personalstory', hashtags)

    def test_llm_suggest_visuals(self):
        """Test LLM generator visual suggestions (lines 467-478)."""
        generator = LLMBriefGenerator()

        visual = generator._suggest_visuals('listicle')
        self.assertIn('carousel', visual.lower())

        visual = generator._suggest_visuals('unknown_type')
        self.assertEqual(visual, 'Professional image or branded graphic')

    def test_empty_playbook_formats_uses_defaults(self):
        """Test empty formats uses default content types (lines 242-247)."""
        playbook_no_formats = {
            "winning_topics": [{"topic": "test", "keywords": []}],
            "trigger_phrases": [],
            "content_formats": []  # Empty
        }

        tool = GenerateContentBriefs(
            playbook_json=playbook_no_formats,
            count=3,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        # Should use default types
        self.assertEqual(len(data['content_briefs']), 3)

    def test_metadata_generation(self):
        """Test generation metadata is complete (lines 156-163)."""
        tool = GenerateContentBriefs(
            playbook_json=self.valid_playbook,
            count=2,
            focus_areas=['how_to'],
            diversity_mode=True,
            use_llm=False
        )

        result = tool.run()
        data = json.loads(result)

        metadata = data['generation_metadata']
        self.assertEqual(metadata['total_briefs'], 2)
        self.assertEqual(metadata['diversity_ensured'], True)
        self.assertEqual(metadata['playbook_version'], '1.0')
        self.assertEqual(metadata['generation_method'], 'template')
        self.assertEqual(metadata['focus_areas'], ['how_to'])
        self.assertIn('generated_at', metadata)


if __name__ == '__main__':
    unittest.main()
