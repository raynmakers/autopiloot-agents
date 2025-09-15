import os
import json
from typing import Dict, Any, List
from pydantic import Field
from openai import OpenAI
from google.cloud import firestore
from agency_swarm.tools import BaseTool


class GenerateShortSummary(BaseTool):
    """
    Generate concise business-focused summaries from video transcripts.
    Creates actionable insights and key concepts for entrepreneurs.
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
            JSON string with bullets, key_concepts, prompt_id, and token_usage
        """
        # Validate required environment variables
        openai_api_key = os.getenv("OPENAI_API_KEY")
        project_id = os.getenv("GCP_PROJECT_ID")
        
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not project_id:
            raise ValueError("GCP_PROJECT_ID environment variable is required")
        
        # Get configuration with defaults
        model = os.getenv("LLM_MODEL", "gpt-4o")
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        
        try:
            # Initialize clients
            client = OpenAI(api_key=openai_api_key)
            db = firestore.Client(project=project_id)
            
            # Retrieve transcript document
            transcript_ref = db.document(self.transcript_doc_ref)
            transcript_doc = transcript_ref.get()
            
            if not transcript_doc.exists:
                raise ValueError(f"Transcript {self.transcript_doc_ref} does not exist")
            
            transcript_data = transcript_doc.to_dict()
            video_id = transcript_data.get('video_id')
            
            # Retrieve video document for additional context
            video_ref = db.collection('videos').document(video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {video_id} does not exist")
            
            # For now, use placeholder for transcript text
            # In production, this would fetch from Google Drive using drive_id_txt
            drive_id_txt = transcript_data.get('drive_id_txt')
            transcript_text = f"[Transcript content would be fetched from Drive ID: {drive_id_txt}]"
            
            # Create summary prompt
            prompt = f"""You are an expert content coach analyzing a transcript from "{self.title}".

Please provide a concise, actionable summary for coaching purposes:

1. Extract 5-7 key actionable insights as bullet points
2. Identify 3-5 key concepts or frameworks mentioned
3. Focus on practical application for entrepreneurs

Transcript:
{transcript_text[:8000]}

Format your response as:
ACTIONABLE INSIGHTS:
• [insight 1]
• [insight 2]
...

KEY CONCEPTS:
• [concept 1]
• [concept 2]
..."""

            # Generate summary using OpenAI
            response = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": "You are an expert content coach specializing in extracting actionable insights for entrepreneurs."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            
            summary_text = response.choices[0].message.content
            
            # Parse structured output
            bullets = []
            key_concepts = []
            
            if "ACTIONABLE INSIGHTS:" in summary_text:
                insights_section = summary_text.split("ACTIONABLE INSIGHTS:")[1]
                if "KEY CONCEPTS:" in insights_section:
                    insights_section = insights_section.split("KEY CONCEPTS:")[0]
                bullets = [line.strip().lstrip('•-').strip() 
                          for line in insights_section.split('\n') 
                          if line.strip() and line.strip().startswith(('•', '-'))]
            
            if "KEY CONCEPTS:" in summary_text:
                concepts_section = summary_text.split("KEY CONCEPTS:")[1]
                key_concepts = [line.strip().lstrip('•-').strip() 
                               for line in concepts_section.split('\n') 
                               if line.strip() and line.strip().startswith(('•', '-'))]
            
            prompt_id = f"summary_{video_id}_{model}"
            
            result = {
                "bullets": bullets,
                "key_concepts": key_concepts,
                "prompt_id": prompt_id,
                "token_usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                },
                "video_id": video_id
            }
            
            return json.dumps(result)
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate short summary: {str(e)}")


if __name__ == "__main__":
    # Test the tool
    tool = GenerateShortSummary(
        transcript_doc_ref="transcripts/test_video_123",
        title="Test Video Title"
    )
    
    try:
        result = tool.run()
        print(f"Success: {result}")
    except Exception as e:
        print(f"Error: {str(e)}")