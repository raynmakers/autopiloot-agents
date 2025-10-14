"""
DetectLeadMagnetPost tool for identifying LinkedIn lead magnet posts.

Lead magnet posts are those that ask readers to comment a specific word
to receive something (e.g., "Comment 'PDF' for the guide", "Drop YES below").

This tool uses regex-based heuristic patterns to detect common CTA phrases.
"""

import re
import json
from typing import List, Set, Optional
from agency_swarm.tools import BaseTool
from pydantic import Field


# Lead magnet detection patterns (compiled once for performance)
LEAD_MAGNET_PATTERNS = [
    # Pattern 1: "comment [word]" variants (must be direct CTA, not "let me know")
    (r"(?:^|\W)comment\s+[\"']?(yes|pdf|guide|template|ebook|playbook|checklist|access|link|download|free|info|details|dm|message)[\"']?", "comment_keyword"),

    # Pattern 2: "drop/type/reply [word]" variants
    (r"(?:drop|type|reply)\s+(?:the\s+word\s+)?[\"']?[a-zA-Z]{2,}[\"']?", "action_keyword"),

    # Pattern 3: "comment below" + trigger nouns
    (r"comment\s+below.*(?:guide|pdf|template|ebook|playbook|checklist|resource|file|document)", "comment_below_noun"),

    # Pattern 4: "comment to get/for" variants
    (r"comment\s+(?:to\s+get|for|and\s+(?:i'll|i\s+will)\s+send)", "comment_to_get"),

    # Pattern 5: "leave a comment" variants
    (r"leave\s+a\s+comment\s+(?:and|to|for)", "leave_comment"),

    # Pattern 6: Direct CTA with quotes
    (r"comment\s+[\"'][a-zA-Z]+[\"']", "comment_quoted_word"),

    # Pattern 7: "send you" variants (implicit lead magnet)
    (r"(?:i'll|i\s+will)\s+send\s+(?:you|it)", "send_promise"),

    # Pattern 8: "DM me" variants
    (r"(?:dm|message)\s+me\s+(?:the\s+word)?", "dm_request"),

    # Pattern 9: All caps trigger words
    (r"\b(?:YES|PDF|GUIDE|TEMPLATE|EBOOK|LINK|FREE|INFO|DM|ME)\b", "caps_trigger"),

    # Pattern 10: "interested" + explicit action (must have 'comment [word]' or 'dm me')
    (r"(?:interested|want).*(?:comment\s+[\"']?[a-z]+[\"']?|dm\s+me)", "interest_action"),
]

# Compile patterns once for performance
COMPILED_PATTERNS = [(re.compile(pattern, re.IGNORECASE), label) for pattern, label in LEAD_MAGNET_PATTERNS]


