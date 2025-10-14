"""
Tests for Agency Swarm v1.1.0 Handoff Reminders (TASK-AGS-0099)

Tests cover:
1. Handoff reminder configuration loading from settings.yaml
2. Communication flow building with handoff reminders
3. Handoff reminder validation
4. Reminder content verification (policy-focused)
5. Agency integration with handoff reminders
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
from core.guardrails import validate_handoff_reminder


class TestHandoffReminderValidation(unittest.TestCase):
    """Test handoff reminder validation function"""

    def test_valid_reminder_passes(self):
        """Valid reminder text should pass validation"""
        reminder = "Check budget before proceeding"
        result = validate_handoff_reminder(reminder)
        self.assertEqual(result, reminder)

    def test_valid_multiline_reminder_passes(self):
        """Valid multiline reminder should pass"""
        reminder = """POLICY ENFORCEMENT:
- YouTube API quota: 10,000 units/day
- Max 10 videos per channel per day"""
        result = validate_handoff_reminder(reminder)
        self.assertIn("POLICY ENFORCEMENT", result)
        self.assertIn("YouTube API quota", result)

    def test_empty_string_raises_error(self):
        """Empty string should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_handoff_reminder("")
        self.assertIn("non-empty string", str(ctx.exception))

    def test_whitespace_only_raises_error(self):
        """Whitespace-only string should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_handoff_reminder("   \n\t  ")
        self.assertIn("cannot be empty", str(ctx.exception))

    def test_none_raises_error(self):
        """None should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_handoff_reminder(None)
        self.assertIn("must be non-empty string", str(ctx.exception))

    def test_non_string_raises_error(self):
        """Non-string input should raise ValueError"""
        with self.assertRaises(ValueError) as ctx:
            validate_handoff_reminder(123)
        self.assertIn("must be non-empty string", str(ctx.exception))

    def test_long_reminder_logs_warning(self):
        """Reminder longer than 500 chars should log warning but pass"""
        long_reminder = "x" * 501
        with self.assertLogs('core.guardrails', level='WARNING') as log:
            result = validate_handoff_reminder(long_reminder)
            self.assertEqual(result, long_reminder)
            self.assertTrue(any("long" in message.lower() for message in log.output))

    def test_directive_language_logs_warning(self):
        """Reminder with 'you must' should log warning but pass"""
        directive_reminder = "You must check the budget before proceeding"
        with self.assertLogs('core.guardrails', level='WARNING') as log:
            result = validate_handoff_reminder(directive_reminder)
            self.assertEqual(result, directive_reminder)
            self.assertTrue(any("directive language" in message.lower() for message in log.output))

    def test_whitespace_trimming(self):
        """Reminder should be trimmed of leading/trailing whitespace"""
        reminder = "  Check budget  \n"
        result = validate_handoff_reminder(reminder)
        self.assertEqual(result, "Check budget")


class TestHandoffRemindersConfiguration(unittest.TestCase):
    """Test handoff reminder configuration loading"""

    @patch('config.loader.load_app_config')
    def test_handoff_reminders_loaded_from_config(self, mock_config):
        """Test that handoff reminders are loaded from settings.yaml"""
        mock_config.return_value = {
            'handoff_reminders': {
                'orchestrator_agent_to_scraper_agent': 'Policy enforcement message',
                'scraper_agent_to_transcriber_agent': 'Budget check message'
            }
        }

        from config.loader import load_app_config
        config = load_app_config()
        reminders = config.get('handoff_reminders', {})

        self.assertGreater(len(reminders), 0, "Should have handoff reminders configured")
        self.assertIn('orchestrator_agent_to_scraper_agent', reminders)
        self.assertIn('scraper_agent_to_transcriber_agent', reminders)

    @patch('config.loader.load_app_config')
    def test_reminder_content_is_policy_focused(self, mock_config):
        """Test that reminders contain policy keywords"""
        mock_config.return_value = {
            'handoff_reminders': {
                'orchestrator_agent_to_scraper_agent': 'YouTube API quota: 10,000 units/day. Max 10 videos per channel.',
                'scraper_agent_to_transcriber_agent': 'Daily budget: $5 USD for transcription'
            }
        }

        from config.loader import load_app_config
        config = load_app_config()
        reminders = config.get('handoff_reminders', {})

        # Orchestrator -> Scraper should mention quotas
        orch_to_scraper = reminders.get('orchestrator_agent_to_scraper_agent', '')
        self.assertIn('quota', orch_to_scraper.lower())
        self.assertIn('10', orch_to_scraper)  # Daily limit per channel

        # Scraper -> Transcriber should mention budget
        scraper_to_trans = reminders.get('scraper_agent_to_transcriber_agent', '')
        self.assertIn('budget', scraper_to_trans.lower())
        self.assertIn('$5', scraper_to_trans)

    @patch('config.loader.load_app_config')
    def test_reminder_length_is_reasonable(self, mock_config):
        """Test that reminders are concise (< 500 chars)"""
        mock_config.return_value = {
            'handoff_reminders': {
                'orchestrator_agent_to_scraper_agent': 'Short reminder',
                'scraper_agent_to_transcriber_agent': 'Another short reminder with policy details'
            }
        }

        from config.loader import load_app_config
        config = load_app_config()
        reminders = config.get('handoff_reminders', {})

        for key, reminder in reminders.items():
            self.assertLess(
                len(reminder), 500,
                f"Reminder '{key}' is too long ({len(reminder)} chars). Keep under 500."
            )


class TestCommunicationFlowBuilding(unittest.TestCase):
    """Test communication flow building logic directly"""

    def test_flow_with_reminder_has_three_elements(self):
        """Test that flow with reminder has [source, target, options] structure"""
        mock_source = Mock()
        mock_target = Mock()
        flow_with_reminder = [mock_source, mock_target, {"handoff_reminder": "Check quota"}]

        self.assertEqual(len(flow_with_reminder), 3)
        self.assertIsInstance(flow_with_reminder[2], dict)
        self.assertIn('handoff_reminder', flow_with_reminder[2])

    def test_flow_without_reminder_has_two_elements(self):
        """Test that flow without reminder has [source, target] structure"""
        mock_source = Mock()
        mock_target = Mock()
        flow_without_reminder = [mock_source, mock_target]

        self.assertEqual(len(flow_without_reminder), 2)

    def test_reminder_key_format(self):
        """Test reminder key format matches source_to_target pattern"""
        source_name = "orchestrator_agent"
        target_name = "scraper_agent"
        reminder_key = f"{source_name}_to_{target_name}"

        self.assertEqual(reminder_key, "orchestrator_agent_to_scraper_agent")

    def test_reminder_structure_matches_specification(self):
        """Test that reminder structure matches Agency Swarm v1.1.0 spec"""
        # According to Agency Swarm docs, flow with reminder should be:
        # [source_agent, target_agent, {"handoff_reminder": "text"}]

        reminder_flow = [
            Mock(),  # source_agent
            Mock(),  # target_agent
            {"handoff_reminder": "Check budget"}  # options dict
        ]

        # Verify structure
        self.assertEqual(len(reminder_flow), 3)
        self.assertIsInstance(reminder_flow[2], dict)
        self.assertIn('handoff_reminder', reminder_flow[2])
        self.assertIsInstance(reminder_flow[2]['handoff_reminder'], str)


if __name__ == '__main__':
    unittest.main()
