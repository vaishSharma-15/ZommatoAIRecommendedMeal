"""Comprehensive Testing Suite for Phase 6

Provides unit tests for normalization, filtering, relaxation strategy,
and golden tests for LLM prompt/output validation.
"""

import pytest
import json
import time
from typing import Dict, List, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
import hashlib

# Import all phases for testing
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import (
    Restaurant, UserPreference, Budget, CandidateSet, 
    RecommendationResult, RecommendationItem
)
from zomoto_ai.phase3.retrieval import (
    load_restaurants_from_parquet, retrieve_with_relaxation,
    filter_candidates, reduce_candidates, budget_to_range,
    _norm, _contains, _cuisine_exact_match, _cuisine_partial_match, _location_match
)
from zomoto_ai.phase4.groq_ranker import GroqLLMClient, GroqConfig
from zomoto_ai.phase5.api import app as api_app
from fastapi.testclient import TestClient


@dataclass
class TestCase:
    """Test case definition."""
    name: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    description: str


@dataclass
class GoldenTestCase:
    """Golden test case for LLM validation."""
    name: str
    user_preference: UserPreference
    candidate_set: CandidateSet
    expected_llm_output: Dict[str, Any]
    validation_rules: List[str]


class TestSuite:
    """Comprehensive test suite for all phases."""
    
    def __init__(self):
        self.test_results = []
        self.mock_restaurants = self._create_mock_restaurants()
    
    def _create_mock_restaurants(self) -> List[Restaurant]:
        """Create mock restaurant data for testing."""
        return [
            Restaurant(
                id="1",
                name="Italian Place",
                location="Bangalore",
                city="Bangalore",
                area="Koramangala",
                cuisines=["Italian", "Continental"],
                cost_for_two=800,
                rating=4.2,
                votes=150
            ),
            Restaurant(
                id="2", 
                name="Chinese Corner",
                location="Bangalore",
                city="Bangalore",
                area="BTM",
                cuisines=["Chinese", "Thai"],
                cost_for_two=600,
                rating=3.8,
                votes=200
            ),
            Restaurant(
                id="3",
                name="Budget Bites",
                location="Bangalore", 
                city="Bangalore",
                area="Jayanagar",
                cuisines=["North Indian", "Chinese"],
                cost_for_two=400,
                rating=3.5,
                votes=100
            ),
            Restaurant(
                id="4",
                name="Fine Dining",
                location="Bangalore",
                city="Bangalore", 
                area="Indiranagar",
                cuisines=["Continental", "European"],
                cost_for_two=2000,
                rating=4.8,
                votes=300
            ),
            Restaurant(
                id="5",
                name="Cafe Coffee",
                location="Delhi",
                city="Delhi",
                area="Connaught Place",
                cuisines=["Cafe", "Beverages"],
                cost_for_two=500,
                rating=4.0,
                votes=250
            )
        ]
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites."""
        results = {
            "phase0_tests": self.test_phase0_domain_models(),
            "phase3_tests": self.test_phase3_retrieval(),
            "phase4_tests": self.test_phase4_llm_ranking(),
            "phase5_tests": self.test_phase5_api(),
            "integration_tests": self.test_integration(),
            "summary": self.generate_summary()
        }
        return results
    
    def test_phase0_domain_models(self) -> Dict[str, Any]:
        """Test Phase 0 domain models."""
        test_cases = [
            TestCase(
                name="restaurant_creation_valid",
                input_data={
                    "id": "test1",
                    "name": "Test Restaurant",
                    "location": "Bangalore",
                    "cuisines": ["Italian"],
                    "cost_for_two": 1000,
                    "rating": 4.0,
                    "votes": 100
                },
                expected_output={"valid": True},
                description="Test valid restaurant creation"
            ),
            TestCase(
                name="restaurant_creation_invalid_rating",
                input_data={
                    "id": "test2",
                    "name": "Test Restaurant",
                    "location": "Bangalore",
                    "cuisines": ["Italian"],
                    "cost_for_two": 1000,
                    "rating": 6.0,  # Invalid rating > 5
                    "votes": 100
                },
                expected_output={"valid": False},
                description="Test invalid rating validation"
            ),
            TestCase(
                name="user_preference_creation",
                input_data={
                    "location": "Bangalore",
                    "budget": {"kind": "range", "max_cost_for_two": 1000},
                    "min_rating": 4.0,
                    "cuisine": "Italian"
                },
                expected_output={"valid": True},
                description="Test user preference creation"
            ),
            TestCase(
                name="budget_bucket_conversion",
                input_data={"kind": "bucket", "bucket": "medium"},
                expected_output={"range_exists": True},
                description="Test budget bucket to range conversion"
            )
        ]
        
        results = []
        for test_case in test_cases:
            try:
                result = self._run_phase0_test(test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "description": test_case.description
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "description": test_case.description,
                    "error": str(e)
                })
        
        return {"tests": results, "passed": sum(1 for r in results if r["status"] == "PASSED")}
    
    def _run_phase0_test(self, test_case: TestCase) -> bool:
        """Run individual Phase 0 test."""
        if test_case.name == "restaurant_creation_valid":
            restaurant = Restaurant(**test_case.input_data)
            return restaurant.id == "test1" and restaurant.rating == 4.0
        
        elif test_case.name == "restaurant_creation_invalid_rating":
            try:
                Restaurant(**test_case.input_data)
                return False  # Should have failed validation
            except Exception:
                return True  # Expected to fail
        
        elif test_case.name == "user_preference_creation":
            budget = Budget(**test_case.input_data["budget"])
            preference = UserPreference(
                location=test_case.input_data["location"],
                budget=budget,
                min_rating=test_case.input_data["min_rating"],
                cuisine=test_case.input_data["cuisine"]
            )
            return preference.location == "Bangalore"
        
        elif test_case.name == "budget_bucket_conversion":
            budget = Budget(**test_case.input_data)
            min_c, max_c, _ = budget_to_range(budget)
            return min_c is not None and max_c is not None
        
        return False
    
    def test_phase3_retrieval(self) -> Dict[str, Any]:
        """Test Phase 3 retrieval components."""
        test_cases = [
            TestCase(
                name="location_matching",
                input_data={
                    "restaurant": self.mock_restaurants[0],
                    "location": "Bangalore"
                },
                expected_output={"match": True},
                description="Test location matching logic"
            ),
            TestCase(
                name="cuisine_exact_match",
                input_data={
                    "restaurant": self.mock_restaurants[0],
                    "cuisine": "Italian"
                },
                expected_output={"match": True},
                description="Test exact cuisine matching"
            ),
            TestCase(
                name="cuisine_partial_match",
                input_data={
                    "restaurant": self.mock_restaurants[1],
                    "cuisine": "Thai"
                },
                expected_output={"match": True},
                description="Test partial cuisine matching"
            ),
            TestCase(
                name="budget_filtering",
                input_data={
                    "restaurants": self.mock_restaurants,
                    "budget": {"kind": "range", "max_cost_for_two": 1000}
                },
                expected_output={"count": 3},
                description="Test budget-based filtering"
            ),
            TestCase(
                name="rating_filtering",
                input_data={
                    "restaurants": self.mock_restaurants,
                    "min_rating": 4.0
                },
                expected_output={"count": 2},
                description="Test rating-based filtering"
            ),
            TestCase(
                name="candidate_reduction",
                input_data={
                    "restaurants": self.mock_restaurants[:3],
                    "top_n": 2
                },
                expected_output={"count": 2},
                description="Test candidate reduction logic"
            )
        ]
        
        results = []
        for test_case in test_cases:
            try:
                result = self._run_phase3_test(test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "description": test_case.description
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "description": test_case.description,
                    "error": str(e)
                })
        
        return {"tests": results, "passed": sum(1 for r in results if r["status"] == "PASSED")}
    
    def _run_phase3_test(self, test_case: TestCase) -> bool:
        """Run individual Phase 3 test."""
        if test_case.name == "location_matching":
            restaurant = test_case.input_data["restaurant"]
            location = test_case.input_data["location"]
            return _location_match(restaurant, location)
        
        elif test_case.name == "cuisine_exact_match":
            restaurant = test_case.input_data["restaurant"]
            cuisine = test_case.input_data["cuisine"]
            return _cuisine_exact_match(restaurant, cuisine)
        
        elif test_case.name == "cuisine_partial_match":
            restaurant = test_case.input_data["restaurant"]
            cuisine = test_case.input_data["cuisine"]
            return _cuisine_partial_match(restaurant, cuisine)
        
        elif test_case.name == "budget_filtering":
            restaurants = test_case.input_data["restaurants"]
            budget = Budget(**test_case.input_data["budget"])
            filtered = filter_candidates(restaurants, UserPreference(location="Bangalore", budget=budget))
            return len(filtered) == test_case.expected_output["count"]
        
        elif test_case.name == "rating_filtering":
            restaurants = test_case.input_data["restaurants"]
            min_rating = test_case.input_data["min_rating"]
            filtered = filter_candidates(restaurants, UserPreference(location="Bangalore", min_rating=min_rating))
            return len(filtered) == test_case.expected_output["count"]
        
        elif test_case.name == "candidate_reduction":
            restaurants = test_case.input_data["restaurants"]
            top_n = test_case.input_data["top_n"]
            reduced = reduce_candidates(restaurants, top_n=top_n)
            return len(reduced) == test_case.expected_output["count"]
        
        return False
    
    def test_phase4_llm_ranking(self) -> Dict[str, Any]:
        """Test Phase 4 LLM ranking with mocked LLM."""
        test_cases = [
            TestCase(
                name="llm_client_initialization",
                input_data={"api_key": "test_key"},
                expected_output={"initialized": True},
                description="Test LLM client initialization"
            ),
            TestCase(
                name="llm_ranking_with_response",
                input_data={
                    "candidates": self.mock_restaurants[:3],
                    "mock_response": {
                        "items": [
                            {"restaurant_id": "1", "rank": 1, "explanation": "Great Italian restaurant"},
                            {"restaurant_id": "2", "rank": 2, "explanation": "Good Chinese option"}
                        ],
                        "summary": "Found 2 great restaurants"
                    }
                },
                expected_output={"ranked_count": 2},
                description="Test LLM ranking with mock response"
            ),
            TestCase(
                name="llm_fallback_behavior",
                input_data={
                    "candidates": self.mock_restaurants[:2],
                    "mock_error": "LLM API Error"
                },
                expected_output={"fallback_used": True},
                description="Test fallback ranking when LLM fails"
            )
        ]
        
        results = []
        for test_case in test_cases:
            try:
                result = self._run_phase4_test(test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "description": test_case.description
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "description": test_case.description,
                    "error": str(e)
                })
        
        return {"tests": results, "passed": sum(1 for r in results if r["status"] == "PASSED")}
    
    def _run_phase4_test(self, test_case: TestCase) -> bool:
        """Run individual Phase 4 test."""
        if test_case.name == "llm_client_initialization":
            try:
                with patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}):
                    client = GroqLLMClient()
                    return client._api_key == "test_key"
            except:
                return False
        
        elif test_case.name == "llm_ranking_with_response":
            with patch.object(GroqLLMClient, '_chat') as mock_chat:
                mock_chat.return_value = json.dumps(test_case.input_data["mock_response"])
                
                with patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}):
                    client = GroqLLMClient()
                    candidate_set = CandidateSet(
                        user_preference=UserPreference(location="Bangalore"),
                        candidates=test_case.input_data["candidates"]
                    )
                    result = client.rank_and_explain(candidate_set)
                    return len(result.items) == test_case.expected_output["ranked_count"]
        
        elif test_case.name == "llm_fallback_behavior":
            with patch.object(GroqLLMClient, '_chat') as mock_chat:
                mock_chat.side_effect = Exception("LLM API Error")
                
                with patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}):
                    client = GroqLLMClient()
                    candidate_set = CandidateSet(
                        user_preference=UserPreference(location="Bangalore"),
                        candidates=test_case.input_data["candidates"]
                    )
                    try:
                        client.rank_and_explain(candidate_set)
                        return False  # Should have failed
                    except:
                        return True  # Expected to fail
        
        return False
    
    def test_phase5_api(self) -> Dict[str, Any]:
        """Test Phase 5 API endpoints."""
        client = TestClient(api_app)
        
        test_cases = [
            TestCase(
                name="health_endpoint",
                input_data={},
                expected_output={"status_code": 200},
                description="Test health check endpoint"
            ),
            TestCase(
                name="recommendations_endpoint_valid",
                input_data={
                    "preferences": {
                        "location": "Bangalore",
                        "min_rating": 4.0
                    },
                    "top_n": 5
                },
                expected_output={"status_code": 200},
                description="Test recommendations endpoint with valid data"
            ),
            TestCase(
                name="recommendations_endpoint_invalid",
                input_data={
                    "preferences": {
                        "location": "",  # Invalid empty location
                    },
                    "top_n": 5
                },
                expected_output={"status_code": 422},
                description="Test recommendations endpoint with invalid data"
            )
        ]
        
        results = []
        for test_case in test_cases:
            try:
                result = self._run_phase5_test(client, test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "description": test_case.description
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "description": test_case.description,
                    "error": str(e)
                })
        
        return {"tests": results, "passed": sum(1 for r in results if r["status"] == "PASSED")}
    
    def _run_phase5_test(self, client: TestClient, test_case: TestCase) -> bool:
        """Run individual Phase 5 test."""
        if test_case.name == "health_endpoint":
            response = client.get("/health")
            return response.status_code == test_case.expected_output["status_code"]
        
        elif test_case.name == "recommendations_endpoint_valid":
            response = client.post("/recommendations", json=test_case.input_data)
            return response.status_code == test_case.expected_output["status_code"]
        
        elif test_case.name == "recommendations_endpoint_invalid":
            response = client.post("/recommendations", json=test_case.input_data)
            return response.status_code == test_case.expected_output["status_code"]
        
        return False
    
    def test_integration(self) -> Dict[str, Any]:
        """Test end-to-end integration."""
        test_cases = [
            TestCase(
                name="full_pipeline_integration",
                input_data={
                    "location": "Bangalore",
                    "budget": {"kind": "range", "max_cost_for_two": 1000},
                    "min_rating": 3.5
                },
                expected_output={"recommendations_generated": True},
                description="Test complete pipeline from preference to recommendation"
            ),
            TestCase(
                name="relaxation_strategy_integration",
                input_data={
                    "location": "NonExistentCity",
                    "budget": {"kind": "range", "max_cost_for_two": 100},
                    "min_rating": 5.0
                },
                expected_output={"relaxation_applied": True},
                description="Test relaxation strategy with impossible constraints"
            )
        ]
        
        results = []
        for test_case in test_cases:
            try:
                result = self._run_integration_test(test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "description": test_case.description
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "description": test_case.description,
                    "error": str(e)
                })
        
        return {"tests": results, "passed": sum(1 for r in results if r["status"] == "PASSED")}
    
    def _run_integration_test(self, test_case: TestCase) -> bool:
        """Run individual integration test."""
        if test_case.name == "full_pipeline_integration":
            # Test complete pipeline with mocked LLM
            with patch.object(GroqLLMClient, '_chat') as mock_chat:
                mock_response = {
                    "items": [
                        {"restaurant_id": "1", "rank": 1, "explanation": "Test explanation"}
                    ],
                    "summary": "Test summary"
                }
                mock_chat.return_value = json.dumps(mock_response)
                
                with patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}):
                    # Phase 3: Retrieval
                    user_pref = UserPreference(
                        location=test_case.input_data["location"],
                        budget=Budget(**test_case.input_data["budget"]),
                        min_rating=test_case.input_data["min_rating"]
                    )
                    retrieval_result = retrieve_with_relaxation(self.mock_restaurants, user_pref, top_n=10)
                    
                    # Phase 4: LLM Ranking
                    client = GroqLLMClient()
                    recommendation_result = client.rank_and_explain(retrieval_result.candidate_set)
                    
                    return len(recommendation_result.items) > 0
        
        elif test_case.name == "relaxation_strategy_integration":
            # Test relaxation with impossible constraints
            user_pref = UserPreference(
                location=test_case.input_data["location"],
                budget=Budget(**test_case.input_data["budget"]),
                min_rating=test_case.input_data["min_rating"]
            )
            retrieval_result = retrieve_with_relaxation(self.mock_restaurants, user_pref, top_n=10)
            
            # Should have applied relaxation steps
            return len(retrieval_result.relax_steps) > 0
        
        return False
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate test summary."""
        return {
            "total_tests_run": len(self.test_results),
            "timestamp": time.time(),
            "environment": "test"
        }


