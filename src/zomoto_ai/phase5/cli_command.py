"""CLI Command for Phase 5 - Complete recommendation pipeline

Integrates all phases (1-4) with CLI presentation for a complete user experience.
"""

import os
import sys
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.prompt import Prompt, IntPrompt, FloatPrompt, Confirm

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from zomoto_ai.phase0.domain.models import Budget, UserPreference
from zomoto_ai.phase3.retrieval import load_restaurants_from_parquet, retrieve_with_relaxation
from zomoto_ai.phase4.groq_ranker import GroqLLMClient
from .cli import EnhancedCLIPresenter


class RecommendationCLI:
    """Complete CLI for restaurant recommendations."""
    
    def __init__(self, data_path: Optional[str] = None):
        self.console = Console()
        self.presenter = EnhancedCLIPresenter(self.console)
        self.data_path = data_path or "data/restaurants_processed.parquet"
        self.restaurants = None
        self.llm_client = None
    
    def initialize(self) -> bool:
        """Initialize the CLI components."""
        try:
            # Load restaurants
            self.console.print("🔄 Loading restaurant database...")
            self.restaurants = load_restaurants_from_parquet(self.data_path)
            self.console.print(f"✅ Loaded {len(self.restaurants)} restaurants\n")
            
            # Initialize LLM client
            if os.getenv("GROQ_API_KEY"):
                self.console.print("🤖 Initializing AI recommendation engine...")
                self.llm_client = GroqLLMClient()
                self.console.print("✅ AI engine ready\n")
            else:
                self.console.print("⚠️  No GROQ_API_KEY found - AI ranking disabled\n")
            
            return True
            
        except Exception as e:
            self.presenter.present_error(f"Failed to initialize: {e}")
            return False
    
    def run_interactive(self) -> None:
        """Run interactive recommendation session."""
        self.console.print("🍽️  Welcome to Zomoto AI Restaurant Recommendations!\n")
        
        if not self.initialize():
            return
        
        while True:
            try:
                # Get user preferences
                user_pref = self._get_user_preferences()
                if not user_pref:
                    break
                
                # Generate recommendations
                self.presenter.present_loading("Finding restaurants for you...")
                result = self._generate_recommendations(user_pref)
                
                # Present results
                self.presenter.present_recommendations(result)
                
                # Ask if user wants another recommendation
                if not Confirm.ask("\nWould you like to try another search?"):
                    break
                    
            except KeyboardInterrupt:
                self.console.print("\n👋 Goodbye!")
                break
            except Exception as e:
                self.presenter.present_error(f"An error occurred: {e}")
                if not Confirm.ask("Would you like to try again?"):
                    break
    
    def run_single(self, location: str, budget: Optional[int] = None, 
                   min_rating: Optional[float] = None, cuisine: Optional[str] = None) -> None:
        """Run a single recommendation with provided parameters."""
        self.console.print("🍽️  Zomoto AI Restaurant Recommendations\n")
        
        if not self.initialize():
            return
        
        # Build user preference
        budget_obj = Budget(kind="range", max_cost_for_two=budget) if budget else None
        rating = min_rating if min_rating is not None else 0.0
        
        user_pref = UserPreference(
            location=location,
            budget=budget_obj,
            cuisine=cuisine,
            min_rating=rating
        )
        
        # Generate and present recommendations
        self.presenter.present_loading("Finding restaurants for you...")
        result = self._generate_recommendations(user_pref)
        self.presenter.present_recommendations(result)
    
    def _get_user_preferences(self) -> Optional[UserPreference]:
        """Get user preferences interactively."""
        self.console.print("📍 Tell us about your preferences:\n")
        
        try:
            # Location
            location = Prompt.ask("Location", default="Bangalore")
            
            # Budget
            has_budget = Confirm.ask("Do you have a budget constraint?")
            budget = None
            if has_budget:
                budget = IntPrompt.ask("Maximum cost for two people", default=1000)
            
            # Rating
            has_rating = Confirm.ask("Do you have a minimum rating requirement?")
            min_rating = 0.0
            if has_rating:
                min_rating = FloatPrompt.ask("Minimum rating (0-5)", default=4.0)
            
            # Cuisine
            cuisine = Prompt.ask("Preferred cuisine (optional)", default="")
            cuisine = cuisine if cuisine else None
            
            # Optional constraints
            has_constraints = Confirm.ask("Any specific restaurant names?")
            optional_constraints = []
            if has_constraints:
                while True:
                    restaurant = Prompt.ask("Restaurant name (or press Enter to finish)", default="")
                    if not restaurant:
                        break
                    optional_constraints.append(restaurant)
            
            return UserPreference(
                location=location,
                budget=Budget(kind="range", max_cost_for_two=budget) if budget else None,
                cuisine=cuisine,
                min_rating=min_rating,
                optional_constraints=optional_constraints
            )
            
        except KeyboardInterrupt:
            return None
    
    def _generate_recommendations(self, user_pref: UserPreference):
        """Generate recommendations using the complete pipeline."""
        # Phase 3: Retrieval with relaxation
        retrieval_result = retrieve_with_relaxation(
            self.restaurants, 
            user_pref, 
            top_n=50
        )
        
        # Phase 4: LLM ranking (if available)
        if self.llm_client and retrieval_result.candidate_set.candidates:
            try:
                return self.llm_client.rank_and_explain(retrieval_result.candidate_set)
            except Exception as e:
                self.console.print(f"⚠️  AI ranking failed: {e}")
                # Fallback to basic ranking
                return self._fallback_ranking(retrieval_result.candidate_set)
        else:
            # Fallback ranking
            return self._fallback_ranking(retrieval_result.candidate_set)
    
    def _fallback_ranking(self, candidate_set):
        """Fallback ranking when LLM is not available."""
        from zomoto_ai.phase0.domain.models import RecommendationResult, RecommendationItem
        
        # Simple ranking by rating and votes
        sorted_candidates = sorted(
            candidate_set.candidates,
            key=lambda r: (r.rating or 0, r.votes or 0),
            reverse=True
        )
        
        items = []
        for i, restaurant in enumerate(sorted_candidates[:10], 1):
            explanation = f"Ranked #{i} by rating ({restaurant.rating or 'N/A'}) and popularity ({restaurant.votes or 'N/A'} votes)"
            items.append(RecommendationItem(
                restaurant_id=restaurant.id,
                rank=i,
                explanation=explanation
            ))
        
        return RecommendationResult(
            user_preference=candidate_set.user_preference,
            items=items,
            summary=f"Top {len(items)} restaurants ranked by rating and popularity (no AI ranking available)"
        )


def main():
    """Main CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Zomoto AI Restaurant Recommendations")
    parser.add_argument("--location", help="Location for recommendations")
    parser.add_argument("--budget", type=int, help="Maximum cost for two")
    parser.add_argument("--rating", type=float, help="Minimum rating")
    parser.add_argument("--cuisine", help="Preferred cuisine")
    parser.add_argument("--data-path", help="Path to restaurant data")
    
    args = parser.parse_args()
    
    cli = RecommendationCLI(data_path=args.data_path)
    
    if args.location:
        # Single recommendation mode
        cli.run_single(
            location=args.location,
            budget=args.budget,
            min_rating=args.rating,
            cuisine=args.cuisine
        )
    else:
        # Interactive mode
        cli.run_interactive()


if __name__ == "__main__":
    main()
