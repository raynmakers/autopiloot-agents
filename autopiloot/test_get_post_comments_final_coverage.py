"""
Final targeted test to achieve 100% coverage for get_post_comments.py
Specifically targeting missing lines 87, 134, 143
"""

import unittest
from unittest.mock import patch, MagicMock
import json
import sys


class TestGetPostCommentsFinalCoverage(unittest.TestCase):
    """Final test to achieve 100% coverage."""

    def test_comprehensive_coverage_all_missing_lines(self):
        """Test to hit all missing lines: 87, 134, 143."""

        # Mock Agency Swarm modules
        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            def mock_field(*args, **kwargs):
                return kwargs.get('default', kwargs.get('default_factory', lambda: None)())
            sys.modules['pydantic'].Field = mock_field

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)
            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            # Mock all environment and external dependencies
            with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.time.sleep') as mock_sleep:

                mock_env.return_value = "test-host"

                from linkedin_agent.tools.get_post_comments import GetPostComments

                # Test 1: Empty post_ids to hit line 87
                # CRITICAL: The empty check happens AFTER environment loading
                # So we need to mock env successfully, then test empty post_ids
                print("Testing empty post_ids (line 87)...")
                tool_empty = GetPostComments(post_ids=[])  # Empty list

                # Mock environment to succeed so we reach the post_ids check
                mock_env.side_effect = None  # Reset side_effect
                mock_env.return_value = "test-value"

                result_empty = tool_empty.run()
                result_data_empty = json.loads(result_empty)

                # This should hit line 87 (empty post_ids check after successful env load)
                self.assertEqual(result_data_empty["error"], "invalid_input")
                self.assertEqual(result_data_empty["message"], "No post IDs provided")
                print("✓ Line 87 covered")

                # Test 2: Failed request to hit line 134
                print("Testing failed request (line 134)...")
                tool_failed = GetPostComments(post_ids=["urn:li:activity:123"])

                # Mock _make_request_with_retry to return None (failed request)
                original_method = tool_failed._make_request_with_retry
                tool_failed._make_request_with_retry = lambda url, headers, params: None

                result_failed = tool_failed.run()
                result_data_failed = json.loads(result_failed)

                # This should hit line 134 (failed fetch handling)
                self.assertIn("comments_by_post", result_data_failed)
                post_data = result_data_failed["comments_by_post"]["urn:li:activity:123"]
                self.assertEqual(post_data["error"], "fetch_failed")
                self.assertEqual(post_data["comments"], [])
                self.assertEqual(post_data["total_count"], 0)
                print("✓ Line 134 covered")

                # Test 3: Multiple posts to hit line 143 (rate limiting)
                print("Testing multiple posts rate limiting (line 143)...")
                tool_multiple = GetPostComments(post_ids=["post1", "post2"])

                # Mock successful requests
                def mock_success_request(url, headers, params):
                    return {
                        "data": [{"id": "comment1", "authorName": "User", "text": "Comment", "likes": 1}],
                        "pagination": {"hasMore": False}
                    }

                tool_multiple._make_request_with_retry = mock_success_request

                result_multiple = tool_multiple.run()
                result_data_multiple = json.loads(result_multiple)

                # This should hit line 143 (sleep between multiple posts)
                mock_sleep.assert_called_with(0.5)
                self.assertIn("comments_by_post", result_data_multiple)
                self.assertEqual(len(result_data_multiple["comments_by_post"]), 2)
                print("✓ Line 143 covered")

                print("All missing lines covered successfully!")


if __name__ == "__main__":
    unittest.main()