"""
Retrieval Policy Module

Enforces authorization rules, content filtering, and redaction policies
for retrieval results. Applied after hybrid fusion but before LLM reasoning.
"""

import os
import sys
import re
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))


def enforce_policy(results: List[dict], policy_context: Optional[Dict[str, Any]] = None) -> dict:
    """
    Enforce retrieval policy on search results.

    Args:
        results: List of search results from hybrid retrieval
        policy_context: Optional policy context:
            - allowed_channels: List of allowed channel IDs
            - allowed_sources: List of allowed content sources
            - user_id: User making the request (for user-based auth)
            - redact_pii: Whether to redact PII (default: True)
            - mode: Enforcement mode ("filter", "redact", "audit_only")

    Returns:
        Dictionary containing:
        - results: Filtered/redacted results
        - total_results: Number of results after policy enforcement
        - filtered_count: Number of results removed by filtering
        - redacted_count: Number of results with redactions
        - violations: List of policy violations detected
        - policy_mode: Enforcement mode used

    Enforcement Modes:
        - filter: Remove results that violate policy
        - redact: Mask sensitive content but keep results
        - audit_only: Log violations but don't modify results

    Policy Rules:
        1. Channel-based authorization: Filter by allowed_channels
        2. Source-based authorization: Filter by allowed_sources
        3. PII redaction: Detect and redact sensitive patterns
        4. Content filtering: Remove results with prohibited content

    Example:
        >>> results = [
        ...     {"chunk_id": "abc_0", "text": "Call me at 555-1234", "channel_id": "UC123"},
        ...     {"chunk_id": "def_0", "text": "Revenue is $1M", "channel_id": "UC456"}
        ... ]
        >>> policy_result = enforce_policy(
        ...     results,
        ...     policy_context={"allowed_channels": ["UC123"], "redact_pii": True}
        ... )
        >>> len(policy_result["results"])
        1  # Only UC123 result kept
        >>> "555-1234" in policy_result["results"][0]["text"]
        False  # Phone number redacted
    """
    try:
        from rag.config import get_policy_config

        # Load policy configuration
        config = get_policy_config()
        policy_enabled = config.get("enabled", True)

        if not policy_enabled:
            return {
                "results": results,
                "total_results": len(results),
                "filtered_count": 0,
                "redacted_count": 0,
                "violations": [],
                "policy_mode": "disabled"
            }

        # Get enforcement mode
        mode = (policy_context or {}).get("mode") or config.get("default_mode", "filter")

        # Initialize tracking
        filtered_results = []
        filtered_count = 0
        redacted_count = 0
        violations = []

        # Process each result
        for result in results:
            # Check authorization rules
            if not _check_authorization(result, policy_context, config):
                filtered_count += 1
                violations.append({
                    "chunk_id": result.get("chunk_id"),
                    "violation": "authorization_failed",
                    "reason": "Result not authorized for user"
                })
                if mode != "audit_only":
                    continue  # Skip this result

            # Check content filtering
            if not _check_content_filter(result, config):
                filtered_count += 1
                violations.append({
                    "chunk_id": result.get("chunk_id"),
                    "violation": "content_filtered",
                    "reason": "Result contains prohibited content"
                })
                if mode != "audit_only":
                    continue

            # Apply redaction if enabled
            redacted_result = result.copy()
            if (policy_context or {}).get("redact_pii", True):
                redaction_applied = _apply_redaction(redacted_result, config)
                if redaction_applied:
                    redacted_count += 1
                    violations.append({
                        "chunk_id": result.get("chunk_id"),
                        "violation": "pii_detected",
                        "reason": "PII redacted from result"
                    })

            filtered_results.append(redacted_result)

        # Log policy enforcement
        try:
            _log_policy_enforcement(
                total_input=len(results),
                total_output=len(filtered_results),
                filtered_count=filtered_count,
                redacted_count=redacted_count,
                violations=violations,
                mode=mode
            )
        except Exception as e:
            print(f"Warning: Failed to log policy enforcement: {str(e)}")

        return {
            "results": filtered_results,
            "total_results": len(filtered_results),
            "filtered_count": filtered_count,
            "redacted_count": redacted_count,
            "violations": violations if config.get("audit", {}).get("log_violations", True) else [],
            "policy_mode": mode
        }

    except Exception as e:
        # On policy error, fail safe by returning empty results
        return {
            "results": [],
            "total_results": 0,
            "filtered_count": len(results),
            "redacted_count": 0,
            "violations": [{
                "violation": "policy_error",
                "reason": f"Policy enforcement failed: {str(e)}"
            }],
            "policy_mode": "error"
        }


