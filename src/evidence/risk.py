import yaml
from pathlib import Path
from ..core.models import Evidence, GateContext

# Risk level ordering: higher number = higher risk
RISK_LEVEL_ORDER = {"R1": 1, "R2": 2, "R3": 3}

def _get_higher_risk_level(level1: str, level2: str) -> str:
    """Return the higher risk level between two levels."""
    rank1 = RISK_LEVEL_ORDER.get(level1, 0)
    rank2 = RISK_LEVEL_ORDER.get(level2, 0)
    return level1 if rank1 >= rank2 else level2

# Load config using centralized path management
from ..core.config import get_config_path

try:
    with open(get_config_path("risk_rules.yaml"), encoding="utf-8") as f:
        RISK_RULES = yaml.safe_load(f)
except FileNotFoundError as e:
    raise RuntimeError(f"Failed to load risk rules configuration: {e}") from e
except yaml.YAMLError as e:
    raise ValueError(f"Invalid YAML in risk_rules.yaml: {e}") from e

DEFAULTS = RISK_RULES.get("defaults", {})
RULES = RISK_RULES.get("rules", [])

async def collect(ctx: GateContext) -> Evidence:
    risk_level = "R1"
    rules_hit = []
    trigger_spans = []

    # Get tool_id from context (explicit only, no routing hints here)
    tool_id = ctx.context.get("tool_id") if ctx.context else None

    for rule in RULES:
        rule_id = rule["rule_id"]
        rule_type = rule["type"]

        if rule_type == "keyword":
            keywords = rule.get("keywords", [])
            matched = [kw for kw in keywords if kw in ctx.text]
            if matched:
                rules_hit.append(rule_id)
                trigger_spans.extend(matched)
                new_level = rule["risk_level"]
                risk_level = _get_higher_risk_level(new_level, risk_level)

        elif rule_type == "threshold":
            applies = rule.get("applies_when", {})
            tool_ids = applies.get("tool_ids", [])
            if tool_id and tool_id in tool_ids:
                field = rule["field"]
                op = rule["op"]
                value_key = rule.get("value_from_default")
                threshold = DEFAULTS.get(value_key, 0)
                if ctx.context and field in ctx.context:
                    field_val = ctx.context[field]
                    if op == ">=" and field_val >= threshold:
                        rules_hit.append(rule_id)
                        new_level = rule["risk_level"]
                        risk_level = _get_higher_risk_level(new_level, risk_level)

        elif rule_type == "missing_fields":
            applies = rule.get("applies_when", {})
            tool_ids = applies.get("tool_ids", [])
            if tool_id and tool_id in tool_ids:
                required = rule.get("required_fields", [])
                missing = [f for f in required if not (ctx.context and f in ctx.context)]
                if missing:
                    rules_hit.append(rule_id)
                    new_level = rule["risk_level"]
                    risk_level = _get_higher_risk_level(new_level, risk_level)

    # Task C: Calculate risk_score and provide extensible dimensions
    # Map risk_level to score (conservative defaults)
    risk_score_map = {"R1": 20, "R2": 50, "R3": 80}
    risk_score = risk_score_map.get(risk_level, 20)

    # Dimensions: extensible structure for future ML/risk models
    dimensions = {
        "level_source": "rule_based",
        "rules_count": len(rules_hit),
        # Future: add "ml_score", "user_history", "device_risk", etc.
    }

    return Evidence(
        provider="risk",
        available=True,
        data={
            "risk_level": risk_level,
            "risk_score": risk_score,
            "dimensions": dimensions,
            "rules_hit": rules_hit,
            "trigger_spans": trigger_spans
        }
    )
