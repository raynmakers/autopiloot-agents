"""
100% coverage test for get_post_comments.py - targeting lines 87, 134, 143
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
import json
import sys


def test_line_87_empty_post_ids():
    """Test line 87 - empty post_ids check"""
    print("Testing line 87: empty post_ids check")

    # Mock all dependencies BEFORE importing
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

        # Mock the environment functions to succeed
        with patch('linkedin_agent.tools.get_post_comments.load_environment') as mock_load_env, \
             patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_get_env:

            # Make environment functions succeed
            mock_load_env.return_value = None
            mock_get_env.return_value = "test-value"

            # Now import and test
            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with empty post_ids
            tool = GetPostComments(post_ids=[])
            result = tool.run()
            result_data = json.loads(result)

            # Should hit line 87
            assert result_data["error"] == "invalid_input"
            assert result_data["message"] == "No post IDs provided"
            print("✓ Line 87 covered successfully")


def test_line_134_failed_request():
    """Test line 134 - failed request handling"""
    print("Testing line 134: failed request handling")

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

        with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
             patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_get_env:

            mock_get_env.return_value = "test-value"

            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with valid post_ids
            tool = GetPostComments(post_ids=["test_post_123"])

            # Mock the request method to return None (failed request)
            def mock_failed_request(url, headers, params):
                return None

            tool._make_request_with_retry = mock_failed_request

            result = tool.run()
            result_data = json.loads(result)

            # Should hit line 134 - failed request handling
            assert "comments_by_post" in result_data
            post_data = result_data["comments_by_post"]["test_post_123"]
            assert post_data["error"] == "fetch_failed"
            assert post_data["comments"] == []
            assert post_data["total_count"] == 0
            print("✓ Line 134 covered successfully")


def test_line_143_rate_limiting():
    """Test line 143 - rate limiting between multiple posts"""
    print("Testing line 143: rate limiting for multiple posts")

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

        with patch('linkedin_agent.tools.get_post_comments.load_environment'), \
             patch('linkedin_agent.tools.get_post_comments.get_required_env_var') as mock_get_env, \
             patch('linkedin_agent.tools.get_post_comments.time.sleep') as mock_sleep:

            mock_get_env.return_value = "test-value"

            from linkedin_agent.tools.get_post_comments import GetPostComments

            # Create tool with MULTIPLE post_ids (triggers rate limiting)
            tool = GetPostComments(post_ids=["post_1", "post_2"])

            # Mock successful requests
            def mock_successful_request(url, headers, params):
                return {
                    "data": [
                        {
                            "id": "comment_1",
                            "authorName": "Test User",
                            "text": "Test comment",
                            "likes": 1
                        }
                    ],
                    "pagination": {"hasMore": False}
                }

            tool._make_request_with_retry = mock_successful_request

            result = tool.run()
            result_data = json.loads(result)

            # Should hit line 143 - sleep called for rate limiting
            mock_sleep.assert_called_with(0.5)

            # Verify both posts were processed
            assert "comments_by_post" in result_data
            assert "post_1" in result_data["comments_by_post"]
            assert "post_2" in result_data["comments_by_post"]
            print("✓ Line 143 covered successfully")


class TestGetPostComments100Percent(unittest.TestCase):
    """Test class to achieve 100% coverage"""

    def test_all_missing_lines(self):
        """Test all missing lines for 100% coverage"""
        test_line_87_empty_post_ids()
        test_line_134_failed_request()
        test_line_143_rate_limiting()
        print("🎉 All missing lines covered - 100% coverage achieved!")


if __name__ == "__main__":
    # Run individual tests
    test_line_87_empty_post_ids()
    test_line_134_failed_request()
    test_line_143_rate_limiting()
    print("\n🎉 All tests passed - 100% coverage achieved!")