#!/usr/bin/env python3
"""
Show exact LLM output from Phase 4 ranking
"""

import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from zomoto_ai.phase0.domain.models import Budget, UserPreference
from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet, retrieve_with_relaxation
from zomoto_ai.phase4.groq_ranker import GroqLLMClient
from zomoto_ai.phase4.prompting import build_rank_prompt


def main():
    print("=== Capturing Exact LLM Output ===\n")
    
    # Set up user preference
    user_pref = UserPreference(
        location="Bangalore",
        budget=Budget(kind="range", min_cost_for_two=None, max_cost_for_two=1000),
        min_rating=4.5
    )
    
    print(f"User Preference: {user_pref.location}, Budget ≤ {user_pref.budget.max_cost_for_two}, Rating ≥ {user_pref.min_rating}\n")
    
    # Load restaurants and get candidates
    data_path = "data/restaurants_processed.parquet"
    restaurants = load_restaurants_from_parquet(data_path)
    retrieval_result = retrieve_with_relaxation(restaurants, user_pref, top_n=10)  # Use smaller set for clearer output
    
    print(f"Candidates for LLM ranking: {len(retrieval_result.candidate_set.candidates)}\n")
    
    # Show the prompt being sent to LLM
    print("=== PROMPT SENT TO LLM ===")
    prompt = build_rank_prompt(retrieval_result.candidate_set, top_k=5)
    print(prompt)
    print("\n" + "="*80 + "\n")
    
    # Initialize client and capture raw LLM response
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not set!")
        return
    
    client = GroqLLMClient()
    
    print("=== RAW LLM RESPONSE ===")
    # Monkey patch to capture the raw response
    original_chat = client._chat
    
    def capture_chat(prompt):
        response = original_chat(prompt)
        print("RAW OUTPUT:")
        print(response)
        print("\n" + "="*80 + "\n")
        return response
    
    client._chat = capture_chat
    
    try:
        result = client.rank_and_explain(retrieval_result.candidate_set)
        
        print("=== FINAL PARSED RESULT ===")
        print(f"Summary: {result.summary}")
        print(f"Items: {len(result.items)}")
        
        for item in result.items:
            print(f"\nRank {item.rank}: Restaurant ID {item.restaurant_id}")
            print(f"Explanation: {item.explanation}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
