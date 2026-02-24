## DECISION CONTRACT

### 1. Scope & Purpose

- **Scope**: This document defines the contract between:
  - **Evidence** (facts from tools/providers),
  - **Explanation** (explain-only labels and traces),
  - **Decision** (final `ALLOW` / `ONLY_SUGGEST` / `HITL` / `DENY`).
- **Purpose**: Ensure the gateway is:
  - **Single‑sourced** in its decision,
  - **Explainable** (why did we get HITL / DENY?),
  - **Auditable & replayable** without ambiguity.

### 2. Layer Responsibilities

- **Evidence Layer**
  - Collects provider outputs and metadata (latency, errors, degradation).
  - May annotate **quality** (OK / TIMEOUT / ERROR / DEGRADED) and timeout/degradation details.
  - **MUST NOT**:
    - Reference `Decision` enum or drive final decisions.
    - Contain business policy logic.
  - Output is a structured dict of evidence entries plus optional `_meta`.

- **Explanation Layer (`_meta`)**
  - Carries **explain-only** labels derived from Evidence, e.g.:
    - `_hitl_suggested: bool`
    - `_degradation_suggested: bool`
  - Represents *suggestions* based on timeout/degradation guardrails.
  - **MUST**:
    - Be treated as **read-only input** by `gate.py`.
    - Never write back into Evidence or Decision structures.
  - **MUST NOT**:
    - Directly encode `ALLOW` / `HITL` / `DENY`.
    - Be interpreted as a second decision source.

- **Decision Layer (`gate.py`)**
  - The **only** module that:
    - Maps intermediate states to `Decision` enum.
    - Writes `Decision` into `DecisionResponse`.
  - Orchestrates stages:
    1. Classifier
    2. Type upgrade rules
    3. Matrix lookup
    4. Missing evidence policy
    5. Conflict resolution & overrides
    6. LoopGuard
    7. Timeout Guard overlays (HITL / DENY)
    8. Postcheck
  - **MUST**:
    - Preserve **tighten‑only** behavior (no relax) for all overlays.
    - Treat Explanation as hints, not decisions.

### 3. Core Invariants

- **Single decision source**
  - Only `gate.py` creates and assigns `Decision` enum.
  - Evidence / helpers / Explanation **never** own decision authority.

- **Tighten‑only overlays**
  - Any overlay (LoopGuard, timeout guard, postcheck) may only:
    - Move decision index **towards stricter outcomes** in `STRICT_ORDER`.
    - **Never** relax to a less strict outcome.

- **Read‑only `_meta`**
  - `_meta` is produced below `gate.py`, consumed by `gate.py`, and:
    - Not mutated within `gate.py`.
    - Not surfaced as a direct decision field in responses.

- **Deterministic pipeline**
  - Given:
    - Same request,
    - Same matrix / config,
    - Same Evidence + `_meta`,
  - `gate.decide` is **pure** and deterministic.

### 4. Timeout Guard Contract (HITL / DENY Overlays)

- **Inputs**
  - `_meta._hitl_suggested: bool` (explain-only “HITL escalation suggested”).
  - `_meta._degradation_suggested: bool` (explain-only “degraded state”).
  - Environment / config:
    - `AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED`
    - `AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED`
    - `AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED`
    - `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION`
    - `AI_GATE_RISK_TIER` (fallback when request does not carry a tier).

- **Risk tiers**
  - Effective tier ∈ {`R0`, `R1`, `R2`, `R3`} resolved by `gate.py` only.
  - Resolution priority:
    1. Future `req.risk_tier` (if present),
    2. Env `AI_GATE_RISK_TIER`,
    3. Default `R2`.

- **Overlay behavior by tier (conceptual)**
  - Let **baseline** be the matrix decision index **before** timeout guard overlays.
  - R0:
    - `_hitl_suggested` and/or `_degradation_suggested` do **not** tighten the decision.
  - R1:
    - `_hitl_suggested=True` → at least `HITL`.
    - `_hitl_suggested=True && _degradation_suggested=True` → **no DENY**, at most `HITL`.
  - R2:
    - `_hitl_suggested=True` → at least `HITL`.
    - `_hitl_suggested=True && _degradation_suggested=True` → `DENY` (fail‑closed).
  - R3:
    - `_hitl_suggested=True` → at least `HITL`.
    - `_hitl_suggested=False && _degradation_suggested=True` → tighten to `HITL`.
    - `_hitl_suggested=True && _degradation_suggested=True` → `DENY`.

- **DENY safety guard**
  - DENY overlay is allowed **only if**:
    - Global feature flag is ON,
    - HITL overlay is enabled (config + tier),
    - DENY overlay is enabled (config + tier),
    - `_hitl_suggested=True && _degradation_suggested=True`.
  - This prevents **direct `ALLOW → DENY`** bypassing HITL semantics.

### 5. Trace Contract (Replay & Explanation)

- **Minimum trace fields (when `verbose=True`)**
  - Request context:
    - Request ID, user text, optional `context`.
  - Matrix selection:
    - Profile → matrix path.
  - Timeout guard metadata:
    - `timeout_guard_policy_version=<vX>`
    - `risk_tier=R? (source=req|env|default)`
    - `timeout_guard_policy=<vX> (risk_tier=R?)`
  - Timeout guard overlays (if applicable):
    - HITL suggestion / degraded flags:
      - `timeout_guard: HITL suggested (hitl_suggested=True)`
      - `timeout_guard: degraded (degradation_suggested=True)`
    - DENY decision trace:
      - `gate_decision=DENY (timeout_guard: hitl+degraded)`
    - Structured reason code (see below).

- **Reason Codes (explain-only)**
  - Internal constants (not part of API surface):
    - `NONE`
    - `HITL_SUGGESTED`
    - `DEGRADED_ONLY`
    - `HITL_AND_DEGRADED`
  - Emitted to trace as (only when reason ≠ `NONE`):
    - `timeout_guard_reason=HITL_SUGGESTED`
    - `timeout_guard_reason=DEGRADED_ONLY`
    - `timeout_guard_reason=HITL_AND_DEGRADED`
  - **MUST NOT** influence `decision` or `primary_reason`; they exist purely for:
    - BI,
    - metrics,
    - audit / debugging.

### 6. Extension Points (Future Work)

Any future change that touches this contract **MUST**:

- Keep:
  - Single decision source in `gate.py`.
  - Tighten‑only overlays.
  - `_meta` as read‑only, explain-only.
- Document:
  - New `_meta` fields and their semantics.
  - New reason codes (bounded, enumerated).
  - Any new risk tiers or policy versions.
- Provide:
  - Backwards‑compatible defaults.
  - Replayability from stored Evidence + `_meta` + config.

