"""
Final coverage tests for GetPostComments to hit the last 3 missing lines.
Targets lines 87, 134, 143 specifically.
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import sys


class TestGetPostCommentsFinalCoverage(unittest.TestCase):
    """Final tests to achieve 100% coverage for GetPostComments."""

    def test_empty_post_ids_direct_line_87(self):
        """Test empty post IDs error to hit line 87 directly."""
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

            with patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.load_environment'):

                mock_env.side_effect = lambda key, desc: "test-value"

                from linkedin_agent.tools.get_post_comments import GetPostComments

                # Create tool with empty post_ids list
                tool = GetPostComments(post_ids=[])

                # This should hit the exact condition on line 86-90
                result = tool.run()
                result_data = json.loads(result)

                # Verify the specific return structure from lines 87-90
                self.assertIn("error", result_data)
                self.assertEqual(result_data["error"], "invalid_input")

    def test_single_post_to_skip_rate_limiting_line_143(self):
        """Test single post to skip rate limiting on line 143."""
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

            with patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.time.sleep') as mock_sleep:

                mock_env.side_effect = lambda key, desc: "test-value"

                from linkedin_agent.tools.get_post_comments import GetPostComments

                # Use single post to avoid hitting line 143 (rate limiting condition)
                tool = GetPostComments(post_ids=["urn:li:activity:123"])

                mock_response_data = {
                    "data": [{"id": "comment_1"}],
                    "pagination": {}
                }

                with patch.object(tool, '_make_request_with_retry', return_value=mock_response_data):
                    result = tool.run()

                    # Verify rate limiting was NOT called for single post
                    mock_sleep.assert_not_called()

                    # Verify result
                    result_data = json.loads(result)
                    self.assertIn("comments_by_post", result_data)

    def test_failed_post_response_line_134(self):
        """Test failed post response to hit line 134 else clause."""
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

            with patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env, \
                 patch('linkedin_agent.tools.get_post_comments.load_environment'):

                mock_env.side_effect = lambda key, desc: "test-value"

                from linkedin_agent.tools.get_post_comments import GetPostComments

                tool = GetPostComments(post_ids=["urn:li:activity:123"])

                # Mock _make_request_with_retry to return None (line 118 condition fails)
                with patch.object(tool, '_make_request_with_retry', return_value=None):
                    result = tool.run()
                    result_data = json.loads(result)

                    # This should hit the else clause on line 134-139
                    post_data = result_data["comments_by_post"]["urn:li:activity:123"]
                    self.assertEqual(post_data["comments"], [])
                    self.assertEqual(post_data["total_count"], 0)
                    self.assertFalse(post_data["has_more"])
                    self.assertEqual(post_data["error"], "fetch_failed")


if __name__ == '__main__':
    unittest.main()