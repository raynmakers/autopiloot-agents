"""Example tests showing how to test different broker types."""

import pytest
import requests


@pytest.mark.integration
class TestCallableBrokers:
    """Examples of testing callable brokers (client-callable functions)."""
    
    def test_example_callable_success(self, firebase_emulator, test_user_id):
        """Test the example callable function."""
        base_url = firebase_emulator["base_url"]
        url = f"{base_url}/example_callable"
        
        headers = {"User-Id": test_user_id}
        
        response = requests.post(
            url,
            json={"data": {"message": "Hello World"}},
            headers=headers,
        )
        
        assert response.status_code == 200
        result = response.json()["result"]
        assert result["success"] is True
        assert result["echo"] == "Hello World"
        assert result["userId"] == test_user_id


@pytest.mark.integration 
class TestHttpsBrokers:
    """Examples of testing HTTPS brokers (REST endpoints)."""
    
    def test_health_check_endpoint(self, firebase_emulator):
        """Test the health check HTTP endpoint."""
        base_url = firebase_emulator["base_url"] 
        # Note: HTTPS functions use different URL pattern
        url = f"http://localhost:5001/test-project/us-central1/health_check"
        
        response = requests.get(url)
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "degraded"]
        assert "services" in data
        assert data["services"]["functions"] == "healthy"
    
    def test_webhook_handler_endpoint(self, firebase_emulator):
        """Test the webhook handler HTTP endpoint."""
        url = f"http://localhost:5001/test-project/us-central1/webhook_handler"
        
        response = requests.post(
            url,
            json={
                "event": "item.created",
                "data": {"itemId": "test-123"},
                "timestamp": "2024-01-01T00:00:00Z"
            },
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["event"] == "item.created"