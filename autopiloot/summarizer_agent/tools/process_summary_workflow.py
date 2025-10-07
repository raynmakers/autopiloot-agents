"""
ProcessSummaryWorkflow tool for orchestrating complete summary processing workflow.
Implements TASK-ZEP-0006 end-to-end workflow: Generate → Zep Upsert → Firestore Record.
"""

import os
import sys
import json
from typing import Dict, Any, List
from agency_swarm.tools import BaseTool
from pydantic import Field

# Add core and config directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from env_loader import get_required_env_var, get_optional_env_var

# Import related tools - use try/except for both package and direct execution
try:
    from .generate_short_summary import GenerateShortSummary
    from .store_short_in_zep import StoreShortInZep
    from .save_summary_record_enhanced import SaveSummaryRecordEnhanced
except ImportError:
    # Fallback for direct execution
    from generate_short_summary import GenerateShortSummary
    from store_short_in_zep import StoreShortInZep
    from save_summary_record_enhanced import SaveSummaryRecordEnhanced


class ProcessSummaryWorkflow(BaseTool):
    """
    Orchestrate complete summary processing workflow with Zep GraphRAG integration.

    Implements the full TASK-ZEP-0006 specification by coordinating:
    1. Short summary generation from transcript
    2. Zep GraphRAG upsert with comprehensive metadata
    3. Enhanced Firestore record with all references (stores actual summary content)

    Provides atomic workflow execution with comprehensive error handling
    and reference linking across Firestore and Zep platforms.
    """
    
    video_id: str = Field(
        ..., 
        description="YouTube video ID for workflow coordination"
    )
    
    transcript_doc_ref: str = Field(
        ...,
        description="Firestore transcript document reference path (e.g., 'transcripts/video_id')"
    )
    
    video_metadata: Dict[str, Any] = Field(
        ...,
        description="Complete video metadata including title, published_at, channel_id"
    )
    
    title: str = Field(
        default="",
        description="Optional video title for summary generation context"
    )
    
    tags: List[str] = Field(
        default_factory=list,
        description="Optional tags for enhanced categorization"
    )
    
    def run(self) -> str:
        """
        Execute complete summary processing workflow with Zep integration.
        
        Returns:
            str: JSON string containing all generated references and status
        
        Raises:
            RuntimeError: If any step in the workflow fails
        """
        try:
            workflow_results = {
                "video_id": self.video_id,
                "workflow_status": "in_progress",
                "steps_completed": []
            }
            
            # Step 1: Generate short summary from transcript
            print(f"Step 1: Generating short summary for {self.video_id}")
            summary_result = self._generate_short_summary()
            workflow_results["summary_generation"] = summary_result
            workflow_results["steps_completed"].append("summary_generation")

            # Extract summary data
            summary_data = json.loads(summary_result)

            # Check for errors
            if "error" in summary_data:
                raise RuntimeError(f"Summary generation failed: {summary_data['error']}")

            # Check if content was rejected as non-business
            if summary_data.get("status") == "not_business_content":
                print(f"⚠️  Content validation failed for {self.video_id}")
                print(f"   Content Type: {summary_data.get('content_type', 'Unknown')}")
                print(f"   Reason: {summary_data.get('reason', 'N/A')}")

                return json.dumps({
                    "workflow_status": "skipped_non_business_content",
                    "video_id": self.video_id,
                    "content_type": summary_data.get("content_type"),
                    "reason": summary_data.get("reason"),
                    "message": "Content is not business/educational material and will not be stored in Zep or Firestore",
                    "token_usage": summary_data.get("token_usage", {}),
                    "steps_completed": workflow_results["steps_completed"]
                })

            short_summary = {
                "bullets": summary_data["bullets"],
                "key_concepts": summary_data["key_concepts"],
                "prompt_id": summary_data["prompt_id"],
                "token_usage": summary_data["token_usage"]
            }
            
            # Step 2: Upsert to Zep GraphRAG with comprehensive metadata
            print(f"Step 2: Upserting summary to Zep GraphRAG for {self.video_id}")
            zep_result = self._upsert_to_zep(short_summary)
            workflow_results["zep_upsert"] = zep_result
            workflow_results["steps_completed"].append("zep_upsert")

            # Extract Zep data
            zep_data = json.loads(zep_result)
            if "error" in zep_data:
                raise RuntimeError(f"Zep upsert failed: {zep_data['error']}")

            # Step 3: Save enhanced Firestore record with all references (includes actual summary content)
            print(f"Step 3: Saving enhanced Firestore record for {self.video_id}")
            firestore_result = self._save_enhanced_record(
                short_summary,
                zep_data,
                summary_data
            )
            workflow_results["firestore_record"] = firestore_result
            workflow_results["steps_completed"].append("firestore_record")

            # Extract Firestore data
            firestore_data = json.loads(firestore_result)
            if "error" in firestore_data:
                raise RuntimeError(f"Firestore record creation failed: {firestore_data['error']}")

            # Workflow completed successfully
            workflow_results["workflow_status"] = "completed"
            workflow_results["final_references"] = {
                "summary_doc_ref": firestore_data["summary_doc_ref"],
                "zep_doc_id": zep_data["zep_doc_id"],
                "zep_collection": zep_data["collection"],
                "rag_refs": zep_data["rag_refs"]
            }
            
            return json.dumps(workflow_results, indent=2)
            
        except Exception as e:
            return json.dumps({
                "error": f"Summary workflow failed: {str(e)}",
                "video_id": self.video_id,
                "workflow_status": "failed",
                "steps_completed": workflow_results.get("steps_completed", [])
            })
    
    def _generate_short_summary(self) -> str:
        """
        Execute summary generation step.
        
        Returns:
            JSON string result from GenerateShortSummary
        """
        try:
            generator = GenerateShortSummary(
                transcript_doc_ref=self.transcript_doc_ref,
                title=self.title or self.video_metadata.get("title", "")
            )
            
            return generator.run()
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate short summary: {str(e)}")
    
    def _upsert_to_zep(self, short_summary: Dict[str, Any]) -> str:
        """
        Execute Zep GraphRAG upsert step.
        
        Args:
            short_summary: Generated summary data
            
        Returns:
            JSON string result from StoreShortInZep
        """
        try:
            # Build RAG references from known transcript storage
            rag_refs = self._build_rag_references()
            
            zep_upserter = StoreShortInZep(
                video_id=self.video_id,
                short_summary=short_summary,
                video_metadata=self.video_metadata,
                transcript_doc_ref=self.transcript_doc_ref,
                rag_refs=rag_refs,
                tags=self.tags
            )
            
            return zep_upserter.run()
            
        except Exception as e:
            raise RuntimeError(f"Failed to upsert to Zep: {str(e)}")
    
    def _save_enhanced_record(
        self,
        short_summary: Dict[str, Any],
        zep_data: Dict[str, Any],
        summary_data: Dict[str, Any]
    ) -> str:
        """
        Execute enhanced Firestore record creation step.

        Args:
            short_summary: Generated summary data
            zep_data: Zep upsert results
            summary_data: Original summary generation results

        Returns:
            JSON string result from SaveSummaryRecordEnhanced
        """
        try:
            # Build comprehensive references object
            refs = {
                "transcript_doc_ref": self.transcript_doc_ref,
                "zep_doc_id": zep_data["zep_doc_id"],
                "zep_collection": zep_data["collection"],
                "prompt_version": summary_data.get("prompt_version", "v1"),
                "token_usage": summary_data["token_usage"],
                "rag_refs": zep_data["rag_refs"],
                "tags": self.tags
            }

            record_saver = SaveSummaryRecordEnhanced(
                video_id=self.video_id,
                bullets=short_summary.get("bullets", []),
                key_concepts=short_summary.get("key_concepts", []),
                prompt_id=summary_data["prompt_id"],
                refs=refs,
                video_metadata=self.video_metadata
            )

            return record_saver.run()

        except Exception as e:
            raise RuntimeError(f"Failed to save enhanced record: {str(e)}")
    
    def _build_rag_references(self) -> List[Dict[str, str]]:
        """
        Build RAG references for comprehensive document linking.
        
        Returns:
            List of RAG reference objects
        """
        rag_refs = []
        
        # Add transcript reference (Firestore-based)
        rag_refs.append({
            "type": "transcript_firestore",
            "ref": self.transcript_doc_ref
        })
        
        # Add any additional logic documents or references
        # This can be extended based on future requirements
        
        return rag_refs
    
    def _validate_workflow_requirements(self) -> None:
        """
        Validate that all required environment variables and configurations are available.
        
        Raises:
            RuntimeError: If required configurations are missing
        """
        required_env_vars = [
            "ZEP_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "OPENAI_API_KEY"
        ]
        
        missing_vars = []
        for var in required_env_vars:
            try:
                get_required_env_var(var, f"{var} for summary workflow")
            except Exception:
                missing_vars.append(var)
        
        if missing_vars:
            raise RuntimeError(f"Missing required environment variables: {', '.join(missing_vars)}")


