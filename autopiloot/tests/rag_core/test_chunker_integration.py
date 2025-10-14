"""
Integration tests for RAG chunker and hashing modules.

Tests the chunker.py and hashing.py modules with realistic data and edge cases.
"""

import unittest
import sys
import os

# Add core/rag to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from core.rag import chunker, hashing


class TestChunkerIntegration(unittest.TestCase):
    """Integration tests for text chunking module."""

    def setUp(self):
        """Set up test fixtures."""
        self.sample_text = """
        Welcome to this tutorial on building scalable SaaS businesses. Today we're going to talk about
        the key principles that separate successful founders from those who struggle. The first principle
        is understanding your unit economics. You need to know your customer acquisition cost, lifetime
        value, and payback period. These metrics form the foundation of your business model.

        The second principle is hiring A-players. Many founders make the mistake of hiring too quickly
        or settling for B-players because they're desperate to fill a role. This is a critical error.
        A-players attract other A-players, and they're 10x more productive than average employees.

        The third principle is building systems and processes before you need them. Document everything
        as you go. Create playbooks for every key function in your business. This allows you to scale
        without chaos and ensures quality as you grow.
        """ * 20  # Repeat to create longer text

    def test_chunk_text_basic(self):
        """Test basic text chunking with default parameters."""
        chunks = chunker.chunk_text(self.sample_text, max_tokens=500, overlap_tokens=50)

        self.assertIsInstance(chunks, list)
        self.assertGreater(len(chunks), 1)

        # Verify each chunk is within token limit
        for chunk in chunks:
            token_count = chunker.count_tokens(chunk)
            self.assertLessEqual(token_count, 500)

    def test_chunk_text_with_overlap(self):
        """Test that chunks have proper overlap."""
        chunks = chunker.chunk_text(self.sample_text, max_tokens=300, overlap_tokens=50)

        self.assertGreaterEqual(len(chunks), 2)

        # Check overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            chunk1_end = chunks[i][-100:]
            chunk2_start = chunks[i + 1][:100]

            # Some words from end of chunk1 should appear in start of chunk2
            words1 = set(chunk1_end.split())
            words2 = set(chunk2_start.split())
            overlap = words1.intersection(words2)

            self.assertGreater(len(overlap), 0, "No overlap detected between consecutive chunks")

    def test_chunk_text_empty_input(self):
        """Test chunking with empty input."""
        chunks = chunker.chunk_text("", max_tokens=500)
        self.assertEqual(chunks, [])

        chunks = chunker.chunk_text("   ", max_tokens=500)
        self.assertEqual(chunks, [])

    def test_chunk_text_short_text(self):
        """Test chunking with text shorter than max_tokens."""
        short_text = "This is a short text."
        chunks = chunker.chunk_text(short_text, max_tokens=1000)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], short_text)

    def test_count_tokens(self):
        """Test token counting."""
        test_cases = [
            ("Hello world", 2),
            ("", 0),
            ("The quick brown fox jumps over the lazy dog", 9)
        ]

        for text, expected_min_tokens in test_cases:
            token_count = chunker.count_tokens(text)
            # Token count should be at least the number of words (could be more due to tokenization)
            self.assertGreaterEqual(token_count, expected_min_tokens - 1)

    def test_chunk_with_metadata(self):
        """Test chunking with metadata."""
        chunks_with_meta = chunker.chunk_with_metadata(
            self.sample_text,
            max_tokens=500,
            overlap_tokens=50,
            doc_id="test_video_123"
        )

        self.assertIsInstance(chunks_with_meta, list)
        self.assertGreater(len(chunks_with_meta), 0)

        # Verify metadata structure
        for i, chunk_data in enumerate(chunks_with_meta):
            self.assertIn("text", chunk_data)
            self.assertIn("tokens", chunk_data)
            self.assertIn("chunk_index", chunk_data)
            self.assertIn("total_chunks", chunk_data)
            self.assertIn("chunk_id", chunk_data)

            # Verify chunk_index
            self.assertEqual(chunk_data["chunk_index"], i)

            # Verify total_chunks consistency
            self.assertEqual(chunk_data["total_chunks"], len(chunks_with_meta))

            # Verify chunk_id format
            self.assertEqual(chunk_data["chunk_id"], f"test_video_123_chunk_{i}")

    def test_chunk_consistency(self):
        """Test that chunking is deterministic."""
        chunks1 = chunker.chunk_text(self.sample_text, max_tokens=500, overlap_tokens=50)
        chunks2 = chunker.chunk_text(self.sample_text, max_tokens=500, overlap_tokens=50)

        self.assertEqual(len(chunks1), len(chunks2))
        for c1, c2 in zip(chunks1, chunks2):
            self.assertEqual(c1, c2)


