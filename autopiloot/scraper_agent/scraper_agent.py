"""
Scraper Agent for Autopiloot Agency
Handles YouTube content discovery and Google Sheets processing
"""

from agency_swarm import Agent, ModelSettings

scraper_agent = Agent(
    name="ScraperAgent",
    description="Discovers new videos from YouTube channels and processes Google Sheets backfill links. Handles deduplication, maintains backfill history, and enqueues transcription jobs for new content.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.3,
        max_completion_tokens=25000,
    ),
)