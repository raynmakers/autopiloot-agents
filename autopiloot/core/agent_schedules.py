"""
Agent Schedules Registry - Dynamic schedule and trigger registration for Firebase Functions.

Allows agents to expose schedules and triggers that get registered automatically
by Firebase Functions based on enabled agents.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from config.loader import load_app_config
from core.agent_registry import create_agent_registry

logger = logging.getLogger(__name__)


@dataclass
class AgentSchedule:
    """Definition of a scheduled function from an agent."""
    schedule: str  # Cron expression (e.g., "0 1 * * *")
    timezone: str  # Timezone (e.g., "Europe/Amsterdam")
    function_name: str  # Unique function name
    description: str  # Human-readable description
    handler: Callable  # Function to execute
    memory_mb: int = 512  # Memory allocation
    timeout_sec: int = 300  # Timeout in seconds
    max_instances: int = 1  # Maximum concurrent instances


@dataclass
class AgentTrigger:
    """Definition of an event-driven trigger from an agent."""
    trigger_type: str  # "firestore", "pubsub", "http"
    document_pattern: Optional[str] = None  # For Firestore triggers (e.g., "transcripts/{video_id}")
    topic_name: Optional[str] = None  # For Pub/Sub triggers
    function_name: str = ""  # Unique function name
    description: str = ""  # Human-readable description
    handler: Callable = None  # Function to execute
    memory_mb: int = 256  # Memory allocation
    timeout_sec: int = 180  # Timeout in seconds
    max_instances: int = 10  # Maximum concurrent instances


class AgentScheduleRegistry:
    """
    Registry for collecting and managing agent-provided schedules and triggers.

    Discovers schedule/trigger definitions from enabled agents and provides
    them to Firebase Functions for dynamic registration.
    """

    def __init__(self):
        self.config = load_app_config()
        self.agent_registry = create_agent_registry()
        self.schedules: Dict[str, AgentSchedule] = {}
        self.triggers: Dict[str, AgentTrigger] = {}

    def discover_agent_schedules(self) -> Dict[str, List[AgentSchedule]]:
        """
        Discover schedules from all enabled agents.

        Returns:
            Dict mapping agent names to their schedules
        """
        agent_schedules = {}

        for agent_name, agent_instance in self.agent_registry.loaded_agents.items():
            try:
                # Check if agent has get_schedules method
                if hasattr(agent_instance, 'get_schedules'):
                    schedules = agent_instance.get_schedules()
                    if schedules:
                        agent_schedules[agent_name] = schedules
                        logger.info(f"Discovered {len(schedules)} schedules from {agent_name}")

                        # Register schedules in global registry
                        for schedule in schedules:
                            if schedule.function_name in self.schedules:
                                logger.warning(f"Duplicate schedule function name: {schedule.function_name}")
                            else:
                                self.schedules[schedule.function_name] = schedule

            except Exception as e:
                logger.warning(f"Failed to discover schedules from {agent_name}: {e}")

        logger.info(f"Discovered {len(self.schedules)} total schedules from {len(agent_schedules)} agents")
        return agent_schedules

    def discover_agent_triggers(self) -> Dict[str, List[AgentTrigger]]:
        """
        Discover triggers from all enabled agents.

        Returns:
            Dict mapping agent names to their triggers
        """
        agent_triggers = {}

        for agent_name, agent_instance in self.agent_registry.loaded_agents.items():
            try:
                # Check if agent has get_triggers method
                if hasattr(agent_instance, 'get_triggers'):
                    triggers = agent_instance.get_triggers()
                    if triggers:
                        agent_triggers[agent_name] = triggers
                        logger.info(f"Discovered {len(triggers)} triggers from {agent_name}")

                        # Register triggers in global registry
                        for trigger in triggers:
                            if trigger.function_name in self.triggers:
                                logger.warning(f"Duplicate trigger function name: {trigger.function_name}")
                            else:
                                self.triggers[trigger.function_name] = trigger

            except Exception as e:
                logger.warning(f"Failed to discover triggers from {agent_name}: {e}")

        logger.info(f"Discovered {len(self.triggers)} total triggers from {len(agent_triggers)} agents")
        return agent_triggers

    def get_all_schedules(self) -> Dict[str, AgentSchedule]:
        """Get all discovered schedules."""
        return self.schedules.copy()

    def get_all_triggers(self) -> Dict[str, AgentTrigger]:
        """Get all discovered triggers."""
        return self.triggers.copy()

    def get_schedule_by_name(self, function_name: str) -> Optional[AgentSchedule]:
        """Get a specific schedule by function name."""
        return self.schedules.get(function_name)

    def get_trigger_by_name(self, function_name: str) -> Optional[AgentTrigger]:
        """Get a specific trigger by function name."""
        return self.triggers.get(function_name)


def create_schedule_registry() -> AgentScheduleRegistry:
    """
    Factory function to create and initialize agent schedule registry.

    Returns:
        Initialized AgentScheduleRegistry with discovered schedules and triggers
    """
    registry = AgentScheduleRegistry()
    registry.discover_agent_schedules()
    registry.discover_agent_triggers()
    return registry


def get_default_schedules() -> List[AgentSchedule]:
    """
    Get default schedules for backwards compatibility.

    These are the core schedules that should always be available
    regardless of agent schedule discovery.
    """
    from datetime import datetime

    def daily_scraper_handler():
        """Default daily scraper implementation."""
        from agency import AutopilootAgency
        agency = AutopilootAgency()
        return agency.run_daily_workflow()

    def daily_digest_handler():
        """Default daily digest implementation."""
        from observability_agent.tools.generate_daily_digest import GenerateDailyDigest
        from observability_agent.tools.send_slack_message import SendSlackMessage

        digest = GenerateDailyDigest()
        result = digest.run()

        slack = SendSlackMessage()
        return slack.run(result)

    return [
        AgentSchedule(
            schedule="0 1 * * *",
            timezone="Europe/Amsterdam",
            function_name="default_daily_scraper",
            description="Default daily content processing workflow",
            handler=daily_scraper_handler,
            memory_mb=512,
            timeout_sec=540,
            max_instances=1
        ),
        AgentSchedule(
            schedule="0 7 * * *",
            timezone="Europe/Amsterdam",
            function_name="default_daily_digest",
            description="Default daily operational digest",
            handler=daily_digest_handler,
            memory_mb=256,
            timeout_sec=300,
            max_instances=1
        )
    ]


def get_default_triggers() -> List[AgentTrigger]:
    """
    Get default triggers for backwards compatibility.

    These are the core triggers that should always be available.
    """
    def budget_monitor_handler(event):
        """Default budget monitoring implementation."""
        from observability_agent.tools.monitor_transcription_budget import MonitorTranscriptionBudget

        monitor = MonitorTranscriptionBudget()
        return monitor.run(event)

    return [
        AgentTrigger(
            trigger_type="firestore",
            document_pattern="transcripts/{video_id}",
            function_name="default_budget_monitor",
            description="Default transcription budget monitoring",
            handler=budget_monitor_handler,
            memory_mb=256,
            timeout_sec=180,
            max_instances=10
        )
    ]


if __name__ == "__main__":
    # Test schedule registry
    try:
        registry = create_schedule_registry()

        schedules = registry.get_all_schedules()
        triggers = registry.get_all_triggers()

        print(f"Discovered schedules: {len(schedules)}")
        for name, schedule in schedules.items():
            print(f"  - {name}: {schedule.schedule} ({schedule.description})")

        print(f"Discovered triggers: {len(triggers)}")
        for name, trigger in triggers.items():
            print(f"  - {name}: {trigger.trigger_type} ({trigger.description})")

        # Test defaults
        default_schedules = get_default_schedules()
        default_triggers = get_default_triggers()

        print(f"Default schedules: {len(default_schedules)}")
        print(f"Default triggers: {len(default_triggers)}")

    except Exception as e:
        print(f"Schedule registry test failed: {e}")
        import traceback
        traceback.print_exc()