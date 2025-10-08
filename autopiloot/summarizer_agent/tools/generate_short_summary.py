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

            # Create comprehensive coaching prompt with structured JSON output
            prompt = f"""You are an expert business coach with deep expertise across sales, marketing, business strategy, and content creation.

STEP 1 - CONTENT VALIDATION:
Determine if this transcript contains actual business, marketing, sales, strategy, or educational content.

RED FLAGS for NON-BUSINESS content:
- Song lyrics, music, poetry, entertainment
- Fiction, stories without business lessons
- Casual vlogs without educational value
- Gaming, sports, recreational content
- News without strategic analysis

STEP 2 - ANALYSIS (if business content):
Extract EVERY valuable insight, framework, concept, tactic, and strategy mentioned.

Video: "{self.title}"

Transcript:
{transcript_text}

Provide comprehensive analysis covering:
- Sales tactics and closing strategies
- Marketing approaches and campaigns
- Business strategy and operations
- Content creation techniques
- Customer acquisition/retention
- Pricing and positioning
- Leadership and team building
- Any other actionable tactics

Extract named frameworks/concepts like:
- "80/20 Principle", "Jobs to Be Done"
- "Flywheel Effect", "Loss Aversion"
- "Brand Promise Framework", etc."""

            # Define JSON schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "is_business_content": {
                        "type": "boolean",
                        "description": "Whether the content is business/educational (true) or entertainment/non-business (false)"
                    },
                    "content_type": {
                        "type": "string",
                        "description": "Type of content: 'Business/Educational', 'Song Lyrics', 'Entertainment', 'Fiction', etc."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Explanation for content classification decision"
                    },
                    "actionable_insights": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Complete descriptions of actionable business insights with implementation details"
                    },
                    "key_concepts": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Names of frameworks, principles, or methodologies mentioned"
                    }
                },
                "required": ["is_business_content", "content_type", "reason", "actionable_insights", "key_concepts"],
                "additionalProperties": False
            }

            # Generate comprehensive summary using GPT-5 reasoning with structured output
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert multi-domain business coach (sales, marketing, strategy, content) specializing in extracting comprehensive, actionable insights. First validate if content is business-related, then extract insights. Always respond with valid JSON matching the schema."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "business_summary_analysis",
                        "strict": True,
                        "schema": response_schema
                    }
                },
                max_completion_tokens=max_output_tokens,
                **({"reasoning_effort": reasoning_effort} if reasoning_effort else {})
            )

            # Parse JSON response directly
            summary_data = json.loads(response.choices[0].message.content)

            # Check if content was flagged as non-business
            if not summary_data.get("is_business_content", False):
                return json.dumps({
                    "status": "not_business_content",
                    "content_type": summary_data.get("content_type", "Unknown"),
                    "reason": summary_data.get("reason", "Content does not contain business/educational material"),
                    "video_id": video_id,
                    "title": self.title,
                    "message": "This content is not business/educational material and cannot be analyzed for business insights",
                    "token_usage": {
                        "input_tokens": response.usage.prompt_tokens,
                        "output_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                })

            # Extract insights and concepts from structured response
            bullets = summary_data.get("actionable_insights", [])
            key_concepts = summary_data.get("key_concepts", [])

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
    print("="*80)
    print("TEST 1: GenerateShortSummary - Rick Astley (Non-Business Content)")
    print("="*80)

    # Test with Rick Astley video (should be rejected as non-business)
    tool_rick = GenerateShortSummary(
        transcript_doc_ref="transcripts/dQw4w9WgXcQ",
        title="Never Gonna Give You Up - Rick Astley"
    )

    try:
        print("Generating summary for Rick Astley (expecting rejection)...")
        result = tool_rick.run()
        data = json.loads(result)

        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        elif data.get("status") == "not_business_content":
            print(f"\n⚠️  Content Validation Failed (Expected)")
            print(f"\n📋 Content Analysis:")
            print(f"   Video: {data.get('title', 'N/A')}")
            print(f"   Content Type: {data.get('content_type', 'Unknown')}")
            print(f"   Business Relevance: Not Applicable")
            print(f"\n💬 Reason:")
            print(f"   {data.get('reason', 'N/A')}")
            print(f"\n📈 Token Usage:")
            print(f"   Input: {data.get('token_usage', {}).get('input_tokens', 0):,}")
            print(f"   Output: {data.get('token_usage', {}).get('output_tokens', 0):,}")
            print(f"   Total: {data.get('token_usage', {}).get('total_tokens', 0):,}")
            print(f"\n✅ Hallucination Prevention: Working correctly!")
            print(f"   The tool correctly identified non-business content and refused to generate fake insights.")
        else:
            print(f"\n⚠️  Unexpected: Content was NOT rejected")
            print(f"   This should have been rejected as non-business content")

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST 2: GenerateShortSummary - Dan Martell (Business Content)")
    print("="*80)

    # Test with Dan Martell video (should generate business summary)
    tool_dan = GenerateShortSummary(
        transcript_doc_ref="transcripts/mZxDw92UXmA",
        title="How to 10x Your Business - Dan Martell"
    )

    try:
        print("Generating summary for Dan Martell (expecting business insights)...")
        result = tool_dan.run()
        data = json.loads(result)

        if "error" in data:
            print(f"\n❌ Error: {data['message']}")
            print(f"   Error type: {data['error']}")
        elif data.get("status") == "not_business_content":
            print(f"\n⚠️  Unexpected: Content was rejected")
            print(f"   Content Type: {data.get('content_type', 'Unknown')}")
            print(f"   Reason: {data.get('reason', 'N/A')}")
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
    print("Testing complete! Two videos tested:")
    print("- dQw4w9WgXcQ: Rick Astley (non-business, should be rejected)")
    print("- mZxDw92UXmA: Dan Martell (business content, should generate insights)")
    print("="*80)