"""
Compatibility wrapper.

Canonical Phase 0 contracts live in `zomoto_ai.phase0.llm`.
"""

from zomoto_ai.phase0.llm.client import LLMClient
from zomoto_ai.phase0.llm.stub import StubLLMClient

__all__ = ["LLMClient", "StubLLMClient"]

