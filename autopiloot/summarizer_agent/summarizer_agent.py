"""
Summarizer Agent for Autopiloot Agency
Generates concise summaries from video transcripts with consistent quality controls
"""

from agency_swarm import Agent, ModelSettings

summarizer_agent = Agent(
    name="SummarizerAgent", 
    description="Generates concise summaries from transcribed videos. Creates brief business-focused summaries and stores them in multiple formats for retrieval.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.3,  # Balanced creativity for quality summaries
        max_completion_tokens=25000,
    ),
)