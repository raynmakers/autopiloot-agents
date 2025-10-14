"""
Integration tests for DetectLeadMagnetPost tool (TASK-LI-0073).

Tests various lead magnet detection scenarios including positive cases,
negative cases, and edge cases with comments.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
import importlib.util

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestDetectLeadMagnetPostIntegration(unittest.TestCase):
    """Integration tests for lead magnet detection with real pattern matching."""

    def setUp(self):
        """Set up test fixtures with mocked Agency Swarm."""
        # Mock agency_swarm module
        mock_agency_swarm = MagicMock()
        mock_tools = MagicMock()
        mock_base_tool = MagicMock()

        # Create BaseTool mock that returns instances
        class MockBaseTool:
            def __init__(self, **kwargs):
                for key, value in kwargs.items():
                    setattr(self, key, value)

        mock_tools.BaseTool = MockBaseTool
        mock_agency_swarm.tools = mock_tools

        # Mock pydantic Field
        def mock_field(*args, **kwargs):
            return kwargs.get('default', None)

        # Inject mocks into sys.modules BEFORE importing
        sys.modules['agency_swarm'] = mock_agency_swarm
        sys.modules['agency_swarm.tools'] = mock_tools
        sys.modules['pydantic'] = MagicMock(Field=mock_field)

        # Import tool module directly
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'linkedin_agent', 'tools', 'detect_lead_magnet_post.py'
        )
        spec = importlib.util.spec_from_file_location("detect_lead_magnet_post", tool_path)
        self.tool_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.tool_module)

    def test_positive_comment_pdf_explicit(self):
        """
        Test detection of explicit 'Comment PDF' CTA.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Want my free guide? Comment 'PDF' below and I'll send it to you!",
            case_insensitive=True,
            min_keyword_hit_threshold=1
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect 'Comment PDF' as lead magnet")
        self.assertGreater(result["hit_count"], 0, "Should have at least 1 pattern match")
        self.assertGreater(result["confidence"], 0.0, "Confidence should be > 0")
        self.assertIn("hits", result, "Result should contain hits list")

    def test_positive_drop_yes_variant(self):
        """
        Test detection of 'Drop a YES' variant.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Drop a YES below to get the template",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect 'Drop YES' variant")
        self.assertGreater(result["hit_count"], 0, "Should match action_keyword pattern")

    def test_positive_dm_me_variant(self):
        """
        Test detection of 'DM me' CTA.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Want the playbook? DM me the word GUIDE",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect 'DM me' CTA")
        self.assertIn("dm_request", result["hits"], "Should match dm_request pattern")

    def test_negative_informative_post(self):
        """
        Test that informative posts without CTAs are NOT detected.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Here are 5 tips to improve your productivity. Hope this helps! What strategies do you use?",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Should NOT detect informative post as lead magnet")
        self.assertEqual(result["hit_count"], 0, "Should have zero pattern matches")
        self.assertEqual(result["confidence"], 0.0, "Confidence should be 0")

    def test_negative_weak_phrasing(self):
        """
        Test that weak phrasing without explicit comment instruction is NOT detected.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="What do you think about this? Share your thoughts below!",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Weak phrasing should NOT be detected")
        self.assertEqual(result["hit_count"], 0, "Should have zero matches")

    def test_negative_engagement_question(self):
        """
        Test that genuine engagement questions are NOT detected.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Had a great meeting today! Anyone else working on similar projects? Would love to hear your thoughts.",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Engagement question should NOT be lead magnet")

    def test_comments_only_detection(self):
        """
        Test detection when CTA is in comments, not post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="I have something valuable for you all.",
            comments_preview=["Comment GUIDE to get access", "DM me for the link"],
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect CTA in comments")
        self.assertGreater(result["hit_count"], 0, "Should match patterns in comments")

    def test_case_insensitive_matching(self):
        """
        Test that case insensitive matching works correctly.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="COMMENT YES IF YOU WANT THE EBOOK",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite ALL CAPS")
        self.assertGreater(result["hit_count"], 0, "Should match patterns regardless of case")

    def test_multiple_patterns_high_confidence(self):
        """
        Test that multiple pattern matches increase confidence score.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment 'GUIDE' below and I'll send you the PDF template. DM me if interested!",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect with multiple patterns")
        self.assertGreaterEqual(result["hit_count"], 2, "Should match multiple patterns")
        self.assertGreater(result["confidence"], 0.3, f"Confidence should be > 0.3 with multiple matches, got {result['confidence']}")

    def test_threshold_enforcement(self):
        """
        Test that min_keyword_hit_threshold parameter is respected.
        """
        # Set high threshold
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment PDF",  # Single weak match
            case_insensitive=True,
            min_keyword_hit_threshold=3  # Require 3 patterns
        )

        result = json.loads(tool.run())

        # With high threshold, this might not be detected
        if result["hit_count"] < 3:
            self.assertFalse(result["is_lead_magnet"], "Should NOT detect when below threshold")

    def test_send_promise_pattern(self):
        """
        Test detection of 'I'll send you' pattern.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Leave a comment and I will send you the complete checklist",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect 'I'll send' promise pattern")
        self.assertIn("send_promise", result["hits"], "Should match send_promise pattern")

    def test_comment_below_noun_pattern(self):
        """
        Test detection of 'comment below' + trigger noun pattern.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Interested in this strategy? Comment below for the full playbook",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect 'comment below' + noun")
        self.assertIn("comment_below_noun", result["hits"], "Should match comment_below_noun pattern")

    def test_empty_post_text(self):
        """
        Test handling of empty post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Empty text should not be lead magnet")
        self.assertEqual(result["hit_count"], 0, "Should have zero matches")

    def test_whitespace_normalization(self):
        """
        Test that excessive whitespace is normalized.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment    'PDF'     below    and   I'll   send   it",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite excessive whitespace")

    def test_matched_patterns_structure(self):
        """
        Test that matched_patterns field contains sample matches.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment 'GUIDE' to get the PDF template",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertIn("matched_patterns", result, "Result should contain matched_patterns")
        self.assertIsInstance(result["matched_patterns"], dict, "matched_patterns should be a dict")

        # Check that matched patterns have sample text
        for pattern_label, samples in result["matched_patterns"].items():
            self.assertIsInstance(samples, list, f"Samples for {pattern_label} should be a list")
            self.assertGreater(len(samples), 0, f"Should have at least one sample for {pattern_label}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
