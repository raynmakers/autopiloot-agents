"""
AnswerWithHybridContext tool for generating LLM answers using hybrid retrieval context.

Architecture:
- Calls HybridRetrieval to get fused results from Zep (semantic) + OpenSearch (keyword)
- Balances context contributions per source (prevents single-source bias)
- Handles evidence alignment and conflict resolution using trust hierarchy
- Invokes LLM with structured outputs for reliable citation extraction
- Returns comprehensive answer with citations and quality metrics

Trust Hierarchy for Conflict Resolution:
1. Multi-source evidence (chunks appearing in both Zep and OpenSearch)
2. Semantic search results (Zep) - better for conceptual understanding
3. Keyword search results (OpenSearch) - better for specific facts/dates
4. Optional BigQuery verification for structured data conflicts
"""

import os
import sys
import json
import yaml
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pydantic import Field
from openai import OpenAI
from agency_swarm.tools import BaseTool

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from env_loader import load_environment
from loader import get_config_value


class AnswerWithHybridContext(BaseTool):
    """
    Generate LLM-powered answers using hybrid retrieval context (Zep + OpenSearch).

    Process Flow:
    1. Call HybridRetrieval to get fused results
    2. Balance context contributions per source
    3. Detect evidence overlaps and conflicts
    4. Build prompt with balanced, aligned context
    5. Invoke LLM with structured outputs
    6. Return answer with citations and quality metrics
    """

    query: str = Field(
        ...,
        description="User question to answer using hybrid retrieval context"
    )
    top_k: int = Field(
        default=10,
        description="Number of context chunks to retrieve (default: 10)"
    )
    max_tokens_per_source: int = Field(
        default=4000,
        description="Maximum tokens per source (Zep/OpenSearch) to prevent bias (default: 4000)"
    )
    channel_id: Optional[str] = Field(
        default=None,
        description="Filter results by YouTube channel ID"
    )
    min_published_date: Optional[str] = Field(
        default=None,
        description="Filter results by minimum publication date (ISO 8601)"
    )
    max_published_date: Optional[str] = Field(
        default=None,
        description="Filter results by maximum publication date (ISO 8601)"
    )

    def _load_settings(self) -> Dict[str, Any]:
        """Load configuration from settings.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (conservative approximation).
        Uses ~4 characters per token average for English.
        """
        return len(text) // 4

    def _balance_context_per_source(
        self,
        results: List[Dict],
        max_tokens_per_source: int
    ) -> Tuple[List[Dict], Dict[str, int]]:
        """
        Balance context contributions to prevent single-source bias.

        Args:
            results: Fused results from hybrid retrieval
            max_tokens_per_source: Maximum tokens allowed per source

        Returns:
            Tuple of (balanced_results, source_token_counts)
        """
        # Track tokens per source
        source_tokens = {"zep": 0, "opensearch": 0, "both": 0}
        balanced_results = []

        # Sort by RRF score (highest first)
        sorted_results = sorted(results, key=lambda x: x.get("rrf_score", 0), reverse=True)

        for result in sorted_results:
            text = result.get("text", "")
            tokens = self._estimate_tokens(text)
            matched_sources = result.get("matched_sources", [])

            # Determine primary source
            if len(matched_sources) > 1:
                source_key = "both"
            elif "zep" in matched_sources:
                source_key = "zep"
            elif "opensearch" in matched_sources:
                source_key = "opensearch"
            else:
                continue

            # Check if adding this chunk would exceed per-source limit
            if source_key == "both":
                # Multi-source evidence gets priority and counts towards both
                source_tokens["both"] += tokens
                balanced_results.append(result)
            elif source_tokens[source_key] + tokens <= max_tokens_per_source:
                source_tokens[source_key] += tokens
                balanced_results.append(result)
            else:
                # Skip this chunk to maintain balance
                continue

        return balanced_results, source_tokens

    def _detect_evidence_overlaps(self, results: List[Dict]) -> Dict[str, Any]:
        """
        Detect chunks that appear in both Zep and OpenSearch (high confidence).

        Args:
            results: Balanced results

        Returns:
            Dict with overlap statistics and high-confidence chunks
        """
        multi_source_chunks = []
        zep_only_chunks = []
        opensearch_only_chunks = []

        for result in results:
            matched_sources = result.get("matched_sources", [])
            source_count = result.get("source_count", 1)

            if source_count > 1:
                multi_source_chunks.append(result["chunk_id"])
            elif "zep" in matched_sources:
                zep_only_chunks.append(result["chunk_id"])
            elif "opensearch" in matched_sources:
                opensearch_only_chunks.append(result["chunk_id"])

        return {
            "multi_source_count": len(multi_source_chunks),
            "zep_only_count": len(zep_only_chunks),
            "opensearch_only_count": len(opensearch_only_chunks),
            "high_confidence_chunks": multi_source_chunks,
            "confidence_ratio": len(multi_source_chunks) / len(results) if results else 0.0
        }

    def _resolve_conflicts_with_trust_hierarchy(self, results: List[Dict]) -> str:
        """
        Apply trust hierarchy for conflict resolution.

        Trust Hierarchy:
        1. Multi-source evidence (both Zep and OpenSearch)
        2. Semantic search (Zep) - better for conceptual understanding
        3. Keyword search (OpenSearch) - better for specific facts

        Returns:
            Guidance text for LLM on evidence reliability
        """
        multi_source_count = sum(1 for r in results if r.get("source_count", 1) > 1)
        total_count = len(results)

        if total_count == 0:
            return "No evidence available."

        confidence_ratio = multi_source_count / total_count

        if confidence_ratio >= 0.5:
            return f"HIGH CONFIDENCE: {multi_source_count}/{total_count} chunks confirmed by both semantic and keyword search. Prioritize multi-source evidence."
        elif confidence_ratio >= 0.25:
            return f"MODERATE CONFIDENCE: {multi_source_count}/{total_count} chunks have multi-source confirmation. Use caution with single-source claims."
        else:
            return f"LOW CONFIDENCE: Only {multi_source_count}/{total_count} chunks have multi-source confirmation. Clearly indicate evidence strength in answer."

    def _build_context_prompt(
        self,
        query: str,
        results: List[Dict],
        overlap_info: Dict[str, Any],
        trust_guidance: str
    ) -> str:
        """
        Build comprehensive prompt with balanced context and evidence guidance.

        Args:
            query: User question
            results: Balanced context chunks
            overlap_info: Evidence overlap statistics
            trust_guidance: Conflict resolution guidance

        Returns:
            Formatted prompt string
        """
        # Build context sections
        context_lines = []
        for i, result in enumerate(results, 1):
            video_title = result.get("title", "Unknown")
            video_id = result.get("video_id", "unknown")
            chunk_id = result.get("chunk_id", "unknown")
            text = result.get("text", "")
            rrf_score = result.get("rrf_score", 0.0)
            matched_sources = result.get("matched_sources", [])
            source_count = result.get("source_count", 1)

            # Indicate confidence level
            confidence_marker = "🔵🔴" if source_count > 1 else ("🔵" if "zep" in matched_sources else "🔴")

            context_lines.append(
                f"[{i}] {confidence_marker} Video: {video_title} (ID: {video_id})\n"
                f"    Chunk: {chunk_id} | RRF Score: {rrf_score:.4f} | Sources: {', '.join(matched_sources)}\n"
                f"    Text: {text}\n"
            )

        context_section = "\n".join(context_lines)

        # Build prompt
        prompt = f"""You are an expert research assistant answering questions using retrieved context from video transcripts.

QUESTION:
{query}

EVIDENCE QUALITY ASSESSMENT:
{trust_guidance}

Legend:
- 🔵🔴 = Multi-source evidence (both semantic and keyword search) - HIGHEST CONFIDENCE
- 🔵 = Semantic search only (Zep) - Good for concepts and understanding
- 🔴 = Keyword search only (OpenSearch) - Good for specific facts

CONTEXT ({len(results)} chunks):
{context_section}

INSTRUCTIONS:
1. Answer the question comprehensively using the provided context
2. ALWAYS cite your sources using [chunk_number] notation (e.g., [1], [2])
3. Prioritize multi-source evidence (🔵🔴) when available
4. If conflicting information exists, explain the discrepancy and your reasoning
5. Clearly state if the context doesn't fully answer the question
6. Include video titles in citations for user reference
7. Provide actionable insights when applicable

Your answer should be well-structured, evidence-based, and helpful."""

        return prompt

    def run(self) -> str:
        """
        Generate answer using hybrid retrieval context with LLM structured outputs.

        Process:
        1. Call HybridRetrieval to get fused results
        2. Balance context per source (prevent bias)
        3. Detect evidence overlaps and conflicts
        4. Build prompt with balanced context
        5. Invoke LLM with structured outputs
        6. Return answer with citations and metrics

        Returns:
            JSON string with answer, citations, evidence quality, and metadata
        """
        try:
            # Load environment and settings
            load_environment()
            settings = self._load_settings()

            # Validate OpenAI API key
            openai_api_key = os.getenv("OPENAI_API_KEY")
            if not openai_api_key:
                return json.dumps({
                    "error": "configuration_error",
                    "message": "OPENAI_API_KEY environment variable is required"
                })

            # Get LLM configuration for RAG Q&A task
            task_config = settings.get('llm', {}).get('tasks', {}).get('rag_answer_question', {})
            model = task_config.get('model', 'gpt-4o')
            temperature = task_config.get('temperature', 0.2)
            max_output_tokens = task_config.get('max_output_tokens', 2000)
            prompt_id = task_config.get('prompt_id', 'rag_qa_v1')

            print(f"🔍 RAG Q&A: '{self.query}'")
            print(f"   Model: {model}")
            print(f"   Top-K: {self.top_k}")
            print(f"   Max tokens per source: {self.max_tokens_per_source}")

            # Step 1: Call HybridRetrieval
            print("   Step 1/5: Calling HybridRetrieval...")
            from .hybrid_retrieval import HybridRetrieval

            retrieval_tool = HybridRetrieval(
                query=self.query,
                top_k=self.top_k,
                channel_id=self.channel_id,
                min_published_date=self.min_published_date,
                max_published_date=self.max_published_date
            )

            retrieval_result = retrieval_tool.run()
            retrieval_data = json.loads(retrieval_result)

            if "error" in retrieval_data:
                return json.dumps({
                    "error": "retrieval_failed",
                    "message": f"Hybrid retrieval failed: {retrieval_data.get('message', 'Unknown error')}",
                    "query": self.query
                })

            results = retrieval_data.get("results", [])
            if not results:
                return json.dumps({
                    "error": "no_results",
                    "message": "No relevant context found for the query",
                    "query": self.query,
                    "retrieval_metadata": {
                        "sources_queried": retrieval_data.get("sources", {}),
                        "source_counts": retrieval_data.get("source_counts", {})
                    }
                })

            print(f"   ✓ Retrieved {len(results)} chunks")

            # Step 2: Balance context per source
            print("   Step 2/5: Balancing context per source...")
            balanced_results, source_token_counts = self._balance_context_per_source(
                results,
                self.max_tokens_per_source
            )
            print(f"   ✓ Balanced to {len(balanced_results)} chunks")
            print(f"      Zep tokens: {source_token_counts['zep']}")
            print(f"      OpenSearch tokens: {source_token_counts['opensearch']}")
            print(f"      Multi-source tokens: {source_token_counts['both']}")

            # Step 3: Detect evidence overlaps
            print("   Step 3/5: Analyzing evidence quality...")
            overlap_info = self._detect_evidence_overlaps(balanced_results)
            trust_guidance = self._resolve_conflicts_with_trust_hierarchy(balanced_results)
            print(f"   ✓ Multi-source chunks: {overlap_info['multi_source_count']}")
            print(f"   ✓ Confidence ratio: {overlap_info['confidence_ratio']:.2%}")

            # Step 4: Build prompt
            print("   Step 4/5: Building LLM prompt...")
            prompt = self._build_context_prompt(
                query=self.query,
                results=balanced_results,
                overlap_info=overlap_info,
                trust_guidance=trust_guidance
            )
            prompt_tokens = self._estimate_tokens(prompt)
            print(f"   ✓ Prompt built (~{prompt_tokens} tokens)")

            # Step 5: Invoke LLM with structured outputs
            print("   Step 5/5: Generating answer with LLM...")

            # Define JSON schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "answer": {
                        "type": "string",
                        "description": "Comprehensive answer to the question with inline citations [n]"
                    },
                    "citations": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "citation_number": {
                                    "type": "integer",
                                    "description": "Citation number used in answer (1, 2, 3...)"
                                },
                                "chunk_id": {
                                    "type": "string",
                                    "description": "Chunk identifier from context"
                                },
                                "video_id": {
                                    "type": "string",
                                    "description": "YouTube video ID"
                                },
                                "video_title": {
                                    "type": "string",
                                    "description": "Video title for user reference"
                                },
                                "source_type": {
                                    "type": "string",
                                    "enum": ["multi_source", "semantic", "keyword"],
                                    "description": "Evidence source type"
                                }
                            },
                            "required": ["citation_number", "chunk_id", "video_id", "video_title", "source_type"],
                            "additionalProperties": False
                        },
                        "description": "List of citations used in the answer"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "moderate", "low"],
                        "description": "Overall confidence in answer based on evidence quality"
                    },
                    "limitations": {
                        "type": "string",
                        "description": "Any limitations or gaps in the available evidence"
                    }
                },
                "required": ["answer", "citations", "confidence", "limitations"],
                "additionalProperties": False
            }

            # Initialize OpenAI client
            client = OpenAI(api_key=openai_api_key)

            # Generate answer with structured output
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert research assistant that answers questions using retrieved context. Always cite sources and assess evidence quality."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "rag_answer_with_citations",
                        "strict": True,
                        "schema": response_schema
                    }
                },
                max_completion_tokens=max_output_tokens
            )

            # Parse structured response
            answer_data = json.loads(response.choices[0].message.content)
            print(f"   ✓ Answer generated with {len(answer_data.get('citations', []))} citations")

            # Build comprehensive result
            result = {
                "query": self.query,
                "answer": answer_data.get("answer"),
                "citations": answer_data.get("citations", []),
                "evidence_quality": {
                    "confidence": answer_data.get("confidence"),
                    "limitations": answer_data.get("limitations"),
                    "multi_source_count": overlap_info["multi_source_count"],
                    "total_chunks_used": len(balanced_results),
                    "confidence_ratio": overlap_info["confidence_ratio"]
                },
                "retrieval_metadata": {
                    "sources_queried": retrieval_data.get("sources", {}),
                    "source_counts": retrieval_data.get("source_counts", {}),
                    "weights": retrieval_data.get("weights", {}),
                    "total_retrieved": len(results),
                    "total_used": len(balanced_results)
                },
                "context_balance": {
                    "zep_tokens": source_token_counts["zep"],
                    "opensearch_tokens": source_token_counts["opensearch"],
                    "multi_source_tokens": source_token_counts["both"],
                    "max_tokens_per_source": self.max_tokens_per_source
                },
                "llm_metadata": {
                    "model": model,
                    "prompt_id": prompt_id,
                    "temperature": temperature,
                    "token_usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                },
                "status": "success"
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "generation_failed",
                "message": f"Failed to generate answer: {str(e)}",
                "query": self.query
            })


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: AnswerWithHybridContext - Business Strategy Question")
    print("="*80)

    try:
        tool = AnswerWithHybridContext(
            query="How do I hire A-players for my SaaS business?",
            top_k=10,
            max_tokens_per_source=4000,
            channel_id="UCkP5J0pXI11VE81q7S7V1Jw"  # Dan Martell's channel
        )

        result = tool.run()
        print("\n✅ Test completed:")

        data = json.loads(result)

        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        else:
            print(f"\n📊 RAG Q&A Summary:")
            print(f"   Query: {data['query']}")
            print(f"   Confidence: {data['evidence_quality']['confidence'].upper()}")
            print(f"   Citations: {len(data['citations'])}")
            print(f"   Multi-source chunks: {data['evidence_quality']['multi_source_count']}")
            print(f"   Confidence ratio: {data['evidence_quality']['confidence_ratio']:.2%}")

            print(f"\n💡 Answer:")
            print(f"   {data['answer'][:300]}{'...' if len(data['answer']) > 300 else ''}")

            print(f"\n📚 Citations (first 3):")
            for citation in data['citations'][:3]:
                print(f"   [{citation['citation_number']}] {citation['video_title']}")
                print(f"       Video ID: {citation['video_id']} | Source: {citation['source_type']}")

            print(f"\n⚖️ Context Balance:")
            print(f"   Zep tokens: {data['context_balance']['zep_tokens']}")
            print(f"   OpenSearch tokens: {data['context_balance']['opensearch_tokens']}")
            print(f"   Multi-source tokens: {data['context_balance']['multi_source_tokens']}")

            print(f"\n📈 Token Usage:")
            print(f"   Input: {data['llm_metadata']['token_usage']['input_tokens']:,}")
            print(f"   Output: {data['llm_metadata']['token_usage']['output_tokens']:,}")
            print(f"   Total: {data['llm_metadata']['token_usage']['total_tokens']:,}")

            if data['evidence_quality'].get('limitations'):
                print(f"\n⚠️  Limitations:")
                print(f"   {data['evidence_quality']['limitations']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
