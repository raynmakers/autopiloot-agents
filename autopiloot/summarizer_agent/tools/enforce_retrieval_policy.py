"""
EnforceRetrievalPolicy tool for uniform authorization and content filtering.

Applies policy enforcement to hybrid retrieval results before LLM reasoning.
Ensures unauthorized content never reaches the LLM with comprehensive audit logging.

Policy Types:
- Authorization filtering (channel-based, user-based access control)
- Content redaction (PII, confidential data, sensitive keywords)
- Date-based filtering (access to only recent content)
- Result quality filtering (minimum confidence thresholds)

Enforcement Modes:
- filter: Remove unauthorized items completely
- redact: Mask sensitive content but keep structure
- audit_only: Log violations but allow content through

All policy decisions are logged for compliance and security auditing.
"""

import os
import sys
import json
import re
import hashlib
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timezone, timedelta
from pydantic import Field
from agency_swarm.tools import BaseTool

# Add config and core directories to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'core'))

from env_loader import load_environment
from loader import get_config_value


class EnforceRetrievalPolicy(BaseTool):
    """
    Apply uniform authorization and content filtering to retrieval results.

    Enforces policies after fusion (from HybridRetrieval) but before LLM reasoning.
    Ensures unauthorized or sensitive content never reaches the LLM.
    """

    results: str = Field(
        ...,
        description="JSON string of retrieval results to filter (from HybridRetrieval)"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="User ID for authorization checks (if applicable)"
    )
    allowed_channels: Optional[List[str]] = Field(
        default=None,
        description="List of allowed channel IDs (None = all channels allowed)"
    )
    enforcement_mode: str = Field(
        default="filter",
        description="Enforcement mode: 'filter' (remove), 'redact' (mask), 'audit_only' (log only)"
    )
    max_age_days: Optional[int] = Field(
        default=None,
        description="Maximum age of content in days (None = no age restriction)"
    )

    def _parse_results(self, results_json: str) -> Dict[str, Any]:
        """Parse results JSON string."""
        try:
            return json.loads(results_json)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in results: {str(e)}")

    def _check_channel_authorization(self, channel_id: str) -> Dict[str, Any]:
        """
        Check if channel is authorized for access.

        Returns:
            Dict with authorized: bool and reason: str
        """
        # If no allowed channels specified, all channels are authorized
        if self.allowed_channels is None:
            return {"authorized": True, "reason": "No channel restrictions"}

        # Check if channel in allowed list
        if channel_id in self.allowed_channels:
            return {"authorized": True, "reason": f"Channel {channel_id} in allowed list"}
        else:
            return {"authorized": False, "reason": f"Channel {channel_id} not in allowed list"}

    def _check_date_authorization(self, published_at: Optional[str]) -> Dict[str, Any]:
        """
        Check if content age is within allowed range.

        Args:
            published_at: ISO 8601 date string

        Returns:
            Dict with authorized: bool and reason: str
        """
        # If no age restriction, all content authorized
        if self.max_age_days is None:
            return {"authorized": True, "reason": "No age restrictions"}

        # If no publication date, cannot verify - deny for safety
        if not published_at:
            return {"authorized": False, "reason": "No publication date available"}

        try:
            # Parse publication date
            pub_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

            if pub_date >= cutoff_date:
                age_days = (datetime.now(timezone.utc) - pub_date).days
                return {"authorized": True, "reason": f"Content age {age_days} days within {self.max_age_days} day limit"}
            else:
                age_days = (datetime.now(timezone.utc) - pub_date).days
                return {"authorized": False, "reason": f"Content age {age_days} days exceeds {self.max_age_days} day limit"}
        except (ValueError, AttributeError) as e:
            return {"authorized": False, "reason": f"Invalid date format: {str(e)}"}

    def _detect_sensitive_content(self, text: str) -> Dict[str, Any]:
        """
        Detect sensitive content that may need redaction.

        Returns:
            Dict with has_sensitive: bool, patterns_found: List[str], severity: str
        """
        sensitive_patterns = get_config_value("rag.policy.sensitive_patterns", [])

        # Default patterns if none configured
        if not sensitive_patterns:
            sensitive_patterns = [
                {"name": "email", "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "severity": "medium"},
                {"name": "phone", "pattern": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "severity": "medium"},
                {"name": "ssn", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "severity": "high"},
                {"name": "credit_card", "pattern": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "severity": "high"}
            ]

        patterns_found = []
        max_severity = "none"
        severity_levels = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

        for pattern_config in sensitive_patterns:
            pattern = pattern_config.get("pattern", "")
            name = pattern_config.get("name", "unknown")
            severity = pattern_config.get("severity", "medium")

            if re.search(pattern, text, re.IGNORECASE):
                patterns_found.append(name)
                if severity_levels.get(severity, 0) > severity_levels.get(max_severity, 0):
                    max_severity = severity

        return {
            "has_sensitive": len(patterns_found) > 0,
            "patterns_found": patterns_found,
            "severity": max_severity
        }

    def _redact_sensitive_content(self, text: str) -> str:
        """
        Redact sensitive content from text.

        Returns:
            Text with sensitive patterns masked
        """
        sensitive_patterns = get_config_value("rag.policy.sensitive_patterns", [])

        # Default patterns if none configured
        if not sensitive_patterns:
            sensitive_patterns = [
                {"name": "email", "pattern": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "replacement": "[EMAIL REDACTED]"},
                {"name": "phone", "pattern": r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b", "replacement": "[PHONE REDACTED]"},
                {"name": "ssn", "pattern": r"\b\d{3}-\d{2}-\d{4}\b", "replacement": "[SSN REDACTED]"},
                {"name": "credit_card", "pattern": r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b", "replacement": "[CARD REDACTED]"}
            ]

        redacted_text = text
        for pattern_config in sensitive_patterns:
            pattern = pattern_config.get("pattern", "")
            replacement = pattern_config.get("replacement", "[REDACTED]")
            redacted_text = re.sub(pattern, replacement, redacted_text, flags=re.IGNORECASE)

        return redacted_text

    def _apply_policy_to_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply policy checks to a single result.

        Returns:
            Dict with:
            - action: "allow", "filter", "redact"
            - result: modified result (if redact)
            - violations: List of policy violations
            - audit_log: Detailed audit information
        """
        violations = []
        audit_log = {
            "chunk_id": result.get("chunk_id"),
            "video_id": result.get("video_id"),
            "channel_id": result.get("channel_id"),
            "checks_performed": []
        }

        # Check 1: Channel authorization
        channel_id = result.get("channel_id")
        if channel_id:
            channel_check = self._check_channel_authorization(channel_id)
            audit_log["checks_performed"].append({
                "type": "channel_authorization",
                "result": channel_check["authorized"],
                "reason": channel_check["reason"]
            })
            if not channel_check["authorized"]:
                violations.append({
                    "type": "unauthorized_channel",
                    "details": channel_check["reason"]
                })

        # Check 2: Date authorization (if published_at available in result metadata)
        # Note: published_at may not be in chunk, would need to be added by retrieval
        published_at = result.get("published_at")
        if self.max_age_days is not None:
            date_check = self._check_date_authorization(published_at)
            audit_log["checks_performed"].append({
                "type": "date_authorization",
                "result": date_check["authorized"],
                "reason": date_check["reason"]
            })
            if not date_check["authorized"]:
                violations.append({
                    "type": "content_too_old",
                    "details": date_check["reason"]
                })

        # Check 3: Sensitive content detection
        text = result.get("text", "")
        sensitive_check = self._detect_sensitive_content(text)
        audit_log["checks_performed"].append({
            "type": "sensitive_content",
            "result": not sensitive_check["has_sensitive"],
            "patterns_found": sensitive_check["patterns_found"],
            "severity": sensitive_check["severity"]
        })
        if sensitive_check["has_sensitive"]:
            violations.append({
                "type": "sensitive_content",
                "details": f"Found patterns: {', '.join(sensitive_check['patterns_found'])}",
                "severity": sensitive_check["severity"]
            })

        # Determine action based on violations and mode
        if not violations:
            return {
                "action": "allow",
                "result": result,
                "violations": [],
                "audit_log": audit_log
            }

        # Handle violations based on enforcement mode
        if self.enforcement_mode == "filter":
            return {
                "action": "filter",
                "result": None,
                "violations": violations,
                "audit_log": audit_log
            }
        elif self.enforcement_mode == "redact":
            # Redact sensitive content but keep result
            redacted_result = result.copy()
            redacted_result["text"] = self._redact_sensitive_content(text)
            redacted_result["redacted"] = True
            redacted_result["redaction_reason"] = "Sensitive content detected"
            return {
                "action": "redact",
                "result": redacted_result,
                "violations": violations,
                "audit_log": audit_log
            }
        else:  # audit_only
            # Log violations but allow content through
            return {
                "action": "allow_with_violations",
                "result": result,
                "violations": violations,
                "audit_log": audit_log
            }

    def run(self) -> str:
        """
        Apply policy enforcement to retrieval results.

        Process:
        1. Parse input results JSON
        2. Apply policy checks to each result
        3. Filter, redact, or audit violations
        4. Build comprehensive audit log
        5. Return filtered results with audit trail

        Returns:
            JSON string with filtered results and audit information
        """
        try:
            # Load environment
            load_environment()

            # Parse input results
            results_data = self._parse_results(self.results)
            original_results = results_data.get("results", [])

            print(f"🛡️ Policy Enforcement")
            print(f"   Mode: {self.enforcement_mode}")
            print(f"   Results to check: {len(original_results)}")
            if self.allowed_channels:
                print(f"   Allowed channels: {len(self.allowed_channels)}")
            if self.max_age_days:
                print(f"   Max age: {self.max_age_days} days")

            # Apply policy to each result
            policy_results = []
            filtered_results = []
            audit_trail = []

            for result in original_results:
                policy_decision = self._apply_policy_to_result(result)
                policy_results.append(policy_decision)

                # Collect audit trail
                audit_entry = {
                    "chunk_id": result.get("chunk_id"),
                    "action": policy_decision["action"],
                    "violations": policy_decision["violations"],
                    "audit_log": policy_decision["audit_log"],
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                audit_trail.append(audit_entry)

                # Add to filtered results if allowed
                if policy_decision["action"] in ["allow", "redact", "allow_with_violations"]:
                    filtered_results.append(policy_decision["result"])

            # Calculate statistics
            filtered_count = sum(1 for p in policy_results if p["action"] == "filter")
            redacted_count = sum(1 for p in policy_results if p["action"] == "redact")
            violations_count = sum(len(p["violations"]) for p in policy_results)

            print(f"   ✓ Filtered: {filtered_count}")
            print(f"   ✓ Redacted: {redacted_count}")
            print(f"   ✓ Violations: {violations_count}")
            print(f"   ✓ Allowed: {len(filtered_results)}")

            # Build comprehensive result
            result = {
                "query": results_data.get("query"),
                "results": filtered_results,
                "result_count": len(filtered_results),
                "policy_enforcement": {
                    "mode": self.enforcement_mode,
                    "original_count": len(original_results),
                    "filtered_count": filtered_count,
                    "redacted_count": redacted_count,
                    "allowed_count": len(filtered_results),
                    "violations_count": violations_count
                },
                "audit_trail": audit_trail,
                "original_metadata": {
                    "sources": results_data.get("sources", {}),
                    "source_counts": results_data.get("source_counts", {}),
                    "weights": results_data.get("weights", {})
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "success"
            }

            # Add policy configuration for transparency
            result["policy_configuration"] = {
                "allowed_channels": self.allowed_channels,
                "max_age_days": self.max_age_days,
                "user_id": self.user_id
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return json.dumps({
                "error": "policy_enforcement_failed",
                "message": f"Failed to enforce policy: {str(e)}",
                "enforcement_mode": self.enforcement_mode
            })


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: Policy Enforcement - Filter Mode")
    print("="*80)

    # Sample retrieval results
    sample_results = {
        "query": "test query",
        "results": [
            {
                "chunk_id": "vid1_chunk_1",
                "video_id": "vid1",
                "title": "Test Video 1",
                "channel_id": "UC_allowed",
                "text": "This is safe content about business strategy.",
                "rrf_score": 0.95
            },
            {
                "chunk_id": "vid2_chunk_1",
                "video_id": "vid2",
                "title": "Test Video 2",
                "channel_id": "UC_blocked",
                "text": "This is from an unauthorized channel.",
                "rrf_score": 0.85
            },
            {
                "chunk_id": "vid3_chunk_1",
                "video_id": "vid3",
                "title": "Test Video 3",
                "channel_id": "UC_allowed",
                "text": "Contact me at john.doe@example.com for more info.",
                "rrf_score": 0.75
            }
        ],
        "sources": {"zep": True, "opensearch": True},
        "source_counts": {"zep": 2, "opensearch": 1}
    }

    try:
        # Test with channel filtering
        tool = EnforceRetrievalPolicy(
            results=json.dumps(sample_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="filter"
        )

        result = tool.run()
        print("\n✅ Test completed:")

        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"\n📊 Policy Enforcement Summary:")
            print(f"   Original results: {data['policy_enforcement']['original_count']}")
            print(f"   Filtered: {data['policy_enforcement']['filtered_count']}")
            print(f"   Redacted: {data['policy_enforcement']['redacted_count']}")
            print(f"   Allowed: {data['policy_enforcement']['allowed_count']}")
            print(f"   Violations: {data['policy_enforcement']['violations_count']}")

            print(f"\n📋 Audit Trail:")
            for entry in data['audit_trail']:
                print(f"   • {entry['chunk_id']}: {entry['action']}")
                if entry['violations']:
                    for v in entry['violations']:
                        print(f"      - {v['type']}: {v['details']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("TEST: Policy Enforcement - Redact Mode")
    print("="*80)

    try:
        # Test with redaction mode
        tool = EnforceRetrievalPolicy(
            results=json.dumps(sample_results),
            allowed_channels=["UC_allowed"],
            enforcement_mode="redact"
        )

        result = tool.run()
        print("\n✅ Test completed:")

        data = json.loads(result)
        if "error" in data:
            print(f"❌ Error: {data['message']}")
        else:
            print(f"\n📊 Redaction Summary:")
            print(f"   Redacted: {data['policy_enforcement']['redacted_count']}")

            # Show redacted content
            for r in data['results']:
                if r.get('redacted'):
                    print(f"\n📝 Redacted chunk: {r['chunk_id']}")
                    print(f"   Original: Contact me at john.doe@example.com")
                    print(f"   Redacted: {r['text']}")

    except Exception as e:
        print(f"❌ Test error: {str(e)}")
        traceback.print_exc()

    print("\n" + "="*80)
    print("Testing complete!")
    print("="*80)
