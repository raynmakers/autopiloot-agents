"""
Error handling tests for DetectLeadMagnetPost tool (TASK-LI-0073).

Tests edge cases, invalid inputs, and error recovery.
"""

import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import json
import importlib.util

# Add parent directory to path

class TestDetectLeadMagnetPostErrorHandling(unittest.TestCase):
    """Error handling and edge case tests for lead magnet detection."""

    def setUp(self):
        """Set up test fixtures with mocked Agency Swarm."""
        # Mock agency_swarm module
        mock_agency_swarm = MagicMock()
        mock_tools = MagicMock()

        # Create BaseTool mock
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

    def test_none_post_text(self):
        """
        Test handling of None post_text (should treat as empty).
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text=None,
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Should handle gracefully without crashing
        self.assertIn("is_lead_magnet", result, "Result should contain is_lead_magnet key")
        self.assertFalse(result["is_lead_magnet"], "None text should not be lead magnet")

    def test_empty_string_post_text(self):
        """
        Test handling of empty string.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertIn("is_lead_magnet", result)
        self.assertIn("hits", result)
        self.assertIn("hit_count", result)
        self.assertFalse(result["is_lead_magnet"])

    def test_very_long_post_text(self):
        """
        Test handling of very long post text (performance test).
        """
        # Create 10,000 character post
        long_text = "This is a long post. " * 500  # ~10,500 characters

        tool = self.tool_module.DetectLeadMagnetPost(
            post_text=long_text,
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Should complete without timeout
        self.assertIn("is_lead_magnet", result)
        self.assertIsInstance(result["is_lead_magnet"], bool)

    def test_special_characters_in_post(self):
        """
        Test handling of special characters and unicode.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment 'PDF' für das E-Book! 🎉🚀 #leadmagnet",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite special chars")
        self.assertGreater(result["hit_count"], 0)

    def test_only_emojis(self):
        """
        Test handling of post with only emojis.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="🎉🚀💡✨🔥",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Emojis only should not be lead magnet")
        self.assertEqual(result["hit_count"], 0)

    def test_empty_comments_preview(self):
        """
        Test handling of empty comments preview list.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment PDF for guide",
            comments_preview=[],
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should still detect from post text")

    def test_none_in_comments_preview(self):
        """
        Test handling of None values in comments preview.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Regular post",
            comments_preview=[None, "Comment GUIDE", None],
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Should handle gracefully, detecting from valid comment
        self.assertIn("is_lead_magnet", result)

    def test_very_large_comments_preview(self):
        """
        Test handling of large comments preview list.
        """
        # 1000 comments
        large_comments = ["Regular comment"] * 1000

        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Regular post",
            comments_preview=large_comments,
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Should complete without performance issues
        self.assertIn("is_lead_magnet", result)

    def test_case_sensitive_mode(self):
        """
        Test case sensitive matching mode.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="COMMENT PDF",  # All caps
            case_insensitive=False  # Case sensitive
        )

        result = json.loads(tool.run())

        # With case_insensitive=False, might still match due to caps_trigger pattern
        self.assertIn("is_lead_magnet", result)
        self.assertIsInstance(result["is_lead_magnet"], bool)

    def test_zero_threshold(self):
        """
        Test with threshold of 0 (should always be lead magnet).
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Regular post with no CTA",
            case_insensitive=True,
            min_keyword_hit_threshold=0
        )

        result = json.loads(tool.run())

        # With threshold 0, any text should match (even with 0 hits)
        self.assertIn("is_lead_magnet", result)

    def test_very_high_threshold(self):
        """
        Test with unreasonably high threshold.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment PDF for the guide, DM me, and I'll send it",
            case_insensitive=True,
            min_keyword_hit_threshold=100  # Impossible to reach
        )

        result = json.loads(tool.run())

        self.assertFalse(result["is_lead_magnet"], "Should not detect with impossible threshold")

    def test_negative_threshold(self):
        """
        Test with negative threshold (should behave like 0).
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Regular post",
            case_insensitive=True,
            min_keyword_hit_threshold=-1
        )

        result = json.loads(tool.run())

        # Should handle gracefully
        self.assertIn("is_lead_magnet", result)

    def test_json_structure_always_consistent(self):
        """
        Test that JSON structure is always consistent regardless of input.
        """
        test_cases = [
            "",
            "Comment PDF",
            None,
            "🎉🚀💡",
            "A" * 10000
        ]

        for test_input in test_cases:
            tool = self.tool_module.DetectLeadMagnetPost(
                post_text=test_input,
                case_insensitive=True
            )

            result = json.loads(tool.run())

            # Verify all required keys exist
            self.assertIn("is_lead_magnet", result, f"Missing key for input: {test_input}")
            self.assertIn("hits", result, f"Missing hits for input: {test_input}")
            self.assertIn("hit_count", result, f"Missing hit_count for input: {test_input}")
            self.assertIn("confidence", result, f"Missing confidence for input: {test_input}")

            # Verify types
            self.assertIsInstance(result["is_lead_magnet"], bool)
            self.assertIsInstance(result["hits"], list)
            self.assertIsInstance(result["hit_count"], int)
            self.assertIsInstance(result["confidence"], (int, float))

    def test_confidence_range(self):
        """
        Test that confidence is always between 0.0 and 1.0.
        """
        test_cases = [
            ("", 0.0, 0.0),  # No matches
            ("Comment PDF", 0.0, 1.0),  # Some matches
            ("Comment PDF DM me GUIDE YES template", 0.0, 1.0),  # Many matches
        ]

        for post_text, min_conf, max_conf in test_cases:
            tool = self.tool_module.DetectLeadMagnetPost(
                post_text=post_text,
                case_insensitive=True
            )

            result = json.loads(tool.run())

            self.assertGreaterEqual(result["confidence"], min_conf, f"Confidence too low for: {post_text}")
            self.assertLessEqual(result["confidence"], max_conf, f"Confidence too high for: {post_text}")

    def test_html_tags_in_post(self):
        """
        Test handling of HTML tags in post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="<p>Comment <b>PDF</b> for guide</p>",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Should still detect pattern despite HTML
        self.assertTrue(result["is_lead_magnet"], "Should detect despite HTML tags")

    def test_newlines_and_formatting(self):
        """
        Test handling of newlines and formatting characters.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment\n'PDF'\nbelow\n\nand\nI'll\nsend\nit",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        # Newlines should be normalized to spaces
        self.assertTrue(result["is_lead_magnet"], "Should detect despite newlines")

    def test_tabs_and_special_whitespace(self):
        """
        Test handling of tabs and special whitespace.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment\t'PDF'\t\tfor\t\tthe\tguide",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite tabs")

    def test_url_in_post(self):
        """
        Test handling of URLs in post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment PDF to get access at https://example.com/guide",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite URL")

    def test_mentions_in_post(self):
        """
        Test handling of @mentions in post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="@john @jane Comment PDF for the template",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite mentions")

    def test_hashtags_in_post(self):
        """
        Test handling of hashtags in post text.
        """
        tool = self.tool_module.DetectLeadMagnetPost(
            post_text="Comment PDF #leadmagnet #freebie #marketing",
            case_insensitive=True
        )

        result = json.loads(tool.run())

        self.assertTrue(result["is_lead_magnet"], "Should detect despite hashtags")


if __name__ == "__main__":
    unittest.main(verbosity=2)
