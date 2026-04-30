"""Phase 5 - Presentation (CLI → API/UI)

This phase provides user-friendly presentation of recommendation results.
It includes both CLI and API/UI options for displaying recommendations.
"""

from .cli import CLIPresenter
from .api import RecommendationAPI
from .frontend import RecommendationUI

__all__ = ["CLIPresenter", "RecommendationAPI", "RecommendationUI"]