if __name__ == "__main__":
    # Test the complete workflow
    test_video_metadata = {
        "title": "How to Scale Your Business Without Burnout - Complete Guide",
        "published_at": "2023-09-15T10:30:00Z",
        "channel_id": "UC1234567890"
    }
    
    workflow = ProcessSummaryWorkflow(
        video_id="test_video_123",
        transcript_doc_ref="transcripts/test_video_123",
        video_metadata=test_video_metadata,
        title="How to Scale Your Business Without Burnout",
        tags=["coaching", "business", "automation", "scaling", "entrepreneurship"]
    )
    
    try:
        result = workflow.run()
        print("ProcessSummaryWorkflow test result:")
        print(result)
        
        # Parse and validate result
        data = json.loads(result)
        if "error" in data:
            print(f"Workflow Error: {data['error']}")
            print(f"Steps Completed: {data.get('steps_completed', [])}")
        else:
            print(f"Workflow Status: {data['workflow_status']}")
            print(f"Steps Completed: {data['steps_completed']}")
            if data["workflow_status"] == "completed":
                refs = data["final_references"]
                print(f"Summary Doc Ref: {refs['summary_doc_ref']}")
                print(f"Zep Doc ID: {refs['zep_doc_id']}")
                print(f"RAG References: {len(refs['rag_refs'])} items")
            
    except Exception as e:
        print(f"Test error: {str(e)}")
        import traceback
        traceback.print_exc()