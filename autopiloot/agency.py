"""
Autopiloot Agency - YouTube Content Discovery and Processing
Agency Swarm v1.0.2 compliant implementation for automated video transcription and summarization

Modular architecture with config-driven agent loading.
"""

import logging
from agency_swarm import Agency
from core.agent_registry import create_agent_registry
from config.loader import load_app_config
from config.env_loader import load_environment

# Load environment variables once at agency initialization
load_environment()

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

        # Add persistence callbacks if enabled (Agency Swarm v1.2.0)
        persistence_config = self.config.get('agency', {}).get('persistence', {})
        persistence_enabled = persistence_config.get('enabled', True)

        callbacks = {}
        if persistence_enabled:
            callbacks['save_threads_callback'] = self._save_threads_to_firestore
            callbacks['load_threads_callback'] = self._load_threads_from_firestore
            logger.info("Conversation persistence enabled (Agency Swarm v1.2.0)")

        super().__init__(
            ceo_agent,
            communication_flows=communication_flows,
            shared_instructions="./agency_manifesto.md",
            **callbacks  # Pass callbacks to Agency
        )

        logger.info("AutopilootAgency initialization complete")

    def _build_communication_flows(self):
        """
        Build communication flows from configuration with handoff reminders.

        Returns flows that reflect the configured communication_flows for enabled agents only.
        Includes handoff reminders (Agency Swarm v1.1.0+) where configured.
        """
        flows = []
        agents = self.loaded_agents
        config_flows = self.config.get('communication_flows', [])
        handoff_reminders = self.config.get('handoff_reminders', {})

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

            # Get agent instances
            source_agent = agents[source_name]
            target_agent = agents[target_name]

            # Check for handoff reminder (Agency Swarm v1.1.0+ feature)
            reminder_key = f"{source_name}_to_{target_name}"
            reminder_text = handoff_reminders.get(reminder_key)

            if reminder_text:
                # Add flow with handoff reminder
                flows.append([
                    source_agent,
                    target_agent,
                    {"handoff_reminder": reminder_text}
                ])
                logger.debug(f"Added flow with reminder: {source_name} -> {target_name}")
            else:
                # Add flow without reminder
                flows.append([source_agent, target_agent])
                logger.debug(f"Added flow: {source_name} -> {target_name}")

        flows_with_reminders = sum(1 for f in flows if len(f) == 3)
        logger.info(f"Built {len(flows)} communication flows ({flows_with_reminders} with handoff reminders)")
        return flows

    def _save_threads_to_firestore(self, threads: dict) -> None:
        """
        Persist conversation threads to Firestore (Agency Swarm v1.2.0 callback).

        Stores thread data with timestamps for stateful workflows across Firebase Function invocations.

        Args:
            threads: Dictionary mapping thread_id to thread data (messages, metadata)
        """
        try:
            from google.cloud import firestore

            db = firestore.Client()
            collection = self.config.get('agency', {}).get('persistence', {}).get('collection', 'agency_threads')

            for thread_id, thread_data in threads.items():
                doc_ref = db.collection(collection).document(thread_id)
                doc_ref.set({
                    'thread_id': thread_id,
                    'messages': thread_data,
                    'updated_at': firestore.SERVER_TIMESTAMP,
                    'created_at': firestore.SERVER_TIMESTAMP
                }, merge=True)

            logger.info(f"Persisted {len(threads)} conversation threads to Firestore collection '{collection}'")

        except Exception as e:
            logger.error(f"Failed to persist conversation threads: {e}")
            # Don't raise - persistence failure should not break the main workflow

    def _load_threads_from_firestore(self) -> dict:
        """
        Load conversation threads from Firestore (Agency Swarm v1.2.0 callback).

        Retrieves persisted thread data to resume workflows across Firebase Function invocations.

        Returns:
            dict: Dictionary mapping thread_id to thread data (messages, metadata)
        """
        try:
            from google.cloud import firestore

            db = firestore.Client()
            collection = self.config.get('agency', {}).get('persistence', {}).get('collection', 'agency_threads')

            threads = {}
            for doc in db.collection(collection).stream():
                doc_data = doc.to_dict()
                if doc_data and 'messages' in doc_data:
                    threads[doc.id] = doc_data['messages']

            logger.info(f"Loaded {len(threads)} conversation threads from Firestore collection '{collection}'")
            return threads

        except Exception as e:
            logger.error(f"Failed to load conversation threads: {e}")
            # Return empty dict on failure - start fresh
            return {}

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