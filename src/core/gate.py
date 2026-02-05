"""
Gate decision pipeline orchestration.

This module is the ONLY place where Decision enum is created and written to responses.
All stages return intermediate states (strings, indices, dictionaries) that are
mapped to Decision enum only in this module.
"""
import uuid
import time
from typing import List
from .models import (
    Decision, DecisionRequest, DecisionResponse, GateContext,
    Explanation, PolicyInfo, ResponsibilityType, ClassifierResult,
    PostcheckResult
)
from .classifier import classify
from .matrix import load_matrix
from .postcheck import postcheck
from .gate_helpers import collect_all_evidence
from .gate_stages import (
    apply_type_upgrade_rules,
    lookup_matrix,
    apply_missing_evidence_policy,
    apply_conflict_resolution_and_overrides,
)

# Decision strict order (only used for mapping intermediate states to Decision enum)
STRICT_ORDER = ["ALLOW", "ONLY_SUGGEST", "HITL", "DENY"]

def _config_str_to_index(decision_str: str) -> int:
    """Convert config string (from matrix YAML) to index. Only conversion point."""
    config_to_index = {
        "ALLOW": 0,
        "ONLY_SUGGEST": 1,
        "HITL": 2,
        "DENY": 3,
    }
    return config_to_index.get(decision_str, 0)

def _map_index_to_decision(index: int) -> Decision:
    """Map decision index to Decision enum. Only function that creates Decision."""
    return Decision(STRICT_ORDER[index])

def _map_string_to_decision(decision_str: str) -> Decision:
    """Map decision string to Decision enum. Only function that creates Decision."""
    return Decision(decision_str)

