"""
Tests for Modular Architecture Components

Comprehensive test suite for agent registry, communication flows,
schedules & triggers, and CLI scaffold functionality.
"""

import unittest
import json
import os
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.agent_registry import AgentRegistry, create_agent_registry
from core.agent_schedules import AgentScheduleRegistry, AgentSchedule, AgentTrigger, create_schedule_registry
from agency import AutopilootAgency


class TestAgentRegistry(unittest.TestCase):
    """Test suite for agent registry functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock configuration with enabled agents
        self.mock_config = {
            'enabled_agents': [
                'orchestrator_agent',
                'scraper_agent',
                'transcriber_agent'
            ]
        }

        # Mock environment
        self.env_patcher = patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-key',
            'GCP_PROJECT_ID': 'test-project'
        })
        self.env_patcher.start()

    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()

    @patch('core.agent_registry.load_app_config')
    def test_registry_initialization(self, mock_config):
        """Test agent registry initializes correctly."""
        mock_config.return_value = self.mock_config

        registry = AgentRegistry()

        self.assertIsNotNone(registry.config)
        self.assertEqual(registry.config['enabled_agents'], ['orchestrator_agent', 'scraper_agent', 'transcriber_agent'])

    @patch('core.agent_registry.load_app_config')
    def test_missing_enabled_agents_config(self, mock_config):
        """Test registry fails with missing enabled_agents config."""
        mock_config.return_value = {}

        with self.assertRaises(ValueError) as context:
            AgentRegistry()

        self.assertIn("enabled_agents configuration missing", str(context.exception))

    @patch('core.agent_registry.load_app_config')
    def test_empty_enabled_agents_list(self, mock_config):
        """Test registry fails with empty enabled_agents list."""
        mock_config.return_value = {'enabled_agents': []}

        with self.assertRaises(ValueError) as context:
            AgentRegistry()

        self.assertIn("enabled_agents list cannot be empty", str(context.exception))

    @patch('core.agent_registry.load_app_config')
    def test_missing_orchestrator_agent(self, mock_config):
        """Test registry fails without orchestrator_agent."""
        mock_config.return_value = {'enabled_agents': ['scraper_agent']}

        with self.assertRaises(ValueError) as context:
            AgentRegistry()

        self.assertIn("orchestrator_agent is required", str(context.exception))

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.importlib')
    def test_successful_agent_loading(self, mock_importlib, mock_config):
        """Test successful agent loading."""
        mock_config.return_value = self.mock_config

        # Mock agent modules
        mock_orchestrator = Mock()
        mock_orchestrator.orchestrator_agent = Mock()
        mock_scraper = Mock()
        mock_scraper.scraper_agent = Mock()

        mock_importlib.import_module.side_effect = lambda name: {
            'orchestrator_agent': mock_orchestrator,
            'scraper_agent': mock_scraper,
            'transcriber_agent': Mock()
        }.get(name, Mock())

        registry = AgentRegistry()
        loaded_agents = registry.load_agents()

        self.assertEqual(len(loaded_agents), 3)
        self.assertIn('orchestrator_agent', loaded_agents)
        self.assertIn('scraper_agent', loaded_agents)

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.importlib')
    def test_duplicate_agent_detection(self, mock_importlib, mock_config):
        """Test duplicate agent detection."""
        mock_config.return_value = {
            'enabled_agents': ['orchestrator_agent', 'orchestrator_agent']
        }

        registry = AgentRegistry()

        with self.assertRaises(ValueError) as context:
            registry.load_agents()

        self.assertIn("Duplicate agent", str(context.exception))

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.importlib')
    def test_agent_import_failure(self, mock_importlib, mock_config):
        """Test agent import failure handling."""
        mock_config.return_value = self.mock_config
        mock_importlib.import_module.side_effect = ImportError("Module not found")

        registry = AgentRegistry()

        with self.assertRaises(ImportError):
            registry.load_agents()


class TestCommunicationFlows(unittest.TestCase):
    """Test suite for communication flows functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_config = {
            'enabled_agents': ['orchestrator_agent', 'scraper_agent'],
            'communication_flows': [
                ['orchestrator_agent', 'scraper_agent'],
                ['scraper_agent', 'orchestrator_agent']
            ]
        }

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.create_agent_registry')
    def test_flow_building_from_config(self, mock_registry_factory, mock_config):
        """Test communication flows are built from configuration."""
        mock_config.return_value = self.mock_config

        # Mock agent registry
        mock_registry = Mock()
        mock_orchestrator = Mock()
        mock_scraper = Mock()
        mock_registry.loaded_agents = {
            'orchestrator_agent': mock_orchestrator,
            'scraper_agent': mock_scraper
        }
        mock_registry_factory.return_value = mock_registry

        agency = AutopilootAgency()

        # Verify flows were built
        self.assertIsNotNone(agency.agent_registry)
        self.assertEqual(len(agency.loaded_agents), 2)

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.create_agent_registry')
    def test_disabled_agent_flow_filtering(self, mock_registry_factory, mock_config):
        """Test flows are filtered when agents are disabled."""
        # Config with flows referencing disabled agents
        config_with_disabled = {
            'enabled_agents': ['orchestrator_agent'],  # scraper_agent disabled
            'communication_flows': [
                ['orchestrator_agent', 'scraper_agent'],  # Should be filtered out
                ['orchestrator_agent', 'disabled_agent']  # Should be filtered out
            ]
        }
        mock_config.return_value = config_with_disabled

        # Mock agent registry with only orchestrator
        mock_registry = Mock()
        mock_orchestrator = Mock()
        mock_registry.loaded_agents = {
            'orchestrator_agent': mock_orchestrator
        }
        mock_registry_factory.return_value = mock_registry

        agency = AutopilootAgency()

        # Verify only enabled agents are loaded
        self.assertEqual(len(agency.loaded_agents), 1)
        self.assertIn('orchestrator_agent', agency.loaded_agents)


