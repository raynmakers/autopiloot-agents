"""
Agent Registry - Dynamic agent loading system for modular agency composition.

Loads agents dynamically based on configuration to enable/disable agents
without code changes.
"""

import importlib
import logging
from typing import List, Dict, Any
from config.loader import load_app_config

logger = logging.getLogger(__name__)


class AgentRegistry:
    """
    Registry for dynamically loading and managing agents based on configuration.

    Supports loading agents from enabled_agents list in settings.yaml and
    validates agent exports exist.
    """

    def __init__(self):
        self.config = load_app_config()
        self.loaded_agents: Dict[str, Any] = {}
        self._validate_config()

    def _validate_config(self):
        """Validate enabled_agents configuration exists and is properly formatted."""
        if 'enabled_agents' not in self.config:
            raise ValueError("enabled_agents configuration missing from settings.yaml")

        enabled_agents = self.config['enabled_agents']
        if not isinstance(enabled_agents, list):
            raise ValueError("enabled_agents must be a list in settings.yaml")

        if not enabled_agents:
            raise ValueError("enabled_agents list cannot be empty")

        # Validate orchestrator_agent is included (required as CEO)
        if 'orchestrator_agent' not in enabled_agents:
            raise ValueError("orchestrator_agent is required and must be in enabled_agents list")

    def load_agents(self) -> Dict[str, Any]:
        """
        Load agents dynamically based on enabled_agents configuration.

        Returns:
            Dict mapping agent names to agent instances

        Raises:
            ImportError: If agent module cannot be imported
            AttributeError: If agent export symbol not found
            ValueError: If duplicate agents detected
        """
        enabled_agents = self.config['enabled_agents']
        logger.info(f"Loading {len(enabled_agents)} enabled agents: {enabled_agents}")

        loaded_agents = {}

        for agent_name in enabled_agents:
            if agent_name in loaded_agents:
                raise ValueError(f"Duplicate agent '{agent_name}' found in enabled_agents")

            try:
                # Dynamic import: from {agent_name} import {agent_name}
                module = importlib.import_module(agent_name)

                # Validate the agent export exists
                if not hasattr(module, agent_name):
                    raise AttributeError(
                        f"Agent module '{agent_name}' does not export '{agent_name}' symbol"
                    )

                agent_instance = getattr(module, agent_name)
                loaded_agents[agent_name] = agent_instance

                logger.info(f"Successfully loaded agent: {agent_name}")

            except ImportError as e:
                logger.error(f"Failed to import agent module '{agent_name}': {e}")
                raise ImportError(f"Cannot import agent '{agent_name}': {e}")

            except AttributeError as e:
                logger.error(f"Agent export validation failed for '{agent_name}': {e}")
                raise AttributeError(f"Agent '{agent_name}' validation failed: {e}")

        self.loaded_agents = loaded_agents
        logger.info(f"Agent registry loaded successfully with {len(loaded_agents)} agents")
        return loaded_agents

    def get_agent(self, agent_name: str) -> Any:
        """
        Get a specific agent by name.

        Args:
            agent_name: Name of the agent to retrieve

        Returns:
            Agent instance

        Raises:
            ValueError: If agent not found in registry
        """
        if agent_name not in self.loaded_agents:
            raise ValueError(f"Agent '{agent_name}' not found in loaded agents")

        return self.loaded_agents[agent_name]

    def get_enabled_agents(self) -> List[str]:
        """Get list of enabled agent names from configuration."""
        return self.config['enabled_agents'].copy()

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if a specific agent is enabled in configuration."""
        return agent_name in self.config['enabled_agents']

    def get_loaded_agent_names(self) -> List[str]:
        """Get list of successfully loaded agent names."""
        return list(self.loaded_agents.keys())


def create_agent_registry() -> AgentRegistry:
    """
    Factory function to create and initialize agent registry.

    Returns:
        Initialized AgentRegistry instance
    """
    registry = AgentRegistry()
    registry.load_agents()
    return registry


if __name__ == "__main__":
    # Test agent registry loading
    try:
        registry = create_agent_registry()
        print(f"Successfully loaded agents: {registry.get_loaded_agent_names()}")

        # Test individual agent access
        orchestrator = registry.get_agent("orchestrator_agent")
        print(f"Orchestrator agent loaded: {orchestrator}")

    except Exception as e:
        print(f"Agent registry test failed: {e}")
        import traceback
        traceback.print_exc()