async def decide(req: DecisionRequest, matrix_path: str = "matrices/v0.1.yaml") -> DecisionResponse:
    """
    Main decision pipeline with phased architecture.

    Stages:
    1. Evidence Collection (concurrent)
    2. Type Upgrade Rules (YAML)
    3. Matrix Decision Lookup
    4. Missing Evidence Policy (YAML)
    5. Conflict Resolution & Overrides
    6. Postcheck

    This function orchestrates all stages and is the ONLY place where Decision enum
    is created and written to DecisionResponse.
    """
    req_id = str(uuid.uuid4())
    request_start = time.perf_counter()

    ctx = GateContext(
        request_id=req_id,
        session_id=req.session_id,
        user_id=req.user_id,
        text=req.text,
        debug=req.debug,
        verbose=req.verbose,
        context=req.context
    )

    trace = []
    if req.verbose:
        trace.append(f"[TRACE] Request ID: {req_id}")
        trace.append(f"[TRACE] User Input: \"{req.text}\"")
        if req.context:
            trace.append(f"[TRACE] Context: {req.context}")

    # Load matrix with error handling
    try:
        matrix = load_matrix(matrix_path)
    except FileNotFoundError as e:
        if req.verbose:
            trace.append(f"[TRACE] FATAL: Matrix file not found: {matrix_path}")
            print("\n".join(trace))
        raise RuntimeError(
            f"System configuration error: Matrix file not found: {matrix_path}. "
            f"System cannot make decisions without matrix configuration."
        ) from e
    except ValueError as e:
        if req.verbose:
            trace.append(f"[TRACE] FATAL: Invalid matrix configuration: {e}")
            print("\n".join(trace))
        raise RuntimeError(
            f"System configuration error: Invalid matrix file {matrix_path}: {e}. "
            f"Please check matrix YAML syntax and structure."
        ) from e
    
    classifier_result = await classify(req.text)

    if req.verbose:
        trace.append(f"[TRACE] 1. Classifier: type={classifier_result.type.value}, confidence={classifier_result.confidence}")

    # Stage 1: Collect all evidence
    evidence = await collect_all_evidence(ctx, trace if req.verbose else [])

    # Extract key data from evidence
    tool_data = evidence["tool"].data if evidence["tool"].available else {}
    routing_data = evidence["routing"].data if evidence["routing"].available else {}
    risk_data = evidence["risk"].data if evidence["risk"].available else {}

    action_type = tool_data.get("action_type", "READ")
    risk_level = risk_data.get("risk_level", "R1")
    risk_rules = risk_data.get("rules_hit", [])
    # Fail-closed: if permission evidence is missing, default to False
    if evidence["permission"].available:
        permission_ok = evidence["permission"].data.get("has_access", False)
    else:
        permission_ok = False

    # Stage 2: Apply type upgrade rules
    final_resp_type = apply_type_upgrade_rules(
        matrix, classifier_result, action_type, trace if req.verbose else []
    )

    # Stage 3: Lookup matrix decision (returns intermediate state)
    matrix_result = lookup_matrix(
        matrix, final_resp_type, action_type, risk_level, risk_rules, permission_ok,
        trace if req.verbose else []
    )
    # Convert config string to index if present (gate.py is the only conversion point)
    if "config_decision_str" in matrix_result:
        decision_index = _config_str_to_index(matrix_result["config_decision_str"])
    elif "decision_index" in matrix_result:
        decision_index = matrix_result["decision_index"]
    else:
        decision_index = 0  # Default fallback
    primary_reason = matrix_result["primary_reason"]
    rules_fired = matrix_result["rules_fired"]

    # Stage 4: Apply missing evidence policy (returns updated intermediate state)
    missing_policy_result = apply_missing_evidence_policy(
        decision_index, primary_reason, evidence, matrix, trace if req.verbose else []
    )
    decision_index = missing_policy_result["decision_index"]
    primary_reason = missing_policy_result["primary_reason"]

    # Stage 5: Apply conflict resolution and overrides (returns updated intermediate state)
    conflict_result = apply_conflict_resolution_and_overrides(
        decision_index, primary_reason, matrix, classifier_result, final_resp_type,
        action_type, risk_level, permission_ok, routing_data, trace if req.verbose else []
    )
    decision_index = conflict_result["decision_index"]
    primary_reason = conflict_result["primary_reason"]

    # Map intermediate state to Decision enum (ONLY place where Decision is created)
    decision = _map_index_to_decision(decision_index)
    decision_str = STRICT_ORDER[decision_index]

    # Build response components
    suggested_action = "answer" if decision == Decision.ALLOW else ("refuse" if decision == Decision.DENY else "handoff")

    evidence_used = []
    for key, ev in evidence.items():
        if ev.available:
            evidence_used.append(key)

    trigger_spans = classifier_result.trigger_spans[:]
    if evidence["risk"].available and evidence["risk"].data.get("trigger_spans"):
        trigger_spans.extend(evidence["risk"].data["trigger_spans"])

    # Build summary (only place where decision strings are used for output)
    base_summaries = {
        "ALLOW": "Request approved for direct answer",
        "ONLY_SUGGEST": "Suggestion-only response with disclaimer required",
        "HITL": "Human-in-the-loop intervention required",
        "DENY": "Request denied due to policy violation",
    }
    summary = base_summaries.get(decision_str, "Unknown decision")
    # Explain evidence conflicts (Issue #3)
    if decision_str == "HITL" and risk_rules and permission_ok:
        missing_fields = any("MISSING" in r for r in risk_rules)
        if missing_fields:
            summary += " (incomplete context requires human review)"

    explanation = Explanation(
        summary=summary,
        evidence_used=evidence_used,
        trigger_spans=trigger_spans
    )

    # Stage 6: Postcheck
    pc_result = postcheck(req.text, decision == Decision.ONLY_SUGGEST, is_input=True)

    if req.verbose:
        trace.append(f"[TRACE] 4. Gate Decision:")
        trace.append(f"[TRACE]   - decision: {decision_str}")
        trace.append(f"[TRACE]   - primary_reason: {primary_reason}")
        trace.append(f"[TRACE]   - suggested_action: {suggested_action}")

    # Apply postcheck tightening (if needed)
    if not pc_result.passed:
        for issue in pc_result.issues:
            if issue.severity == "critical":
                decision_index = min(decision_index + 2, len(STRICT_ORDER) - 1)
            else:
                decision_index = min(decision_index + 1, len(STRICT_ORDER) - 1)
        primary_reason = f"POSTCHECK_FAIL:{pc_result.issues[0].code}"
        # Re-map to Decision enum after postcheck tightening
        decision = _map_index_to_decision(decision_index)
        decision_str = STRICT_ORDER[decision_index]
        if req.verbose:
            trace.append(f"[TRACE]   - postcheck: triggered tightening")
            trace.append(f"[TRACE]   - issues: {[i.code for i in pc_result.issues]}")

    if req.verbose:
        trace.append(f"[TRACE] 5. Postcheck:")
        if pc_result.passed:
            trace.append(f"[TRACE]   - ok")
        else:
            trace.append(f"[TRACE]   - issues: {[i.code for i in pc_result.issues]}")
        print("\n".join(trace))

    policy = PolicyInfo(
        matrix_version=matrix.version,
        rules_fired=rules_fired if req.debug else None
    )

    total_latency_ms = int((time.perf_counter() - request_start) * 1000)

    # Final Decision enum assignment (ONLY place where Decision is written to response)
    return DecisionResponse(
        request_id=req_id,
        session_id=req.session_id,
        responsibility_type=final_resp_type,
        decision=decision,  # Decision enum written here
        primary_reason=primary_reason,
        suggested_action=suggested_action,
        explanation=explanation,
        policy=policy,
        latency_ms=total_latency_ms
    )