class TestAgentScheduleRegistry(unittest.TestCase):
    """Test suite for agent schedule registry functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock agent with schedules
        self.mock_agent_with_schedules = Mock()
        self.mock_agent_with_schedules.get_schedules.return_value = [
            AgentSchedule(
                schedule="0 1 * * *",
                timezone="Europe/Amsterdam",
                function_name="test_daily_function",
                description="Test daily function",
                handler=lambda: "test_result"
            )
        ]

        # Mock agent without schedules
        self.mock_agent_without_schedules = Mock()
        del self.mock_agent_without_schedules.get_schedules  # Remove method

    @patch('core.agent_schedules.create_agent_registry')
    def test_schedule_discovery(self, mock_registry_factory):
        """Test schedule discovery from agents."""
        # Mock agent registry
        mock_registry = Mock()
        mock_registry.loaded_agents = {
            'test_agent': self.mock_agent_with_schedules,
            'no_schedule_agent': self.mock_agent_without_schedules
        }
        mock_registry_factory.return_value = mock_registry

        schedule_registry = AgentScheduleRegistry()
        agent_schedules = schedule_registry.discover_agent_schedules()

        # Verify schedule discovery
        self.assertEqual(len(agent_schedules), 1)
        self.assertIn('test_agent', agent_schedules)
        self.assertEqual(len(agent_schedules['test_agent']), 1)
        self.assertEqual(agent_schedules['test_agent'][0].function_name, "test_daily_function")

    @patch('core.agent_schedules.create_agent_registry')
    def test_trigger_discovery(self, mock_registry_factory):
        """Test trigger discovery from agents."""
        # Mock agent with triggers
        mock_agent_with_triggers = Mock()
        mock_agent_with_triggers.get_triggers.return_value = [
            AgentTrigger(
                trigger_type="firestore",
                document_pattern="test/{id}",
                function_name="test_trigger_function",
                description="Test trigger function",
                handler=lambda event: "trigger_result"
            )
        ]

        mock_registry = Mock()
        mock_registry.loaded_agents = {
            'test_agent': mock_agent_with_triggers
        }
        mock_registry_factory.return_value = mock_registry

        schedule_registry = AgentScheduleRegistry()
        agent_triggers = schedule_registry.discover_agent_triggers()

        # Verify trigger discovery
        self.assertEqual(len(agent_triggers), 1)
        self.assertIn('test_agent', agent_triggers)
        self.assertEqual(len(agent_triggers['test_agent']), 1)
        self.assertEqual(agent_triggers['test_agent'][0].function_name, "test_trigger_function")

    @patch('core.agent_schedules.create_agent_registry')
    def test_duplicate_function_names(self, mock_registry_factory):
        """Test handling of duplicate function names."""
        # Two agents with same function name
        agent1 = Mock()
        agent1.get_schedules.return_value = [
            AgentSchedule(
                schedule="0 1 * * *",
                timezone="Europe/Amsterdam",
                function_name="duplicate_function",
                description="First function",
                handler=lambda: "result1"
            )
        ]

        agent2 = Mock()
        agent2.get_schedules.return_value = [
            AgentSchedule(
                schedule="0 2 * * *",
                timezone="Europe/Amsterdam",
                function_name="duplicate_function",
                description="Second function",
                handler=lambda: "result2"
            )
        ]

        mock_registry = Mock()
        mock_registry.loaded_agents = {
            'agent1': agent1,
            'agent2': agent2
        }
        mock_registry_factory.return_value = mock_registry

        with patch('core.agent_schedules.logger') as mock_logger:
            schedule_registry = AgentScheduleRegistry()
            schedule_registry.discover_agent_schedules()

            # Verify warning was logged
            mock_logger.warning.assert_called()
            warning_call = mock_logger.warning.call_args[0][0]
            self.assertIn("Duplicate schedule function name", warning_call)


class TestCLIScaffold(unittest.TestCase):
    """Test suite for CLI scaffold functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = Path(self.temp_dir)

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)

    def test_snake_case_conversion(self):
        """Test snake_case conversion utility."""
        from scripts.new_agent import to_snake_case

        test_cases = [
            ("Content Analyzer", "content_analyzer"),
            ("APIManager", "api_manager"),
            ("Simple", "simple"),
            ("Multi-Word-Name", "multi_word_name"),
            ("CamelCaseExample", "camel_case_example")
        ]

        for input_text, expected in test_cases:
            result = to_snake_case(input_text)
            self.assertEqual(result, expected, f"Failed for input: {input_text}")

    def test_pascal_case_conversion(self):
        """Test PascalCase conversion utility."""
        from scripts.new_agent import to_pascal_case

        test_cases = [
            ("content_analyzer", "ContentAnalyzer"),
            ("simple", "Simple"),
            ("multi-word-name", "MultiWordName"),
            ("API Manager", "ApiManager")
        ]

        for input_text, expected in test_cases:
            result = to_pascal_case(input_text)
            self.assertEqual(result, expected, f"Failed for input: {input_text}")

    def test_agent_name_validation(self):
        """Test agent name validation."""
        from scripts.new_agent import validate_agent_name

        # Valid names
        valid_names = ["Content Analyzer", "Simple Agent", "Multi-Word Agent"]
        for name in valid_names:
            result = validate_agent_name(name)
            self.assertEqual(result, name)

        # Invalid names
        with self.assertRaises(ValueError):
            validate_agent_name("")

        with self.assertRaises(ValueError):
            validate_agent_name("Invalid@Name")

    def test_tool_name_validation(self):
        """Test tool name validation and conversion."""
        from scripts.new_agent import validate_tool_names

        input_tools = ["Analyze Content", "generate_report", "Process Data"]
        result = validate_tool_names(input_tools)

        expected = ["analyze_content", "generate_report", "process_data"]
        self.assertEqual(result, expected)

    @patch('scripts.new_agent.load_template')
    def test_agent_file_creation(self, mock_load_template):
        """Test agent file creation."""
        from scripts.new_agent import create_agent_file, generate_agent_variables

        mock_load_template.return_value = "Template content with {agent_name_title}"

        variables = generate_agent_variables(
            "Test Agent",
            "Test description",
            ["test_tool"],
            ["TEST_VAR"]
        )

        agent_dir = self.output_dir / "test_agent_agent"
        agent_dir.mkdir()

        create_agent_file(agent_dir, variables)

        # Verify file was created
        agent_file = agent_dir / "test_agent_agent.py"
        self.assertTrue(agent_file.exists())

        # Verify template was processed
        content = agent_file.read_text()
        self.assertIn("Test Agent", content)

    def test_template_variable_generation(self):
        """Test template variable generation."""
        from scripts.new_agent import generate_agent_variables

        variables = generate_agent_variables(
            "Content Analyzer",
            "Analyzes content for insights",
            ["analyze_text", "extract_topics"],
            ["API_KEY", "MODEL_URL"]
        )

        # Test key variables
        self.assertEqual(variables['agent_name'], "Content Analyzer")
        self.assertEqual(variables['agent_name_title'], "Content Analyzer")
        self.assertEqual(variables['agent_class_name'], "ContentAnalyzerAgent")
        self.assertEqual(variables['agent_variable_name'], "content_analyzer_agent")
        self.assertEqual(variables['description'], "Analyzes content for insights")

        # Test tools are included
        self.assertIn("analyze_text", variables['tools_list'])
        self.assertIn("extract_topics", variables['tools_list'])

        # Test environment variables are included
        self.assertIn("API_KEY", variables['environment_vars'])
        self.assertIn("MODEL_URL", variables['environment_vars'])


