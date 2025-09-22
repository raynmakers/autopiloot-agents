"""
Targeted test to achieve 100% coverage for get_post_comments.py
Focuses specifically on the 3 missing lines: 87, 134, 143
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import sys
import time


class TestGetPostCommentsTargetedCoverage(unittest.TestCase):
    """Targeted tests for 100% coverage of get_post_comments.py"""

    def setUp(self):
        """Set up comprehensive mocking for Agency Swarm."""
        # Mock all Agency Swarm dependencies
        def mock_field(*args, **kwargs):
            return kwargs.get('default', kwargs.get('default_factory', lambda: None)())

        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            sys.modules['pydantic'].Field = mock_field

            class MockBaseTool:
                def __init__(self, **kwargs):
                    for key, value in kwargs.items():
                        setattr(self, key, value)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

    def test_empty_post_ids_line_87(self):
        """Test empty post_ids to hit line 87 - the return statement."""
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

            # Import after mocking
            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with empty post_ids
            tool = GetPostComments(post_ids=[])

            # Mock environment to avoid issues with env loading
            with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env:

                mock_env.return_value = "test-value"

                # This should hit line 87 (empty post_ids check)
                result = tool.run()
                result_data = json.loads(result)

                self.assertEqual(result_data["error"], "invalid_input")
                self.assertEqual(result_data["message"], "No post IDs provided")

    def test_failed_request_line_134(self):
        """Test failed API request to hit line 134 - failed fetch handling."""
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

            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with valid post_ids
            tool = GetPostComments(post_ids=["urn:li:activity:123"])

            with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.requests') as mock_requests:

                mock_env.return_value = "test-value"

                # Create mock response that returns None (failed request)
                def mock_make_request_with_retry(url, headers, params):
                    return None  # This triggers line 134

                # Patch the internal method to return None
                tool._make_request_with_retry = mock_make_request_with_retry

                result = tool.run()
                result_data = json.loads(result)

                # Verify we hit the failed fetch path (line 134)
                self.assertIn("comments_by_post", result_data)
                self.assertIn("urn:li:activity:123", result_data["comments_by_post"])
                self.assertEqual(result_data["comments_by_post"]["urn:li:activity:123"]["error"], "fetch_failed")
                self.assertEqual(result_data["comments_by_post"]["urn:li:activity:123"]["comments"], [])
                self.assertEqual(result_data["comments_by_post"]["urn:li:activity:123"]["total_count"], 0)

    def test_multiple_posts_rate_limiting_line_143(self):
        """Test multiple posts to hit line 143 - rate limiting sleep."""
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

            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with MULTIPLE post_ids (triggers line 143)
            tool = GetPostComments(post_ids=["urn:li:activity:123", "urn:li:activity:456"])

            with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.time.sleep') as mock_sleep:

                mock_env.return_value = "test-value"

                # Mock successful responses
                def mock_make_request_with_retry(url, headers, params):
                    return {
                        "data": [
                            {
                                "id": "comment_1",
                                "authorName": "Test User",
                                "text": "Test comment",
                                "likes": 5
                            }
                        ],
                        "pagination": {"hasMore": False}
                    }

                tool._make_request_with_retry = mock_make_request_with_retry

                result = tool.run()
                result_data = json.loads(result)

                # Verify rate limiting was called (line 143)
                # Since we have 2 posts, sleep should be called once (between posts)
                mock_sleep.assert_called_with(0.5)

                # Verify both posts were processed
                self.assertIn("comments_by_post", result_data)
                self.assertIn("urn:li:activity:123", result_data["comments_by_post"])
                self.assertIn("urn:li:activity:456", result_data["comments_by_post"])


if __name__ == "__main__":
    unittest.main()