"""
Autopiloot Agency - YouTube Content Discovery and Processing
Agency Swarm v1.0.0 compliant implementation for automated video transcription and summarization
"""

from agency_swarm import Agency
from orchestrator_agent import orchestrator_agent
from scraper_agent import scraper_agent
from transcriber_agent import transcriber_agent
from summarizer_agent import summarizer_agent
from observability_agent import observability_agent
from linkedin_agent import linkedin_agent
from strategy_agent import strategy_agent
from drive_agent import drive_agent


class AutopilootAgency(Agency):
    """
    Multi-agent system for content discovery, processing, and knowledge management.

    Workflow:
    1. OrchestratorAgent (CEO) coordinates end-to-end pipeline and enforces policies
    2. ScraperAgent discovers new videos from target channels and Google Sheets
    3. TranscriberAgent converts videos to text using AssemblyAI with quality controls
    4. SummarizerAgent generates business-focused summaries and stores across platforms
    5. LinkedInAgent ingests LinkedIn posts, comments, and reactions for knowledge management
    6. StrategyAgent analyzes LinkedIn corpus to generate actionable content strategy and playbooks
    7. DriveAgent tracks configured Google Drive files/folders and indexes content into Zep GraphRAG
    8. ObservabilityAgent handles notifications, monitoring, and operational oversight
    """
    
    def __init__(self):
        # Define communication flows between agents (Agency Swarm v1.0.0 format)
        communication_flows = [
            # CEO to all agents for coordination and policy enforcement
            [orchestrator_agent, scraper_agent],
            [orchestrator_agent, transcriber_agent],
            [orchestrator_agent, summarizer_agent],
            [orchestrator_agent, linkedin_agent],
            [orchestrator_agent, strategy_agent],
            [orchestrator_agent, drive_agent],
            [orchestrator_agent, observability_agent],

            # Primary workflow: Scraper -> Transcriber -> Summarizer
            [scraper_agent, transcriber_agent],
            [transcriber_agent, summarizer_agent],

            # LinkedIn workflow: LinkedIn -> Strategy (for content analysis)
            [linkedin_agent, strategy_agent],

            # Drive Agent can be accessed by CEO (no specific flows needed initially per task spec)
            # Future: Drive -> Strategy for document-based insights

            # Observability can communicate with all agents for monitoring/notifications
            [observability_agent, scraper_agent],
            [observability_agent, transcriber_agent],
            [observability_agent, summarizer_agent],
            [observability_agent, linkedin_agent],
            [observability_agent, strategy_agent],
            [observability_agent, drive_agent],

            # Bidirectional communication for error handling and status updates
            [scraper_agent, observability_agent],
            [transcriber_agent, observability_agent],
            [summarizer_agent, observability_agent],
            [linkedin_agent, observability_agent],
            [strategy_agent, observability_agent],
            [drive_agent, observability_agent],
        ]
        
        super().__init__(
            # OrchestratorAgent as CEO (entry point)
            orchestrator_agent,
            communication_flows=communication_flows,
            shared_instructions="./agency_manifesto.md",
        )


# Initialize the agency
autopiloot_agency = AutopilootAgency()

if __name__ == "__main__":
    # For testing and development
    autopiloot_agency.demo_gradio(height=900)