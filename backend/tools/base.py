from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class ToolError(Exception):
    """Tool-level failure with a human-readable message (PRD 6.1)."""


@dataclass
class ToolResult:
    """Result of one tool call; `ref` is the stable citation id used as evidence."""
    tool: str
    ref: str
    summary: str
    data: Any = None
    meta: dict[str, Any] = field(default_factory=dict)
