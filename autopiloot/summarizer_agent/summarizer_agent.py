"""
Summarizer Agent for Autopiloot Agency
Generates concise summaries from video transcripts with consistent quality controls
"""

from agency_swarm import Agent, ModelSettings
from config.loader import get_config_value
from core.guardrails import validate_summarizer_output

# Get agent-specific LLM configuration with fallback to default
model = get_config_value('llm.agents.summarizer_agent.model',
                         default=get_config_value('llm.default.model', default='gpt-4.1'))
temperature = get_config_value('llm.agents.summarizer_agent.temperature',
                               default=get_config_value('llm.default.temperature', default=0.3))
max_tokens = get_config_value('llm.agents.summarizer_agent.max_output_tokens',
                              default=get_config_value('llm.default.max_output_tokens', default=25000))

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
    output_guardrails=[validate_summarizer_output],  # Agency Swarm v1.2.0 - validates summary length and rejection reasons
)