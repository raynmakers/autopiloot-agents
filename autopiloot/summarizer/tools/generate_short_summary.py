import os
import json
from typing import Dict, Any, List
from openai import OpenAI
from google.cloud import firestore
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class GenerateShortSummary(BaseTool):
    def __init__(self):
        super().__init__()
        self.client = OpenAI(api_key=self.openai_api_key)
        self.db = self._initialize_firestore()
    
    def _validate_env_vars(self):
        self.openai_api_key = self.get_env_var("OPENAI_API_KEY")
        self.service_account_path = self.get_env_var("GOOGLE_SERVICE_ACCOUNT_PATH")
        self.project_id = self.get_env_var("GCP_PROJECT_ID")
        self.model = self.get_env_var("LLM_MODEL", required=False) or "gpt-4-turbo-preview"
        self.temperature = float(self.get_env_var("LLM_TEMPERATURE", required=False) or "0.2")
    
    def _initialize_firestore(self):
        return firestore.Client(
            project=self.project_id,
            credentials=None
        )
    
    def _chunk_text(self, text: str, max_tokens: int = 100000) -> List[str]:
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) // 4
            if current_length + word_length > max_tokens:
                chunks.append(' '.join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        transcript_doc_ref = request.get('transcript_doc_ref', '')
        title = request.get('title', '')
        
        if not transcript_doc_ref:
            raise ValueError("transcript_doc_ref is required")
        if not title:
            raise ValueError("title is required")
        
        try:
            transcript_ref = self.db.document(transcript_doc_ref)
            transcript_doc = transcript_ref.get()
            
            if not transcript_doc.exists:
                raise ValueError(f"Transcript {transcript_doc_ref} does not exist")
            
            transcript_data = transcript_doc.to_dict()
            
            video_id = transcript_data.get('video_id')
            video_ref = self.db.collection('videos').document(video_id)
            video_doc = video_ref.get()
            
            if not video_doc.exists:
                raise ValueError(f"Video {video_id} does not exist")
            
            video_data = video_doc.to_dict()
            
            transcript_text = ""
            drive_id_txt = transcript_data.get('drive_id_txt')
            if drive_id_txt:
                transcript_text = f"[Transcript from Drive: {drive_id_txt}]"
            
            prompt = f"""You are an expert content coach analyzing a transcript from "{title}".

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

            response = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": "You are an expert content coach specializing in extracting actionable insights for entrepreneurs."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            
            summary_text = response.choices[0].message.content
            
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
            
            prompt_id = f"summary_{video_id}_{self.model}"
            
            return {
                "bullets": bullets,
                "key_concepts": key_concepts,
                "prompt_id": prompt_id,
                "token_usage": {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                }
            }
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate short summary: {str(e)}")


if __name__ == "__main__":
    tool = GenerateShortSummary()
    
    test_request = {
        "transcript_doc_ref": "transcripts/test_video_123",
        "title": "Test Video Title"
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: Generated summary")
        print(f"Bullets: {len(result.get('bullets', []))}")
        print(f"Key concepts: {len(result.get('key_concepts', []))}")
        print(f"Token usage: {json.dumps(result.get('token_usage', {}), indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")