"""
Shared action type inference logic.
Used by ToolEvidence and PermissionEvidence to maintain consistency.
"""
import yaml
from ..core.config import get_tools_path

with open(get_tools_path("catalog.yaml"), encoding="utf-8") as f:
    TOOL_CATALOG = yaml.safe_load(f)

ROUTING_HINTS = TOOL_CATALOG.get("routing_hints", [])

def infer_action_type_from_text(text: str) -> str:
    """
    Infer action_type from text using routing hints.
    Returns: READ, WRITE, MONEY, ENTITLEMENT, or POLICY
    """
    for hint in ROUTING_HINTS:
        if any(kw in text for kw in hint.get("keywords", [])):
            tool_id = hint.get("tool_id")
            if tool_id:
                tool = TOOL_CATALOG.get("tools", [])
                for t in tool:
                    if t.get("tool_id") == tool_id:
                        return t.get("action_type", "READ")
    return "READ"  # Safe default
