"""
Content Hashing Module

Provides SHA-256 hashing for content deduplication and idempotency.
Used across all RAG sinks for consistent chunk identification.
"""

import hashlib
from typing import List, Dict


def sha256_hex(s: str) -> str:
    """
    Generate SHA-256 hash of string as hex digest.

    Args:
        s: Input string to hash

    Returns:
        64-character hex string (SHA-256 hash)

    Example:
        >>> sha256_hex("hello world")
        'b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9'
        >>> sha256_hex("")
        'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
    """
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def sha256_bytes(s: str) -> bytes:
    """
    Generate SHA-256 hash of string as bytes.

    Args:
        s: Input string to hash

    Returns:
        32-byte SHA-256 hash

    Example:
        >>> hash_bytes = sha256_bytes("hello world")
        >>> len(hash_bytes)
        32
    """
    return hashlib.sha256(s.encode('utf-8')).digest()


def hash_chunks(chunks: List[str]) -> List[Dict[str, str]]:
    """
    Hash multiple text chunks and return chunk data with hashes.

    Args:
        chunks: List of text chunks

    Returns:
        List of dictionaries containing:
        - text: Original chunk text
        - hash: SHA-256 hex hash
        - index: 0-based chunk index

    Example:
        >>> chunks = ["First chunk", "Second chunk", "Third chunk"]
        >>> hashed = hash_chunks(chunks)
        >>> hashed[0]
        {
            'text': 'First chunk',
            'hash': '3d8b9...',
            'index': 0
        }
    """
    return [
        {
            "text": chunk,
            "hash": sha256_hex(chunk),
            "index": i
        }
        for i, chunk in enumerate(chunks)
    ]


def verify_hash(text: str, expected_hash: str) -> bool:
    """
    Verify that text matches expected SHA-256 hash.

    Args:
        text: Input text
        expected_hash: Expected SHA-256 hex hash

    Returns:
        True if hash matches, False otherwise

    Example:
        >>> text = "hello world"
        >>> hash_val = sha256_hex(text)
        >>> verify_hash(text, hash_val)
        True
        >>> verify_hash("different text", hash_val)
        False
    """
    actual_hash = sha256_hex(text)
    return actual_hash == expected_hash


def detect_duplicates(chunks: List[str]) -> Dict[str, List[int]]:
    """
    Detect duplicate chunks by hash.

    Args:
        chunks: List of text chunks

    Returns:
        Dictionary mapping hash → list of chunk indices with that hash

    Example:
        >>> chunks = ["text A", "text B", "text A", "text C"]
        >>> duplicates = detect_duplicates(chunks)
        >>> # Returns hash → [0, 2] for "text A"
    """
    hash_to_indices: Dict[str, List[int]] = {}

    for i, chunk in enumerate(chunks):
        chunk_hash = sha256_hex(chunk)
        if chunk_hash not in hash_to_indices:
            hash_to_indices[chunk_hash] = []
        hash_to_indices[chunk_hash].append(i)

    # Return only duplicates (hash appearing more than once)
    return {h: indices for h, indices in hash_to_indices.items() if len(indices) > 1}


def deduplicate_chunks(chunks: List[str]) -> List[str]:
    """
    Remove duplicate chunks based on content hash.

    Args:
        chunks: List of text chunks (may contain duplicates)

    Returns:
        List of unique chunks (preserves first occurrence order)

    Example:
        >>> chunks = ["A", "B", "A", "C", "B"]
        >>> deduplicate_chunks(chunks)
        ["A", "B", "C"]
    """
    seen_hashes = set()
    unique_chunks = []

    for chunk in chunks:
        chunk_hash = sha256_hex(chunk)
        if chunk_hash not in seen_hashes:
            seen_hashes.add(chunk_hash)
            unique_chunks.append(chunk)

    return unique_chunks


if __name__ == "__main__":
    print("="*80)
    print("TEST: Content Hashing Module")
    print("="*80)

    # Test 1: Basic hashing
    print("\n1. Testing sha256_hex():")
    test_strings = [
        "hello world",
        "The quick brown fox",
        "",
        "A" * 1000  # Long string
    ]
    for s in test_strings:
        hash_val = sha256_hex(s)
        preview = s[:30] + "..." if len(s) > 30 else s
        print(f"   '{preview}' → {hash_val[:16]}...")

    # Test 2: Hash consistency
    print("\n2. Testing hash consistency:")
    text = "consistent text"
    hash1 = sha256_hex(text)
    hash2 = sha256_hex(text)
    print(f"   Text: '{text}'")
    print(f"   Hash 1: {hash1}")
    print(f"   Hash 2: {hash2}")
    print(f"   Consistent: {hash1 == hash2}")

    # Test 3: Hash uniqueness
    print("\n3. Testing hash uniqueness:")
    similar_texts = ["hello world", "hello world!", "hello world "]
    hashes = [sha256_hex(t) for t in similar_texts]
    print(f"   Texts: {similar_texts}")
    print(f"   All unique hashes: {len(set(hashes)) == len(hashes)}")
    for i, (text, hash_val) in enumerate(zip(similar_texts, hashes)):
        print(f"   {i+1}. '{text}' → {hash_val[:16]}...")

    # Test 4: Hash multiple chunks
    print("\n4. Testing hash_chunks():")
    chunks = ["First chunk", "Second chunk", "Third chunk"]
    hashed = hash_chunks(chunks)
    print(f"   Input chunks: {len(chunks)}")
    print(f"   Hashed results: {len(hashed)}")
    for item in hashed:
        print(f"   [{item['index']}] '{item['text']}' → {item['hash'][:16]}...")

    # Test 5: Verify hash
    print("\n5. Testing verify_hash():")
    text = "verify this text"
    correct_hash = sha256_hex(text)
    wrong_hash = sha256_hex("different text")
    print(f"   Text: '{text}'")
    print(f"   Verify with correct hash: {verify_hash(text, correct_hash)}")
    print(f"   Verify with wrong hash: {verify_hash(text, wrong_hash)}")

    # Test 6: Detect duplicates
    print("\n6. Testing detect_duplicates():")
    chunks_with_dups = ["A", "B", "A", "C", "B", "D", "A"]
    duplicates = detect_duplicates(chunks_with_dups)
    print(f"   Chunks: {chunks_with_dups}")
    print(f"   Duplicate groups: {len(duplicates)}")
    for hash_val, indices in duplicates.items():
        text = chunks_with_dups[indices[0]]
        print(f"   '{text}' appears at indices: {indices}")

    # Test 7: Deduplicate chunks
    print("\n7. Testing deduplicate_chunks():")
    chunks_with_dups = ["A", "B", "A", "C", "B", "D"]
    unique = deduplicate_chunks(chunks_with_dups)
    print(f"   Original: {chunks_with_dups} ({len(chunks_with_dups)} items)")
    print(f"   Unique: {unique} ({len(unique)} items)")

    # Test 8: Bytes hashing
    print("\n8. Testing sha256_bytes():")
    text = "bytes test"
    hash_bytes = sha256_bytes(text)
    print(f"   Text: '{text}'")
    print(f"   Hash bytes length: {len(hash_bytes)}")
    print(f"   Hash hex: {hash_bytes.hex()[:16]}...")

    print("\n" + "="*80)
    print("✅ All tests completed successfully")
