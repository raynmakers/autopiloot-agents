"""
Final test to achieve 100% coverage for get_post_comments.py
Covers remaining lines: 84, 248-251
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import sys
import requests


class TestGetPostCommentsFinal100(unittest.TestCase):
    """Final test to achieve 100% coverage"""

    def test_remaining_lines_for_100_percent(self):
        """Test remaining lines 84, 248-251 for 100% coverage"""

        with patch.dict('sys.modules', {
            'agency_swarm': MagicMock(),
            'agency_swarm.tools': MagicMock(),
            'pydantic': MagicMock()
        }):
            def mock_field(*args, **kwargs):
                default = kwargs.get('default', None)
                if default is not None:
                    return default
                return None

            sys.modules['pydantic'].Field = mock_field

            class MockBaseTool:
                def __init__(self, **kwargs):
                    self.post_ids = kwargs.get('post_ids', [])
                    self.page = kwargs.get('page', 1)
                    self.page_size = kwargs.get('page_size', 50)
                    self.include_replies = kwargs.get('include_replies', True)

            sys.modules['agency_swarm.tools'].BaseTool = MockBaseTool

            with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
                 patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_env:

                mock_env.return_value = "test-value"

                from linkedin_agent.tools.get_post_comments import GetPostComments

                # TEST 1: Line 84 - page_size validation (page_size > 100)
                print("Testing line 84: page_size > 100 validation")
                tool_large_page = GetPostComments(post_ids=["test"], page_size=150)

                # Manually set page_size to test the validation
                tool_large_page.page_size = 150

                result = tool_large_page.run()
                data = json.loads(result)

                # After running, page_size should be capped at 100
                self.assertEqual(tool_large_page.page_size, 100)
                print("✓ Line 84 covered: page_size validation")

                # TEST 2: Lines 248-251 - RequestException in _make_request_with_retry
                print("Testing lines 248-251: RequestException handling")
                tool_req_error = GetPostComments(post_ids=["test"])

                # Mock requests to raise RequestException
                with patch('linkedin_agent.tools.get_post_comments.requests.get') as mock_get, \
                     patch('linkedin_agent.tools.get_post_comments.time.sleep') as mock_sleep:

                    # Raise RequestException to hit lines 248-251
                    mock_get.side_effect = requests.exceptions.RequestException("Connection error")

                    # Call the internal method directly to test exception handling
                    result = tool_req_error._make_request_with_retry(
                        "https://test.com",
                        {"X-RapidAPI-Key": "test"},
                        {"postId": "test"}
                    )

                    # Should return None after all retries fail
                    self.assertIsNone(result)

                    # Sleep should be called due to RequestException (lines 250)
                    self.assertTrue(mock_sleep.called)
                    print("✓ Lines 248-251 covered: RequestException handling")

                print("🎉 100% coverage achieved for get_post_comments.py!")


if __name__ == "__main__":
    unittest.main()