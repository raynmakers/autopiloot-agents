import os
import sys
import json
import yaml
from typing import Dict, Any, List
from pydantic import Field
from openai import OpenAI
from google.cloud import firestore
from agency_swarm.tools import BaseTool

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))


class GenerateShortSummary(BaseTool):
    """
    Generate comprehensive business summaries from video transcripts.
    Provides actionable insights across sales, marketing, business strategy, and content creation.
    Powered by GPT-5 reasoning models for deep analysis with no length constraints.
    """

    transcript_doc_ref: str = Field(
        ...,
        description="Firestore document reference path for the transcript (e.g., 'transcripts/video_id')"
    )
    title: str = Field(
        ...,
        description="Video title for context in summary generation"
    )
    
    def _load_settings(self) -> Dict[str, Any]:
        """Load configuration from settings.yaml"""
        config_path = os.path.join(os.path.dirname(__file__), '..', '..', 'config', 'settings.yaml')
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)

    def run(self) -> str:
        """
        Generate comprehensive business summary with deep analysis across multiple coaching domains.

        Returns:
            JSON string with bullets, key_concepts, prompt_id, prompt_version, and token_usage
        """
        # Validate required environment variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        project_id = os.getenv("GCP_PROJECT_ID")

        if not openai_api_key:
            return json.dumps({
                "error": "configuration_error",
                "message": "OPENAI_API_KEY environment variable is required"
            })
        if not project_id:
            return json.dumps({
                "error": "configuration_error",
                "message": "GCP_PROJECT_ID environment variable is required"
            })

        try:
            # Load settings from settings.yaml
            settings = self._load_settings()
            task_config = settings.get('llm', {}).get('tasks', {}).get('summarizer_generate_short', {})

            # Get model configuration
            model = task_config.get('model', 'o3-mini')
            temperature = task_config.get('temperature', 1.0)
            max_output_tokens = task_config.get('max_output_tokens', 50000)
            reasoning_effort = task_config.get('reasoning_effort', 'high')
            prompt_id = task_config.get('prompt_id', 'comprehensive_coach_v2')
            prompt_version = task_config.get('prompt_version', 'v2')

            # Initialize clients
            client = OpenAI(api_key=openai_api_key)
            db = firestore.Client(project=project_id)

            # Retrieve transcript document from Firestore
            transcript_ref = db.document(self.transcript_doc_ref)
            transcript_doc = transcript_ref.get()

            if not transcript_doc.exists:
                return json.dumps({
                    "error": "document_not_found",
                    "message": f"Transcript {self.transcript_doc_ref} does not exist"
                })

            transcript_data = transcript_doc.to_dict()

            # Extract video_id from document ID (transcripts/{video_id})
            video_id = self.transcript_doc_ref.split('/')[-1]

            # Get transcript text directly from Firestore (stored since migration)
            transcript_text = transcript_data.get('transcript_text', '')

            if not transcript_text:
                return json.dumps({
                    "error": "missing_data",
                    "message": "Transcript text not found in Firestore document"
                })

            # Create comprehensive coaching prompt
            prompt = f"""You are an expert business coach with deep expertise across sales, marketing, business strategy, and content creation.

Analyze this transcript from "{self.title}" and provide a COMPREHENSIVE analysis with NO LIMITS on depth or breadth.

Your goal is to extract EVERY valuable insight, framework, concept, tactic, and strategy mentioned. Be as thorough and detailed as possible.

Organize your analysis into:

1. ACTIONABLE INSIGHTS: Extract ALL specific, implementable insights. Include:
   - Sales tactics and strategies
   - Marketing approaches and campaigns
   - Business strategy and operations
   - Content creation techniques
   - Customer acquisition methods
   - Retention and engagement tactics
   - Pricing and positioning strategies
   - Team building and leadership insights
   - Any other tactical advice

2. KEY CONCEPTS & FRAMEWORKS: Identify ALL concepts, frameworks, mental models, or methodologies mentioned:
   - Named frameworks (e.g., "80/20 Principle", "Jobs to Be Done")
   - Business philosophies
   - Strategic approaches
   - Decision-making frameworks
   - Analytical models
   - Conceptual patterns

DO NOT limit yourself. Extract everything valuable. Be exhaustive and comprehensive.

Transcript:
{transcript_text}

Format your response as:
ACTIONABLE INSIGHTS:
• [insight 1]
• [insight 2]
• [insight 3]
... (continue with ALL insights, no limit)

KEY CONCEPTS:
• [concept 1]
• [concept 2]
• [concept 3]
... (continue with ALL concepts, no limit)"""

            # Generate comprehensive summary using GPT-5 reasoning
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert multi-domain business coach (sales, marketing, strategy, content) specializing in extracting comprehensive, actionable insights. Be thorough and exhaustive - extract every valuable insight without limits."
                    },
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=max_output_tokens,
                **({"reasoning_effort": reasoning_effort} if reasoning_effort else {})
            )

            summary_text = response.choices[0].message.content

            # Parse structured output
            bullets = []
            key_concepts = []

            if "ACTIONABLE INSIGHTS:" in summary_text:
                insights_section = summary_text.split("ACTIONABLE INSIGHTS:")[1]
                if "KEY CONCEPTS:" in insights_section:
                    insights_section = insights_section.split("KEY CONCEPTS:")[0]
                bullets = [line.strip().lstrip('•-*').strip()
                          for line in insights_section.split('\n')
                          if line.strip() and any(line.strip().startswith(c) for c in ('•', '-', '*', '1', '2', '3', '4', '5', '6', '7', '8', '9'))]

            if "KEY CONCEPTS:" in summary_text:
                concepts_section = summary_text.split("KEY CONCEPTS:")[1]
                key_concepts = [line.strip().lstrip('•-*').strip()
                               for line in concepts_section.split('\n')
                               if line.strip() and any(line.strip().startswith(c) for c in ('•', '-', '*', '1', '2', '3', '4', '5', '6', '7', '8', '9'))]

            result = {
                "bullets": bullets,
                "key_concepts": key_concepts,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "token_usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                "video_id": video_id,
                "model": model,
                "reasoning_effort": reasoning_effort
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "generation_error",
                "message": f"Failed to generate comprehensive summary: {str(e)}",
                "video_id": video_id if 'video_id' in locals() else None
            })


