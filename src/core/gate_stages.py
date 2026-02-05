"""
Gate decision pipeline stages.

These functions implement each stage of the decision pipeline.
They return intermediate states (indices, dictionaries) and NEVER return Decision enum or decision strings.
Only gate.py can map these intermediate states to Decision enum.
"""
from typing import List, Optional, Dict, Any
from .models import ResponsibilityType, ClassifierResult
from .matrix import Matrix
from .gate_helpers import tighten_one_step

# Decision index constants
DECISION_IDX_0 = 0
DECISION_IDX_1 = 1
DECISION_IDX_2 = 2
DECISION_IDX_3 = 3

# Reason codes (as constants, not decision values)
REASON_DEFAULT = "DEFAULT_DECISION"
REASON_LOW_CONFIDENCE = "CLASSIFIER_LOW_CONFIDENCE"
REASON_GUARANTEE_OVERRIDE = "RISK_GUARANTEE_OVERRIDE"
REASON_PERMISSION_DENIED = "PERMISSION_DENIED"
REASON_MISSING_PERMISSION = "EVIDENCE_PERMISSION_MISSING"
REASON_MISSING_RISK = "EVIDENCE_RISK_MISSING"
REASON_MISSING_KNOWLEDGE = "EVIDENCE_KNOWLEDGE_MISSING"
REASON_ROUTING_WEAK_SIGNAL = "ROUTING_WEAK_SIGNAL_TIGHTEN"

def apply_type_upgrade_rules(
    matrix: Matrix,
    classifier_result: ClassifierResult,
    action_type: str,
    trace: List[str]
) -> ResponsibilityType:
    """Apply YAML-configured type upgrade rules."""
    type_upgrade_rules = matrix.data.get("type_upgrade_rules", [])
    final_resp_type = classifier_result.type

    # Check type upgrade rules from YAML
    for rule in type_upgrade_rules:
        when = rule.get("when", {})
        if when.get("tool_action") == action_type:
            if final_resp_type == ResponsibilityType.Information:
                target = rule.get("upgrade_to")
                if target == "EntitlementDecision":
                    final_resp_type = ResponsibilityType.EntitlementDecision
                    if trace:
                        trace.append(f"[TRACE]   - responsibility_type upgraded: Information -> EntitlementDecision (action_type={action_type})")

    return final_resp_type

def lookup_matrix(
    matrix: Matrix,
    final_resp_type: ResponsibilityType,
    action_type: str,
    risk_level: str,
    risk_rules: List[str],
    permission_ok: bool,
    trace: List[str]
) -> Dict[str, Any]:
    """
    Lookup decision from matrix rules and apply overrides.
    
    Returns intermediate state dictionary:
    {
        "decision_index": int,  # 0-3, or None if needs config conversion
        "config_decision_str": Optional[str],  # Config string if needs conversion
        "primary_reason": str,
        "rules_fired": List[str],
        "matched_rule": Optional[dict],
        "has_guarantee_override": bool,
        "has_permission_denied": bool,
    }
    """
    rules_fired = []
    primary_reason = REASON_DEFAULT
    matched_rule = None
    has_guarantee_override = False
    has_permission_denied = False
    config_decision_str = None
    decision_index = None

    # Override: RISK_GUARANTEE_CLAIM (highest priority)
    if "RISK_GUARANTEE_CLAIM" in risk_rules:
        decision_index = DECISION_IDX_3
        primary_reason = REASON_GUARANTEE_OVERRIDE
        has_guarantee_override = True

    # Override: Permission denied
    elif not permission_ok:
        decision_index = DECISION_IDX_2
        if primary_reason == REASON_DEFAULT:
            primary_reason = REASON_PERMISSION_DENIED
        has_permission_denied = True

    # Matrix rule match or default (needs config string conversion)
    else:
        matched_rule = matrix.match_rule(final_resp_type.value, action_type, risk_level)
        if matched_rule:
            # Store config string, gate.py will convert to index
            config_decision_str = matched_rule["decision"]
            if primary_reason == REASON_DEFAULT:
                primary_reason = matched_rule["primary_reason"]
            rules_fired.append(matched_rule["rule_id"])
        else:
            # Use default from matrix config
            default_str = matrix.get_default(final_resp_type.value)
            if default_str:
                config_decision_str = default_str
            else:
                # No default, use index 0
                decision_index = DECISION_IDX_0

    if trace:
        if matched_rule:
            trace.append(f"[TRACE] 3. Matrix Lookup:")
            trace.append(f"[TRACE]   - version: {matrix.version}")
            trace.append(f"[TRACE]   - matched: rule_id={matched_rule['rule_id']}, primary_reason={matched_rule['primary_reason']}")
        else:
            trace.append(f"[TRACE] 3. Matrix Lookup:")
            trace.append(f"[TRACE]   - version: {matrix.version}")
            if decision_index is not None:
                trace.append(f"[TRACE]   - default: type={final_resp_type.value}, decision_index={decision_index}")
            elif config_decision_str:
                trace.append(f"[TRACE]   - default: type={final_resp_type.value}, config_decision_str=present")

    result = {
        "primary_reason": primary_reason,
        "rules_fired": rules_fired,
        "matched_rule": matched_rule,
        "has_guarantee_override": has_guarantee_override,
        "has_permission_denied": has_permission_denied,
    }
    if decision_index is not None:
        result["decision_index"] = decision_index
    if config_decision_str:
        result["config_decision_str"] = config_decision_str
    
    return result

