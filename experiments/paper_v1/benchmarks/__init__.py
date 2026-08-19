"""Pinned public-benchmark adapters for M3 paper-v1."""

from .agentdojo_adapter import build_agentdojo_index
from .injecagent_adapter import build_injecagent_index

__all__ = ["build_agentdojo_index", "build_injecagent_index"]
