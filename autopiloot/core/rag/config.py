"""
RAG Configuration Module

Provides centralized access to RAG-specific configuration from settings.yaml.
All configuration keys are resolved under the `rag.*` namespace.
"""

import os
import sys
from typing import Any, Optional

# Add config directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'config'))

from loader import get_config_value as _get_config_value


def get_rag_flag(key: str, default: bool = False) -> bool:
    """
    Get a boolean flag from RAG configuration.

    Args:
        key: Configuration key under `rag.*` namespace (e.g., "sinks.opensearch.enabled")
        default: Default value if key not found (default: False)

    Returns:
        Boolean configuration value

    Example:
        >>> get_rag_flag("sinks.opensearch.enabled", False)
        True
    """
    full_key = f"rag.{key}"
    value = _get_config_value(full_key, default)
    return bool(value)


def get_rag_value(key: str, default: Any = None) -> Any:
    """
    Get a configuration value from RAG configuration.

    Args:
        key: Configuration key under `rag.*` namespace (e.g., "chunking.max_tokens")
        default: Default value if key not found (default: None)

    Returns:
        Configuration value (can be any type: str, int, float, dict, list, etc.)

    Example:
        >>> get_rag_value("chunking.max_tokens", 1000)
        1000
        >>> get_rag_value("opensearch.host")
        "https://opensearch.example.com"
    """
    full_key = f"rag.{key}"
    return _get_config_value(full_key, default)


def get_sink_config(sink_name: str) -> dict:
    """
    Get complete configuration for a specific sink.

    Args:
        sink_name: Sink name (e.g., "opensearch", "bigquery", "zep")

    Returns:
        Dictionary containing all sink configuration

    Example:
        >>> config = get_sink_config("opensearch")
        >>> config["enabled"]
        True
        >>> config["host"]
        "https://opensearch.example.com"
    """
    return get_rag_value(sink_name, {})


def is_sink_enabled(sink_name: str) -> bool:
    """
    Check if a specific sink is enabled.

    Args:
        sink_name: Sink name (e.g., "opensearch", "bigquery", "zep")

    Returns:
        True if sink is enabled, False otherwise

    Example:
        >>> is_sink_enabled("opensearch")
        True
        >>> is_sink_enabled("bigquery")
        False
    """
    return get_rag_flag(f"{sink_name}.enabled", False)


def get_chunking_config() -> dict:
    """
    Get chunking configuration.

    Returns:
        Dictionary containing chunking parameters:
        - max_tokens_per_chunk: Maximum tokens per chunk
        - overlap_tokens: Token overlap between chunks
        - strategy: Chunking strategy ("token_aware" or "paragraph")

    Example:
        >>> config = get_chunking_config()
        >>> config["max_tokens_per_chunk"]
        1000
        >>> config["overlap_tokens"]
        100
    """
    return {
        "max_tokens_per_chunk": get_rag_value("zep.transcripts.chunking.max_tokens_per_chunk", 1000),
        "overlap_tokens": get_rag_value("zep.transcripts.chunking.overlap_tokens", 100),
        "strategy": get_rag_value("zep.transcripts.chunking.strategy", "token_aware")
    }


def get_retrieval_config() -> dict:
    """
    Get retrieval configuration.

    Returns:
        Dictionary containing retrieval parameters:
        - top_k: Number of results to retrieve per source
        - timeout_ms: Timeout per source in milliseconds
        - weights: Fusion weights for semantic, keyword, sql sources

    Example:
        >>> config = get_retrieval_config()
        >>> config["top_k"]
        20
        >>> config["weights"]["semantic"]
        0.6
    """
    return {
        "top_k": get_rag_value("experiments.default_parameters.retrieval.top_k", 20),
        "timeout_ms": get_rag_value("experiments.default_parameters.retrieval.timeout_ms", 2000),
        "weights": get_rag_value("experiments.default_parameters.weights", {
            "semantic": 0.6,
            "keyword": 0.3,
            "sql": 0.1
        })
    }


