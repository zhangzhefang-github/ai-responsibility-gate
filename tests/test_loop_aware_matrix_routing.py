"""
Phase 1: Loop-Aware Matrix Routing tests.

Verifies that when loop_state and loop_policy are present, core resolves
effective matrix path before pipeline. Fallback to base matrix when
loop_state is absent, parse fails, or matrix has no loop_policy.
"""
import pytest

from src.core.models import DecisionRequest
from src.core.gate import decide as core_decide


async def _decide(signals: list, matrix_path: str, loop_state=None):
    """Decide with structured_input signals and optional loop_state."""
    req = DecisionRequest(
        text="loop_routing_test",
        structured_input={"signals": signals},
        context={"loop_state": loop_state} if loop_state is not None else None,
    )
    return await core_decide(req, matrix_path=matrix_path)


@pytest.mark.asyncio
async def test_no_loop_state_uses_base_matrix():
    """No loop_state in context → use base matrix, no loop routing."""
    # R0 signals with pr_loop_demo (has loop_policy) but no loop_state in context
    # Should get ONLY_SUGGEST (base matrix default for Information)
    req = DecisionRequest(
        text="loop_routing_test",
        structured_input={"signals": ["LOW_VALUE_NITS"]},
        # context omitted → no loop_state, loop routing not triggered
    )
    resp = await core_decide(req, matrix_path="matrices/pr_loop_demo.yaml")
    assert resp.decision.value == "ONLY_SUGGEST"


@pytest.mark.asyncio
async def test_no_loop_policy_uses_base_matrix():
    """loop_state present but matrix (v0.1) has no loop_policy → use base matrix."""
    req = DecisionRequest(
        text="loop_routing_test",
        structured_input={"signals": []},
        context={"loop_state": {"round_index": 2, "nit_only_streak": 3}},
    )
    resp = await core_decide(req, matrix_path="matrices/v0.1.yaml")
    # v0.1 has no loop_policy, so no routing; decision from v0.1 defaults
    assert resp.policy.matrix_version == "v0.1"


@pytest.mark.asyncio
async def test_nit_only_streak_reaches_threshold_uses_converged_matrix():
    """nit_only_streak >= 3 with R0 signals → use converged matrix → ALLOW."""
    resp = await _decide(
        signals=["LOW_VALUE_NITS"],
        matrix_path="matrices/pr_loop_demo.yaml",
        loop_state={"round_index": 2, "nit_only_streak": 3},
    )
    assert resp.decision.value == "ALLOW"
    assert resp.policy.matrix_version == "pr_loop_phase_e_v0.1"


@pytest.mark.asyncio
async def test_round_index_reaches_max_rounds_uses_churn_matrix():
    """round_index >= max_rounds (5) → use churn matrix → HITL."""
    resp = await _decide(
        signals=["LOW_VALUE_NITS"],
        matrix_path="matrices/pr_loop_demo.yaml",
        loop_state={"round_index": 5, "nit_only_streak": 0},
    )
    assert resp.decision.value == "HITL"
    assert resp.primary_reason == "PR_LOOP_CHURN"


@pytest.mark.asyncio
async def test_churn_priority_over_converged():
    """Both conditions met: round_index >= 5 and nit_only_streak >= 3 → churn wins."""
    resp = await _decide(
        signals=["LOW_VALUE_NITS"],
        matrix_path="matrices/pr_loop_demo.yaml",
        loop_state={"round_index": 5, "nit_only_streak": 3},
    )
    assert resp.decision.value == "HITL"
    assert resp.primary_reason == "PR_LOOP_CHURN"


@pytest.mark.asyncio
async def test_invalid_loop_state_fallback_to_base():
    """loop_state parse failure (invalid value) → fallback to base matrix, no exception."""
    req = DecisionRequest(
        text="loop_routing_test",
        structured_input={"signals": ["LOW_VALUE_NITS"]},
        context={"loop_state": {"round_index": -1, "nit_only_streak": 0}},  # round_index < 0 fails validation
    )
    resp = await core_decide(req, matrix_path="matrices/pr_loop_demo.yaml")
    # Fallback to base matrix → ONLY_SUGGEST for R0 in pr_loop_demo
    assert resp.decision.value == "ONLY_SUGGEST"
    assert resp.policy.matrix_version == "pr_loop_demo_v0.1"
