"""
Compatibility wrapper.

Phase-wise code lives under `zomoto_ai.phase0.*`. This module remains to avoid
breaking imports while the project evolves.
"""

from zomoto_ai.phase0.config import Settings

__all__ = ["Settings"]

