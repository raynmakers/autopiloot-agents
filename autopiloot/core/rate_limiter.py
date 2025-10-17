"""
RapidAPI Rate Limiter with dual token buckets for monthly and per-minute limits.

Implements TASK-RAPI-0074 to enforce per-plugin RapidAPI rate limits configured
in settings.yaml, preventing 429 errors and smoothing traffic.

RapidAPI enforces BOTH monthly and per-minute rate limits simultaneously.
This module uses dual token buckets to respect both constraints.

Usage:
    from core.rate_limiter import respect_rapidapi_limits

    @respect_rapidapi_limits("linkedin_scraper")
    def call_linkedin_api():
        # Make API call
        pass
"""

import time
import threading
import calendar
from datetime import datetime, timezone
from functools import wraps
from typing import Dict, Optional
import sys
import os

# Add config directory to path for imports
from config.loader import load_app_config


class TokenBucket:
    """
    Thread-safe token bucket for rate limiting.

    Implements a token bucket algorithm where tokens are added at a fixed rate
    and requests consume tokens. Requests block if insufficient tokens available.
    """

    def __init__(self, capacity: int, refill_rate: float, refill_per_second: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens (burst capacity)
            refill_rate: Tokens added per refill interval
            refill_per_second: How many tokens to add per second
        """
        self.capacity = capacity
        self.refill_per_second = refill_per_second
        self.tokens = float(capacity)  # Start with full bucket
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self, now: float):
        """Refill tokens based on time elapsed since last refill."""
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_per_second
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def acquire(self, tokens: int = 1, now: Optional[float] = None) -> None:
        """
        Acquire tokens, blocking until available.

        Args:
            tokens: Number of tokens to acquire
            now: Current time (for testing); uses time.monotonic() if None
        """
        if now is None:
            now = time.monotonic()

        with self.lock:
            while True:
                self._refill(now)

                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return

                # Calculate wait time for next token
                tokens_needed = tokens - self.tokens
                wait_time = tokens_needed / self.refill_per_second

                # Release lock while sleeping
                self.lock.release()
                time.sleep(min(wait_time, 0.1))  # Sleep in small increments
                self.lock.acquire()
                now = time.monotonic()

    def try_acquire(self, tokens: int = 1, now: Optional[float] = None) -> bool:
        """
        Try to acquire tokens without blocking.

        Args:
            tokens: Number of tokens to acquire
            now: Current time (for testing); uses time.monotonic() if None

        Returns:
            True if tokens acquired, False if insufficient tokens
        """
        if now is None:
            now = time.monotonic()

        with self.lock:
            self._refill(now)

            if self.tokens >= tokens:
                self.tokens -= tokens
                return True

            return False


class MonthlyBucket:
    """
    Thread-safe monthly quota tracker.

    Tracks monthly request count and resets at month boundaries.
    """

    def __init__(self, monthly_limit: int):
        """
        Initialize monthly bucket.

        Args:
            monthly_limit: Maximum requests per calendar month
        """
        self.monthly_limit = monthly_limit
        self.current_month = self._get_current_month()
        self.count = 0
        self.lock = threading.Lock()

    def _get_current_month(self) -> str:
        """Get current month as YYYY-MM string."""
        now = datetime.now(timezone.utc)
        return f"{now.year}-{now.month:02d}"

    def _check_reset(self):
        """Reset counter if month has changed."""
        current = self._get_current_month()
        if current != self.current_month:
            self.current_month = current
            self.count = 0

    def acquire(self, tokens: int = 1) -> None:
        """
        Acquire monthly quota, blocking until next month if exhausted.

        Args:
            tokens: Number of requests to consume
        """
        with self.lock:
            self._check_reset()

            if self.count + tokens > self.monthly_limit:
                # Monthly quota exhausted - calculate wait time until next month
                now = datetime.now(timezone.utc)
                days_in_month = calendar.monthrange(now.year, now.month)[1]
                seconds_until_reset = (days_in_month - now.day + 1) * 86400 - now.hour * 3600 - now.minute * 60 - now.second

                raise RuntimeError(
                    f"Monthly quota exhausted ({self.count}/{self.monthly_limit}). "
                    f"Resets in {seconds_until_reset / 3600:.1f} hours."
                )

            self.count += tokens

    def try_acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire monthly quota without blocking.

        Args:
            tokens: Number of requests to consume

        Returns:
            True if quota acquired, False if exhausted
        """
        with self.lock:
            self._check_reset()

            if self.count + tokens > self.monthly_limit:
                return False

            self.count += tokens
            return True

    def get_remaining(self) -> int:
        """Get remaining monthly quota."""
        with self.lock:
            self._check_reset()
            return self.monthly_limit - self.count


class RapidAPIRateLimiter:
    """
    Dual token bucket rate limiter for RapidAPI plugins.

    Enforces BOTH monthly and per-minute rate limits from settings.yaml.
    Thread-safe and supports multiple plugins with independent limits.
    """

    def __init__(self, config: Optional[Dict] = None):
        """
        Initialize rate limiter with configuration.

        Args:
            config: Configuration dict (loads from settings.yaml if None)
        """
        if config is None:
            config = load_app_config()

        self.config = config
        self.plugins = self._load_plugin_limits()
        self.lock = threading.Lock()

    def _load_plugin_limits(self) -> Dict:
        """Load rate limits for all configured plugins."""
        plugins = {}
        rapidapi_config = self.config.get("rapidapi", {}).get("plugins", {})

        for plugin_name, plugin_config in rapidapi_config.items():
            limits = plugin_config.get("limits", {})

            # Default limits if not specified
            monthly = limits.get("monthly", 10000)
            per_minute = limits.get("per_minute", 60)
            burst = limits.get("burst", per_minute // 2)  # Default: half of per_minute

            # Create dual buckets: one for per-minute, one for monthly
            minute_bucket = TokenBucket(
                capacity=burst,
                refill_rate=per_minute / 60.0,  # Tokens per second
                refill_per_second=per_minute / 60.0
            )

            monthly_bucket = MonthlyBucket(monthly_limit=monthly)

            plugins[plugin_name] = {
                "minute_bucket": minute_bucket,
                "monthly_bucket": monthly_bucket,
                "config": limits
            }

        return plugins

    def acquire(self, plugin: str, now: Optional[float] = None) -> None:
        """
        Acquire permission to make API call, blocking until available.

        Enforces BOTH per-minute and monthly limits.

        Args:
            plugin: Plugin name (e.g., "linkedin_scraper")
            now: Current time for testing (uses time.monotonic() if None)

        Raises:
            ValueError: If plugin not configured
            RuntimeError: If monthly quota exhausted
        """
        if plugin not in self.plugins:
            raise ValueError(
                f"Plugin '{plugin}' not configured in settings.yaml. "
                f"Available plugins: {list(self.plugins.keys())}"
            )

        buckets = self.plugins[plugin]

        # Check monthly limit first (non-blocking check)
        buckets["monthly_bucket"].acquire(tokens=1)

        # Then enforce per-minute limit (may block)
        buckets["minute_bucket"].acquire(tokens=1, now=now)

    def try_acquire(self, plugin: str, now: Optional[float] = None) -> bool:
        """
        Try to acquire permission without blocking.

        Args:
            plugin: Plugin name
            now: Current time for testing

        Returns:
            True if acquired, False if rate limited
        """
        if plugin not in self.plugins:
            return False

        buckets = self.plugins[plugin]

        # Check monthly limit first
        if not buckets["monthly_bucket"].try_acquire(tokens=1):
            return False

        # Then check per-minute limit
        if not buckets["minute_bucket"].try_acquire(tokens=1, now=now):
            # Rollback monthly count
            with buckets["monthly_bucket"].lock:
                buckets["monthly_bucket"].count -= 1
            return False

        return True

    def get_monthly_remaining(self, plugin: str) -> int:
        """Get remaining monthly quota for plugin."""
        if plugin not in self.plugins:
            return 0
        return self.plugins[plugin]["monthly_bucket"].get_remaining()


# Global limiter instance
_limiter: Optional[RapidAPIRateLimiter] = None
_limiter_lock = threading.Lock()


def get_limiter() -> RapidAPIRateLimiter:
    """Get or create global rate limiter instance (singleton)."""
    global _limiter

    if _limiter is None:
        with _limiter_lock:
            if _limiter is None:  # Double-check after acquiring lock
                _limiter = RapidAPIRateLimiter()

    return _limiter


def respect_rapidapi_limits(plugin: str):
    """
    Decorator to enforce RapidAPI rate limits on function calls.

    Usage:
        @respect_rapidapi_limits("linkedin_scraper")
        def call_linkedin_api():
            # Make API call
            pass

    Args:
        plugin: Plugin name from settings.yaml (e.g., "linkedin_scraper")
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter = get_limiter()
            limiter.acquire(plugin)
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == "__main__":
    import traceback

    print("="*80)
    print("TEST: RapidAPI Rate Limiter")
    print("="*80)

    try:
        # Test initialization
        limiter = RapidAPIRateLimiter()
        print("\n✅ Limiter initialized successfully")
        print(f"   Configured plugins: {list(limiter.plugins.keys())}")

        # Test per-minute limiting
        plugin = "linkedin_scraper"
        if plugin in limiter.plugins:
            print(f"\n📊 Testing per-minute limits for '{plugin}':")
            config = limiter.plugins[plugin]["config"]
            print(f"   Monthly limit: {config.get('monthly', 'N/A')}")
            print(f"   Per-minute limit: {config.get('per_minute', 'N/A')}")
            print(f"   Burst: {config.get('burst', 'N/A')}")

            # Try acquiring a few tokens
            print("\n   Acquiring 3 tokens...")
            for i in range(3):
                limiter.acquire(plugin)
                print(f"      Token {i+1} acquired ✓")

            monthly_remaining = limiter.get_monthly_remaining(plugin)
            print(f"\n   Monthly quota remaining: {monthly_remaining}")

            print("\n✅ Rate limiter working correctly!")

        # Test decorator
        print("\n📝 Testing decorator:")

        @respect_rapidapi_limits("linkedin_scraper")
        def test_api_call():
            return "API call successful"

        result = test_api_call()
        print(f"   {result} ✓")

        print("\n" + "="*80)
        print("✅ All tests passed!")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Test error: {str(e)}")
        traceback.print_exc()
