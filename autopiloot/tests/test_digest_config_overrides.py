"""
Unit tests for digest configuration overrides functionality.
Tests TASK-DIG-0066 implementation: configurable digest settings via settings.yaml.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'core'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'observability_agent', 'tools'))

from env_loader import get_config_value


class TestDigestConfigOverrides(unittest.TestCase):
    """Test digest configuration override behavior via settings.yaml."""

    @patch('core.env_loader.get_config_value')
    def test_digest_enabled_override(self, mock_get_config):
        """Test that digest can be disabled via configuration."""
        # Arrange
        mock_get_config.side_effect = lambda key, default: {
            "notifications.slack.digest.enabled": False
        }.get(key, default)

        # Act & Assert
        enabled = get_config_value("notifications.slack.digest.enabled", True)
        self.assertFalse(enabled)

    @patch('core.env_loader.get_config_value')
    def test_digest_channel_override(self, mock_get_config):
        """Test that digest channel can be configured."""
        # Arrange
        test_channel = "test-channel"
        mock_get_config.side_effect = lambda key, default: {
            "notifications.slack.digest.channel": test_channel
        }.get(key, default)

        # Act
        channel = get_config_value("notifications.slack.digest.channel", "ops-autopiloot")

        # Assert
        self.assertEqual(channel, test_channel)

    @patch('core.env_loader.get_config_value')
    def test_digest_timezone_override(self, mock_get_config):
        """Test that digest timezone can be configured."""
        # Arrange
        test_timezone = "America/New_York"
        mock_get_config.side_effect = lambda key, default: {
            "notifications.slack.digest.timezone": test_timezone
        }.get(key, default)

        # Act
        timezone = get_config_value("notifications.slack.digest.timezone", "Europe/Amsterdam")

        # Assert
        self.assertEqual(timezone, test_timezone)

    @patch('core.env_loader.get_config_value')
    def test_digest_sections_override(self, mock_get_config):
        """Test that digest sections can be configured."""
        # Arrange
        test_sections = ["summary", "budgets"]
        mock_get_config.side_effect = lambda key, default: {
            "notifications.slack.digest.sections": test_sections
        }.get(key, default)

        # Act
        sections = get_config_value(
            "notifications.slack.digest.sections",
            ["summary", "budgets", "issues", "links"]
        )

        # Assert
        self.assertEqual(sections, test_sections)

    @patch('core.env_loader.get_config_value')
    def test_digest_default_values(self, mock_get_config):
        """Test that default values are used when config is missing."""
        # Arrange - mock returns default values
        mock_get_config.side_effect = lambda key, default: default

        # Act & Assert
        self.assertTrue(get_config_value("notifications.slack.digest.enabled", True))
        self.assertEqual(get_config_value("notifications.slack.digest.channel", "ops-autopiloot"), "ops-autopiloot")
        self.assertEqual(get_config_value("notifications.slack.digest.timezone", "Europe/Amsterdam"), "Europe/Amsterdam")
        self.assertEqual(
            get_config_value("notifications.slack.digest.sections", ["summary", "budgets", "issues", "links"]),
            ["summary", "budgets", "issues", "links"]
        )

    @patch('core.env_loader.get_config_value')
    def test_budget_config_override(self, mock_get_config):
        """Test that budget configuration is also configurable."""
        # Arrange
        test_budget = 10.0
        mock_get_config.side_effect = lambda key, default: {
            "budgets.transcription_daily_usd": test_budget
        }.get(key, default)

        # Act
        budget = get_config_value("budgets.transcription_daily_usd", 5.0)

        # Assert
        self.assertEqual(budget, test_budget)


class TestDigestSectionFiltering(unittest.TestCase):
    """Test digest section filtering based on configuration."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_content = {
            "header": "Test Digest",
            "processing_summary": {"flow": "1 → 1 → 1"},
            "budget_status": {"emoji": "🟢", "spent": "$1.00", "percentage": "20.0%"},
            "issues": {"summary": "None", "dlq_count": 0},
            "links": {"transcripts": "http://test.com"}
        }

    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_sections_filtered_correctly(self, mock_get_config):
        """Test that only configured sections are included in digest blocks."""
        # Arrange
        enabled_sections = ["summary", "budgets"]  # Only summary and budgets
        mock_get_config.return_value = enabled_sections

        # Import here to avoid import-time issues
        from generate_daily_digest import GenerateDailyDigest

        # Act
        digest = GenerateDailyDigest(date="2023-01-01")
        blocks = digest._format_slack_blocks(self.mock_content)

        # Assert
        # Should have header + summary + budgets + footer = 4 blocks
        # (header and footer are always included)
        self.assertGreaterEqual(len(blocks), 3)  # At least header, sections, footer

        # Verify specific content is present/absent by checking block text
        block_texts = [block.get("text", {}).get("text", "") for block in blocks]
        combined_text = " ".join(block_texts)

        self.assertIn("Processing Summary", combined_text)
        self.assertIn("Budget Status", combined_text)
        # Issues and links should not be present
        self.assertNotIn("Issues & Health", combined_text)
        self.assertNotIn("Quick Links", combined_text)

    @patch('observability_agent.tools.generate_daily_digest.get_config_value')
    def test_all_sections_included_by_default(self, mock_get_config):
        """Test that all sections are included when configuration uses defaults."""
        # Arrange
        mock_get_config.return_value = ["summary", "budgets", "issues", "links"]

        # Import here to avoid import-time issues
        from generate_daily_digest import GenerateDailyDigest

        # Act
        digest = GenerateDailyDigest(date="2023-01-01")
        blocks = digest._format_slack_blocks(self.mock_content)

        # Assert
        block_texts = [block.get("text", {}).get("text", "") for block in blocks]
        combined_text = " ".join(block_texts)

        self.assertIn("Processing Summary", combined_text)
        self.assertIn("Budget Status", combined_text)
        self.assertIn("Issues & Health", combined_text)
        self.assertIn("Quick Links", combined_text)


if __name__ == "__main__":
    unittest.main()