if __name__ == "__main__":
    print("Testing GenerateShortSummary with comprehensive coaching...")
    print("="*80)

    # Test with Rick Astley video
    tool = GenerateShortSummary(
        transcript_doc_ref="transcripts/dQw4w9WgXcQ",
        title="Never Gonna Give You Up - Rick Astley"
    )

    try:
        print("Generating comprehensive summary (this may take a while with GPT-5 reasoning)...")
        result = tool.run()
        data = json.loads(result)

        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        else:
            print(f"\n✅ Summary generated successfully!")
            print(f"\n📊 Summary Statistics:")
            print(f"   Model: {data.get('model', 'N/A')}")
            print(f"   Reasoning Effort: {data.get('reasoning_effort', 'N/A')}")
            print(f"   Prompt ID: {data.get('prompt_id', 'N/A')}")
            print(f"   Prompt Version: {data.get('prompt_version', 'N/A')}")
            print(f"   Video ID: {data.get('video_id', 'N/A')}")
            print(f"\n📈 Token Usage:")
            print(f"   Input: {data.get('token_usage', {}).get('input_tokens', 0):,}")
            print(f"   Output: {data.get('token_usage', {}).get('output_tokens', 0):,}")
            print(f"   Total: {data.get('token_usage', {}).get('total_tokens', 0):,}")
            print(f"\n💡 Actionable Insights: {len(data.get('bullets', []))} insights extracted")
            print(f"🎯 Key Concepts: {len(data.get('key_concepts', []))} concepts identified")

            # Show first few items
            if data.get('bullets'):
                print(f"\n📝 Sample Insights (first 5):")
                for i, bullet in enumerate(data.get('bullets', [])[:5], 1):
                    print(f"   {i}. {bullet[:100]}{'...' if len(bullet) > 100 else ''}")

            if data.get('key_concepts'):
                print(f"\n🔑 Sample Concepts (first 5):")
                for i, concept in enumerate(data.get('key_concepts', [])[:5], 1):
                    print(f"   {i}. {concept[:100]}{'...' if len(concept) > 100 else ''}")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete!")