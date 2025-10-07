"""
Autopiloot Agency - YouTube Content Discovery and Processing
Agency Swarm v1.0.2 compliant implementation for automated video transcription and summarization

Modular architecture with config-driven agent loading.
"""

import logging
from agency_swarm import Agency
from core.agent_registry import create_agent_registry
from config.loader import load_app_config

logger = logging.getLogger(__name__)


class AutopilootAgency(Agency):
    """
    Multi-agent system for content discovery, processing, and knowledge management.

    Modular architecture with config-driven agent loading from settings.yaml enabled_agents.

    Workflow (when all agents enabled):
    1. OrchestratorAgent (CEO) coordinates end-to-end pipeline and enforces policies
    2. ScraperAgent discovers new videos from target channels and Google Sheets
    3. TranscriberAgent converts videos to text using AssemblyAI with quality controls
    4. SummarizerAgent generates business-focused summaries and stores across platforms
    5. LinkedInAgent ingests LinkedIn posts, comments, and reactions for knowledge management
    6. StrategyAgent analyzes LinkedIn corpus to generate actionable content strategy and playbooks
    7. DriveAgent tracks configured Google Drive files/folders and indexes content into Zep GraphRAG
    8. ObservabilityAgent handles notifications, monitoring, and operational oversight
    """

    def __init__(self, config=None):
        self.config = config or load_app_config()
        self.agent_registry = create_agent_registry()
        self.loaded_agents = self.agent_registry.loaded_agents

        logger.info(f"Initializing AutopilootAgency with {len(self.loaded_agents)} agents")

        # Build communication flows dynamically based on loaded agents
        communication_flows = self._build_communication_flows()

        # Get CEO agent (orchestrator_agent is required)
        ceo_agent = self.agent_registry.get_agent("orchestrator_agent")

        super().__init__(
            ceo_agent,
            communication_flows=communication_flows,
            shared_instructions="./agency_manifesto.md",
        )

        logger.info("AutopilootAgency initialization complete")

    def _build_communication_flows(self):
        """
        Build communication flows from configuration, filtering by enabled agents.

        Returns flows that reflect the configured communication_flows for enabled agents only.
        """
        flows = []
        agents = self.loaded_agents
        config_flows = self.config.get('communication_flows', [])

        if not config_flows:
            logger.warning("No communication_flows found in configuration, using empty flows")
            return flows

        logger.info(f"Processing {len(config_flows)} configured communication flows")

        for flow_config in config_flows:
            if not isinstance(flow_config, list) or len(flow_config) != 2:
                logger.warning(f"Invalid flow configuration: {flow_config} (must be [source, target])")
                continue

            source_name, target_name = flow_config

            # Validate both agents exist in loaded agents
            if source_name not in agents:
                logger.debug(f"Skipping flow {source_name} -> {target_name}: source agent not enabled")
                continue

            if target_name not in agents:
                logger.debug(f"Skipping flow {source_name} -> {target_name}: target agent not enabled")
                continue

            # Add the flow with actual agent instances
            source_agent = agents[source_name]
            target_agent = agents[target_name]
            flows.append([source_agent, target_agent])

            logger.debug(f"Added flow: {source_name} -> {target_name}")

        logger.info(f"Built {len(flows)} communication flows from configuration")
        return flows

    def get_enabled_agents(self):
        """Get list of enabled agent names."""
        return self.agent_registry.get_enabled_agents()

    def get_loaded_agents(self):
        """Get dictionary of loaded agent instances."""
        return self.loaded_agents.copy()

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if specific agent is enabled."""
        return self.agent_registry.is_agent_enabled(agent_name)


# Initialize the agency
autopiloot_agency = AutopilootAgency()

if __name__ == "__main__":
    # For testing and development
    autopiloot_agency.demo_gradio(height=900)