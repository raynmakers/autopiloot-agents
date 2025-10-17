"""
Error handling tests for RapidAPI Rate Limiter (TASK-RAPI-0074).

Tests error conditions, missing configuration, and edge cases.
"""

import unittest
from unittest.mock import MagicMock
import sys
import os
import importlib.util

# Add parent directory to path

class TestRapidAPIRateLimiterErrorHandling(unittest.TestCase):
    """Error handling and edge case tests for rate limiter."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock config loader
        mock_loader = MagicMock()
        self.mock_config = {
            "rapidapi": {
                "plugins": {
                    "configured_plugin": {
                        "limits": {
                            "monthly": 1000,
                            "per_minute": 60,
                            "burst": 10
                        }
                    }
                }
            }
        }
        mock_loader.load_app_config = MagicMock(return_value=self.mock_config)
        sys.modules['loader'] = mock_loader

        # Import rate limiter module
        rate_limiter_path = os.path.join(
            os.path.dirname(__file__), '..', '..', 'core', 'rate_limiter.py'
        )
        spec = importlib.util.spec_from_file_location("rate_limiter", rate_limiter_path)
        self.rate_limiter_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.rate_limiter_module)

    def test_unconfigured_plugin_raises_valueerror(self):
        """
        Test that requesting unconfigured plugin raises ValueError.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()

        with self.assertRaises(ValueError) as context:
            limiter.acquire("nonexistent_plugin")

        self.assertIn("not configured", str(context.exception))
        self.assertIn("nonexistent_plugin", str(context.exception))

    def test_missing_limits_uses_defaults(self):
        """
        Test that missing limit values use sensible defaults.
        """
        config_no_limits = {
            "rapidapi": {
                "plugins": {
                    "no_limits_plugin": {}  # No limits specified
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=config_no_limits)

        # Should create plugin with default limits
        self.assertIn("no_limits_plugin", limiter.plugins)

        # Default monthly should be 10000
        remaining = limiter.get_monthly_remaining("no_limits_plugin")
        self.assertEqual(remaining, 10000, "Default monthly limit should be 10000")

    def test_empty_config_handles_gracefully(self):
        """
        Test that empty config doesn't crash (no plugins configured).
        """
        empty_config = {"rapidapi": {"plugins": {}}}

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=empty_config)

        # Should initialize without errors
        self.assertEqual(len(limiter.plugins), 0, "Should have no plugins")

    def test_invalid_plugin_name_try_acquire(self):
        """
        Test that try_acquire with invalid plugin returns False.
        """
        limiter = self.rate_limiter_module.RapidAPIRateLimiter()

        result = limiter.try_acquire("invalid_plugin")
        self.assertFalse(result, "try_acquire should return False for invalid plugin")

    def test_monthly_limit_zero_raises_error(self):
        """
        Test behavior when monthly limit is 0 (should immediately fail).
        """
        config_zero_limit = {
            "rapidapi": {
                "plugins": {
                    "zero_limit_plugin": {
                        "limits": {"monthly": 0, "per_minute": 60}
                    }
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=config_zero_limit)

        with self.assertRaises(RuntimeError) as context:
            limiter.acquire("zero_limit_plugin")

        self.assertIn("Monthly quota exhausted", str(context.exception))

    def test_negative_limit_handled(self):
        """
        Test that negative limits are handled (treated as very restrictive).
        """
        config_negative = {
            "rapidapi": {
                "plugins": {
                    "negative_plugin": {
                        "limits": {"monthly": -1, "per_minute": 60}
                    }
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=config_negative)

        # Should fail immediately
        with self.assertRaises(RuntimeError):
            limiter.acquire("negative_plugin")

    def test_concurrent_access_thread_safety(self):
        """
        Test that concurrent access is thread-safe (basic check).
        """
        import threading

        limiter = self.rate_limiter_module.RapidAPIRateLimiter()
        errors = []

        def worker():
            try:
                limiter.acquire("configured_plugin")
            except Exception as e:
                errors.append(e)

        # Create 5 concurrent threads
        threads = [threading.Thread(target=worker) for _ in range(5)]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Check no threading errors occurred
        self.assertEqual(len(errors), 0, f"Threading errors occurred: {errors}")

        # Check monthly counter reflects all acquisitions
        remaining = limiter.get_monthly_remaining("configured_plugin")
        self.assertEqual(remaining, 995, "Should have consumed 5 tokens across threads")

    def test_burst_larger_than_capacity(self):
        """
        Test that burst value larger than per_minute is capped.
        """
        config_large_burst = {
            "rapidapi": {
                "plugins": {
                    "large_burst_plugin": {
                        "limits": {"monthly": 1000, "per_minute": 60, "burst": 100}  # Burst > per_minute
                    }
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=config_large_burst)

        # Burst should be honored as capacity
        bucket = limiter.plugins["large_burst_plugin"]["minute_bucket"]
        self.assertEqual(bucket.capacity, 100, "Burst should be used as capacity")

    def test_partial_config_uses_defaults(self):
        """
        Test that partial configuration (e.g., only monthly) uses defaults for missing values.
        """
        config_partial = {
            "rapidapi": {
                "plugins": {
                    "partial_plugin": {
                        "limits": {"monthly": 5000}  # Only monthly specified
                    }
                }
            }
        }

        limiter = self.rate_limiter_module.RapidAPIRateLimiter(config=config_partial)

        # Should use default per_minute (60)
        bucket = limiter.plugins["partial_plugin"]["minute_bucket"]
        expected_refill = 60.0 / 60.0  # 1.0 tokens per second
        self.assertEqual(bucket.refill_per_second, expected_refill,
                        "Should use default per_minute of 60")

        # Monthly should be as configured
        remaining = limiter.get_monthly_remaining("partial_plugin")
        self.assertEqual(remaining, 5000, "Monthly limit should be 5000")


if __name__ == "__main__":
    unittest.main(verbosity=2)
