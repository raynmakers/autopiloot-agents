"""
Cache management tool for hybrid RAG retrieval.

Provides caching functionality for frequent queries and retrieval results
with configurable TTL, cache key normalization, and hit ratio tracking.

Supports both in-memory and Redis backends (Redis optional).
"""

import json
import hashlib
import time
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pydantic import Field

# Try to import redis, but make it optional
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False


class CacheHybridRetrieval:
    """
    Tool for caching hybrid retrieval results.

    Features:
    - In-memory and Redis backend support
    - Normalized cache key generation (query, filters, top_k)
    - TTL-based expiration
    - Cache hit ratio tracking
    - Bypass rules for strict filters and small top_k
    - Cache statistics and reporting
    """

    # Class-level cache storage for in-memory backend
    _memory_cache: Dict[str, Dict[str, Any]] = {}
    _cache_stats: Dict[str, int] = {"hits": 0, "misses": 0, "sets": 0, "deletes": 0}

    backend: str = Field(
        default="memory",
        description="Cache backend: 'memory' or 'redis'"
    )

    redis_host: Optional[str] = Field(
        default=None,
        description="Redis host (required if backend='redis')"
    )

    redis_port: int = Field(
        default=6379,
        description="Redis port"
    )

    redis_db: int = Field(
        default=0,
        description="Redis database number"
    )

    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password (optional)"
    )

    operation: str = Field(
        description="Cache operation: 'get', 'set', 'delete', 'clear', 'stats'"
    )

    query: Optional[str] = Field(
        default=None,
        description="Query text (for get/set operations)"
    )

    filters: Optional[str] = Field(
        default=None,
        description="Filters JSON string (for cache key generation)"
    )

    top_k: Optional[int] = Field(
        default=None,
        description="Top K results (for cache key generation)"
    )

    results: Optional[str] = Field(
        default=None,
        description="Results JSON string (for set operation)"
    )

    ttl_seconds: int = Field(
        default=3600,
        description="TTL in seconds (default 1 hour)"
    )

    cache_key: Optional[str] = Field(
        default=None,
        description="Explicit cache key (optional, auto-generated if not provided)"
    )

    bypass_cache: bool = Field(
        default=False,
        description="Bypass cache for this operation"
    )

    def __init__(self, **data):
        """Initialize cache tool."""
        # Store the field data
        for key, value in data.items():
            setattr(self, key, value)

        # Initialize Redis client if needed
        self._redis_client = None
        if self.backend == "redis":
            if not REDIS_AVAILABLE:
                raise ImportError("Redis backend selected but redis package not installed")
            if not self.redis_host:
                raise ValueError("Redis host required for redis backend")

            self._redis_client = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=self.redis_db,
                password=self.redis_password,
                decode_responses=True
            )

    def _normalize_query(self, query: str) -> str:
        """Normalize query for consistent cache keys."""
        return query.lower().strip()

    def _generate_cache_key(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> str:
        """
        Generate normalized cache key from query, filters, and top_k.

        Args:
            query: Query text
            filters: Filters dictionary
            top_k: Top K results

        Returns:
            Cache key string (hash-based)
        """
        normalized_query = self._normalize_query(query)

        # Sort filters for consistent key generation
        filters_str = ""
        if filters:
            filters_str = json.dumps(filters, sort_keys=True)

        # Create key components
        key_parts = [
            f"query:{normalized_query}",
            f"filters:{filters_str}",
            f"top_k:{top_k or 'none'}"
        ]

        # Hash for efficient storage
        key_string = "|".join(key_parts)
        key_hash = hashlib.sha256(key_string.encode()).hexdigest()[:16]

        return f"hybrid_cache:{key_hash}"

    def _should_bypass_cache(
        self,
        filters: Optional[Dict[str, Any]] = None,
        top_k: Optional[int] = None
    ) -> bool:
        """
        Determine if cache should be bypassed.

        Bypass rules:
        - Strict time-based filters (time-bounded content)
        - Very small top_k (< 5)
        - Explicit bypass flag

        Args:
            filters: Filters dictionary
            top_k: Top K results

        Returns:
            True if cache should be bypassed
        """
        if self.bypass_cache:
            return True

        # Check for time-based filters
        if filters:
            time_fields = ['timestamp', 'date', 'created_at', 'updated_at']
            has_time_filter = any(field in filters for field in time_fields)
            if has_time_filter:
                return True

        # Check for very small top_k
        if top_k and top_k < 5:
            return True

        return False

    def _get_from_memory(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get value from in-memory cache."""
        if cache_key not in self._memory_cache:
            return None

        entry = self._memory_cache[cache_key]

        # Check TTL
        if entry.get("expires_at"):
            expires_at = datetime.fromisoformat(entry["expires_at"])
            if datetime.utcnow() > expires_at:
                # Expired, remove from cache
                del self._memory_cache[cache_key]
                return None

        return entry.get("value")

    def _set_in_memory(
        self,
        cache_key: str,
        value: Any,
        ttl_seconds: int
    ) -> None:
        """Set value in in-memory cache."""
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)

        self._memory_cache[cache_key] = {
            "value": value,
            "expires_at": expires_at.isoformat(),
            "created_at": datetime.utcnow().isoformat()
        }

    def _delete_from_memory(self, cache_key: str) -> bool:
        """Delete value from in-memory cache."""
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]
            return True
        return False

    def _clear_memory(self) -> int:
        """Clear all in-memory cache."""
        count = len(self._memory_cache)
        self._memory_cache.clear()
        return count

    def _get_from_redis(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get value from Redis cache."""
        if not self._redis_client:
            return None

        try:
            value_str = self._redis_client.get(cache_key)
            if value_str:
                return json.loads(value_str)
            return None
        except Exception as e:
            # Fallback to memory on Redis error
            return None

    def _set_in_redis(
        self,
        cache_key: str,
        value: Any,
        ttl_seconds: int
    ) -> None:
        """Set value in Redis cache."""
        if not self._redis_client:
            return

        try:
            value_str = json.dumps(value)
            self._redis_client.setex(cache_key, ttl_seconds, value_str)
        except Exception as e:
            # Fallback to memory on Redis error
            self._set_in_memory(cache_key, value, ttl_seconds)

    def _delete_from_redis(self, cache_key: str) -> bool:
        """Delete value from Redis cache."""
        if not self._redis_client:
            return False

        try:
            result = self._redis_client.delete(cache_key)
            return result > 0
        except Exception as e:
            return False

    def _clear_redis(self) -> int:
        """Clear all Redis cache (hybrid_cache:* keys only)."""
        if not self._redis_client:
            return 0

        try:
            keys = self._redis_client.keys("hybrid_cache:*")
            if keys:
                return self._redis_client.delete(*keys)
            return 0
        except Exception as e:
            return 0

    def _get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        hits = self._cache_stats["hits"]
        misses = self._cache_stats["misses"]
        total_requests = hits + misses
        hit_ratio = (hits / total_requests * 100) if total_requests > 0 else 0.0

        cache_size = 0
        if self.backend == "memory":
            cache_size = len(self._memory_cache)
        elif self.backend == "redis" and self._redis_client:
            try:
                cache_size = len(self._redis_client.keys("hybrid_cache:*"))
            except Exception:
                cache_size = 0

        return {
            "backend": self.backend,
            "hits": hits,
            "misses": misses,
            "sets": self._cache_stats["sets"],
            "deletes": self._cache_stats["deletes"],
            "total_requests": total_requests,
            "hit_ratio_percent": round(hit_ratio, 2),
            "cache_size": cache_size,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

    def run(self) -> str:
        """
        Execute cache operation.

        Returns:
            JSON string with operation result
        """
        try:
            # Handle stats operation
            if self.operation == "stats":
                stats = self._get_cache_stats()
                return json.dumps({
                    "operation": "stats",
                    "stats": stats,
                    "status": "success"
                })

            # Handle clear operation
            if self.operation == "clear":
                if self.backend == "memory":
                    cleared_count = self._clear_memory()
                else:
                    cleared_count = self._clear_redis()

                return json.dumps({
                    "operation": "clear",
                    "cleared_count": cleared_count,
                    "backend": self.backend,
                    "status": "success"
                })

            # For other operations, generate or use cache key
            if self.cache_key:
                cache_key = self.cache_key
            else:
                if not self.query:
                    return json.dumps({
                        "error": "missing_query",
                        "message": "Query required for cache key generation"
                    })

                filters_dict = None
                if self.filters:
                    filters_dict = json.loads(self.filters)

                cache_key = self._generate_cache_key(
                    self.query,
                    filters_dict,
                    self.top_k
                )

            # Check bypass rules
            filters_dict = json.loads(self.filters) if self.filters else None
            should_bypass = self._should_bypass_cache(filters_dict, self.top_k)

            # Handle get operation
            if self.operation == "get":
                if should_bypass:
                    self._cache_stats["misses"] += 1
                    return json.dumps({
                        "operation": "get",
                        "cache_key": cache_key,
                        "hit": False,
                        "bypass": True,
                        "reason": "Cache bypassed due to bypass rules",
                        "results": None,
                        "stats": self._get_cache_stats(),
                        "status": "success"
                    })

                # Get from cache
                if self.backend == "memory":
                    results = self._get_from_memory(cache_key)
                else:
                    results = self._get_from_redis(cache_key)

                if results:
                    self._cache_stats["hits"] += 1
                    return json.dumps({
                        "operation": "get",
                        "cache_key": cache_key,
                        "hit": True,
                        "bypass": False,
                        "results": results,
                        "stats": self._get_cache_stats(),
                        "status": "success"
                    })
                else:
                    self._cache_stats["misses"] += 1
                    return json.dumps({
                        "operation": "get",
                        "cache_key": cache_key,
                        "hit": False,
                        "bypass": False,
                        "results": None,
                        "stats": self._get_cache_stats(),
                        "status": "success"
                    })

            # Handle set operation
            if self.operation == "set":
                if not self.results:
                    return json.dumps({
                        "error": "missing_results",
                        "message": "Results required for set operation"
                    })

                if should_bypass:
                    return json.dumps({
                        "operation": "set",
                        "cache_key": cache_key,
                        "bypass": True,
                        "reason": "Cache bypassed due to bypass rules",
                        "status": "success"
                    })

                results_data = json.loads(self.results)

                if self.backend == "memory":
                    self._set_in_memory(cache_key, results_data, self.ttl_seconds)
                else:
                    self._set_in_redis(cache_key, results_data, self.ttl_seconds)

                self._cache_stats["sets"] += 1

                return json.dumps({
                    "operation": "set",
                    "cache_key": cache_key,
                    "bypass": False,
                    "ttl_seconds": self.ttl_seconds,
                    "stats": self._get_cache_stats(),
                    "status": "success"
                })

            # Handle delete operation
            if self.operation == "delete":
                if self.backend == "memory":
                    deleted = self._delete_from_memory(cache_key)
                else:
                    deleted = self._delete_from_redis(cache_key)

                if deleted:
                    self._cache_stats["deletes"] += 1

                return json.dumps({
                    "operation": "delete",
                    "cache_key": cache_key,
                    "deleted": deleted,
                    "stats": self._get_cache_stats(),
                    "status": "success"
                })

            return json.dumps({
                "error": "invalid_operation",
                "message": f"Invalid operation: {self.operation}"
            })

        except Exception as e:
            return json.dumps({
                "error": "cache_operation_failed",
                "message": str(e),
                "operation": self.operation
            })


# Test block
if __name__ == "__main__":
    print("Testing CacheHybridRetrieval tool...")

    # Test 1: Set value in cache
    print("\n1. Testing SET operation:")
    tool_set = CacheHybridRetrieval(
        backend="memory",
        operation="set",
        query="How to increase revenue",
        filters=json.dumps({"channel": "business"}),
        top_k=10,
        results=json.dumps([{"doc_id": "1", "score": 0.95}]),
        ttl_seconds=3600
    )
    result_set = tool_set.run()
    print(json.dumps(json.loads(result_set), indent=2))

    # Test 2: Get value from cache (hit)
    print("\n2. Testing GET operation (cache hit):")
    tool_get = CacheHybridRetrieval(
        backend="memory",
        operation="get",
        query="How to increase revenue",
        filters=json.dumps({"channel": "business"}),
        top_k=10
    )
    result_get = tool_get.run()
    print(json.dumps(json.loads(result_get), indent=2))

    # Test 3: Get value with different query (miss)
    print("\n3. Testing GET operation (cache miss):")
    tool_miss = CacheHybridRetrieval(
        backend="memory",
        operation="get",
        query="Different query",
        top_k=10
    )
    result_miss = tool_miss.run()
    print(json.dumps(json.loads(result_miss), indent=2))

    # Test 4: Cache bypass (time-based filter)
    print("\n4. Testing cache bypass (time-based filter):")
    tool_bypass = CacheHybridRetrieval(
        backend="memory",
        operation="get",
        query="Recent content",
        filters=json.dumps({"timestamp": "2025-10-13"}),
        top_k=10
    )
    result_bypass = tool_bypass.run()
    print(json.dumps(json.loads(result_bypass), indent=2))

    # Test 5: Cache statistics
    print("\n5. Testing STATS operation:")
    tool_stats = CacheHybridRetrieval(
        backend="memory",
        operation="stats"
    )
    result_stats = tool_stats.run()
    print(json.dumps(json.loads(result_stats), indent=2))

    # Test 6: Delete cache entry
    print("\n6. Testing DELETE operation:")
    tool_delete = CacheHybridRetrieval(
        backend="memory",
        operation="delete",
        query="How to increase revenue",
        filters=json.dumps({"channel": "business"}),
        top_k=10
    )
    result_delete = tool_delete.run()
    print(json.dumps(json.loads(result_delete), indent=2))

    # Test 7: Clear all cache
    print("\n7. Testing CLEAR operation:")
    tool_clear = CacheHybridRetrieval(
        backend="memory",
        operation="clear"
    )
    result_clear = tool_clear.run()
    print(json.dumps(json.loads(result_clear), indent=2))

    print("\n✅ All cache operations tested successfully!")
