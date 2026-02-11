"""
Core-level Loop Guard hook (Phase B).

This module introduces a minimal, generic LoopState schema and a default
Loop Guard evaluation function. It is intentionally:

- Repo-agnostic: does NOT know about PRs, diffs, files, etc.
- Tighten-only safe: default behavior NEVER relaxes decisions.
- L0-usable: requires no configuration; default is deterministic no-op.

Domain-specific callers can pass loop_state via DecisionRequest.context
under the \"loop_state\" key. The core gate will parse it using LoopState
and call evaluate_loop_guard, while enforcing tighten-only at the call site.
"""

from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field


class LoopState(BaseModel):
    """
    Generic loop state schema.

    This is intentionally minimal and domain-agnostic. It can be used by
    any caller that runs the gate in a loop (e.g., AI coding × AI review).

    Fields:
    - round_index:     Current loop round (0-based).
    - nit_only_streak: Domain-agnostic counter for \"benign\" rounds.
                       Core does NOT interpret semantics; callers decide.
    - last_signal_fingerprint: Optional hash/fingerprint of signals from
                               previous round (for future use).
    """

    round_index: int = Field(0, ge=0)
    nit_only_streak: int = Field(0, ge=0)
    last_signal_fingerprint: Optional[str] = None


def parse_loop_state(raw: Optional[Dict[str, Any]]) -> Optional[LoopState]:
    """
    Parse raw loop_state dict into LoopState.

    - If raw is None/empty, returns None.
    - If parsing fails, returns None (fail-closed: treat as no loop state).
    """
    if not raw:
        return None
    if not isinstance(raw, dict):
        return None

    try:
        return LoopState(**raw)
    except Exception:
        # Fail-closed: invalid loop_state is treated as \"no loop info\"
        return None


def evaluate_loop_guard(
    decision_index: int,
    loop_state: Optional[LoopState],
    trace: Optional[List[str]] = None,
) -> int:
    """
    Default Loop Guard evaluation (L0 behavior).

    Properties:
    - Deterministic: given the same inputs, returns the same index.
    - Tighten-only safe: NEVER relaxes the decision index.
    - No-op by default: does NOT change the decision index.
    - Auditable: when trace is provided and loop_state is present,
      logs the observed loop_state and that the default guard is a no-op.

    Note:
    - Domain-specific logic (e.g., nit-only consecutive N rounds → ALLOW)
      MUST live outside core, using this hook and LoopState schema.
    - The call-site (gate.py) enforces tighten-only by ignoring any
      attempted relax (index decrease) from custom implementations.
    """
    if loop_state is not None and trace is not None:
        trace.append(
            "[TRACE] 5. LoopGuard (default, no-op): "
            f"round_index={loop_state.round_index}, "
            f"nit_only_streak={loop_state.nit_only_streak}"
        )

    # Default implementation: strict no-op.
    return decision_index

