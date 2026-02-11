import yaml
from pathlib import Path
from ..core.models import Evidence, GateContext

# Risk level ordering: higher number = higher risk
# Phase C: add \"R0\" as an explicit lowest-risk level for generic use.
RISK_LEVEL_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}

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
    # Phase D: start from explicit lowest risk level R0, and only tighten upwards.
    risk_level = "R0"
    rules_hit = []
    trigger_spans = []

    # Normalize text to be safe when ctx.text is None.
    text = ctx.text or ""

    # Get tool_id from context (explicit only, no routing hints here)
    tool_id = ctx.context.get("tool_id") if ctx.context else None

    for rule in RULES:
        rule_id = rule["rule_id"]
        rule_type = rule["type"]

        if rule_type == "keyword":
            keywords = rule.get("keywords", [])
            matched = [kw for kw in keywords if kw in text]
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

    # Phase D: Generic adjustment based on structured_input signals (if present).
    # 说明：
    # - 保持域无关：只根据抽象字符串信号调整风险，不引入 PR / repo 语义
    # - 不再读取 loop_state，Evidence 层不承载收敛策略
    # - 只允许"上调"（tighten），不允许从更高风险降级到 R0
    #   · SECURITY_BOUNDARY / BUILD_CHAIN → 至少 R3
    #   · BUG_RISK → 至少 R2
    #   · 仅 LOW_VALUE_NITS 且当前仍为 R0 → 保持 R0（无需显式赋值）
    si = ctx.structured_input if isinstance(ctx.structured_input, dict) else {}
    signals = si.get("signals", [])

    if isinstance(signals, list) and signals:
        # High-risk: security boundary or build chain touched → at least R3
        if any(s in ("SECURITY_BOUNDARY", "BUILD_CHAIN") for s in signals):
            risk_level = _get_higher_risk_level("R3", risk_level)
        # Medium-risk: generic bug risk → at least R2
        elif "BUG_RISK" in signals:
            risk_level = _get_higher_risk_level("R2", risk_level)
        # Benign: only LOW_VALUE_NITS and current level is R0 → keep R0 (no-op)
        elif set(signals).issubset({"LOW_VALUE_NITS"}) and risk_level == "R0":
            pass

    # Task C: Calculate risk_score and provide extensible dimensions
    # Map risk_level to score (conservative defaults)
    risk_score_map = {"R0": 10, "R1": 20, "R2": 50, "R3": 80}
    risk_score = risk_score_map.get(risk_level, 10)

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
