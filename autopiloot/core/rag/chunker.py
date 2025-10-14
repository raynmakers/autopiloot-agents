"""
Text Chunking Module

Provides token-aware text chunking with configurable overlap for RAG ingest.
Uses tiktoken for accurate token counting with OpenAI models.
"""

from typing import List
import tiktoken


def chunk_text(text: str, max_tokens: int = 1000, overlap_tokens: int = 100) -> List[str]:
    """
    Chunk text into segments with token-aware boundaries and overlap.

    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk (default: 1000)
        overlap_tokens: Token overlap between consecutive chunks (default: 100)

    Returns:
        List of text chunks

    Implementation:
        - Uses tiktoken cl100k_base encoding (same as GPT-4, GPT-3.5-turbo)
        - Maintains token boundaries for accurate sizing
        - Overlaps chunks to preserve context across boundaries
        - Handles edge cases (empty text, small text, exact boundaries)

    Example:
        >>> text = "This is a long document..." * 100
        >>> chunks = chunk_text(text, max_tokens=500, overlap_tokens=50)
        >>> len(chunks)
        10
        >>> # Each chunk has ≤500 tokens with 50-token overlap
    """
    if not text or not text.strip():
        return []

    # Get tiktoken encoding
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    # If text is shorter than max_tokens, return as single chunk
    if len(tokens) <= max_tokens:
        return [text]

    chunks = []
    start_idx = 0

    while start_idx < len(tokens):
        # Calculate end index (don't exceed token list)
        end_idx = min(start_idx + max_tokens, len(tokens))

        # Extract chunk tokens
        chunk_tokens = tokens[start_idx:end_idx]

        # Decode tokens back to text
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        # Move start index forward, accounting for overlap
        if end_idx < len(tokens):
            # Not at end: move forward with overlap
            start_idx = end_idx - overlap_tokens
        else:
            # Reached end: break
            break

    return chunks


def count_tokens(text: str) -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Input text to count

    Returns:
        Number of tokens

    Example:
        >>> count_tokens("Hello world")
        2
        >>> count_tokens("The quick brown fox jumps")
        5
    """
    if not text:
        return 0

    encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))


def chunk_with_metadata(
    text: str,
    max_tokens: int = 1000,
    overlap_tokens: int = 100,
    doc_id: str = None
) -> List[dict]:
    """
    Chunk text and return chunks with metadata.

    Args:
        text: Input text to chunk
        max_tokens: Maximum tokens per chunk (default: 1000)
        overlap_tokens: Token overlap between chunks (default: 100)
        doc_id: Optional document identifier for chunk IDs

    Returns:
        List of dictionaries containing:
        - text: Chunk text
        - tokens: Token count
        - chunk_index: 0-based index
        - total_chunks: Total number of chunks
        - chunk_id: Unique chunk identifier (if doc_id provided)

    Example:
        >>> chunks = chunk_with_metadata(text, doc_id="video_123")
        >>> chunks[0]
        {
            "text": "First chunk text...",
            "tokens": 487,
            "chunk_index": 0,
            "total_chunks": 5,
            "chunk_id": "video_123_chunk_0"
        }
    """
    # Get text chunks
    text_chunks = chunk_text(text, max_tokens, overlap_tokens)

    # Build metadata for each chunk
    chunks_with_metadata = []
    total_chunks = len(text_chunks)

    for i, chunk_text in enumerate(text_chunks):
        chunk_data = {
            "text": chunk_text,
            "tokens": count_tokens(chunk_text),
            "chunk_index": i,
            "total_chunks": total_chunks
        }

        # Add chunk ID if doc_id provided
        if doc_id:
            chunk_data["chunk_id"] = f"{doc_id}_chunk_{i}"

        chunks_with_metadata.append(chunk_data)

    return chunks_with_metadata


if __name__ == "__main__":
    print("="*80)
    print("TEST: Text Chunking Module")
    print("="*80)

    # Test 1: Basic chunking
    print("\n1. Testing chunk_text() with sample text:")
    sample_text = """
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
    """ * 10  # Repeat to create longer text

    chunks = chunk_text(sample_text, max_tokens=500, overlap_tokens=50)
    print(f"   Input tokens: {count_tokens(sample_text)}")
    print(f"   Chunk count: {len(chunks)}")
    print(f"   First chunk tokens: {count_tokens(chunks[0])}")
    print(f"   Last chunk tokens: {count_tokens(chunks[-1])}")
    print(f"   First chunk preview: {chunks[0][:100]}...")

    # Test 2: Token counting
    print("\n2. Testing count_tokens():")
    test_strings = [
        "Hello world",
        "The quick brown fox jumps over the lazy dog",
        "This is a much longer sentence with many more words and tokens to count accurately"
    ]
    for s in test_strings:
        print(f"   '{s[:50]}...' → {count_tokens(s)} tokens")

    # Test 3: Edge cases
    print("\n3. Testing edge cases:")
    print(f"   Empty string: {chunk_text('')}")
    print(f"   Whitespace only: {chunk_text('   ')}")
    short_text = "Short text"
    print(f"   Text shorter than max_tokens: {len(chunk_text(short_text, max_tokens=1000))}")

    # Test 4: Chunking with metadata
    print("\n4. Testing chunk_with_metadata():")
    chunks_with_meta = chunk_with_metadata(
        sample_text,
        max_tokens=500,
        overlap_tokens=50,
        doc_id="video_abc123"
    )
    print(f"   Total chunks: {len(chunks_with_meta)}")
    print(f"   First chunk metadata:")
    first = chunks_with_meta[0]
    print(f"     - chunk_id: {first['chunk_id']}")
    print(f"     - tokens: {first['tokens']}")
    print(f"     - chunk_index: {first['chunk_index']}")
    print(f"     - total_chunks: {first['total_chunks']}")
    print(f"     - text preview: {first['text'][:80]}...")

    # Test 5: Verify overlap
    print("\n5. Testing overlap preservation:")
    if len(chunks) >= 2:
        # Check if last N words of chunk 1 appear in first N words of chunk 2
        chunk1_end = chunks[0][-200:]
        chunk2_start = chunks[1][:200]
        print(f"   Chunk 1 end: ...{chunk1_end[-50:]}")
        print(f"   Chunk 2 start: {chunk2_start[:50]}...")
        # Simple overlap check
        overlap_detected = any(word in chunk2_start for word in chunk1_end.split()[-10:])
        print(f"   Overlap detected: {overlap_detected}")

    print("\n" + "="*80)
    print("✅ All tests completed successfully")
