"""
Autopiloot Agency - Multi-agent system for YouTube content processing.

This package contains 8 specialized agents working together to discover,
transcribe, summarize, and analyze YouTube content at scale.

Agents:
    - OrchestratorAgent: CEO pattern coordinating all other agents
    - ScraperAgent: Content discovery and metadata management
    - TranscriberAgent: AssemblyAI integration and transcript processing
    - SummarizerAgent: LLM-powered summarization and storage
    - DriveAgent: Google Drive document management and Zep GraphRAG integration
    - LinkedinAgent: LinkedIn data ingestion and social content analysis
    - StrategyAgent: Content strategy analysis with NLP clustering
    - ObservabilityAgent: Monitoring, alerting, and operational oversight

Architecture:
    - Event-driven broker pattern with Firestore as data store and event broker
    - Firebase Functions v2 for scheduling and automation
    - Comprehensive monitoring with strict cost controls
    - 86 production tools across all agents

For more information, see docs/AGENTS_OVERVIEW.md
"""

__version__ = "1.0.0"
__author__ = "Autopiloot Team"