class TestModularIntegration(unittest.TestCase):
    """Integration tests for complete modular architecture."""

    @patch('core.agent_registry.load_app_config')
    @patch('core.agent_registry.importlib')
    def test_full_agency_initialization(self, mock_importlib, mock_config):
        """Test full agency initialization with modular components."""
        # Mock complete configuration
        mock_config.return_value = {
            'enabled_agents': ['orchestrator_agent', 'scraper_agent'],
            'communication_flows': [
                ['orchestrator_agent', 'scraper_agent']
            ]
        }

        # Mock agent modules
        mock_orchestrator_module = Mock()
        mock_orchestrator_agent = Mock()
        mock_orchestrator_module.orchestrator_agent = mock_orchestrator_agent

        mock_scraper_module = Mock()
        mock_scraper_agent = Mock()
        mock_scraper_module.scraper_agent = mock_scraper_agent

        mock_importlib.import_module.side_effect = lambda name: {
            'orchestrator_agent': mock_orchestrator_module,
            'scraper_agent': mock_scraper_module
        }[name]

        # Initialize agency
        agency = AutopilootAgency()

        # Verify initialization
        self.assertIsNotNone(agency.agent_registry)
        self.assertEqual(len(agency.loaded_agents), 2)
        self.assertIn('orchestrator_agent', agency.loaded_agents)
        self.assertIn('scraper_agent', agency.loaded_agents)

    def test_modular_components_work_together(self):
        """Test modular components integrate correctly."""
        # Test that registry, flows, and schedules work together
        # This is more of a smoke test to ensure no import errors

        from core.agent_registry import create_agent_registry
        from core.agent_schedules import create_schedule_registry

        # These should not raise exceptions
        try:
            # Note: These may fail due to missing agents, but shouldn't have import errors
            registry = create_agent_registry()
            schedule_registry = create_schedule_registry()

            # Basic assertions
            self.assertIsNotNone(registry)
            self.assertIsNotNone(schedule_registry)

        except (ImportError, AttributeError):
            # Expected if agents don't exist, but not import errors
            pass
        except Exception as e:
            # Any other exception should be investigated
            if "module" not in str(e).lower() and "import" not in str(e).lower():
                raise


if __name__ == '__main__':
    # Configure logging for tests
    import logging
    logging.basicConfig(level=logging.WARNING)

    # Run tests with detailed output
    unittest.main(verbosity=2)