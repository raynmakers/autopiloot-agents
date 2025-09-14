"""
Autopiloot Agency - Multi-agent system for YouTube content processing.
"""

from agency_swarm import Agency
import os
import sys

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ScraperAgent.ScraperAgent import ScraperAgent


class AutopilootAgency:
    """
    Main agency coordinating all agents in the YouTube content processing pipeline.
    """
    
    def __init__(self):
        """Initialize the agency with all agents and communication flows."""
        
        # Initialize agents
        self.scraper = ScraperAgent()
        
        # For now, just create a simple agency with the ScraperAgent
        # We'll expand this as we add more agents
        self.agency = Agency(
            [
                self.scraper,  # CEO agent (can communicate with all others)
            ],
            shared_instructions="""
            You are part of the Autopiloot system for automated YouTube content processing.
            
            Core Mission: Transform expert YouTube content into actionable insights for entrepreneurs.
            
            Quality Standards:
            - Maintain data integrity throughout the pipeline
            - Enforce business rules consistently  
            - Handle errors gracefully with proper logging
            - Respect API rate limits and quotas
            
            Communication Protocol:
            - Always include relevant context in inter-agent messages
            - Use structured data formats for consistency
            - Report progress and completion status clearly
            - Escalate blocking issues promptly
            """,
            temperature=0.1,
            max_prompt_tokens=4000
        )
    
    def start_daily_scrape(self, channel_handle: str = "@AlexHormozi"):
        """
        Initiate the daily scraping workflow.
        
        Args:
            channel_handle: YouTube channel to scrape
            
        Returns:
            str: Result of the scraping operation
        """
        message = f"""
        Start the daily YouTube scraping workflow:
        
        1. Resolve the channel handle '{channel_handle}' to get the channel ID
        2. List videos uploaded in the last 24 hours
        3. Save metadata for each new video (max 10 videos per day)
        4. Report summary: videos found, processed, skipped, and any errors
        
        Focus on data quality and business rule compliance.
        """
        
        return self.agency.get_completion(message, recipient_agent=self.scraper)
    
    def process_backfill_request(self, sheet_id: str, description: str = ""):
        """
        Process backfill videos from Google Sheet.
        
        Args:
            sheet_id: Google Sheet ID containing video links
            description: Optional description of the backfill batch
            
        Returns:
            str: Result of the backfill operation
        """
        message = f"""
        Process backfill request from Google Sheet:
        
        Sheet ID: {sheet_id}
        Description: {description}
        
        1. Read pending links from the sheet
        2. Extract YouTube video URLs from each page
        3. Save metadata for valid videos (source='sheet')
        4. Remove processed rows from the sheet
        5. Report summary of the operation
        
        Follow all business rules including duration limits.
        """
        
        return self.agency.get_completion(message, recipient_agent=self.scraper)


def main():
    """Test the agency instantiation."""
    print("🚀 Initializing Autopiloot Agency...")
    
    try:
        agency = AutopilootAgency()
        print("✅ Agency created successfully!")
        print(f"   Agents: {len(agency.agency.agents)}")
        print("   - ScraperAgent: Ready for YouTube discovery")
        
        # Test a simple interaction
        print("\n🧪 Testing agent communication...")
        response = agency.agency.get_completion(
            "Hello! Please introduce yourself and describe your capabilities.",
            recipient_agent=agency.scraper
        )
        print(f"✅ Agent Response: {response[:200]}...")
        
    except Exception as e:
        print(f"❌ Failed to initialize agency: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()