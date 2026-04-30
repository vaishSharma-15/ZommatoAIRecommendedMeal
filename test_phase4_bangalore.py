#!/usr/bin/env python3
"""
Test Phase 4 with live example using Bangalore (since dataset has Bangalore restaurants):
Input: Bangalore, Budget: 1000, Rating: 4.5
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
    print("=== Phase 4 Test: Bangalore, Budget 1000, Rating 4.5 ===\n")
    
    # Set up user preference with Bangalore instead of Delhi
    user_pref = UserPreference(
        location="Bangalore",
        budget=Budget(kind="range", min_cost_for_two=None, max_cost_for_two=1000),
        min_rating=4.5
    )
    
    print(f"User Preference:")
    print(f"  Location: {user_pref.location}")
    print(f"  Budget: Up to {user_pref.budget.max_cost_for_two} for two")
    print(f"  Min Rating: {user_pref.min_rating}")
    print()
    
    # Load restaurants
    data_path = "data/restaurants_processed.parquet"
    print(f"Loading restaurants from {data_path}...")
    restaurants = load_restaurants_from_parquet(data_path)
    print(f"Loaded {len(restaurants)} restaurants\n")
    
    # Phase 3: Retrieval with relaxation
    print("=== Phase 3: Retrieval with Relaxation ===")
    retrieval_result = retrieve_with_relaxation(restaurants, user_pref, top_n=50)
    
    print(f"Relaxation steps: {len(retrieval_result.relax_steps)}")
    for i, step in enumerate(retrieval_result.relax_steps, 1):
        print(f"  {i}. {step.action}: {step.note}")
    
    print(f"\nCandidates found: {retrieval_result.total_candidates_before_reduce}")
    print(f"Reduced to: {retrieval_result.reduced_to}")
    print()
    
    # Show some candidates
    print("=== Sample Candidates ===")
    for i, restaurant in enumerate(retrieval_result.candidate_set.candidates[:5], 1):
        print(f"{i}. {restaurant.name}")
        print(f"   Location: {restaurant.location or restaurant.city}")
        print(f"   Cuisines: {', '.join(restaurant.cuisines[:3])}")
        print(f"   Cost: {restaurant.cost_for_two}, Rating: {restaurant.rating}")
        print()
    
    # Phase 4: Groq LLM ranking
    print("=== Phase 4: Groq LLM Ranking ===")
    try:
        # Check for API key
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            print("Error: GROQ_API_KEY environment variable not set!")
            print("Please set it using: export GROQ_API_KEY=your_key")
            return
        
        print("Initializing Groq LLM Client...")
        client = GroqLLMClient()
        
        print("Ranking and generating explanations...")
        recommendation_result = client.rank_and_explain(retrieval_result.candidate_set)
        
        print(f"\n=== Final Recommendations ===")
        print(f"Summary: {recommendation_result.summary}")
        print(f"\nTop {len(recommendation_result.items)} recommendations:")
        
        for item in recommendation_result.items:
            restaurant = next(r for r in retrieval_result.candidate_set.candidates if r.id == item.restaurant_id)
            print(f"\n{item.rank}. {restaurant.name}")
            print(f"   Location: {restaurant.location or restaurant.city}")
            print(f"   Cuisines: {', '.join(restaurant.cuisines[:3])}")
            print(f"   Cost: {restaurant.cost_for_two}, Rating: {restaurant.rating}")
            print(f"   Explanation: {item.explanation}")
        
        print(f"\n✅ Phase 4 test completed successfully!")
        
    except Exception as e:
        print(f"❌ Error in Phase 4: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
