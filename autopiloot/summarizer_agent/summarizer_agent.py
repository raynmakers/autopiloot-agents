"""
Summarizer Agent for Autopiloot Agency
Generates concise summaries from video transcripts with consistent quality controls
"""

from agency_swarm import Agent, ModelSettings
from config.loader import load_app_config

# Load configuration
config = load_app_config()

# Get agent-specific LLM configuration
agent_config = config.get('llm', {}).get('agents', {}).get('summarizer_agent', {})
default_config = config.get('llm', {}).get('default', {})

# Use agent-specific config with fallback to default
model = agent_config.get('model', default_config.get('model', 'gpt-4.1'))
temperature = agent_config.get('temperature', default_config.get('temperature', 0.3))
max_tokens = agent_config.get('max_output_tokens', default_config.get('max_output_tokens', 25000))

summarizer_agent = Agent(
    name="SummarizerAgent", 
    description="Generates concise summaries from transcribed videos. Creates brief business-focused summaries and stores them in multiple formats for retrieval.",
    instructions="./instructions.md",
    tools_folder="./tools",
    model_settings=ModelSettings(
        model=model,
        temperature=temperature,
        max_completion_tokens=max_tokens,
    ),
)