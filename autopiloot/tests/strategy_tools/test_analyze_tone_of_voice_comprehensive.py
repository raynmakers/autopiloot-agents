#!/usr/bin/env python3
"""
Comprehensive test suite for analyze_tone_of_voice.py - targeting 100% coverage

This test suite covers all functionality of the AnalyzeToneOfVoice tool including:
- Content tone analysis with multiple analyzers
- EmotionAnalyzer for sentiment and emotional patterns
- StyleAnalyzer for writing style and linguistic patterns
- AuthorityAnalyzer for credibility markers
- LLMToneAnalyzer with OpenAI integration and mock fallback
- Engagement correlation analysis
- Recommendation generation
- Main block execution

Target: 100% line coverage through comprehensive mocking and scenario testing
"""

import unittest
from unittest.mock import patch, MagicMock, Mock, call
import sys
import json
import os
import re
from io import StringIO


class TestAnalyzeToneOfVoiceComprehensive(unittest.TestCase):
    """Comprehensive test suite targeting 100% coverage of analyze_tone_of_voice.py"""

    def setUp(self):
        """Set up comprehensive mocks for all external dependencies."""
        # Mock ALL external dependencies before any imports
        self.mock_modules = {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock(),
            'openai': MagicMock(),
            'config': MagicMock(),
            'config.env_loader': MagicMock(),
            'config.loader': MagicMock(),
            'core': MagicMock(),
            'env_loader': MagicMock(),
            'loader': MagicMock()
        }

        # Mock pydantic Field properly
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        self.mock_modules['pydantic'].Field = mock_field

        # Mock BaseTool with Agency Swarm v1.0.0 pattern
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        self.mock_modules['agency_swarm.tools'].BaseTool = MockBaseTool

        # Mock environment and config functions
        self.mock_modules['env_loader'].get_required_env_var = MagicMock(return_value='test-api-key')
        self.mock_modules['env_loader'].load_environment = MagicMock()
        self.mock_modules['loader'].load_app_config = MagicMock(return_value={'test': 'config'})
        self.mock_modules['loader'].get_config_value = MagicMock(return_value='test-config-value')

        # Mock OpenAI client
        self.mock_openai_client = MagicMock()
        self.mock_modules['openai'].OpenAI.return_value = self.mock_openai_client

        # Apply all patches
        self.patchers = []
        for module_name, mock_module in self.mock_modules.items():
            patcher = patch.dict('sys.modules', {module_name: mock_module})
            patcher.start()
            self.patchers.append(patcher)

    def tearDown(self):
        """Clean up patches after each test."""
        for patcher in self.patchers:
            patcher.stop()

        # Remove the imported module if it exists
        if 'strategy_agent.tools.analyze_tone_of_voice' in sys.modules:
            del sys.modules['strategy_agent.tools.analyze_tone_of_voice']

    def _create_sample_content_items(self):
        """Create sample content items for testing."""
        return [
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
                "content": "Yesterday was incredible! Our team achieved a 150% increase in conversion rates by implementing a simple A/B testing framework. The results speak for themselves - sometimes the smallest changes create the biggest impact.",
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
                "content": "Struggling with team productivity? I used to think longer hours meant better results. Boy, was I wrong! After implementing time-blocking and focus sessions, our output doubled while working 20% fewer hours.",
                "metadata": {
                    "engagement": {
                        "reaction_count": 112,
                        "comment_count": 18,
                        "share_count": 15
                    }
                }
            }
        ]

    def test_successful_tone_analysis_all_features_enabled(self):
        """Test successful tone analysis with all features enabled."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Set up OpenAI environment
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "primary_characteristics": ["confident", "educational", "personal"],
                "confidence_score": 0.85,
                "consistency_score": 0.78,
                "analysis_method": "llm"
            })
            self.mock_openai_client.chat.completions.create.return_value = mock_response

            # Create and run tool
            tool = AnalyzeToneOfVoice(
                items=self._create_sample_content_items(),
                analyze_emotions=True,
                analyze_style=True,
                analyze_authority=True,
                use_llm=True
            )

            result = tool.run()

            # Verify result
            parsed_result = json.loads(result)
            self.assertIsInstance(parsed_result, dict)
            self.assertIn('overall_tone', parsed_result)
            self.assertIn('content_analysis', parsed_result)
            self.assertIn('emotional_analysis', parsed_result)
            self.assertIn('style_analysis', parsed_result)
            self.assertIn('authority_markers', parsed_result)
            self.assertIn('engagement_correlation', parsed_result)
            self.assertIn('recommendations', parsed_result)

    def test_tone_analysis_without_llm(self):
        """Test tone analysis using heuristic fallback without LLM."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create tool without LLM
        tool = AnalyzeToneOfVoice(
            items=self._create_sample_content_items(),
            analyze_emotions=True,
            analyze_style=True,
            analyze_authority=True,
            use_llm=False
        )

        result = tool.run()

        # Verify heuristic analysis
        parsed_result = json.loads(result)
        self.assertIsInstance(parsed_result, dict)
        self.assertIn('overall_tone', parsed_result)
        overall_tone = parsed_result['overall_tone']
        self.assertEqual(overall_tone.get('analysis_method'), 'heuristic')
        self.assertIn('primary_characteristics', overall_tone)
        self.assertIn('confidence_score', overall_tone)

    def test_empty_items_error_handling(self):
        """Test error handling when no items are provided."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create tool with empty items
        tool = AnalyzeToneOfVoice(items=[])

        result = tool.run()

        # Verify error response
        parsed_result = json.loads(result)
        self.assertIsInstance(parsed_result, dict)
        self.assertIn('error', parsed_result)
        self.assertEqual(parsed_result['error'], 'no_content')
        self.assertIn('message', parsed_result)

    def test_items_without_content_error_handling(self):
        """Test error handling when items have no valid content."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create items without content
        invalid_items = [
            {"id": "post1"},  # No content
            {"id": "post2", "content": ""},  # Empty content
            {"id": "post3", "metadata": {"test": "data"}}  # No content
        ]

        tool = AnalyzeToneOfVoice(items=invalid_items)

        result = tool.run()

        # Verify error response
        parsed_result = json.loads(result)
        self.assertIsInstance(parsed_result, dict)
        self.assertIn('error', parsed_result)
        self.assertEqual(parsed_result['error'], 'no_valid_content')

    def test_selective_analysis_flags(self):
        """Test selective enabling/disabling of analysis components."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Test with only emotion analysis enabled
        tool = AnalyzeToneOfVoice(
            items=self._create_sample_content_items(),
            analyze_emotions=True,
            analyze_style=False,
            analyze_authority=False,
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)

        # Should have emotion analysis but not style or authority
        self.assertIn('emotional_analysis', parsed_result)
        self.assertNotIn('style_analysis', parsed_result)
        self.assertNotIn('authority_markers', parsed_result)

    def test_engagement_metrics_extraction(self):
        """Test engagement metrics extraction from various formats."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create items with different engagement formats
        items_with_various_engagements = [
            {
                "content": "Test content 1",
                "metadata": {
                    "engagement": {
                        "reaction_count": 50,
                        "comment_count": 10,
                        "share_count": 5,
                        "view_count": 1000,
                        "engagement_rate": 0.065
                    }
                }
            },
            {
                "content": "Test content 2",
                "metadata": {
                    "engagement": {
                        "likes": 30,  # Alternative naming
                        "comments": 8,
                        "shares": 2
                    }
                }
            },
            {
                "content": "Test content 3",
                # No engagement data
            }
        ]

        tool = AnalyzeToneOfVoice(items=items_with_various_engagements, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        self.assertIsInstance(parsed_result, dict)
        # Should still have engagement correlation even with mixed data
        self.assertIn('engagement_correlation', parsed_result)

    def test_emotion_analyzer_functionality(self):
        """Test EmotionAnalyzer class functionality."""
        from strategy_agent.tools.analyze_tone_of_voice import EmotionAnalyzer

        analyzer = EmotionAnalyzer()

        # Test with content containing various emotions
        content_list = [
            "I'm so excited and thrilled about this amazing opportunity! It's going to be fantastic.",
            "I'm frustrated with the challenges we're facing. This is really difficult and disappointing.",
            "This is a neutral business update about our quarterly results and market position."
        ]

        result = analyzer.analyze(content_list)

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn('sentiment_distribution', result)
        self.assertIn('emotion_markers', result)
        self.assertIn('emotional_range', result)
        self.assertIn('emotional_density', result)

        # Verify sentiment distribution
        sentiment = result['sentiment_distribution']
        self.assertIn('positive', sentiment)
        self.assertIn('negative', sentiment)
        self.assertIn('neutral', sentiment)
        self.assertEqual(round(sentiment['positive'] + sentiment['negative'] + sentiment['neutral'], 1), 1.0)

    def test_emotion_analyzer_with_no_emotional_content(self):
        """Test EmotionAnalyzer with neutral content."""
        from strategy_agent.tools.analyze_tone_of_voice import EmotionAnalyzer

        analyzer = EmotionAnalyzer()

        # Test with neutral content
        neutral_content = [
            "The quarterly report shows steady progress in market penetration.",
            "Our team completed the project deliverables on schedule."
        ]

        result = analyzer.analyze(neutral_content)

        # Should handle neutral content gracefully
        self.assertIsInstance(result, dict)
        self.assertEqual(result['emotional_range'], 'low')
        self.assertTrue(result['sentiment_distribution']['neutral'] > 0.5)

    def test_style_analyzer_functionality(self):
        """Test StyleAnalyzer class functionality."""
        from strategy_agent.tools.analyze_tone_of_voice import StyleAnalyzer

        analyzer = StyleAnalyzer()

        # Test with content having different styles
        content_list = [
            "I believe that strategic business optimization requires comprehensive data analytics and market research methodologies! What do you think?",
            "Hey everyone! I just wanted to share my personal experience with team leadership. It's been incredible!",
            "Our analysis indicates significant growth potential in the technology sector through automation frameworks."
        ]

        result = analyzer.analyze(content_list)

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn('writing_style', result)
        self.assertIn('linguistic_patterns', result)
        self.assertIn('vocabulary_analysis', result)

        # Verify writing style metrics
        writing_style = result['writing_style']
        self.assertIn('formality_level', writing_style)
        self.assertIn('complexity_score', writing_style)
        self.assertIn('avg_sentence_length', writing_style)
        self.assertIn('readability_score', writing_style)

        # Verify vocabulary analysis
        vocab = result['vocabulary_analysis']
        self.assertIn('unique_words_ratio', vocab)
        self.assertIn('business_vocabulary_ratio', vocab)
        self.assertIn('technical_vocabulary_ratio', vocab)

    def test_style_analyzer_linguistic_patterns(self):
        """Test StyleAnalyzer linguistic pattern detection."""
        from strategy_agent.tools.analyze_tone_of_voice import StyleAnalyzer

        analyzer = StyleAnalyzer()

        # Test content with specific patterns
        pattern_content = [
            "I really think that my experience shows this approach works. I've seen it myself many times.",  # High first person
            "Are you ready to transform your business? Do you want better results? Can you imagine the possibilities?",  # High questions
            "This is absolutely amazing! The results are incredible! I can't believe how fantastic this is!"  # High exclamations
        ]

        result = analyzer.analyze(pattern_content)

        # Verify patterns are detected
        patterns = result['linguistic_patterns']
        self.assertIsInstance(patterns, list)

        # Should detect first person narrative, rhetorical questions, and exclamatory style
        pattern_types = [p['pattern'] for p in patterns]
        self.assertTrue(any('first_person' in pattern for pattern in pattern_types))

    def test_authority_analyzer_functionality(self):
        """Test AuthorityAnalyzer class functionality."""
        from strategy_agent.tools.analyze_tone_of_voice import AuthorityAnalyzer

        analyzer = AuthorityAnalyzer()

        # Test with content containing authority markers
        authority_content = [
            "Research shows that 85% of companies achieve better results with this approach. In my 15+ years of experience, I've found this to be consistently true.",
            "Our data reveals a $2.5M increase in revenue after implementation. The study found significant improvements across all metrics.",
            "Over 10 years, I've learned that results-oriented strategies increased performance by 40%. Our team achieved remarkable growth from these insights."
        ]

        result = analyzer.analyze(authority_content)

        # Verify result structure
        self.assertIsInstance(result, dict)
        self.assertIn('credibility_indicators', result)
        self.assertIn('expertise_signals', result)
        self.assertIn('authority_score', result)

        # Verify authority markers are detected
        credibility = result['credibility_indicators']
        self.assertIsInstance(credibility, list)
        self.assertTrue(any(indicator['type'] == 'data_citations' for indicator in credibility))
        self.assertTrue(any(indicator['type'] == 'experience_references' for indicator in credibility))

        expertise = result['expertise_signals']
        self.assertIsInstance(expertise, list)
        self.assertTrue(len(expertise) > 0)

    def test_authority_analyzer_with_low_authority_content(self):
        """Test AuthorityAnalyzer with content lacking authority markers."""
        from strategy_agent.tools.analyze_tone_of_voice import AuthorityAnalyzer

        analyzer = AuthorityAnalyzer()

        # Test with low authority content
        low_authority_content = [
            "I think this might work for some people. Maybe you could try it.",
            "This is just my opinion, but it seems like it could be helpful."
        ]

        result = analyzer.analyze(low_authority_content)

        # Should handle low authority content
        self.assertIsInstance(result, dict)
        self.assertTrue(result['authority_score'] < 0.3)
        self.assertEqual(len(result['credibility_indicators']), 0)

    def test_llm_tone_analyzer_with_openai(self):
        """Test LLMToneAnalyzer with OpenAI integration."""
        from strategy_agent.tools.analyze_tone_of_voice import LLMToneAnalyzer

        # Mock OpenAI response
        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            mock_response = MagicMock()
            mock_response.choices[0].message.content = json.dumps({
                "primary_characteristics": ["confident", "educational"],
                "confidence_score": 0.85,
                "consistency_score": 0.78,
                "analysis_method": "llm"
            })
            self.mock_openai_client.chat.completions.create.return_value = mock_response

            analyzer = LLMToneAnalyzer("gpt-4o")
            content_list = ["Test content for LLM analysis"]

            result = analyzer.analyze_overall_tone(content_list)

            # Verify LLM analysis result
            self.assertIsInstance(result, dict)
            self.assertEqual(result['analysis_method'], 'llm')
            self.assertIn('primary_characteristics', result)
            self.assertIn('confidence_score', result)

            # Verify OpenAI was called
            self.mock_openai_client.chat.completions.create.assert_called_once()

    def test_llm_tone_analyzer_without_openai_key(self):
        """Test LLMToneAnalyzer fallback when no OpenAI key is available."""
        from strategy_agent.tools.analyze_tone_of_voice import LLMToneAnalyzer

        # Test without OpenAI key
        with patch.dict('os.environ', {}, clear=True):
            analyzer = LLMToneAnalyzer("gpt-4o")
            content_list = ["Test content for mock analysis"]

            result = analyzer.analyze_overall_tone(content_list)

            # Should fall back to mock client
            self.assertIsInstance(result, dict)
            self.assertEqual(result['analysis_method'], 'mock_llm')

    def test_llm_tone_analyzer_openai_error_handling(self):
        """Test LLMToneAnalyzer error handling when OpenAI fails."""
        from strategy_agent.tools.analyze_tone_of_voice import LLMToneAnalyzer

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            # Mock OpenAI to raise exception
            self.mock_openai_client.chat.completions.create.side_effect = Exception("API Error")

            analyzer = LLMToneAnalyzer("gpt-4o")
            content_list = ["Test content"]

            result = analyzer.analyze_overall_tone(content_list)

            # Should fall back to mock response
            self.assertIsInstance(result, dict)
            self.assertEqual(result['analysis_method'], 'mock_llm')

    def test_llm_tone_analyzer_invalid_json_response(self):
        """Test LLMToneAnalyzer handling invalid JSON from OpenAI."""
        from strategy_agent.tools.analyze_tone_of_voice import LLMToneAnalyzer

        with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
            # Mock OpenAI to return invalid JSON
            mock_response = MagicMock()
            mock_response.choices[0].message.content = "Invalid JSON response"
            self.mock_openai_client.chat.completions.create.return_value = mock_response

            analyzer = LLMToneAnalyzer("gpt-4o")
            content_list = ["Test content"]

            result = analyzer.analyze_overall_tone(content_list)

            # Should fall back to mock response
            self.assertIsInstance(result, dict)
            self.assertEqual(result['analysis_method'], 'mock_llm')

    def test_mock_llm_client_functionality(self):
        """Test MockLLMClient functionality."""
        from strategy_agent.tools.analyze_tone_of_voice import MockLLMClient

        mock_client = MockLLMClient()
        content_list = ["Test content"]

        result = mock_client.analyze_tone(content_list)

        # Verify mock response structure
        self.assertIsInstance(result, dict)
        self.assertEqual(result['analysis_method'], 'mock_llm')
        self.assertIn('primary_characteristics', result)
        self.assertIn('confidence_score', result)
        self.assertIn('consistency_score', result)

    def test_engagement_correlation_analysis(self):
        """Test engagement correlation analysis functionality."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create content with specific patterns and varying engagement
        items_with_patterns = [
            {
                "content": "I love sharing my personal experience when I was starting my business. It was amazing!",
                "metadata": {"engagement": {"reaction_count": 100, "comment_count": 20, "share_count": 10}}
            },
            {
                "content": "Are you ready to transform your business? Do you want better results?",
                "metadata": {"engagement": {"reaction_count": 80, "comment_count": 15, "share_count": 5}}
            },
            {
                "content": "I'm so excited about these incredible results! This is absolutely amazing!",
                "metadata": {"engagement": {"reaction_count": 120, "comment_count": 25, "share_count": 15}}
            },
            {
                "content": "Standard business content without emotional markers or personal elements.",
                "metadata": {"engagement": {"reaction_count": 30, "comment_count": 3, "share_count": 1}}
            }
        ]

        tool = AnalyzeToneOfVoice(items=items_with_patterns, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        self.assertIn('engagement_correlation', parsed_result)

        correlation = parsed_result['engagement_correlation']
        self.assertIn('high_engagement_traits', correlation)
        self.assertIn('baseline_engagement', correlation)

        # Should identify patterns that correlate with higher engagement
        high_traits = correlation['high_engagement_traits']
        self.assertIsInstance(high_traits, list)

    def test_engagement_correlation_with_zero_engagement(self):
        """Test engagement correlation when all content has zero engagement."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create content with zero engagement
        zero_engagement_items = [
            {
                "content": "Test content with personal story when I was young",
                "metadata": {"engagement": {"reaction_count": 0, "comment_count": 0, "share_count": 0}}
            },
            {
                "content": "Another test with questions?",
                "metadata": {"engagement": {"reaction_count": 0, "comment_count": 0, "share_count": 0}}
            }
        ]

        tool = AnalyzeToneOfVoice(items=zero_engagement_items, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        # Should not include engagement correlation when no engagement data
        self.assertNotIn('engagement_correlation', parsed_result)

    def test_recommendation_generation(self):
        """Test recommendation generation based on analysis results."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create content that should trigger specific recommendations
        low_authority_items = [
            {
                "content": "I think this might work. Maybe you could try it sometime if you want.",
                "metadata": {"engagement": {"reaction_count": 5, "comment_count": 1, "share_count": 0}}
            }
        ]

        tool = AnalyzeToneOfVoice(
            items=low_authority_items,
            analyze_emotions=True,
            analyze_style=True,
            analyze_authority=True,
            use_llm=False
        )

        result = tool.run()
        parsed_result = json.loads(result)

        # Should generate recommendations
        self.assertIn('recommendations', parsed_result)
        recommendations = parsed_result['recommendations']
        self.assertIsInstance(recommendations, list)
        self.assertTrue(len(recommendations) <= 5)  # Limited to 5

        # Should include authority building recommendation
        authority_rec = any(rec['aspect'] == 'authority_building' for rec in recommendations)
        engagement_rec = any(rec['aspect'] == 'engagement_optimization' for rec in recommendations)
        self.assertTrue(authority_rec or engagement_rec)

    def test_exception_handling_in_run_method(self):
        """Test exception handling in the main run method."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create tool and mock analyzer to raise exception
        tool = AnalyzeToneOfVoice(items=self._create_sample_content_items())

        # Mock EmotionAnalyzer to raise exception
        with patch('strategy_agent.tools.analyze_tone_of_voice.EmotionAnalyzer') as mock_emotion:
            mock_emotion.return_value.analyze.side_effect = Exception("Analyzer error")

            result = tool.run()

            # Should handle exception gracefully
            parsed_result = json.loads(result)
            self.assertIn('error', parsed_result)
            self.assertEqual(parsed_result['error'], 'tone_analysis_failed')
            self.assertIn('message', parsed_result)
            self.assertIn('items_count', parsed_result)

    def test_heuristic_tone_analysis_edge_cases(self):
        """Test heuristic tone analysis with edge cases."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Test with very short content
        short_content_items = [
            {"content": "Yes!"},
            {"content": "No."},
            {"content": "Maybe?"}
        ]

        tool = AnalyzeToneOfVoice(items=short_content_items, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        self.assertIn('overall_tone', parsed_result)

        # Test with very long content
        long_content_items = [
            {
                "content": " ".join(["This is a very long sentence with many words."] * 20)
            }
        ]

        tool = AnalyzeToneOfVoice(items=long_content_items, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        overall_tone = parsed_result['overall_tone']
        self.assertIn('detailed', overall_tone.get('primary_characteristics', []))

    def test_style_analyzer_edge_cases(self):
        """Test StyleAnalyzer with edge cases."""
        from strategy_agent.tools.analyze_tone_of_voice import StyleAnalyzer

        analyzer = StyleAnalyzer()

        # Test with empty content
        empty_result = analyzer.analyze([""])
        self.assertIsInstance(empty_result, dict)

        # Test with content without sentences
        no_sentences_result = analyzer.analyze(["word word word"])
        self.assertIsInstance(no_sentences_result, dict)

        # Test with only punctuation
        punctuation_result = analyzer.analyze(["!!! ??? ..."])
        self.assertIsInstance(punctuation_result, dict)

    def test_content_analysis_metrics(self):
        """Test content analysis metrics calculation."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        items = self._create_sample_content_items()
        tool = AnalyzeToneOfVoice(items=items, use_llm=False)
        result = tool.run()

        parsed_result = json.loads(result)
        content_analysis = parsed_result['content_analysis']

        self.assertIn('total_items', content_analysis)
        self.assertIn('total_words', content_analysis)
        self.assertIn('avg_content_length', content_analysis)

        self.assertEqual(content_analysis['total_items'], 3)
        self.assertTrue(content_analysis['total_words'] > 0)
        self.assertTrue(content_analysis['avg_content_length'] > 0)

    def test_main_block_execution(self):
        """Test main block execution for coverage."""
        with patch('builtins.print') as mock_print:
            # Mock successful execution environment
            with patch.dict('os.environ', {'OPENAI_API_KEY': 'test-key'}):
                # Mock OpenAI response
                mock_response = MagicMock()
                mock_response.choices[0].message.content = json.dumps({
                    "primary_characteristics": ["confident", "educational"],
                    "confidence_score": 0.85,
                    "consistency_score": 0.78,
                    "analysis_method": "llm"
                })
                self.mock_openai_client.chat.completions.create.return_value = mock_response

                # Import module to trigger main block
                import strategy_agent.tools.analyze_tone_of_voice

                # Verify main block executed (print was called)
                self.assertTrue(mock_print.called)

    def test_openai_import_error_handling(self):
        """Test handling when OpenAI is not available."""
        from strategy_agent.tools.analyze_tone_of_voice import LLMToneAnalyzer

        # Mock import error for openai
        with patch.dict('sys.modules', {'openai': None}):
            with patch('strategy_agent.tools.analyze_tone_of_voice.LLMToneAnalyzer._initialize_client') as mock_init:
                # Simulate import error
                def mock_initialize_with_import_error(self):
                    try:
                        import openai
                    except ImportError:
                        from strategy_agent.tools.analyze_tone_of_voice import MockLLMClient
                        self.client = MockLLMClient()

                mock_init.side_effect = mock_initialize_with_import_error

                analyzer = LLMToneAnalyzer()
                content_list = ["Test content"]

                result = analyzer.analyze_overall_tone(content_list)

                # Should fall back to mock client
                self.assertIsInstance(result, dict)

    def test_engagement_extraction_with_missing_metadata(self):
        """Test engagement extraction when metadata is missing."""
        from strategy_agent.tools.analyze_tone_of_voice import AnalyzeToneOfVoice

        # Create items with missing or incomplete metadata
        items_with_missing_metadata = [
            {"content": "Content without metadata"},
            {"content": "Content with empty metadata", "metadata": {}},
            {"content": "Content with partial metadata", "metadata": {"other": "data"}}
        ]

        tool = AnalyzeToneOfVoice(items=items_with_missing_metadata, use_llm=False)
        result = tool.run()

        # Should handle missing metadata gracefully
        parsed_result = json.loads(result)
        self.assertIsInstance(parsed_result, dict)

    def test_formality_level_detection(self):
        """Test formality level detection in StyleAnalyzer."""
        from strategy_agent.tools.analyze_tone_of_voice import StyleAnalyzer

        analyzer = StyleAnalyzer()

        # Test formal content
        formal_content = [
            "Our comprehensive business strategy leverages advanced analytics and market research methodologies to optimize revenue generation and enhance customer acquisition frameworks."
        ]

        formal_result = analyzer.analyze(formal_content)
        self.assertEqual(formal_result['writing_style']['formality_level'], 'formal')

        # Test casual content
        casual_content = [
            "Hey! I just wanted to share my thoughts. What do you think? It's pretty cool!"
        ]

        casual_result = analyzer.analyze(casual_content)
        self.assertEqual(casual_result['writing_style']['formality_level'], 'casual')

    def test_zero_division_protection(self):
        """Test protection against zero division errors."""
        from strategy_agent.tools.analyze_tone_of_voice import EmotionAnalyzer, StyleAnalyzer

        # Test EmotionAnalyzer with zero words
        emotion_analyzer = EmotionAnalyzer()
        empty_result = emotion_analyzer.analyze([""])
        self.assertIsInstance(empty_result, dict)

        # Test StyleAnalyzer with zero words
        style_analyzer = StyleAnalyzer()
        empty_style_result = style_analyzer.analyze([""])
        self.assertIsInstance(empty_style_result, dict)
        self.assertEqual(empty_style_result['vocabulary_analysis']['unique_words_ratio'], 0)


if __name__ == '__main__':
    unittest.main()