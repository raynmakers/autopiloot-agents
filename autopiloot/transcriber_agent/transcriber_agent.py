"""
Transcriber Agent for Autopiloot Agency
Handles video transcription using AssemblyAI with duration limits and quality controls
"""

from agency_swarm import Agent, ModelSettings
from config.loader import load_app_config
from core.guardrails import validate_transcriber_output

# Load configuration
config = load_app_config()

# Get agent-specific LLM configuration
agent_config = config.get('llm', {}).get('agents', {}).get('transcriber_agent', {})
default_config = config.get('llm', {}).get('default', {})

# Use agent-specific config with fallback to default
model = agent_config.get('model', default_config.get('model', 'gpt-3.5-turbo'))
temperature = agent_config.get('temperature', default_config.get('temperature', 0.1))
max_tokens = agent_config.get('max_output_tokens', default_config.get('max_output_tokens', 4000))

transcriber_agent = Agent(
    name="TranscriberAgent",
    description="Transcribes videos discovered by Scraper using AssemblyAI. Enforces max video length of 70 minutes. Stores full transcript to Google Drive and Firestore.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    ),
    output_guardrails=validate_transcriber_output,  # Agency Swarm v1.2.0 - validates transcript_id and video_id
)