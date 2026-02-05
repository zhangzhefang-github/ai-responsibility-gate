import yaml
from ..core.models import Evidence, GateContext
from ..core.config import get_tools_path

with open(get_tools_path("catalog.yaml"), encoding="utf-8") as f:
    TOOL_CATALOG = yaml.safe_load(f)

TOOLS = {t["tool_id"]: t for t in TOOL_CATALOG["tools"]}

def get_tool_info(tool_id: str) -> dict:
    """Get tool info from catalog"""
    return TOOLS.get(tool_id)

def _match_tool_from_routing(text: str) -> str:
    """Match tool from routing hints (for evidence collection only, not decision)"""
    ROUTING_HINTS = TOOL_CATALOG.get("routing_hints", [])
    for hint in ROUTING_HINTS:
        if any(kw in text for kw in hint.get("keywords", [])):
            return hint.get("tool_id")
    return None

async def collect(ctx: GateContext) -> Evidence:
    """
    Tool catalog evidence provider.
    Priority:
    1. Explicit tool_id from context (highest confidence)
    2. Routing hints match (for evidence collection, marked as hints)
    3. Safe defaults (READ, I1, normal_user)
    """
    tool_id = None
    source = "default"

    # Priority 1: Explicit tool_id from context
    if ctx.context and "tool_id" in ctx.context:
        tool_id = ctx.context["tool_id"]
        source = "context_explicit"
    # Priority 2: Routing hints (for backward compatibility and evidence collection)
    else:
        hinted_tool = _match_tool_from_routing(ctx.text)
        if hinted_tool:
            tool_id = hinted_tool
            source = "routing_hint"

    if tool_id and tool_id in TOOLS:
        tool = TOOLS[tool_id]
        return Evidence(
            provider="tool",
            available=True,
            data={
                "tool_id": tool_id,
                "action_type": tool["action_type"],
                "impact_level": tool["impact_level"],
                "required_role": tool["required_role"],
                "source": source
            }
        )

    # Safe defaults
    return Evidence(
        provider="tool",
        available=True,
        data={
            "tool_id": None,
            "action_type": "READ",
            "impact_level": "I1",
            "required_role": "normal_user",
            "source": "default"
        }
    )