def get_observability_config() -> dict:
    """
    Get observability configuration for tracing.

    Returns:
        Dictionary containing observability settings:
        - enabled: Whether observability is enabled
        - trace_all_requests: Whether to trace all requests
        - latency: Latency thresholds
        - error_rates: Error rate thresholds
        - coverage: Coverage thresholds

    Example:
        >>> config = get_observability_config()
        >>> config["enabled"]
        True
        >>> config["latency"]["slow_path_threshold_ms"]
        1000
    """
    return {
        "enabled": get_rag_flag("observability.enabled", True),
        "trace_all_requests": get_rag_flag("observability.trace_all_requests", True),
        "latency": {
            "slow_path_threshold_ms": get_rag_value("observability.latency.slow_path_threshold_ms", 1000),
            "alert_p95_threshold_ms": get_rag_value("observability.latency.alert_p95_threshold_ms", 2000),
            "alert_max_threshold_ms": get_rag_value("observability.latency.alert_max_threshold_ms", 5000)
        },
        "error_rates": {
            "warning_threshold": get_rag_value("observability.error_rates.warning_threshold", 25),
            "critical_threshold": get_rag_value("observability.error_rates.critical_threshold", 50),
            "track_per_source": get_rag_flag("observability.error_rates.track_per_source", True)
        },
        "coverage": {
            "warning_threshold": get_rag_value("observability.coverage.warning_threshold", 67),
            "critical_threshold": get_rag_value("observability.coverage.critical_threshold", 33),
            "track_source_availability": get_rag_flag("observability.coverage.track_source_availability", True)
        }
    }


def get_policy_config() -> dict:
    """
    Get retrieval policy configuration.

    Returns:
        Dictionary containing policy settings:
        - enabled: Whether policy enforcement is enabled
        - default_mode: Default enforcement mode ("filter", "redact", "audit_only")
        - sensitive_patterns: List of sensitive patterns to detect
        - authorization: Authorization rules

    Example:
        >>> config = get_policy_config()
        >>> config["enabled"]
        True
        >>> config["default_mode"]
        "filter"
    """
    return {
        "enabled": get_rag_flag("policy.enabled", True),
        "default_mode": get_rag_value("policy.default_mode", "filter"),
        "sensitive_patterns": get_rag_value("policy.sensitive_patterns", []),
        "authorization": get_rag_value("policy.authorization", {})
    }


if __name__ == "__main__":
    print("="*80)
    print("TEST: RAG Configuration Module")
    print("="*80)

    print("\n1. Testing get_rag_flag():")
    print(f"   opensearch.enabled: {get_rag_flag('opensearch.enabled', False)}")
    print(f"   bigquery.enabled: {get_rag_flag('bigquery.enabled', False)}")
    print(f"   zep.transcripts.enabled: {get_rag_flag('zep.transcripts.enabled', False)}")

    print("\n2. Testing get_rag_value():")
    print(f"   opensearch.index_transcripts: {get_rag_value('opensearch.index_transcripts', 'default')}")
    print(f"   bigquery.dataset: {get_rag_value('bigquery.dataset', 'default')}")

    print("\n3. Testing is_sink_enabled():")
    print(f"   opensearch: {is_sink_enabled('opensearch')}")
    print(f"   bigquery: {is_sink_enabled('bigquery')}")
    print(f"   zep: {is_sink_enabled('zep')}")

    print("\n4. Testing get_chunking_config():")
    chunking = get_chunking_config()
    print(f"   max_tokens_per_chunk: {chunking['max_tokens_per_chunk']}")
    print(f"   overlap_tokens: {chunking['overlap_tokens']}")
    print(f"   strategy: {chunking['strategy']}")

    print("\n5. Testing get_retrieval_config():")
    retrieval = get_retrieval_config()
    print(f"   top_k: {retrieval['top_k']}")
    print(f"   timeout_ms: {retrieval['timeout_ms']}")
    print(f"   weights: {retrieval['weights']}")

    print("\n6. Testing get_observability_config():")
    obs = get_observability_config()
    print(f"   enabled: {obs['enabled']}")
    print(f"   trace_all_requests: {obs['trace_all_requests']}")
    print(f"   slow_path_threshold_ms: {obs['latency']['slow_path_threshold_ms']}")

    print("\n7. Testing get_policy_config():")
    policy = get_policy_config()
    print(f"   enabled: {policy['enabled']}")
    print(f"   default_mode: {policy['default_mode']}")

    print("\n" + "="*80)
    print("✅ All tests completed successfully")
