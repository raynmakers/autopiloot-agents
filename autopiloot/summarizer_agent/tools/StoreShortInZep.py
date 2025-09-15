"""
StoreShortInZep tool for persisting short summaries in Zep GraphRAG for semantic retrieval.
Implements TASK-SUM-0031 specification with proper Zep SDK integration and metadata handling.
"""

import os
import sys
import json
from typing import Dict, Any
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var


class StoreShortInZep(BaseTool):
    """
    Persist short summary in Zep GraphRAG collection for semantic search and coaching retrieval.
    
    Stores actionable insights and key concepts with proper metadata linking
    to video source and transcript for enhanced content discovery workflows.
    
    Uses the autopiloot_guidelines collection as specified in task requirements.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for document reference and metadata linking"
    )
    
    short_summary: Dict[str, Any] = Field(
        ..., 
        description="Generated summary containing bullets and key_concepts from GenerateShortSummary"
    )
    
    def run(self) -> str:
        """
        Store short summary in Zep GraphRAG collection with proper metadata.
        
        Returns:
            str: JSON string containing zep_doc_id for reference tracking
        
        Raises:
            RuntimeError: If Zep storage fails
        """
        try:
            # Validate Zep credentials
            zep_api_key = get_required_env_var("ZEP_API_KEY", "Zep API key for GraphRAG storage")
            zep_collection = get_optional_env_var("ZEP_COLLECTION", "autopiloot_guidelines")
            
            # Initialize Zep client
            zep_client = self._initialize_zep_client(zep_api_key)
            
            # Prepare content for Zep storage
            content_text = self._format_content_for_zep(self.short_summary)
            metadata = self._build_zep_metadata(self.video_id, self.short_summary)
            
            # Store document in Zep collection
            zep_doc_id = self._store_in_zep_collection(
                zep_client, 
                zep_collection, 
                content_text, 
                metadata,
                self.video_id
            )
            
            return json.dumps({
                "zep_doc_id": zep_doc_id
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to store summary in Zep: {str(e)}",
                "zep_doc_id": None
            })
    
    def _initialize_zep_client(self, api_key: str):
        """
        Initialize Zep client with proper authentication.
        
        Args:
            api_key: Zep API key for authentication
            
        Returns:
            Zep client instance
        """
        try:
            from zep_python import ZepClient
            
            # Initialize with API key and optional base URL
            base_url = get_optional_env_var("ZEP_BASE_URL", "https://api.getzep.com")
            
            return ZepClient(
                api_key=api_key,
                base_url=base_url
            )
            
        except ImportError:
            raise RuntimeError("zep-python package not available. Install with: pip install zep-python>=2.0.0")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Zep client: {str(e)}")
    
    def _format_content_for_zep(self, summary: Dict[str, Any]) -> str:
        """
        Format summary content for optimal Zep semantic search.
        
        Args:
            summary: Summary data with bullets and key_concepts
            
        Returns:
            Formatted text content for Zep storage
        """
        bullets = summary.get("bullets", [])
        key_concepts = summary.get("key_concepts", [])
        
        content_parts = []
        
        # Add actionable insights
        if bullets:
            content_parts.append("ACTIONABLE INSIGHTS:")
            for bullet in bullets:
                content_parts.append(f"• {bullet}")
        
        # Add key concepts
        if key_concepts:
            content_parts.append("\nKEY CONCEPTS:")
            for concept in key_concepts:
                content_parts.append(f"• {concept}")
        
        return "\n".join(content_parts)
    
    def _build_zep_metadata(self, video_id: str, summary: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build metadata dictionary for Zep document.
        
        Args:
            video_id: YouTube video identifier
            summary: Summary data with additional metadata
            
        Returns:
            Metadata dictionary for Zep storage
        """
        return {
            "video_id": video_id,
            "content_type": "coaching_summary",
            "bullets_count": len(summary.get("bullets", [])),
            "concepts_count": len(summary.get("key_concepts", [])),
            "prompt_id": summary.get("prompt_id", ""),
            "token_usage": summary.get("token_usage", {}),
            "source": "autopiloot_summarizer",
            "collection": "autopiloot_guidelines"
        }
    
    def _store_in_zep_collection(
        self, 
        zep_client, 
        collection_name: str, 
        content: str, 
        metadata: Dict[str, Any],
        document_id: str
    ) -> str:
        """
        Store document in Zep collection with upsert behavior.
        
        Args:
            zep_client: Initialized Zep client
            collection_name: Target collection name
            content: Formatted content text
            metadata: Document metadata
            document_id: Unique document identifier
            
        Returns:
            Zep document ID
        """
        from zep_python import Document
        
        # Create document object
        doc = Document(
            content=content,
            metadata=metadata,
            document_id=f"summary_{document_id}"
        )
        
        try:
            # Try to get or create the collection
            try:
                collection = zep_client.document.get_collection(collection_name)
            except Exception:
                # Collection doesn't exist, create it
                from zep_python import CreateCollectionRequest
                
                collection_request = CreateCollectionRequest(
                    name=collection_name,
                    description="Autopiloot coaching guidelines and actionable insights from video summaries"
                )
                collection = zep_client.document.add_collection(collection_request)
            
            # Add document to collection (upsert behavior)
            zep_client.document.add_document(collection_name, doc)
            
            return doc.document_id
            
        except Exception as e:
            raise RuntimeError(f"Failed to store document in Zep collection '{collection_name}': {str(e)}")


if __name__ == "__main__":
    # Test the tool
    test_summary = {
        "bullets": [
            "Focus on customer acquisition through targeted marketing",
            "Implement systematic sales processes for consistency",
            "Build automated systems that scale without manual intervention"
        ],
        "key_concepts": [
            "Customer Acquisition Cost (CAC) optimization",
            "Sales process systematization",
            "Business automation frameworks"
        ],
        "prompt_id": "coach_v1_12345678",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        }
    }
    
    tool = StoreShortInZep(
        video_id="test_video_123",
        short_summary=test_summary
    )
    
    try:
        result = tool.run()
        print("StoreShortInZep test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Successfully stored in Zep with ID: {data['zep_doc_id']}")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()