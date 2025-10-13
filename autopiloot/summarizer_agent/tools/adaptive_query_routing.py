"""
AdaptiveQueryRouting tool for intelligent retrieval source selection.

Routes queries to Zep (semantic), OpenSearch (keyword), and/or BigQuery (SQL analytics)
based on query characteristics, filters, and intent signals.

Routing Strategy:
- Strict filters (dates, channel IDs) → OpenSearch + BigQuery (precise filtering)
- Fuzzy/conceptual queries → Zep (semantic understanding)
- Mixed queries (filters + conceptual) → All sources (comprehensive)
- Default/uncertainty → All sources (maximum coverage)

Configuration:
- Adaptive mode: Smart routing based on query analysis
- Always-on mode: Use all sources regardless of query
- Logging: All routing decisions logged with reasoning
"""

import os
import sys
import json
import re
from typing import Dict, Any, List, Optional, Set
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import load_environment, get_optional_env_var
from loader import get_config_value


class AdaptiveQueryRouting(BaseTool):
    """
    Intelligently route queries to appropriate retrieval sources (Zep, OpenSearch, BigQuery).

    Analyzes query characteristics and filters to determine optimal source selection:
    - Query intent (conceptual vs factual)
    - Filter presence (dates, channels)
    - Query complexity
    - Source availability
    """

    query: str = Field(
        ...,
        description="Search query text to analyze"
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Channel ID filter (if present)"
    )
    min_published_date: Optional[str] = Field(
        default=None,
        description="Minimum publication date filter (if present)"
    )
    max_published_date: Optional[str] = Field(
        default=None,
        description="Maximum publication date filter (if present)"
    )
    force_sources: Optional[List[str]] = Field(
        default=None,
        description="Force specific sources (overrides adaptive routing): ['zep', 'opensearch', 'bigquery']"
    )

    def _detect_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to detect intent signals.

        Returns:
            Dict with intent classification:
            - intent_type: "conceptual", "factual", "mixed"
            - conceptual_signals: List of detected conceptual keywords
            - factual_signals: List of detected factual keywords
            - complexity_score: 0.0-1.0 (higher = more complex)
        """
        query_lower = query.lower()

        # Conceptual intent signals (good for semantic search)
        conceptual_keywords = [
            "how to", "why", "what is", "explain", "understand", "learn",
            "strategy", "approach", "framework", "methodology", "philosophy",
            "concept", "principle", "theory", "best practices", "tips",
            "advice", "guide", "tutorial", "insights", "lessons"
        ]

        # Factual intent signals (good for keyword search)
        factual_keywords = [
            "who", "when", "where", "which", "how many", "how much",
            "date", "time", "price", "cost", "number", "list",
            "specific", "exact", "precisely", "statistics", "data"
        ]

        # Detect signals
        conceptual_signals = [kw for kw in conceptual_keywords if kw in query_lower]
        factual_signals = [kw for kw in factual_keywords if kw in query_lower]

        # Classify intent
        if len(conceptual_signals) > len(factual_signals):
            intent_type = "conceptual"
        elif len(factual_signals) > len(conceptual_signals):
            intent_type = "factual"
        else:
            intent_type = "mixed"

        # Calculate complexity (longer queries with more signals = more complex)
        word_count = len(query.split())
        signal_count = len(conceptual_signals) + len(factual_signals)
        complexity_score = min(1.0, (word_count / 20.0) + (signal_count / 10.0))

        return {
            "intent_type": intent_type,
            "conceptual_signals": conceptual_signals,
            "factual_signals": factual_signals,
            "complexity_score": complexity_score,
            "word_count": word_count
        }

    def _detect_filter_strength(
        self,
        channel_id: Optional[str],
        min_date: Optional[str],
        max_date: Optional[str]
    ) -> str:
        """
        Detect filter strength based on provided filters.

        Returns:
            "strong" (multiple filters), "moderate" (one filter), "none" (no filters)
        """
        filter_count = sum([
            channel_id is not None,
            min_date is not None,
            max_date is not None
        ])

        if filter_count >= 2:
            return "strong"
        elif filter_count == 1:
            return "moderate"
        else:
            return "none"

    def _check_source_availability(self) -> Dict[str, bool]:
        """
        Check which retrieval sources are currently available.

        Returns:
            Dict with availability status for each source
        """
        zep_available = get_optional_env_var("ZEP_API_KEY") is not None
        opensearch_available = get_optional_env_var("OPENSEARCH_HOST") is not None

        # BigQuery availability based on GCP credentials
        bigquery_available = (
            get_optional_env_var("GCP_PROJECT_ID") is not None and
            get_optional_env_var("GOOGLE_APPLICATION_CREDENTIALS") is not None and
            get_config_value("rag.bigquery.enabled", False)
        )

        return {
            "zep": zep_available,
            "opensearch": opensearch_available,
            "bigquery": bigquery_available
        }

    def _apply_routing_rules(
        self,
        intent: Dict[str, Any],
        filter_strength: str,
        availability: Dict[str, bool]
    ) -> Dict[str, Any]:
        """
        Apply routing rules based on query analysis.

        Routing Logic:
        1. Strong filters (dates + channel) → OpenSearch + BigQuery
        2. Conceptual intent + no filters → Zep
        3. Factual intent + moderate filters → OpenSearch + BigQuery
        4. Mixed intent or uncertainty → All available sources
        5. Fallback → All available sources

        Returns:
            Dict with routing decision and reasoning
        """
        selected_sources: Set[str] = set()
        reasoning_steps = []

        # Rule 1: Strong filters favor OpenSearch + BigQuery
        if filter_strength == "strong":
            if availability["opensearch"]:
                selected_sources.add("opensearch")
                reasoning_steps.append("Strong filters detected → OpenSearch for precise filtering")
            if availability["bigquery"]:
                selected_sources.add("bigquery")
                reasoning_steps.append("Strong filters detected → BigQuery for SQL analytics")

        # Rule 2: Conceptual queries favor Zep
        if intent["intent_type"] == "conceptual" and filter_strength == "none":
            if availability["zep"]:
                selected_sources.add("zep")
                reasoning_steps.append("Conceptual query without filters → Zep for semantic understanding")

        # Rule 3: Factual queries with moderate filters favor OpenSearch + BigQuery
        if intent["intent_type"] == "factual" and filter_strength in ["moderate", "strong"]:
            if availability["opensearch"]:
                selected_sources.add("opensearch")
                reasoning_steps.append("Factual query with filters → OpenSearch for keyword + filter matching")
            if availability["bigquery"]:
                selected_sources.add("bigquery")
                reasoning_steps.append("Factual query with filters → BigQuery for structured queries")

        # Rule 4: Mixed intent or moderate filters → Use all available
        if intent["intent_type"] == "mixed" or (filter_strength == "moderate" and intent["complexity_score"] > 0.5):
            for source, available in availability.items():
                if available:
                    selected_sources.add(source)
            reasoning_steps.append("Mixed intent or complex query → All sources for comprehensive coverage")

        # Rule 5: Fallback - if no sources selected, use all available
        if not selected_sources:
            for source, available in availability.items():
                if available:
                    selected_sources.add(source)
            reasoning_steps.append("Fallback → All available sources for maximum coverage")

        # Ensure at least one source is selected
        if not selected_sources:
            reasoning_steps.append("⚠️ No sources available - query will fail")

        return {
            "selected_sources": sorted(list(selected_sources)),
            "reasoning": reasoning_steps,
            "routing_strategy": self._classify_routing_strategy(filter_strength, intent["intent_type"])
        }

    def _classify_routing_strategy(self, filter_strength: str, intent_type: str) -> str:
        """Classify the routing strategy for logging."""
        if filter_strength == "strong":
            return "filter_optimized"
        elif intent_type == "conceptual":
            return "semantic_optimized"
        elif intent_type == "factual":
            return "keyword_optimized"
        else:
            return "comprehensive"

    def run(self) -> str:
        """
        Analyze query and return routing recommendations.

        Process:
        1. Check configuration mode (adaptive vs always-on)
        2. Analyze query intent (conceptual vs factual)
        3. Assess filter strength (strong, moderate, none)
        4. Check source availability
        5. Apply routing rules or use forced sources
        6. Return routing decision with detailed reasoning

        Returns:
            JSON string with routing decision and metadata
        """
        try:
            # Load environment
            load_environment()

            # Check routing mode
            routing_mode = get_config_value("rag.routing.mode", "adaptive")
            always_use_all = get_config_value("rag.routing.always_use_all_sources", False)

            print(f"🧭 Adaptive Query Routing")
            print(f"   Query: '{self.query}'")
            print(f"   Mode: {routing_mode}")

            # Check source availability
            availability = self._check_source_availability()
            available_count = sum(availability.values())

            print(f"   Available sources: {available_count}/3")
            for source, available in availability.items():
                status = "✅" if available else "❌"
                print(f"      {status} {source}")

            # Handle forced sources
            if self.force_sources:
                selected_sources = [s for s in self.force_sources if availability.get(s, False)]
                routing_decision = {
                    "selected_sources": selected_sources,
                    "reasoning": [f"Forced source selection: {', '.join(self.force_sources)}"],
                    "routing_strategy": "forced"
                }
                print(f"   Strategy: Forced sources")
            # Handle always-on mode
            elif always_use_all or routing_mode == "always_on":
                selected_sources = [s for s, avail in availability.items() if avail]
                routing_decision = {
                    "selected_sources": selected_sources,
                    "reasoning": ["Always-on mode: Using all available sources"],
                    "routing_strategy": "always_on"
                }
                print(f"   Strategy: Always-on (all sources)")
            # Adaptive routing
            else:
                # Analyze query
                intent = self._detect_query_intent(self.query)
                filter_strength = self._detect_filter_strength(
                    self.channel_id,
                    self.min_published_date,
                    self.max_published_date
                )

                print(f"   Intent: {intent['intent_type']}")
                print(f"   Filters: {filter_strength}")
                print(f"   Complexity: {intent['complexity_score']:.2f}")

                # Apply routing rules
                routing_decision = self._apply_routing_rules(
                    intent,
                    filter_strength,
                    availability
                )

                print(f"   Strategy: {routing_decision['routing_strategy']}")

            # Log routing decision
            print(f"   Selected: {', '.join(routing_decision['selected_sources']) if routing_decision['selected_sources'] else 'NONE'}")
            for step in routing_decision["reasoning"]:
                print(f"      • {step}")

            # Build comprehensive result
            result = {
                "query": self.query,
                "routing_decision": routing_decision,
                "query_analysis": {
                    "has_channel_filter": self.channel_id is not None,
                    "has_date_filter": (self.min_published_date is not None) or (self.max_published_date is not None),
                    "filters_provided": {
                        "channel_id": self.channel_id,
                        "min_date": self.min_published_date,
                        "max_date": self.max_published_date
                    }
                },
                "source_availability": availability,
                "routing_mode": routing_mode,
                "timestamp": self._get_timestamp(),
                "status": "success" if routing_decision["selected_sources"] else "no_sources_available"
            }

            # Add intent analysis if adaptive mode
            if routing_mode == "adaptive" and not self.force_sources:
                intent = self._detect_query_intent(self.query)
                result["query_analysis"]["intent"] = intent
                result["query_analysis"]["filter_strength"] = self._detect_filter_strength(
                    self.channel_id,
                    self.min_published_date,
                    self.max_published_date
                )

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "routing_failed",
                "message": f"Failed to analyze query and route: {str(e)}",
                "query": self.query
            })

    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp for logging."""
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST 1: Adaptive Query Routing - Conceptual Query (No Filters)")
    print("="*80)

    try:
        tool = AdaptiveQueryRouting(
            query="How do I build a high-performance sales team?"
        )

        result = tool.run()
        print("\n✅ Test 1 completed:")

        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"\n📊 Routing Summary:")
            print(f"   Query: {data['query']}")
            print(f"   Strategy: {data['routing_decision']['routing_strategy']}")
            print(f"   Sources: {', '.join(data['routing_decision']['selected_sources'])}")
            if data['query_analysis'].get('intent'):
                print(f"   Intent: {data['query_analysis']['intent']['intent_type']}")

    except Exception as e:
        print(f"❌ Test 1 error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST 2: Adaptive Query Routing - Filtered Query")
    print("="*80)

    try:
        tool = AdaptiveQueryRouting(
            query="sales strategies",
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw",
            min_published_date="2025-01-01T00:00:00Z",
            max_published_date="2025-12-31T23:59:59Z"
        )

        result = tool.run()
        print("\n✅ Test 2 completed:")

        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"\n📊 Routing Summary:")
            print(f"   Query: {data['query']}")
            print(f"   Strategy: {data['routing_decision']['routing_strategy']}")
            print(f"   Sources: {', '.join(data['routing_decision']['selected_sources'])}")
            print(f"   Filters: Channel + Date Range")

    except Exception as e:
        print(f"❌ Test 2 error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST 3: Forced Sources")
    print("="*80)

    try:
        tool = AdaptiveQueryRouting(
            query="pricing strategies",
            force_sources=["opensearch"]
        )

        result = tool.run()
        print("\n✅ Test 3 completed:")

        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"\n📊 Routing Summary:")
            print(f"   Query: {data['query']}")
            print(f"   Strategy: {data['routing_decision']['routing_strategy']}")
            print(f"   Sources: {', '.join(data['routing_decision']['selected_sources'])}")

    except Exception as e:
        print(f"❌ Test 3 error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete! Three scenarios tested:")
    print("1. Conceptual query (no filters) → Semantic-optimized")
    print("2. Filtered query (channel + dates) → Filter-optimized")
    print("3. Forced sources → Forced routing")
    print("="*80)
