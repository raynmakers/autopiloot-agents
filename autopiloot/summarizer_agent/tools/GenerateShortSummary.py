"""
GenerateShortSummary tool for creating concise, actionable summaries from transcripts.
Implements TASK-SUM-0030 with proper configuration loading, Langfuse tracing, and adaptive chunking.
"""

import os
import sys
import json
import hashlib
import math
from typing import Dict, Any, List, Optional, TypedDict
from agency_swarm.tools import BaseTool
from pydantic import Field
from openai import OpenAI
from google.cloud import firestore
import tiktoken

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var
from loader import load_app_config


class TokenUsage(TypedDict):
    input_tokens: int
    output_tokens: int


class GenerateShortSummaryResponse(TypedDict):
    bullets: List[str]
    key_concepts: List[str]
    token_usage: TokenUsage
    prompt_id: str
    prompt_version: str


class GenerateShortSummary(BaseTool):
    """
    Generate concise, actionable bullet summaries from video transcripts for coaching contexts.
    
    Uses model and temperature from settings.yaml configuration with Langfuse tracing.
    Implements adaptive chunking to handle long transcripts efficiently.
    
    Returns structured output with bullets, key concepts, token usage, and prompt ID.
    """
    
    transcript_doc_ref: str = Field(
        ..., 
        description="Firestore document reference path for the transcript (e.g., 'transcripts/video_id')"
    )
    
    title: str = Field(
        ..., 
        description="Video title for context in summary generation"
    )
    
    def run(self) -> str:
        """
        Generate actionable summary with insights and key concepts from transcript.
        
        Returns:
            str: JSON string containing bullets, key_concepts, prompt_id, and token_usage
        
        Raises:
            RuntimeError: If summary generation fails
        """
        try:
            # Load configuration
            config = load_app_config()
            
            # Get LLM configuration from settings.yaml
            llm_config = self._get_llm_config(config)
            model = llm_config["model"]
            temperature = llm_config["temperature"]
            max_output_tokens = llm_config["max_output_tokens"]
            prompt_id = llm_config["prompt_id"]
            prompt_version = llm_config["prompt_version"]
            
            # Initialize clients
            openai_client = self._initialize_openai_client()
            firestore_client = self._initialize_firestore_client()
            
            # Load transcript content
            transcript_text = self._load_transcript(firestore_client, self.transcript_doc_ref)
            
            # Generate summary with adaptive chunking
            summary_response = self._generate_summary(
                openai_client, 
                transcript_text, 
                self.title, 
                model, 
                temperature,
                max_output_tokens,
                prompt_id,
                prompt_version
            )
            
            # Initialize Langfuse tracing if available
            self._trace_with_langfuse(summary_response, model, temperature, prompt_id, prompt_version)
            
            return json.dumps(summary_response, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to generate short summary: {str(e)}",
                "bullets": [],
                "key_concepts": [],
                "token_usage": {"input_tokens": 0, "output_tokens": 0},
                "prompt_id": "",
                "prompt_version": "v1"
            })
    
    def _get_llm_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract LLM configuration from settings.yaml with task-specific overrides.
        
        Args:
            config: Application configuration from settings.yaml
            
        Returns:
            Dictionary with model, temperature, max_output_tokens, prompt_id, and prompt_version
        """
        llm_section = config.get("llm", {})
        
        # Check for task-specific configuration first
        task_config = llm_section.get("tasks", {}).get("summarizer_generate_short", {})
        
        if task_config:
            return {
                "model": task_config.get("model", "gpt-4.1"),
                "temperature": task_config.get("temperature", 0.2),
                "max_output_tokens": task_config.get("max_output_tokens", 1500),
                "prompt_id": task_config.get("prompt_id", "coach_v1"),
                "prompt_version": task_config.get("prompt_version", "v1")
            }
        
        # Fall back to default configuration
        default_config = llm_section.get("default", {})
        prompt_id = llm_section.get("prompts", {}).get("summarizer_short_id", "coach_v1")
        
        return {
            "model": default_config.get("model", "gpt-4.1"),
            "temperature": default_config.get("temperature", 0.2),
            "max_output_tokens": default_config.get("max_output_tokens", 1500),
            "prompt_id": prompt_id,
            "prompt_version": "v1"
        }
    
    def _initialize_openai_client(self) -> OpenAI:
        """Initialize OpenAI client with API key from environment."""
        api_key = get_required_env_var("OPENAI_API_KEY", "OpenAI API key for LLM operations")
        return OpenAI(api_key=api_key)
    
    def _initialize_firestore_client(self) -> firestore.Client:
        """Initialize Firestore client for transcript retrieval."""
        # Firestore client will use GOOGLE_APPLICATION_CREDENTIALS automatically
        return firestore.Client()
    
    def _load_transcript(self, firestore_client: firestore.Client, transcript_doc_ref: str) -> str:
        """
        Load transcript content from Firestore and Google Drive.
        
        Args:
            firestore_client: Firestore client
            transcript_doc_ref: Document reference path
            
        Returns:
            Full transcript text content
            
        Raises:
            ValueError: If transcript document doesn't exist
        """
        # Get transcript metadata from Firestore
        transcript_ref = firestore_client.document(transcript_doc_ref)
        transcript_doc = transcript_ref.get()
        
        if not transcript_doc.exists:
            raise ValueError(f"Transcript document {transcript_doc_ref} does not exist")
        
        transcript_data = transcript_doc.to_dict()
        
        # For now, return the full text from Firestore
        # In production, this would fetch from Google Drive using drive_id_txt
        full_text = transcript_data.get('full_text', '')
        
        if not full_text:
            # Fallback: try to get from segments
            segments = transcript_data.get('segments', [])
            if segments:
                full_text = ' '.join([segment.get('text', '') for segment in segments])
        
        if not full_text:
            raise ValueError(f"No transcript text found in {transcript_doc_ref}")
        
        return full_text
    
    def _generate_summary(
        self, 
        openai_client: OpenAI, 
        transcript_text: str, 
        title: str, 
        model: str, 
        temperature: float,
        max_output_tokens: int,
        prompt_id: str,
        prompt_version: str
    ) -> GenerateShortSummaryResponse:
        """
        Generate summary using OpenAI with adaptive chunking for long transcripts.
        
        Args:
            openai_client: OpenAI client
            transcript_text: Full transcript content
            title: Video title
            model: LLM model name
            temperature: Model temperature
            max_output_tokens: Maximum output tokens
            prompt_id: Prompt identifier
            prompt_version: Prompt version (e.g., 'v1')
            
        Returns:
            Structured summary response
        """
        # Initialize tokenizer for the model
        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            # Fallback to a common encoding if model-specific one isn't available
            encoding = tiktoken.get_encoding("cl100k_base")
        
        # Calculate token count
        transcript_tokens = len(encoding.encode(transcript_text))
        
        # Model context limits (conservative estimates)
        model_limits = {
            "gpt-4.1": 128000,
            "gpt-4o": 128000,
            "gpt-4": 8000,
            "gpt-3.5-turbo": 16000
        }
        
        max_context = model_limits.get(model, 8000)
        # Reserve tokens for prompt and response
        max_transcript_tokens = max_context - 2000
        
        if transcript_tokens <= max_transcript_tokens:
            # Process full transcript
            return self._generate_summary_chunk(
                openai_client, transcript_text, title, model, temperature, max_output_tokens, prompt_id, prompt_version
            )
        else:
            # Use adaptive chunking
            return self._generate_summary_chunked(
                openai_client, transcript_text, title, model, temperature, max_output_tokens, prompt_id, prompt_version, encoding, max_transcript_tokens
            )
    
    def _generate_summary_chunk(
        self, 
        openai_client: OpenAI, 
        transcript_text: str, 
        title: str, 
        model: str, 
        temperature: float,
        max_output_tokens: int,
        prompt_id: str,
        prompt_version: str
    ) -> GenerateShortSummaryResponse:
        """
        Generate summary for a single chunk of transcript.
        
        Args:
            openai_client: OpenAI client
            transcript_text: Transcript content
            title: Video title
            model: LLM model name
            temperature: Model temperature
            prompt_id: Prompt identifier
            
        Returns:
            Structured summary response
        """
        # Create coaching-focused prompt
        prompt = self._create_summary_prompt(transcript_text, title)
        
        # Generate summary
        response = openai_client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert business coach analyzing content for actionable insights. Extract practical advice that entrepreneurs can immediately apply to grow their businesses."
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=max_output_tokens
        )
        
        summary_text = response.choices[0].message.content
        
        # Parse structured output
        bullets, key_concepts = self._parse_summary_response(summary_text)
        
        # Generate stable prompt ID hash including version
        prompt_hash = hashlib.md5(f"{prompt_id}_{prompt_version}_{model}_{temperature}".encode()).hexdigest()[:8]
        
        return {
            "bullets": bullets,
            "key_concepts": key_concepts,
            "token_usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens
            },
            "prompt_id": f"{prompt_id}_{prompt_hash}",
            "prompt_version": prompt_version
        }
    
    def _generate_summary_chunked(
        self, 
        openai_client: OpenAI, 
        transcript_text: str, 
        title: str, 
        model: str, 
        temperature: float,
        max_output_tokens: int,
        prompt_id: str,
        prompt_version: str,
        encoding, 
        max_tokens: int
    ) -> GenerateShortSummaryResponse:
        """
        Generate summary for long transcripts using adaptive chunking.
        
        Args:
            openai_client: OpenAI client
            transcript_text: Full transcript content
            title: Video title
            model: LLM model name
            temperature: Model temperature
            prompt_id: Prompt identifier
            encoding: Tokenizer encoding
            max_tokens: Maximum tokens per chunk
            
        Returns:
            Aggregated summary response
        """
        # Split transcript into chunks
        chunks = self._chunk_transcript(transcript_text, encoding, max_tokens)
        
        all_bullets = []
        all_concepts = []
        total_input_tokens = 0
        total_output_tokens = 0
        
        # Process each chunk
        for i, chunk in enumerate(chunks):
            chunk_response = self._generate_summary_chunk(
                openai_client, chunk, f"{title} (Part {i+1}/{len(chunks)})", model, temperature, max_output_tokens, prompt_id, prompt_version
            )
            
            all_bullets.extend(chunk_response["bullets"])
            all_concepts.extend(chunk_response["key_concepts"])
            total_input_tokens += chunk_response["token_usage"]["input_tokens"]
            total_output_tokens += chunk_response["token_usage"]["output_tokens"]
        
        # Deduplicate and consolidate
        unique_bullets = self._deduplicate_items(all_bullets)
        unique_concepts = self._deduplicate_items(all_concepts)
        
        # Limit to target output size (6-12 bullets, 3-6 concepts)
        final_bullets = unique_bullets[:12]
        final_concepts = unique_concepts[:6]
        
        # Generate stable prompt ID hash including version
        prompt_hash = hashlib.md5(f"{prompt_id}_{prompt_version}_{model}_{temperature}_chunked".encode()).hexdigest()[:8]
        
        return {
            "bullets": final_bullets,
            "key_concepts": final_concepts,
            "token_usage": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens
            },
            "prompt_id": f"{prompt_id}_{prompt_hash}",
            "prompt_version": prompt_version
        }
    
    def _chunk_transcript(self, transcript_text: str, encoding, max_tokens: int) -> List[str]:
        """
        Split transcript into chunks that fit within token limits.
        
        Args:
            transcript_text: Full transcript content
            encoding: Tokenizer encoding
            max_tokens: Maximum tokens per chunk
            
        Returns:
            List of transcript chunks
        """
        # Split by sentences for better coherence
        sentences = transcript_text.split('. ')
        
        chunks = []
        current_chunk = ""
        current_tokens = 0
        
        for sentence in sentences:
            sentence_tokens = len(encoding.encode(sentence + '. '))
            
            if current_tokens + sentence_tokens > max_tokens and current_chunk:
                # Start new chunk
                chunks.append(current_chunk.strip())
                current_chunk = sentence + '. '
                current_tokens = sentence_tokens
            else:
                # Add to current chunk
                current_chunk += sentence + '. '
                current_tokens += sentence_tokens
        
        # Add final chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _create_summary_prompt(self, transcript_text: str, title: str) -> str:
        """
        Create coaching-focused summary prompt.
        
        Args:
            transcript_text: Transcript content
            title: Video title
            
        Returns:
            Formatted prompt string
        """
        return f"""Analyze this transcript from "{title}" and create a concise summary for business coaching purposes.

