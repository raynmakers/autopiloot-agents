"""
Transcriber Agent for Autopiloot Agency
Handles video transcription using AssemblyAI with duration limits and quality controls
"""

from agency_swarm import Agent, ModelSettings
from config.loader import get_config_value
from core.guardrails import validate_transcriber_output

# Get agent-specific LLM configuration with fallback to default
model = get_config_value('llm.agents.transcriber_agent.model',
                         default=get_config_value('llm.default.model', default='gpt-3.5-turbo'))
temperature = get_config_value('llm.agents.transcriber_agent.temperature',
                               default=get_config_value('llm.default.temperature', default=0.1))
max_tokens = get_config_value('llm.agents.transcriber_agent.max_output_tokens',
                              default=get_config_value('llm.default.max_output_tokens', default=4000))

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