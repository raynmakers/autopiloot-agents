"""
UpsertSummaryToZep tool for comprehensive Zep GraphRAG integration with extended metadata.
Implements TASK-ZEP-0006 specification with RAG references and complete video metadata.
"""

import os
import sys
import json
from typing import Dict, Any, List, TypedDict, Literal
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var


# Type definitions from TASK-ZEP-0006 specification
class RAGRef(TypedDict):
    type: Literal["transcript_drive", "logic_doc", "other"]
    ref: str


class ZepMetadata(TypedDict):
    video_id: str
    title: str
    published_at: str
    channel_id: str
    transcript_doc_ref: str
    tags: List[str]
    rag_refs: List[RAGRef]


class UpsertSummaryToZep(BaseTool):
    """
    Upsert short summary to Zep GraphRAG with comprehensive metadata and RAG references.
    
    Implements TASK-ZEP-0006 specification for storing actionable coaching summaries
    with complete video metadata, transcript references, and RAG document linkage
    for enhanced semantic search and retrieval workflows.
    
    Uses the autopiloot_guidelines collection as specified in requirements.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for document reference and metadata linking"
    )
    
    short_summary: Dict[str, Any] = Field(
        ..., 
        description="Generated summary containing bullets and key_concepts from GenerateShortSummary"
    )
    
    video_metadata: Dict[str, Any] = Field(
        ...,
        description="Complete video metadata including title, published_at, channel_id for Zep storage"
    )
    
    transcript_doc_ref: str = Field(
        ...,
        description="Firestore transcript document reference path (e.g., 'transcripts/video_id')"
    )
    
    rag_refs: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of RAG reference objects with type and ref fields"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Optional tags for enhanced categorization and discovery"
    )
    
    def run(self) -> str:
        """
        Upsert short summary to Zep GraphRAG collection with comprehensive metadata.
        
        Returns:
            str: JSON string containing zep_doc_id for reference tracking
        
        Raises:
            RuntimeError: If Zep storage fails
        """
        try:
            # Initialize Zep client
            zep_client = self._initialize_zep_client()
            
            # Get collection name from environment
            collection_name = get_optional_env_var("ZEP_COLLECTION", "autopiloot_guidelines")
            
            # Ensure collection exists
            self._ensure_collection_exists(zep_client, collection_name)
            
            # Format content for semantic search
            content = self._format_content_for_zep(self.short_summary)
            
            # Build comprehensive metadata
            metadata = self._build_zep_metadata(
                self.video_id, 
                self.short_summary, 
                self.video_metadata,
                self.transcript_doc_ref,
                self.rag_refs,
                self.tags
            )
            
            # Upsert document to Zep
            zep_doc_id = self._upsert_to_zep_collection(
                zep_client,
                collection_name,
                content,
                metadata,
                self.video_id
            )
            
            return json.dumps({
                "zep_doc_id": zep_doc_id,
                "collection": collection_name,
                "rag_refs": self.rag_refs
            }, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Failed to upsert summary to Zep: {str(e)}",
                "zep_doc_id": None,
                "rag_refs": None
            })
    
    def _initialize_zep_client(self):
        """Initialize Zep client with proper authentication and configuration."""
        try:
            # Get required API key
            api_key = get_required_env_var("ZEP_API_KEY", "Zep API key for GraphRAG access")
            
            # Import Zep SDK
            try:
                from zep_python import ZepClient
            except ImportError:
                raise RuntimeError("zep-python package not available. Install with: pip install zep-python>=2.0.0")
            
            # Initialize with API key and optional base URL
            base_url = get_optional_env_var("ZEP_BASE_URL", "https://api.getzep.com")
            
            return ZepClient(
                api_key=api_key,
                base_url=base_url
            )
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Zep client: {str(e)}")
    
    def _ensure_collection_exists(self, zep_client, collection_name: str) -> None:
        """
        Ensure target collection exists, create if necessary.
        
        Args:
            zep_client: Initialized Zep client
            collection_name: Target collection name
        """
        try:
            # Try to get collection
            zep_client.document.get_collection(collection_name)
            
        except Exception:
            # Collection doesn't exist, create it
            try:
                from zep_python import CreateCollectionRequest
                
                collection_request = CreateCollectionRequest(
                    name=collection_name,
                    description="Autopiloot coaching guidelines and actionable insights from video summaries"
                )
                
                zep_client.document.add_collection(collection_request)
                
            except Exception as e:
                raise RuntimeError(f"Failed to create Zep collection '{collection_name}': {str(e)}")
    
    def _format_content_for_zep(self, summary: Dict[str, Any]) -> str:
        """
        Format summary content for optimal Zep semantic search and retrieval.
        
        Args:
            summary: Summary data with bullets and key_concepts
            
        Returns:
            Formatted text content optimized for GraphRAG
        """
        bullets = summary.get("bullets", [])
        key_concepts = summary.get("key_concepts", [])
        
        content_parts = []
        
        # Add structured sections for semantic search
        if bullets:
            content_parts.append("ACTIONABLE INSIGHTS:")
            for bullet in bullets:
                content_parts.append(f"• {bullet}")
        
        if key_concepts:
            content_parts.append("\nKEY CONCEPTS:")
            for concept in key_concepts:
                content_parts.append(f"• {concept}")
        
        # Add coaching context
        if bullets or key_concepts:
            content_parts.append("\n--- COACHING SUMMARY ---")
            content_parts.append("This summary provides actionable business insights and key frameworks")
            content_parts.append("for entrepreneurs to implement immediately in their operations.")
        
        return "\n".join(content_parts)
    
    def _build_zep_metadata(
        self, 
        video_id: str, 
        summary: Dict[str, Any],
        video_metadata: Dict[str, Any],
        transcript_doc_ref: str,
        rag_refs: List[Dict[str, str]],
        tags: List[str]
    ) -> ZepMetadata:
        """
        Build comprehensive metadata dictionary for Zep document according to TASK-ZEP-0006.
        
        Args:
            video_id: YouTube video identifier
            summary: Summary data with additional metadata
            video_metadata: Complete video information
            transcript_doc_ref: Firestore transcript reference
            rag_refs: RAG reference objects
            tags: Categorization tags
            
        Returns:
            Complete Zep metadata following specification
        """
        # Convert rag_refs to proper format
        formatted_rag_refs: List[RAGRef] = []
        for ref in rag_refs:
            formatted_rag_refs.append({
                "type": ref.get("type", "other"),
                "ref": ref.get("ref", "")
            })
        
        # Build metadata according to specification
        metadata: ZepMetadata = {
            "video_id": video_id,
            "title": video_metadata.get("title", ""),
            "published_at": video_metadata.get("published_at", ""),
            "channel_id": video_metadata.get("channel_id", ""),
            "transcript_doc_ref": transcript_doc_ref,
            "tags": tags,
            "rag_refs": formatted_rag_refs
        }
        
        # Add coaching-specific metadata
        metadata.update({
            "content_type": "coaching_summary",
            "bullets_count": len(summary.get("bullets", [])),
            "concepts_count": len(summary.get("key_concepts", [])),
            "prompt_id": summary.get("prompt_id", ""),
            "source": "autopiloot_summarizer",
            "created_by": "UpsertSummaryToZep"
        })
        
        return metadata
    
    def _upsert_to_zep_collection(
        self, 
        zep_client, 
        collection_name: str, 
        content: str, 
        metadata: ZepMetadata,
        document_id: str
    ) -> str:
        """
        Upsert document to Zep collection with comprehensive metadata.
        
        Args:
            zep_client: Initialized Zep client
            collection_name: Target collection name
            content: Formatted content text
            metadata: Complete document metadata
            document_id: Unique document identifier
            
        Returns:
            Zep document ID
        """
        try:
            from zep_python import Document
            
            # Create document object with unique ID
            zep_doc_id = f"summary_{document_id}"
            
            doc = Document(
                content=content,
                metadata=metadata,
                document_id=zep_doc_id
            )
            
            # Upsert to collection
            zep_client.document.add_document(collection_name, doc)
            
            return zep_doc_id
            
        except Exception as e:
            raise RuntimeError(f"Failed to upsert document to Zep collection: {str(e)}")


if __name__ == "__main__":
    # Test the tool with comprehensive data
    test_summary = {
        "bullets": [
            "Focus on systematic customer acquisition through targeted marketing channels",
            "Implement automated sales processes with clear metrics and conversion tracking",
            "Build scalable business systems that operate without constant manual intervention"
        ],
        "key_concepts": [
            "Customer Acquisition Cost (CAC) optimization strategies",
            "Sales funnel systematization and automation",
            "Business process automation frameworks",
            "Performance metrics and KPI tracking systems"
        ],
        "prompt_id": "coach_v1_12345678",
        "token_usage": {
            "input_tokens": 1500,
            "output_tokens": 300
        }
    }
    
    test_video_metadata = {
        "title": "How to Scale Your Business Without Burnout",
        "published_at": "2023-09-15T10:30:00Z",
        "channel_id": "UC1234567890"
    }
    
    test_rag_refs = [
        {
            "type": "transcript_drive",
            "ref": "1AbC2DefGhI3jKlMnOpQ4rStU5vWx"
        },
        {
            "type": "logic_doc",
            "ref": "1ZyX3WvU2TsR4qPoN5mLkJ6iH7gFe"
        }
    ]
    
    tool = UpsertSummaryToZep(
        video_id="test_video_123",
        short_summary=test_summary,
        video_metadata=test_video_metadata,
        transcript_doc_ref="transcripts/test_video_123",
        rag_refs=test_rag_refs,
        tags=["coaching", "business", "automation", "scaling"]
    )
    
    try:
        result = tool.run()
        print("UpsertSummaryToZep test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Error: {data['error']}")
        else:
            print(f"Successfully upserted to Zep with ID: {data['zep_doc_id']}")
            print(f"Collection: {data['collection']}")
            print(f"RAG References: {len(data['rag_refs'])} items")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()