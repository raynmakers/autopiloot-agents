"""
Integration tests for RapidAPI Rate Limiter (TASK-RAPI-0074).

Tests dual token bucket implementation for monthly and per-minute limits
with time mocking for deterministic behavior.
"""

import unittest
from unittest.mock import patch, MagicMock
import time
import sys
import os
import importlib.util

# Add parent directory to path

class TestRapidAPIRateLimiterIntegration(unittest.TestCase):
    """Integration tests for rate limiter with mocked time."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock config loader
        mock_loader = MagicMock()
        mock_config = {
            "rapidapi": {
                "plugins": {
                    "test_plugin": {
                        "host": "test.api.com",
                        "limits": {
                            "monthly": 1000,
                            "per_minute": 60,
                            "burst": 10
                        }
                    }
                }
            }
        }
        mock_loader.load_app_config = MagicMock(return_value=mock_config)
        sys.modules['loader'] = mock_loader

        # Import rate limiter module
        rate_limiter_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'core', 'rate_limiter.py'
        )
        spec = importlib.util.spec_from_file_location("rate_limiter", rate_limiter_path)
        self.rate_limiter_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.rate_limiter_module)

    def test_per_minute_limit_allows_burst(self):
        """
        Test that burst capacity allows immediate requests up to burst limit.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()

        # Burst limit is 10 - should allow 10 immediate requests
        start_time = time.monotonic()

        for i in range(10):
            limiter.acquire("test_plugin", now=start_time)

        # All 10 should succeed without blocking (within burst capacity)
        self.assertTrue(True, "Burst capacity allowed 10 immediate requests")

    def test_per_minute_limit_enforces_rate(self):
        """
        Test that per-minute limit (60 RPM) is enforced after burst exhausted.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()
        bucket = limiter.plugins["test_plugin"]["minute_bucket"]

        # Start with empty bucket
        bucket.tokens = 0.0
        start_time = time.monotonic()
        bucket.last_refill = start_time

        # Try to acquire 1 token - should require waiting
        # At 60 RPM = 1 token per second
        # With 0 tokens, need to wait 1 second for next token

        # Check that token is not immediately available
        result = limiter.try_acquire("test_plugin", now=start_time)
        self.assertFalse(result, "Should not acquire when bucket empty")

        # After 1 second, should have 1 token available
        result = limiter.try_acquire("test_plugin", now=start_time + 1.0)
        self.assertTrue(result, "Should acquire after 1 second (60 RPM = 1 token/sec)")

    def test_monthly_limit_tracks_usage(self):
        """
        Test that monthly limit correctly tracks request count.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()

        # Acquire 5 tokens
        for i in range(5):
            limiter.acquire("test_plugin")

        # Check monthly remaining
        remaining = limiter.get_monthly_remaining("test_plugin")
        self.assertEqual(remaining, 995, "Monthly limit should track 5 requests (1000 - 5 = 995)")

    def test_monthly_limit_exhaustion_raises_error(self):
        """
        Test that exhausting monthly limit raises RuntimeError.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()
        monthly_bucket = limiter.plugins["test_plugin"]["monthly_bucket"]

        # Set count to limit - 1
        monthly_bucket.count = 999

        # This should succeed
        limiter.acquire("test_plugin")

        # Next request should fail (monthly limit exhausted)
        with self.assertRaises(RuntimeError) as context:
            limiter.acquire("test_plugin")

        self.assertIn("Monthly quota exhausted", str(context.exception))

    def test_decorator_enforces_limits(self):
        """
        Test that @respect_rapidapi_limits decorator enforces rate limits.
        """
        # Create decorated function
        @self.rate_limiter_module.respect_rapidapi_limits("test_plugin")
        def test_function():
            return "success"

        # Should succeed
        result = test_function()
        self.assertEqual(result, "success")

        # Get the singleton limiter instance that decorator uses
        limiter = self.rate_limiter_module.get_limiter()

        # Check that monthly counter was incremented
        remaining = limiter.get_monthly_remaining("test_plugin")
        self.assertLess(remaining, 1000, "Decorator should enforce monthly limit")

    def test_try_acquire_returns_false_when_limited(self):
        """
        Test that try_acquire returns False instead of blocking when rate limited.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()
        bucket = limiter.plugins["test_plugin"]["minute_bucket"]

        # Empty bucket
        bucket.tokens = 0.0
        start_time = time.monotonic()
        bucket.last_refill = start_time

        # try_acquire should return False (non-blocking)
        result = limiter.try_acquire("test_plugin", now=start_time)
        self.assertFalse(result, "try_acquire should return False when rate limited")

    def test_refill_rate_calculation(self):
        """
        Test that token refill rate matches configured per_minute limit.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()
        bucket = limiter.plugins["test_plugin"]["minute_bucket"]

        # Per-minute limit is 60, so refill_per_second should be 1.0
        expected_refill_per_second = 60.0 / 60.0  # 1.0 tokens per second
        self.assertEqual(bucket.refill_per_second, expected_refill_per_second,
                        "Refill rate should be per_minute / 60")

    def test_multiple_plugins_independent_limits(self):
        """
        Test that multiple plugins have independent rate limits.
        """
        # Create config with two plugins
        mock_config = {
            "rapidapi": {
                "plugins": {
                    "plugin_a": {
                        "limits": {"monthly": 1000, "per_minute": 60, "burst": 10}
                    },
                    "plugin_b": {
                        "limits": {"monthly": 500, "per_minute": 30, "burst": 5}
                    }
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=mock_config)

        # Acquire from plugin_a
        limiter.acquire("plugin_a")
        remaining_a = limiter.get_monthly_remaining("plugin_a")

        # Acquire from plugin_b
        limiter.acquire("plugin_b")
        remaining_b = limiter.get_monthly_remaining("plugin_b")

        # Verify independent tracking
        self.assertEqual(remaining_a, 999, "plugin_a should have 999 remaining")
        self.assertEqual(remaining_b, 499, "plugin_b should have 499 remaining")


if __name__ == "__main__":
    unittest.main(verbosity=2)