def apply_missing_evidence_policy(
    decision_index: int,
    primary_reason: str,
    evidence: dict,
    matrix: Matrix,
    trace: List[str]
) -> Dict[str, Any]:
    """
    Apply YAML-configured missing evidence policies.
    
    Returns:
    {
        "decision_index": int,  # Updated index after tightening
        "primary_reason": str,   # Updated reason
        "tighten_steps": int,    # Steps tightened (for trace)
    }
    """
    missing_policy = matrix.missing_evidence_policy
    tighten_steps = 0

    # If already at max index, no further tightening
    if decision_index == DECISION_IDX_3:
        return {
            "decision_index": decision_index,
            "primary_reason": primary_reason,
            "tighten_steps": 0,
        }

    if not evidence["permission"].available:
        policy_action = missing_policy.get("missing_permission", "hitl")
        if policy_action == "hitl":
            decision_index = DECISION_IDX_2
            tighten_steps = 2 if decision_index < DECISION_IDX_2 else 0
        elif policy_action == "tighten":
            tighten_steps = 2
            decision_index = tighten_one_step(decision_index, 2)
        if primary_reason == REASON_DEFAULT:
            primary_reason = REASON_MISSING_PERMISSION
        if trace:
            trace.append(f"[TRACE]   - permission missing, policy={policy_action}, decision_index={decision_index}")

    elif not evidence["risk"].available:
        policy_action = missing_policy.get("missing_risk", "tighten")
        if policy_action == "tighten":
            tighten_steps = 1
            decision_index = tighten_one_step(decision_index, 1)
        if primary_reason == REASON_DEFAULT:
            primary_reason = REASON_MISSING_RISK
        if trace:
            trace.append(f"[TRACE]   - risk missing, tightened: decision_index={decision_index}")

    elif not evidence["knowledge"].available:
        policy_action = missing_policy.get("missing_knowledge", "tighten")
        if policy_action == "tighten":
            tighten_steps = 1
            decision_index = tighten_one_step(decision_index, 1)
        if primary_reason == REASON_DEFAULT:
            primary_reason = REASON_MISSING_KNOWLEDGE
        if trace:
            trace.append(f"[TRACE]   - knowledge missing, tightened: decision_index={decision_index}")

    return {
        "decision_index": decision_index,
        "primary_reason": primary_reason,
        "tighten_steps": tighten_steps,
    }

def apply_conflict_resolution_and_overrides(
    decision_index: int,
    primary_reason: str,
    matrix: Matrix,
    classifier_result: ClassifierResult,
    final_resp_type: ResponsibilityType,
    action_type: str,
    risk_level: str,
    permission_ok: bool,
    routing_data: dict,
    trace: List[str]
) -> Dict[str, Any]:
    """
    Apply conflict resolution and override rules.
    
    Returns:
    {
        "decision_index": int,
        "primary_reason": str,
        "tighten_steps": int,
    }
    """
    tighten_steps = 0

    # Conflict resolution: R3 + permission ok
    conflict_policy = matrix.conflict_resolution
    if decision_index != DECISION_IDX_3 and risk_level == "R3" and permission_ok and action_type in ("MONEY", "ENTITLEMENT"):
        if conflict_policy.get("risk_high_overrides_permission_ok", True):
            r3_action = conflict_policy.get("r3_with_permission_action", "hitl")
            if r3_action == "hitl" and decision_index != DECISION_IDX_2:
                decision_index = DECISION_IDX_2
                if primary_reason == REASON_DEFAULT:
                    primary_reason = "RISK_WITH_PERMISSION_CONFLICT"
                if trace:
                    trace.append(f"[TRACE]   - conflict resolution: R3 + permission ok -> decision_index={DECISION_IDX_2}")

    # Low confidence override
    if decision_index != DECISION_IDX_3:
        if classifier_result.confidence < matrix.get_low_threshold():
            tighten_steps = 1
            decision_index = tighten_one_step(decision_index, 1)
            if primary_reason == REASON_DEFAULT:
                primary_reason = REASON_LOW_CONFIDENCE
            if trace:
                trace.append(f"[TRACE]   - confidence low, tightened: decision_index={decision_index}")

    # Routing weak signal override (max 1 step, never max index)
    if decision_index != DECISION_IDX_3 and routing_data:
        routing_conf = routing_data.get("confidence", 0.0)
        hinted_tools = routing_data.get("hinted_tools", [])
        if decision_index == DECISION_IDX_0 and routing_conf >= 0.7 and hinted_tools:
            tighten_steps = 1
            decision_index = tighten_one_step(decision_index, 1)
            if primary_reason == REASON_DEFAULT:
                primary_reason = REASON_ROUTING_WEAK_SIGNAL
            if trace:
                tool_ids = [h["tool_id"] for h in hinted_tools]
                trace.append(f"[TRACE]   - routing weak signal (conf={routing_conf:.2f}, tools={tool_ids}), tightened: decision_index={decision_index}")

    return {
        "decision_index": decision_index,
        "primary_reason": primary_reason,
        "tighten_steps": tighten_steps,
    }