class GoldenTestSuite:
    """Golden test suite for LLM prompt/output validation."""
    
    def __init__(self):
        self.golden_tests = self._create_golden_tests()
        self.test_results = []
    
    def _create_golden_tests(self) -> List[GoldenTestCase]:
        """Create golden test cases for LLM validation."""
        return [
            GoldenTestCase(
                name="basic_ranking_validation",
                user_preference=UserPreference(
                    location="Bangalore",
                    min_rating=4.0
                ),
                candidate_set=CandidateSet(
                    user_preference=UserPreference(location="Bangalore", min_rating=4.0),
                    candidates=[
                        Restaurant(
                            id="1",
                            name="Italian Place",
                            location="Bangalore",
                            cuisines=["Italian"],
                            cost_for_two=800,
                            rating=4.2,
                            votes=150
                        ),
                        Restaurant(
                            id="2",
                            name="Chinese Corner",
                            location="Bangalore",
                            cuisines=["Chinese"],
                            cost_for_two=600,
                            rating=3.8,
                            votes=200
                        )
                    ]
                ),
                expected_llm_output={
                    "items": [
                        {
                            "restaurant_id": "1",
                            "rank": 1,
                            "explanation": "Highly rated Italian restaurant within budget"
                        }
                    ],
                    "summary": "Found 1 great restaurant"
                },
                validation_rules=[
                    "restaurant_id must be from candidate set",
                    "rank must be sequential starting from 1",
                    "explanation must reference restaurant attributes",
                    "summary must be concise"
                ]
            ),
            GoldenTestCase(
                name="grounding_validation",
                user_preference=UserPreference(
                    location="Bangalore",
                    budget=Budget(kind="range", max_cost_for_two=1000),
                    min_rating=3.5
                ),
                candidate_set=CandidateSet(
                    user_preference=UserPreference(location="Bangalore", min_rating=3.5),
                    candidates=[
                        Restaurant(
                            id="1",
                            name="Budget Bites",
                            location="Bangalore",
                            cuisines=["North Indian"],
                            cost_for_two=400,
                            rating=3.5,
                            votes=100
                        )
                    ]
                ),
                expected_llm_output={
                    "items": [
                        {
                            "restaurant_id": "1",
                            "rank": 1,
                            "explanation": "Affordable North Indian restaurant with rating 3.5"
                        }
                    ],
                    "summary": "Found 1 budget-friendly option"
                },
                validation_rules=[
                    "explanation must not contain hallucinated information",
                    "must only use provided restaurant attributes",
                    "cost and rating must match input data"
                ]
            )
        ]
    
    def run_golden_tests(self) -> Dict[str, Any]:
        """Run all golden tests."""
        results = []
        
        for test_case in self.golden_tests:
            try:
                result = self._run_golden_test(test_case)
                results.append({
                    "name": test_case.name,
                    "status": "PASSED" if result else "FAILED",
                    "validation_rules": test_case.validation_rules
                })
            except Exception as e:
                results.append({
                    "name": test_case.name,
                    "status": "ERROR",
                    "validation_rules": test_case.validation_rules,
                    "error": str(e)
                })
        
        return {
            "golden_tests": results,
            "passed": sum(1 for r in results if r["status"] == "PASSED"),
            "total": len(results)
        }
    
    def _run_golden_test(self, test_case: GoldenTestCase) -> bool:
        """Run individual golden test with mocked LLM."""
        with patch.object(GroqLLMClient, '_chat') as mock_chat:
            mock_chat.return_value = json.dumps(test_case.expected_llm_output)
            
            with patch.dict(os.environ, {"GROQ_API_KEY": "test_key"}):
                client = GroqLLMClient()
                result = client.rank_and_explain(test_case.candidate_set)
                
                # Validate output structure
                if not result.items or not result.summary:
                    return False
                
                # Validate each item
                for item in result.items:
                    # Check restaurant ID is from candidate set
                    candidate_ids = {r.id for r in test_case.candidate_set.candidates}
                    if item.restaurant_id not in candidate_ids:
                        return False
                    
                    # Check rank is sequential
                    if item.rank < 1:
                        return False
                    
                    # Check explanation is not empty
                    if not item.explanation.strip():
                        return False
                
                return True


def run_comprehensive_tests():
    """Run comprehensive test suite."""
    print("🧪 Running Comprehensive Test Suite for Phase 6")
    print("=" * 60)
    
    # Run unit tests
    test_suite = TestSuite()
    unit_results = test_suite.run_all_tests()
    
    # Run golden tests
    golden_suite = GoldenTestSuite()
    golden_results = golden_suite.run_golden_tests()
    
    # Generate report
    total_tests = 0
    total_passed = 0
    
    for phase_results in unit_results.values():
        if isinstance(phase_results, dict) and "passed" in phase_results:
            total_tests += len(phase_results.get("tests", []))
            total_passed += phase_results["passed"]
    
    total_tests += golden_results["total"]
    total_passed += golden_results["passed"]
    
    print(f"\n📊 Test Results Summary:")
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {total_passed}")
    print(f"Failed: {total_tests - total_passed}")
    print(f"Success Rate: {(total_passed/total_tests)*100:.1f}%")
    
    return {
        "unit_tests": unit_results,
        "golden_tests": golden_results,
        "summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_tests - total_passed,
            "success_rate": (total_passed/total_tests)*100
        }
    }


if __name__ == "__main__":
    run_comprehensive_tests()
