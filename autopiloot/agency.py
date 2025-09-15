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


class AutopilootAgency(Agency):
    """
    Multi-agent system for YouTube content discovery, transcription, and summarization.
    
    Workflow:
    1. OrchestratorAgent (CEO) coordinates end-to-end pipeline and enforces policies
    2. ScraperAgent discovers new videos from target channels and Google Sheets
    3. TranscriberAgent converts videos to text using AssemblyAI with quality controls
    4. SummarizerAgent generates business-focused summaries and stores across platforms
    5. ObservabilityAgent handles notifications, monitoring, and operational oversight
    """
    
    def __init__(self):
        # Define communication flows between agents
        agency_chart = [
            # OrchestratorAgent as CEO can communicate with all other agents
            orchestrator_agent,
            
            # CEO to all agents for coordination and policy enforcement
            [orchestrator_agent, scraper_agent],
            [orchestrator_agent, transcriber_agent],
            [orchestrator_agent, summarizer_agent],
            [orchestrator_agent, observability_agent],
            
            # Primary workflow: Scraper -> Transcriber -> Summarizer
            [scraper_agent, transcriber_agent],
            [transcriber_agent, summarizer_agent],
            
            # Observability can communicate with all agents for monitoring/notifications
            [observability_agent, scraper_agent],
            [observability_agent, transcriber_agent], 
            [observability_agent, summarizer_agent],
            
            # Bidirectional communication for error handling and status updates
            [scraper_agent, observability_agent],
            [transcriber_agent, observability_agent],
            [summarizer_agent, observability_agent],
        ]
        
        super().__init__(
            agency_chart=agency_chart,
            shared_instructions="./agency_manifesto.md",
            max_prompt_tokens=25000,
            max_completion_tokens=25000,
        )


# Initialize the agency
autopiloot_agency = AutopilootAgency()

if __name__ == "__main__":
    # For testing and development
    autopiloot_agency.demo_gradio(height=900)