Extract 6-12 actionable insights as bullet points that entrepreneurs can immediately implement. Focus on:
- Specific strategies and tactics
- Mindset shifts and mental frameworks
- Business operations and growth advice
- Marketing and sales insights
- Leadership and management principles

Also identify 3-6 key concepts or frameworks mentioned that entrepreneurs should understand.

Transcript:
{transcript_text}

Format your response exactly as:

ACTIONABLE INSIGHTS:
• [specific actionable insight 1]
• [specific actionable insight 2]
• [specific actionable insight 3]
...

KEY CONCEPTS:
• [key concept/framework 1]
• [key concept/framework 2]
• [key concept/framework 3]
...

Focus on practical, implementable advice rather than general observations."""
    
    def _parse_summary_response(self, summary_text: str) -> tuple[List[str], List[str]]:
        """
        Parse structured summary response into bullets and concepts.
        
        Args:
            summary_text: Raw LLM response
            
        Returns:
            Tuple of (bullets, key_concepts)
        """
        bullets = []
        key_concepts = []
        
        # Extract actionable insights
        if "ACTIONABLE INSIGHTS:" in summary_text:
            insights_section = summary_text.split("ACTIONABLE INSIGHTS:")[1]
            if "KEY CONCEPTS:" in insights_section:
                insights_section = insights_section.split("KEY CONCEPTS:")[0]
            
            bullets = [
                line.strip().lstrip('•-*').strip() 
                for line in insights_section.split('\n') 
                if line.strip() and any(line.strip().startswith(prefix) for prefix in ['•', '-', '*'])
            ]
        
        # Extract key concepts
        if "KEY CONCEPTS:" in summary_text:
            concepts_section = summary_text.split("KEY CONCEPTS:")[1]
            key_concepts = [
                line.strip().lstrip('•-*').strip() 
                for line in concepts_section.split('\n') 
                if line.strip() and any(line.strip().startswith(prefix) for prefix in ['•', '-', '*'])
            ]
        
        return bullets, key_concepts
    
    def _deduplicate_items(self, items: List[str]) -> List[str]:
        """
        Remove duplicates while preserving order.
        
        Args:
            items: List of strings to deduplicate
            
        Returns:
            Deduplicated list
        """
        seen = set()
        result = []
        
        for item in items:
            # Normalize for comparison
            normalized = item.lower().strip()
            if normalized not in seen and normalized:
                seen.add(normalized)
                result.append(item)
        
        return result
    
    def _trace_with_langfuse(
        self, 
        summary_response: GenerateShortSummaryResponse, 
        model: str, 
        temperature: float, 
        prompt_id: str,
        prompt_version: str
    ) -> None:
        """
        Send trace information to Langfuse if configured.
        
        Args:
            summary_response: Generated summary response
            model: LLM model used
            temperature: Model temperature
            prompt_id: Prompt identifier
            prompt_version: Prompt version (e.g., 'v1')
        """
        try:
            # Check if Langfuse is configured
            langfuse_public_key = get_optional_env_var("LANGFUSE_PUBLIC_KEY")
            langfuse_secret_key = get_optional_env_var("LANGFUSE_SECRET_KEY")
            
            if not langfuse_public_key or not langfuse_secret_key:
                return
            
            # Import Langfuse only if keys are available
            from langfuse import Langfuse
            
            langfuse_host = get_optional_env_var("LANGFUSE_HOST", "https://cloud.langfuse.com")
            langfuse = Langfuse(
                public_key=langfuse_public_key,
                secret_key=langfuse_secret_key,
                host=langfuse_host
            )
            
            # Create trace
            trace = langfuse.trace(
                name="generate_short_summary",
                metadata={
                    "model": model,
                    "temperature": temperature,
                    "prompt_id": prompt_id,
                    "prompt_version": prompt_version,
                    "transcript_doc_ref": self.transcript_doc_ref,
                    "title": self.title
                }
            )
            
            # Add generation span
            trace.generation(
                name="summary_generation",
                model=model,
                model_parameters={
                    "temperature": temperature,
                    "max_tokens": 1500
                },
                usage={
                    "input": summary_response["token_usage"]["input_tokens"],
                    "output": summary_response["token_usage"]["output_tokens"]
                },
                metadata={
                    "bullets_count": len(summary_response["bullets"]),
                    "concepts_count": len(summary_response["key_concepts"])
                }
            )
            
            # Flush to ensure data is sent
            langfuse.flush()
            
        except Exception as e:
            # Don't fail the entire operation if tracing fails
            print(f"Warning: Langfuse tracing failed: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = GenerateShortSummary(
        transcript_doc_ref="transcripts/test_video_123",
        title="Building a 7-Figure Business: Key Strategies"
    )
    
    try:
        result = tool.run()
        print("GenerateShortSummary test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Generated {len(data['bullets'])} bullets and {len(data['key_concepts'])} concepts")
            print(f"Token usage: {data['token_usage']}")
            print(f"Prompt ID: {data['prompt_id']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()