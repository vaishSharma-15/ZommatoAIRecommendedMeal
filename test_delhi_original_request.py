#!/usr/bin/env python3
"""
Test Phase 4 with ORIGINAL request: Delhi, Budget 1000, Rating 4.5
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from zomoto_ai.phase0.domain.models import Budget, UserPreference
from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet, retrieve_with_relaxation
from zomoto_ai.phase4.groq_ranker import GroqLLMClient


def main():
    print("=== Phase 4 Test: ORIGINAL REQUEST - Delhi, Budget 1000, Rating 4.5 ===\n")
    
    # Set up user preference with ORIGINAL request
    user_pref = UserPreference(
        location="Delhi",
        budget=Budget(kind="range", min_cost_for_two=None, max_cost_for_two=1000),
        min_rating=4.5
    )
    
    print(f"ORIGINAL User Preference:")
    print(f"  Location: {user_pref.location}")
    print(f"  Budget: Up to {user_pref.budget.max_cost_for_two} for two")
    print(f"  Min Rating: {user_pref.min_rating}")
    print()
    
    # Load restaurants
    data_path = "data/restaurants_processed.parquet"
    print(f"Loading restaurants from {data_path}...")
    restaurants = load_restaurants_from_parquet(data_path)
    print(f"Loaded {len(restaurants)} restaurants\n")
    
    # Check if ANY Delhi restaurants exist
    print("=== Checking for Delhi Restaurants ===")
    delhi_restaurants = []
    for restaurant in restaurants:
        location_match = (
            (restaurant.city and 'delhi' in restaurant.city.lower()) or
            (restaurant.area and 'delhi' in restaurant.area.lower()) or
            (restaurant.location and 'delhi' in restaurant.location.lower())
        )
        if location_match:
            delhi_restaurants.append(restaurant)
    
    print(f"Delhi restaurants found: {len(delhi_restaurants)}")
    if delhi_restaurants:
        for restaurant in delhi_restaurants[:5]:
            print(f"  - {restaurant.name}: {restaurant.location or restaurant.city}")
    else:
        print("  ❌ NO DELHI RESTAURANTS FOUND IN DATASET")
        print("\nDataset contains only Bangalore restaurants!")
        
        # Show what cities ARE available
        cities = {}
        for restaurant in restaurants:
            if restaurant.city:
                cities[restaurant.city] = cities.get(restaurant.city, 0) + 1
        
        print("\nAvailable cities in dataset:")
        for city, count in sorted(cities.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  - {city}: {count} restaurants")
    
    print()
    
    # Phase 3: Retrieval with relaxation (will show extensive relaxation)
    print("=== Phase 3: Retrieval with Relaxation ===")
    retrieval_result = retrieve_with_relaxation(restaurants, user_pref, top_n=50)
    
    print(f"Relaxation steps: {len(retrieval_result.relax_steps)}")
    for i, step in enumerate(retrieval_result.relax_steps, 1):
        print(f"  {i}. {step.action}: {step.note}")
    
    print(f"\nCandidates found: {retrieval_result.total_candidates_before_reduce}")
    print(f"Reduced to: {retrieval_result.reduced_to}")
    print()
    
    # Phase 4: Groq LLM ranking (will show no candidates)
    print("=== Phase 4: Groq LLM Ranking ===")
    try:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY environment variable not set!")
            return
        
        print("Initializing Groq LLM Client...")
        client = GroqLLMClient()
        
        print("Ranking and generating explanations...")
        recommendation_result = client.rank_and_explain(retrieval_result.candidate_set)
        
        print(f"\n=== Final Recommendations ===")
        print(f"Summary: {recommendation_result.summary}")
        print(f"Items returned: {len(recommendation_result.items)}")
        
        if len(recommendation_result.items) == 0:
            print("❌ NO RECOMMENDATIONS - No Delhi restaurants found in dataset")
        else:
            for item in recommendation_result.items:
                restaurant = next(r for r in retrieval_result.candidate_set.candidates if r.id == item.restaurant_id)
                print(f"\n{item.rank}. {restaurant.name}")
                print(f"   Location: {restaurant.location or restaurant.city}")
                print(f"   Explanation: {item.explanation}")
        
        print(f"\n✅ Phase 4 test completed - shows dataset limitation!")
        
    except Exception as e:
        print(f"❌ Error in Phase 4: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
