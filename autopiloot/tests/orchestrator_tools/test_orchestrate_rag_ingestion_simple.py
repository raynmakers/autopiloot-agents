"""
Simple integration test for OrchestrateRagIngestion tool (TASK-0095).

Verifies that the tool uses the new RagIndexTranscript wrapper instead of
deprecated tools (UpsertFullTranscriptToZep, IndexFullTranscriptToOpenSearch, StreamFullTranscriptToBigQuery).
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import json
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))


class TestOrchestrateRagIngestionSimple(unittest.TestCase):
    """Simple test to verify RagIndexTranscript is used (not deprecated tools)."""

    def test_uses_rag_index_transcript_wrapper(self):
        """
        Verify that orchestrate_rag_ingestion.py contains RagIndexTranscript, not old tools.

        This is a simple file content test to verify the migration happened.
        """
        # Read the tool file
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'orchestrator_agent', 'tools', 'orchestrate_rag_ingestion.py'
        )

        with open(tool_path, 'r') as f:
            content = f.read()

        # Verify new wrapper is present
        self.assertIn('RagIndexTranscript', content,
                     "RagIndexTranscript wrapper should be in the file")

        # Verify agent parameter is used
        self.assertIn('"agent":', content,
                     "Agent parameter should be specified in operations")
        self.assertIn('transcriber_agent', content,
                     "transcriber_agent should be the agent for RagIndexTranscript")

        # Verify old tool names are NOT in the operations list
        # They may still exist in comments or docstrings, but not in the operations
        self.assertNotIn('{"name": "zep", "tool": "UpsertFullTranscriptToZep"}', content,
                        "Old UpsertFullTranscriptToZep should not be in operations")
        self.assertNotIn('{"name": "opensearch", "tool": "IndexFullTranscriptToOpenSearch"}', content,
                        "Old IndexFullTranscriptToOpenSearch should not be in operations")
        self.assertNotIn('{"name": "bigquery", "tool": "StreamFullTranscriptToBigQuery"}', content,
                        "Old StreamFullTranscriptToBigQuery should not be in operations")

        # Verify unified wrapper operation
        self.assertIn('"rag_unified"', content,
                     "Should use rag_unified operation name")

    def test_uses_text_parameter_not_transcript_text(self):
        """
        Verify that tool uses 'text' parameter for RagIndexTranscript (not 'transcript_text').
        """
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'orchestrator_agent', 'tools', 'orchestrate_rag_ingestion.py'
        )

        with open(tool_path, 'r') as f:
            content = f.read()

        # Look for the _call_rag_tool method where parameters are set
        self.assertIn('text=transcript_data["transcript_text"]', content,
                     "Should map transcript_text to 'text' parameter")

        # Verify there's a comment about RagIndexTranscript using 'text' parameter
        self.assertIn("RagIndexTranscript uses 'text' parameter", content,
                     "Should document that RagIndexTranscript uses 'text' not 'transcript_text'")

    def test_docstring_mentions_unified_wrapper(self):
        """
        Verify that docstrings mention the unified wrapper approach.
        """
        tool_path = os.path.join(
            os.path.dirname(__file__), '..', '..',
            'orchestrator_agent', 'tools', 'orchestrate_rag_ingestion.py'
        )

        with open(tool_path, 'r') as f:
            content = f.read()

        # Check docstrings mention new approach
        self.assertIn('TASK-RAG-0095', content,
                     "Should reference TASK-0095 in module docstring")
        self.assertIn('RagIndexTranscript wrapper', content,
                     "Should mention RagIndexTranscript wrapper in docstrings")
        self.assertIn('core library', content,
                     "Should mention core library delegation")


if __name__ == "__main__":
    unittest.main(verbosity=2)