class DetectLeadMagnetPost(BaseTool):
    """
    Detects whether a LinkedIn post is a "lead magnet" post.

    Lead magnet posts typically contain calls-to-action asking readers to
    comment a specific word to receive something (guide, PDF, template, etc.).

    Uses regex-based heuristic patterns to identify common CTA phrases.
    Returns classification result with pattern matches and confidence score.
    """

    post_text: str = Field(
        ...,
        description="Raw LinkedIn post text to analyze"
    )

    comments_preview: List[str] = Field(
        default=[],
        description="Optional sample of early comments (helps detect comment-based CTAs)"
    )

    case_insensitive: bool = Field(
        default=True,
        description="Whether to normalize text case for matching (default: True)"
    )

    min_keyword_hit_threshold: int = Field(
        default=1,
        description="Minimum number of distinct pattern hits to classify as lead magnet (default: 1)"
    )

    def run(self) -> str:
        """
        Analyzes post text and comments to detect lead magnet patterns.

        Returns:
            str: JSON string with format:
                {
                    "is_lead_magnet": bool,
                    "confidence": float,  # 0.0-1.0
                    "hits": [str],        # List of matched pattern labels
                    "hit_count": int,
                    "matched_patterns": {
                        "pattern_label": ["matched text", ...]
                    }
                }
        """
        try:
            # Normalize text
            text_to_analyze = self._normalize_text(self.post_text)

            # Combine with comments preview if provided
            if self.comments_preview:
                comments_text = " ".join(self._normalize_text(c) for c in self.comments_preview)
                text_to_analyze = f"{text_to_analyze} {comments_text}"

            # Apply pattern matching
            matches = self._apply_patterns(text_to_analyze)

            # Count unique pattern types that matched
            unique_hits = list(matches.keys())
            hit_count = len(unique_hits)

            # Determine if this is a lead magnet
            is_lead_magnet = hit_count >= self.min_keyword_hit_threshold

            # Calculate confidence score (0.0-1.0)
            # More patterns matched = higher confidence
            # Max out at 5 patterns for 100% confidence
            confidence = min(hit_count / 5.0, 1.0)

            # Extract sample matched text for each pattern
            matched_patterns = {}
            for pattern_label, match_texts in matches.items():
                # Take first 3 unique matches per pattern
                matched_patterns[pattern_label] = list(set(match_texts))[:3]

            result = {
                "is_lead_magnet": is_lead_magnet,
                "confidence": round(confidence, 2),
                "hits": unique_hits,
                "hit_count": hit_count,
                "matched_patterns": matched_patterns
            }

            return json.dumps(result)

        except Exception as e:
            error_result = {
                "error": "detection_failed",
                "message": str(e),
                "is_lead_magnet": False,
                "confidence": 0.0,
                "hits": [],
                "hit_count": 0
            }
            return json.dumps(error_result)

    def _normalize_text(self, text: str) -> str:
        """
        Normalize text for pattern matching.

        Args:
            text: Raw text to normalize

        Returns:
            str: Normalized text
        """
        if not text:
            return ""

        # Remove extra whitespace
        normalized = " ".join(text.split())

        # Optionally lowercase
        if self.case_insensitive:
            normalized = normalized.lower()

        return normalized

    def _apply_patterns(self, text: str) -> dict:
        """
        Apply all compiled regex patterns to text.

        Args:
            text: Normalized text to search

        Returns:
            dict: Mapping of pattern_label -> [matched_text, ...]
        """
        matches = {}

        for pattern, label in COMPILED_PATTERNS:
            # Find all matches for this pattern
            pattern_matches = pattern.findall(text)

            if pattern_matches:
                # Handle both string and tuple results from findall
                if isinstance(pattern_matches[0], tuple):
                    # Pattern has groups - use full match
                    matched_texts = [match[0] if match else "" for match in pattern_matches]
                else:
                    matched_texts = pattern_matches

                # Store non-empty matches
                non_empty = [m for m in matched_texts if m]
                if non_empty:
                    matches[label] = non_empty

        return matches


if __name__ == "__main__":
    print("=" * 80)
    print("TEST: DetectLeadMagnetPost Tool")
    print("=" * 80)

    # Test Case 1: Obvious lead magnet
    print("\n[Test 1] Obvious lead magnet - 'Comment PDF'")
    tool = DetectLeadMagnetPost(
        post_text="Want my free guide? Comment 'PDF' below and I'll send it to you!",
        case_insensitive=True,
        min_keyword_hit_threshold=1
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == True, "Should detect lead magnet"
    print("✅ PASS")

    # Test Case 2: Drop keyword variant
    print("\n[Test 2] Drop keyword variant")
    tool = DetectLeadMagnetPost(
        post_text="Drop a YES below to get the template",
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == True, "Should detect lead magnet"
    print("✅ PASS")

    # Test Case 3: Negative - informative post
    print("\n[Test 3] Negative case - informative post")
    tool = DetectLeadMagnetPost(
        post_text="Here are 5 tips to improve your productivity. Hope this helps!",
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == False, "Should NOT detect lead magnet"
    print("✅ PASS")

    # Test Case 4: Comments-based detection
    print("\n[Test 4] Comments-based detection")
    tool = DetectLeadMagnetPost(
        post_text="I have something valuable for you all.",
        comments_preview=["Comment GUIDE to get access", "DM me for the link"],
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == True, "Should detect from comments"
    print("✅ PASS")

    # Test Case 5: Case sensitivity test
    print("\n[Test 5] Case sensitivity - ALL CAPS")
    tool = DetectLeadMagnetPost(
        post_text="COMMENT YES IF YOU WANT THE EBOOK",
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == True, "Should detect despite caps"
    print("✅ PASS")

    # Test Case 6: Weak phrasing (negative)
    print("\n[Test 6] Weak phrasing - no explicit CTA")
    tool = DetectLeadMagnetPost(
        post_text="What do you think about this? Let me know in the comments!",
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == False, "Should NOT detect weak phrasing"
    print("✅ PASS")

    # Test Case 7: Multiple patterns (high confidence)
    print("\n[Test 7] Multiple patterns - high confidence")
    tool = DetectLeadMagnetPost(
        post_text="Comment 'GUIDE' below and I'll send you the PDF template. DM me if interested!",
        case_insensitive=True
    )
    result = json.loads(tool.run())
    print(f"Result: {json.dumps(result, indent=2)}")
    assert result["is_lead_magnet"] == True, "Should detect with high confidence"
    assert result["confidence"] >= 0.4, f"Confidence should be >= 0.4, got {result['confidence']}"
    print("✅ PASS")

    print("\n" + "=" * 80)
    print("✅ All tests passed!")
    print("=" * 80)