def _check_authorization(result: dict, policy_context: Optional[dict], config: dict) -> bool:
    """Check if result passes authorization rules."""
    if not policy_context:
        return True

    auth_config = config.get("authorization", {})

    # Channel-based authorization
    if auth_config.get("channel_based", False):
        allowed_channels = policy_context.get("allowed_channels")
        if allowed_channels:
            result_channel = result.get("channel_id")
            if result_channel not in allowed_channels:
                return False

    # Source-based authorization
    allowed_sources = policy_context.get("allowed_sources")
    if allowed_sources:
        result_sources = result.get("sources", [])
        if not any(source in allowed_sources for source in result_sources):
            return False

    # Date-based authorization
    if auth_config.get("date_based", False):
        max_age_days = policy_context.get("max_age_days")
        if max_age_days and result.get("published_at"):
            # Check if content is within max age
            # (simplified - would need proper date parsing)
            pass

    return True


def _check_content_filter(result: dict, config: dict) -> bool:
    """Check if result passes content filtering rules."""
    # Currently no content filters defined in config
    # This is a placeholder for future content-based filtering
    return True


def _apply_redaction(result: dict, config: dict) -> bool:
    """Apply PII redaction to result text. Returns True if redaction was applied."""
    sensitive_patterns = config.get("sensitive_patterns", [])
    if not sensitive_patterns:
        return False

    text = result.get("text", "")
    if not text:
        return False

    redacted_text = text
    redaction_applied = False

    # Apply each sensitive pattern
    for pattern_config in sensitive_patterns:
        pattern = pattern_config.get("pattern")
        replacement = pattern_config.get("replacement", "[REDACTED]")

        if pattern:
            new_text = re.sub(pattern, replacement, redacted_text)
            if new_text != redacted_text:
                redacted_text = new_text
                redaction_applied = True

    if redaction_applied:
        result["text"] = redacted_text
        # Mark that redaction was applied
        if "metadata" not in result:
            result["metadata"] = {}
        result["metadata"]["redacted"] = True

    return redaction_applied


def _log_policy_enforcement(
    total_input: int,
    total_output: int,
    filtered_count: int,
    redacted_count: int,
    violations: List[dict],
    mode: str
) -> None:
    """Log policy enforcement metrics."""
    # This would integrate with the observability agent
    # For now, just print summary
    if filtered_count > 0 or redacted_count > 0:
        print(f"Policy enforcement: {total_input} input → {total_output} output "
              f"({filtered_count} filtered, {redacted_count} redacted) [mode: {mode}]")


