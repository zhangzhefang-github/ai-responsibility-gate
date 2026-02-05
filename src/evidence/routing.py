import yaml
from ..core.models import Evidence, GateContext
from ..core.config import get_tools_path

with open(get_tools_path("catalog.yaml"), encoding="utf-8") as f:
    TOOL_CATALOG = yaml.safe_load(f)

ROUTING_HINTS = TOOL_CATALOG.get("routing_hints", [])

def _match_hints(text: str) -> list:
    """Match routing hints and return list of (tool_id, confidence, source)"""
    matched = []
    for hint in ROUTING_HINTS:
        keywords = hint.get("keywords", [])
        tool_id = hint.get("tool_id")

        # Count keyword matches for confidence scoring
        match_count = sum(1 for kw in keywords if kw in text)
        if match_count > 0:
            # Simple confidence: 0.6 base + 0.1 per match, max 0.9
            confidence = min(0.6 + (match_count * 0.1), 0.9)
            matched.append({
                "tool_id": tool_id,
                "confidence": confidence,
                "source": "keyword"
            })

    return matched

async def collect(ctx: GateContext) -> Evidence:
    """Collect routing hints as weak evidence"""
    hints = _match_hints(ctx.text)

    return Evidence(
        provider="routing",
        available=True,
        data={
            "hinted_tools": [
                {"tool_id": h["tool_id"], "confidence": h["confidence"]}
                for h in hints
            ],
            "confidence": max([h["confidence"] for h in hints], default=0.0),
            "source": "keyword"
        }
    )
