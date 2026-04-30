"""Main entry point for Phase 5 - Presentation Layer

Provides both CLI and API/UI options for restaurant recommendations.
"""

import sys
import argparse
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from .cli_command import RecommendationCLI
from .api import RecommendationAPI
from .frontend import main as frontend_main


def main():
    """Main entry point with mode selection."""
    parser = argparse.ArgumentParser(
        description="Zomoto AI Restaurant Recommendations - Phase 5",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive CLI mode
  python -m zomoto_ai.phase5
  
  # Single CLI recommendation
  python -m zomoto_ai.phase5 cli --location Bangalore --budget 1000 --rating 4.0
  
  # API server
  python -m zomoto_ai.phase5 api --port 8000
  
  # Full web UI
  python -m zomoto_ai.phase5 ui --port 8000
        """
    )
    
    parser.add_argument(
        "mode",
        choices=["cli", "api", "ui"],
        nargs="?",
        default="cli",
        help="Operation mode: cli (default), api, or ui"
    )
    
    # CLI-specific arguments
    cli_group = parser.add_argument_group("CLI Options")
    cli_group.add_argument("--location", help="Location for recommendations")
    cli_group.add_argument("--budget", type=int, help="Maximum cost for two")
    cli_group.add_argument("--rating", type=float, help="Minimum rating")
    cli_group.add_argument("--cuisine", help="Preferred cuisine")
    cli_group.add_argument("--data-path", help="Path to restaurant data")
    
    # API/UI-specific arguments
    server_group = parser.add_argument_group("Server Options")
    server_group.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    server_group.add_argument("--port", type=int, default=8000, help="Port to bind to")
    server_group.add_argument("--reload", action="store_true", help="Enable auto-reload")
    
    args = parser.parse_args()
    
    if args.mode == "cli":
        # CLI mode
        if args.location:
            # Single recommendation mode
            cli = RecommendationCLI(data_path=args.data_path)
            cli.run_single(
                location=args.location,
                budget=args.budget,
                min_rating=args.rating,
                cuisine=args.cuisine
            )
        else:
            # Interactive mode
            cli = RecommendationCLI(data_path=args.data_path)
            cli.run_interactive()
    
    elif args.mode == "api":
        # API server mode
        api = RecommendationAPI(host=args.host, port=args.port)
        api.run(reload=args.reload)
    
    elif args.mode == "ui":
        # Full UI server mode
        # Update sys.argv for frontend main
        sys.argv = [sys.argv[0]] + ["--host", args.host, "--port", str(args.port)]
        if args.reload:
            sys.argv.append("--reload")
        frontend_main()


if __name__ == "__main__":
    main()