class TestHashingIntegration(unittest.TestCase):
    """Integration tests for content hashing module."""

    def test_sha256_hex_basic(self):
        """Test basic SHA-256 hashing."""
        text = "hello world"
        hash_val = hashing.sha256_hex(text)

        self.assertIsInstance(hash_val, str)
        self.assertEqual(len(hash_val), 64)  # SHA-256 produces 64 hex characters

    def test_sha256_hex_consistency(self):
        """Test that hashing is deterministic."""
        text = "consistent text"
        hash1 = hashing.sha256_hex(text)
        hash2 = hashing.sha256_hex(text)

        self.assertEqual(hash1, hash2)

    def test_sha256_hex_uniqueness(self):
        """Test that similar texts produce different hashes."""
        texts = ["hello world", "hello world!", "hello world "]
        hashes = [hashing.sha256_hex(t) for t in texts]

        # All hashes should be unique
        self.assertEqual(len(set(hashes)), len(hashes))

    def test_hash_chunks(self):
        """Test hashing multiple chunks."""
        chunks = ["First chunk", "Second chunk", "Third chunk"]
        hashed = hashing.hash_chunks(chunks)

        self.assertEqual(len(hashed), len(chunks))

        for i, item in enumerate(hashed):
            self.assertIn("text", item)
            self.assertIn("hash", item)
            self.assertIn("index", item)

            self.assertEqual(item["text"], chunks[i])
            self.assertEqual(item["index"], i)
            self.assertEqual(len(item["hash"]), 64)

    def test_verify_hash(self):
        """Test hash verification."""
        text = "verify this text"
        correct_hash = hashing.sha256_hex(text)
        wrong_hash = hashing.sha256_hex("different text")

        self.assertTrue(hashing.verify_hash(text, correct_hash))
        self.assertFalse(hashing.verify_hash(text, wrong_hash))

    def test_detect_duplicates(self):
        """Test duplicate detection."""
        chunks = ["A", "B", "A", "C", "B", "D", "A"]
        duplicates = hashing.detect_duplicates(chunks)

        # Should find 2 duplicate groups: "A" and "B"
        self.assertEqual(len(duplicates), 2)

        # Find hash for "A" and verify indices
        hash_a = hashing.sha256_hex("A")
        self.assertIn(hash_a, duplicates)
        self.assertEqual(duplicates[hash_a], [0, 2, 6])

        # Find hash for "B" and verify indices
        hash_b = hashing.sha256_hex("B")
        self.assertIn(hash_b, duplicates)
        self.assertEqual(duplicates[hash_b], [1, 4])

    def test_deduplicate_chunks(self):
        """Test chunk deduplication."""
        chunks = ["A", "B", "A", "C", "B", "D"]
        unique = hashing.deduplicate_chunks(chunks)

        self.assertEqual(len(unique), 4)  # A, B, C, D
        self.assertEqual(unique, ["A", "B", "C", "D"])

    def test_deduplicate_preserves_order(self):
        """Test that deduplication preserves first occurrence order."""
        chunks = ["Z", "A", "B", "A", "C"]
        unique = hashing.deduplicate_chunks(chunks)

        self.assertEqual(unique, ["Z", "A", "B", "C"])


class TestChunkerHashingIntegration(unittest.TestCase):
    """Integration tests combining chunker and hashing."""

    def test_chunk_and_hash_workflow(self):
        """Test complete chunk + hash workflow."""
        sample_text = "This is a sample transcript. " * 100

        # Step 1: Chunk text
        chunks = chunker.chunk_text(sample_text, max_tokens=200, overlap_tokens=20)

        # Step 2: Hash chunks
        hashed_chunks = hashing.hash_chunks(chunks)

        # Verify workflow
        self.assertEqual(len(chunks), len(hashed_chunks))

        for i, hashed in enumerate(hashed_chunks):
            # Verify hash matches text
            self.assertTrue(hashing.verify_hash(hashed["text"], hashed["hash"]))

            # Verify index
            self.assertEqual(hashed["index"], i)

    def test_chunk_metadata_with_hashing(self):
        """Test chunk_with_metadata and hashing integration."""
        sample_text = "Sample content for testing. " * 50

        # Get chunks with metadata
        chunks_with_meta = chunker.chunk_with_metadata(
            sample_text,
            max_tokens=150,
            overlap_tokens=15,
            doc_id="video_abc123"
        )

        # Add hashes to metadata
        for chunk_data in chunks_with_meta:
            chunk_data["content_sha256"] = hashing.sha256_hex(chunk_data["text"])

        # Verify structure
        for chunk_data in chunks_with_meta:
            self.assertIn("text", chunk_data)
            self.assertIn("tokens", chunk_data)
            self.assertIn("chunk_id", chunk_data)
            self.assertIn("content_sha256", chunk_data)

            # Verify hash
            self.assertTrue(
                hashing.verify_hash(chunk_data["text"], chunk_data["content_sha256"])
            )

    def test_idempotency_via_hashing(self):
        """Test that identical chunks produce identical hashes (idempotency)."""
        text = "Identical content for idempotency testing."

        # Chunk twice
        chunks1 = chunker.chunk_text(text, max_tokens=50)
        chunks2 = chunker.chunk_text(text, max_tokens=50)

        # Hash both
        hashes1 = [hashing.sha256_hex(c) for c in chunks1]
        hashes2 = [hashing.sha256_hex(c) for c in chunks2]

        # Should be identical
        self.assertEqual(hashes1, hashes2)


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
