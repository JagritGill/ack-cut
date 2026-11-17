"""Offline scalar-offset crash-cut analysis."""

from .core import Report, TraceError, audit
from .io import load_trace

__all__ = ["Report", "TraceError", "audit", "load_trace"]
