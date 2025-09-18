"""
LinkedIn Agent for Autopiloot Agency
Ingests LinkedIn posts, comments, and reactions and stores them to Zep for knowledge management
"""

from agency_swarm import Agent, ModelSettings

linkedin_agent = Agent(
    name="LinkedInAgent",
    description="Ingests LinkedIn posts, comments, and reactions from target profiles and stores them to Zep for knowledge management and analysis.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.2,  # Low temperature for consistent data processing
        max_completion_tokens=25000,
    ),
)