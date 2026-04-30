"""Tests for Phase 5 - Presentation Layer

Tests for CLI, API, and UI components.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

# Import modules to test
from .cli import CLIPresenter, EnhancedCLIPresenter
from .api import app, RecommendationAPI, get_cache_key, convert_budget_request
from zomoto_ai.phase0.domain.models import Budget, UserPreference, RecommendationResult, RecommendationItem


class TestCLIPresenter:
    """Test CLI presentation components."""
    
    def test_cli_presenter_init(self):
        """Test CLI presenter initialization."""
        presenter = CLIPresenter()
        assert presenter.console is not None
    
    def test_enhanced_cli_presenter_init(self):
        """Test enhanced CLI presenter initialization."""
        presenter = EnhancedCLIPresenter()
        assert presenter.console is not None
        assert presenter._restaurant_cache == {}
    
    def test_wrap_text(self):
        """Test text wrapping functionality."""
        presenter = EnhancedCLIPresenter()
        
        # Test short text
        short_text = "Short text"
        wrapped = presenter._wrap_text(short_text, 50)
        assert wrapped == short_text
        
        # Test long text
        long_text = "This is a very long text that should be wrapped into multiple lines"
        wrapped = presenter._wrap_text(long_text, 20)
        assert '\n' in wrapped
        assert len(wrapped.split('\n')) <= 3


class TestAPIComponents:
    """Test API components."""
    
    def test_convert_budget_request(self):
        """Test budget request conversion."""
        # Test with budget
        budget_req = BudgetRequest(
            kind="range",
            max_cost_for_two=1000
        )
        budget = convert_budget_request(budget_req)
        assert budget.kind == "range"
        assert budget.max_cost_for_two == 1000
        
        # Test without budget
        budget = convert_budget_request(None)
        assert budget is None
    
    def test_get_cache_key(self):
        """Test cache key generation."""
        preferences = UserPreferenceRequest(
            location="Bangalore",
            cuisine="Italian",
            min_rating=4.0,
            optional_constraints=["FreshMenu"]
        )
        candidate_ids = ["id1", "id2", "id3"]
        
        key1 = get_cache_key(preferences, candidate_ids)
        key2 = get_cache_key(preferences, candidate_ids)
        
        assert key1 == key2
        assert isinstance(key1, str)
        assert len(key1) == 32  # MD5 hash length
    
    def test_cache_key_different_inputs(self):
        """Test cache key differs for different inputs."""
        preferences1 = UserPreferenceRequest(location="Bangalore")
        preferences2 = UserPreferenceRequest(location="Delhi")
        candidate_ids = ["id1", "id2"]
        
        key1 = get_cache_key(preferences1, candidate_ids)
        key2 = get_cache_key(preferences2, candidate_ids)
        
        assert key1 != key2


class TestAPIEndpoints:
    """Test API endpoints."""
    
    def setup_method(self):
        """Setup test client."""
        self.client = TestClient(app)
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = self.client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "restaurants_loaded" in data
        assert "llm_available" in data
        assert "cache_enabled" in data
    
    def test_cache_stats_endpoint(self):
        """Test cache statistics endpoint."""
        response = self.client.get("/cache/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "cache_size" in data
        assert "cache_enabled" in data
    
    def test_clear_cache_endpoint(self):
        """Test cache clearing endpoint."""
        response = self.client.delete("/cache")
        assert response.status_code == 200
        
        data = response.json()
        assert "message" in data
        assert data["message"] == "Cache cleared"
    
    @patch('zomoto_ai.phase5.api.restaurants')
    @patch('zomoto_ai.phase5.api.llm_client')
    def test_recommendations_endpoint_success(self, mock_llm, mock_restaurants):
        """Test successful recommendation generation."""
        # Mock restaurants
        mock_restaurants.__len__ = Mock(return_value=100)
        
        # Mock LLM response
        mock_result = RecommendationResult(
            user_preference=UserPreference(location="Bangalore"),
            items=[
                RecommendationItem(
                    restaurant_id="test_id",
                    rank=1,
                    explanation="Test explanation"
                )
            ],
            summary="Test summary"
        )
        mock_llm.rank_and_explain.return_value = mock_result
        
        # Test request
        request_data = {
            "preferences": {
                "location": "Bangalore",
                "min_rating": 4.0
            },
            "top_n": 5
        }
        
        response = self.client.post("/recommendations", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data
        assert "summary" in data
        assert len(data["recommendations"]) == 1
    
    def test_recommendations_endpoint_invalid_data(self):
        """Test recommendation endpoint with invalid data."""
        request_data = {
            "preferences": {
                "location": "",  # Invalid empty location
            },
            "top_n": 5
        }
        
        response = self.client.post("/recommendations", json=request_data)
        assert response.status_code == 422  # Validation error


class TestIntegration:
    """Integration tests for Phase 5 components."""
    
    @patch('zomoto_ai.phase5.api.load_restaurants_from_parquet')
    @patch('zomoto_ai.phase5.api.GroqLLMClient')
    def test_full_pipeline_integration(self, mock_llm_client_class, mock_load):
        """Test full recommendation pipeline integration."""
        # Mock restaurant loading
        from zomoto_ai.phase0.domain.models import Restaurant
        mock_restaurants = [
            Restaurant(
                id="1",
                name="Test Restaurant",
                location="Bangalore",
                cuisines=["Italian"],
                cost_for_two=1000,
                rating=4.5,
                votes=100
            )
        ]
        mock_load.return_value = mock_restaurants
        
        # Mock LLM client
        mock_llm_client = Mock()
        mock_llm_client.rank_and_explain.return_value = RecommendationResult(
            user_preference=UserPreference(location="Bangalore"),
            items=[
                RecommendationItem(
                    restaurant_id="1",
                    rank=1,
                    explanation="Great Italian restaurant"
                )
            ],
            summary="Found 1 great restaurant"
        )
        mock_llm_client_class.return_value = mock_llm_client
        
        # Test API client
        client = TestClient(app)
        
        request_data = {
            "preferences": {
                "location": "Bangalore",
                "min_rating": 4.0
            },
            "top_n": 5
        }
        
        response = self.client.post("/recommendations", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert len(data["recommendations"]) == 1
        assert data["recommendations"][0]["restaurant_id"] == "1"


# Pydantic models for testing
class BudgetRequest:
    def __init__(self, kind=None, bucket=None, min_cost_for_two=None, max_cost_for_two=None):
        self.kind = kind
        self.bucket = bucket
        self.min_cost_for_two = min_cost_for_two
        self.max_cost_for_two = max_cost_for_two


class UserPreferenceRequest:
    def __init__(self, location=None, budget=None, cuisine=None, min_rating=0.0, optional_constraints=None):
        self.location = location
        self.budget = budget
        self.cuisine = cuisine
        self.min_rating = min_rating
        self.optional_constraints = optional_constraints or []


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