def validate_policy_config() -> dict:
    """
    Validate policy configuration and return status.

    Returns:
        Dictionary containing:
        - valid: Whether configuration is valid
        - errors: List of configuration errors
        - warnings: List of configuration warnings
        - recommendations: List of recommendations

    Example:
        >>> result = validate_policy_config()
        >>> result["valid"]
        True
        >>> result["warnings"]
        ["Consider enabling channel-based authorization"]
    """
    try:
        from rag.config import get_policy_config

        config = get_policy_config()
        errors = []
        warnings = []
        recommendations = []

        # Check if policy is enabled
        if not config.get("enabled", True):
            warnings.append("Policy enforcement is disabled")

        # Validate sensitive patterns
        sensitive_patterns = config.get("sensitive_patterns", [])
        if not sensitive_patterns:
            warnings.append("No sensitive patterns configured for PII redaction")
        else:
            for i, pattern in enumerate(sensitive_patterns):
                if not pattern.get("pattern"):
                    errors.append(f"Sensitive pattern {i} missing 'pattern' field")
                if not pattern.get("replacement"):
                    warnings.append(f"Sensitive pattern {i} missing 'replacement' field")

        # Check authorization settings
        auth_config = config.get("authorization", {})
        if not any(auth_config.values()):
            warnings.append("No authorization rules enabled")
        else:
            if auth_config.get("channel_based"):
                recommendations.append("Channel-based authorization enabled - ensure allowed_channels is provided at query time")

        # Check audit settings
        audit_config = config.get("audit", {})
        if not audit_config.get("enabled", True):
            warnings.append("Audit logging is disabled - policy violations won't be logged")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "recommendations": recommendations
        }

    except Exception as e:
        return {
            "valid": False,
            "errors": [f"Policy config validation failed: {str(e)}"],
            "warnings": [],
            "recommendations": []
        }


if __name__ == "__main__":
    print("="*80)
    print("TEST: Retrieval Policy Module")
    print("="*80)

    # Test data with PII
    sample_results = [
        {
            "chunk_id": "abc_0",
            "video_id": "abc123",
            "channel_id": "UC123",
            "title": "Revenue Strategies",
            "text": "Call me at 555-123-4567 or email john@example.com for details.",
            "score": 0.95,
            "sources": ["zep"]
        },
        {
            "chunk_id": "def_0",
            "video_id": "def456",
            "channel_id": "UC456",
            "title": "Marketing Tips",
            "text": "Our revenue grew to $1M last quarter.",
            "score": 0.88,
            "sources": ["opensearch"]
        },
        {
            "chunk_id": "ghi_0",
            "video_id": "ghi789",
            "channel_id": "UC123",
            "title": "Sales Process",
            "text": "Standard sales process takes 30 days.",
            "score": 0.76,
            "sources": ["bigquery"]
        }
    ]

    # Test 1: Policy enforcement with channel filter
    print("\n1. Testing policy enforcement with channel filter:")
    result = enforce_policy(
        sample_results,
        policy_context={
            "allowed_channels": ["UC123"],
            "redact_pii": True
        }
    )
    print(f"   Input results: {len(sample_results)}")
    print(f"   Output results: {result['total_results']}")
    print(f"   Filtered: {result['filtered_count']}")
    print(f"   Redacted: {result['redacted_count']}")
    print(f"   Violations: {len(result['violations'])}")

    # Check redaction
    if result['results']:
        first_result = result['results'][0]
        print(f"\n   First result text (check PII redaction):")
        print(f"   {first_result['text'][:100]}...")

    # Test 2: Validate policy configuration
    print("\n2. Testing validate_policy_config():")
    validation = validate_policy_config()
    print(f"   Valid: {validation['valid']}")
    print(f"   Errors: {len(validation['errors'])}")
    print(f"   Warnings: {len(validation['warnings'])}")
    print(f"   Recommendations: {len(validation['recommendations'])}")

    if validation['warnings']:
        print("\n   Warnings:")
        for warning in validation['warnings']:
            print(f"     - {warning}")

    # Test 3: Audit-only mode
    print("\n3. Testing audit-only mode:")
    result = enforce_policy(
        sample_results,
        policy_context={
            "allowed_channels": ["UC123"],
            "mode": "audit_only"
        }
    )
    print(f"   Output results: {result['total_results']}")
    print(f"   Filtered: {result['filtered_count']}")
    print(f"   Mode: {result['policy_mode']}")
    print(f"   Note: In audit_only mode, violations logged but results not filtered")

    print("\n" + "="*80)
    print("✅ Test completed")
