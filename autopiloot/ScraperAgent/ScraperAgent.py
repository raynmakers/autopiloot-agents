"""
ScraperAgent for YouTube content discovery and processing.
"""

from agency_swarm import Agent


class ScraperAgent(Agent):
    """
    YouTube content discovery agent responsible for finding and processing videos
    from target channels. Handles both automated daily scraping and manual backfill
    requests from Google Sheets.
    """
    
    def __init__(self):
        super().__init__(
            name="ScraperAgent",
            description="Discovers and processes YouTube videos from target channels with data quality validation",
            instructions="./instructions.md",
            tools_folder="./tools",
            temperature=0.1,  # Low temperature for consistent, factual operations
            max_prompt_tokens=4000,
            model="gpt-4o-mini"  # Cost-effective model for structured tasks
        )