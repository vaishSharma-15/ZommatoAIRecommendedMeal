"""CLI Presenter for Phase 5 - Option A

Provides user-friendly command-line presentation of recommendation results.
"""

from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from zomoto_ai.phase0.domain.models import RecommendationResult, UserPreference


class CLIPresenter:
    """CLI presenter for restaurant recommendations with rich formatting."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console or Console()
    
    def present_recommendations(
        self, 
        result: RecommendationResult, 
        show_summary: bool = True,
        max_items: Optional[int] = None
    ) -> None:
        """Present recommendations in a user-friendly CLI format."""
        
        if show_summary and result.summary:
            self._show_summary(result.summary)
        
        if not result.items:
            self._show_no_results()
            return
        
        # Show user preference context
        self._show_user_preference(result.user_preference)
        
        # Show recommendations table
        self._show_recommendations_table(result, max_items)
    
    def _show_summary(self, summary: str) -> None:
        """Display the recommendation summary."""
        panel = Panel(
            Text(summary, style="italic"),
            title="🎯 Summary",
            border_style="blue",
            padding=(0, 1)
        )
        self.console.print(panel)
        self.console.print()
    
    def _show_user_preference(self, preference: UserPreference) -> None:
        """Display the user preferences that generated these results."""
        table = Table(title="🔍 Your Preferences", show_header=False, box=None)
        table.add_column("Preference", style="bold")
        table.add_column("Value")
        
        table.add_row("Location", preference.location)
        
        if preference.budget:
            if preference.budget.kind == "bucket":
                budget_str = f"Bucket: {preference.budget.bucket or 'medium'}"
            else:
                budget_str = f"Range: {preference.budget.min_cost_for_two or 'any'} - {preference.budget.max_cost_for_two or 'any'}"
            table.add_row("Budget", budget_str)
        else:
            table.add_row("Budget", "No constraint")
        
        table.add_row("Min Rating", f"⭐ {preference.min_rating}")
        
        if preference.cuisine:
            table.add_row("Cuisine", preference.cuisine)
        
        if preference.optional_constraints:
            constraints = ", ".join(preference.optional_constraints)
            table.add_row("Specific Requests", constraints)
        
        self.console.print(table)
        self.console.print()
    
    def _show_recommendations_table(self, result: RecommendationResult, max_items: Optional[int]) -> None:
        """Display recommendations in a formatted table."""
        items_to_show = result.items[:max_items] if max_items else result.items
        
        table = Table(
            title=f"🍽️  Top {len(items_to_show)} Restaurant Recommendations",
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("Rank", style="bold", width=6)
        table.add_column("Name", style="bold cyan", min_width=20)
        table.add_column("Location", style="green", min_width=15)
        table.add_column("Cuisines", style="yellow", min_width=15)
        table.add_column("Cost", style="red", width=8)
        table.add_column("Rating", style="blue", width=7)
        table.add_column("Explanation", style="white", min_width=30)
        
        for item in items_to_show:
            # Find restaurant details (we'd need access to candidate set for full details)
            # For now, we'll show what's available in the recommendation result
            rank_text = f"#{item.rank}"
            name_text = item.restaurant_id  # In real implementation, we'd fetch restaurant name
            
            # Create a simple explanation display
            explanation = item.explanation
            if len(explanation) > 50:
                explanation = explanation[:47] + "..."
            
            table.add_row(
                rank_text,
                name_text,
                "Location info",  # Would be populated from restaurant data
                "Cuisine info",   # Would be populated from restaurant data
                "₹???",          # Would be populated from restaurant data
                "⭐?.?",         # Would be populated from restaurant data
                explanation
            )
        
        self.console.print(table)
        self.console.print()
        
        if max_items and len(result.items) > max_items:
            self.console.print(f"... and {len(result.items) - max_items} more recommendations")
    
    def _show_no_results(self) -> None:
        """Display message when no recommendations are available."""
        panel = Panel(
            Text("No restaurants found matching your preferences. Try relaxing your criteria!", style="bold red"),
            title="❌ No Results",
            border_style="red",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def present_error(self, error_message: str) -> None:
        """Present error message in CLI format."""
        panel = Panel(
            Text(error_message, style="bold red"),
            title="❌ Error",
            border_style="red",
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def present_loading(self, message: str = "Generating recommendations...") -> None:
        """Present loading message."""
        self.console.print(f"⏳ {message}")


class EnhancedCLIPresenter(CLIPresenter):
    """Enhanced CLI presenter with restaurant details integration."""
    
    def __init__(self, console: Optional[Console] = None):
        super().__init__(console)
        # In a real implementation, we'd have access to restaurant data
        # For now, we'll create a simple mapping for demonstration
        self._restaurant_cache = {}
    
    def _show_recommendations_table(self, result: RecommendationResult, max_items: Optional[int]) -> None:
        """Display recommendations with full restaurant details."""
        items_to_show = result.items[:max_items] if max_items else result.items
        
        table = Table(
            title=f"🍽️  Top {len(items_to_show)} Restaurant Recommendations",
            show_header=True,
            header_style="bold magenta"
        )
        
        table.add_column("Rank", style="bold", width=6)
        table.add_column("Name", style="bold cyan", min_width=20)
        table.add_column("Location", style="green", min_width=15)
        table.add_column("Cuisines", style="yellow", min_width=15)
        table.add_column("Cost", style="red", width=8)
        table.add_column("Rating", style="blue", width=7)
        table.add_column("Explanation", style="white", min_width=30)
        
        for item in items_to_show:
            rank_text = f"#{item.rank}"
            
            # Try to get restaurant info from cache (in real implementation)
            restaurant_name = item.restaurant_id  # Fallback to ID
            
            # Format explanation with proper wrapping
            explanation = self._wrap_text(item.explanation, 40)
            
            table.add_row(
                rank_text,
                restaurant_name,
                "See location",  # Would be populated from restaurant data
                "See cuisines",   # Would be populated from restaurant data
                "₹???",          # Would be populated from restaurant data
                "⭐?.?",         # Would be populated from restaurant data
                explanation
            )
        
        self.console.print(table)
        self.console.print()
    
    def _wrap_text(self, text: str, max_length: int) -> str:
        """Wrap text to fit within specified length."""
        if len(text) <= max_length:
            return text
        
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            if len(current_line) + len(word) + 1 <= max_length:
                current_line += (" " if current_line else "") + word
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        
        if current_line:
            lines.append(current_line)
        
        return "\n".join(lines[:3])  # Max 3 lines
