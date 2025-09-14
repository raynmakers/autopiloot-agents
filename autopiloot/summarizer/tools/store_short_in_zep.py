import os
import json
from typing import Dict, Any
from zep_python import ZepClient
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from core.base_tool import BaseTool


class StoreShortInZep(BaseTool):
    def __init__(self):
        super().__init__()
        self.zep = ZepClient(api_key=self.zep_api_key, base_url=self.zep_base_url)
    
    def _validate_env_vars(self):
        self.zep_api_key = self.get_env_var("ZEP_API_KEY")
        self.zep_base_url = self.get_env_var("ZEP_BASE_URL", required=False) or "https://api.getzep.com"
        self.zep_collection = self.get_env_var("ZEP_COLLECTION", required=False) or "autopiloot_summaries"
    
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        video_id = request.get('video_id', '')
        short_summary = request.get('short_summary', {})
        
        if not video_id:
            raise ValueError("video_id is required")
        if not short_summary:
            raise ValueError("short_summary is required")
        
        try:
            bullets = short_summary.get('bullets', [])
            key_concepts = short_summary.get('key_concepts', [])
            
            document_content = f"Video ID: {video_id}\n\n"
            document_content += "ACTIONABLE INSIGHTS:\n"
            for bullet in bullets:
                document_content += f"• {bullet}\n"
            document_content += "\nKEY CONCEPTS:\n"
            for concept in key_concepts:
                document_content += f"• {concept}\n"
            
            metadata = {
                "video_id": video_id,
                "type": "short_summary",
                "bullets_count": len(bullets),
                "concepts_count": len(key_concepts)
            }
            
            if short_summary.get('prompt_id'):
                metadata['prompt_id'] = short_summary['prompt_id']
            
            from zep_python import Document
            
            document = Document(
                content=document_content,
                metadata=metadata,
                document_id=f"summary_{video_id}"
            )
            
            collection = self.zep.document.get_collection(self.zep_collection)
            if not collection:
                collection = self.zep.document.add_collection(
                    name=self.zep_collection,
                    description="Autopiloot video summaries for coaching"
                )
            
            collection.add_documents([document])
            
            return {"zep_doc_id": f"summary_{video_id}"}
            
        except Exception as e:
            raise RuntimeError(f"Failed to store summary in Zep: {str(e)}")


if __name__ == "__main__":
    tool = StoreShortInZep()
    
    test_request = {
        "video_id": "test_video_123",
        "short_summary": {
            "bullets": [
                "Test insight 1",
                "Test insight 2",
                "Test insight 3"
            ],
            "key_concepts": [
                "Concept A",
                "Concept B"
            ],
            "prompt_id": "summary_test_gpt4"
        }
    }
    
    try:
        result = tool.run(test_request)
        print(f"Success: {json.dumps(result, indent=2)}")
    except Exception as e:
        print(f"Error: {str(e)}")