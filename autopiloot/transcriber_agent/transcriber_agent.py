"""
Transcriber Agent for Autopiloot Agency
Handles video transcription using AssemblyAI with duration limits and quality controls
"""

from agency_swarm import Agent, ModelSettings

transcriber_agent = Agent(
    name="TranscriberAgent", 
    description="Transcribes videos discovered by Scraper using AssemblyAI. Enforces max video length of 70 minutes. Stores full transcript to Google Drive and Firestore.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model="gpt-4o",
        temperature=0.1,  # Low temperature for precise transcription handling
        max_completion_tokens=25000,
    ),
)