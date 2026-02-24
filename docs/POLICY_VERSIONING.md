## POLICY VERSIONING

### 1. Goals

- **Traceable**: Every decision that depends on timeout guard overlays must record **which policy version** and **which risk tier** were applied.
- **Safe to change**: New policy versions should be:
  - Rollout‑friendly (canary, partial rollout),
  - Rollback‑friendly (easy to revert to previous behavior),
  - Backwards‑compatible by default.
- **Separable concerns**:
  - Matrix / business policy versions live in matrix files.
  - Timeout guard overlay policies are versioned independently.

---

### 2. Core Concepts

- **Matrix version**
  - Carried in `DecisionResponse.policy.matrix_version`.
  - Owned by matrix YAML files and matrix loader.
  - Controls **base decision** (risk rules, entitlements, etc.).

- **Timeout Guard Policy Version**
  - Identified via:
    - Env: `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION` (string, e.g. `"v1"`, `"v2"`).
    - Trace:
      - `timeout_guard_policy_version=<vX>`
      - `timeout_guard_policy=<vX> (risk_tier=R?)`
  - Owned by `gate.py` overlays:
    - HITL overlay behavior,
    - DENY overlay behavior,
    - Tier‑specific overlay configuration.

- **Risk Tier**
  - Effective tier ∈ {`R0`, `R1`, `R2`, `R3`}.
  - Driven by:
    - Future `req.risk_tier`, or
    - Env `AI_GATE_RISK_TIER`, or
    - Default `R2`.
  - Used only by `gate.py` to choose **how aggressive** timeout guard overlays are.

---

### 3. Version Semantics (Current)

- **v1 (implicit)**
  - Early phase with:
    - `_meta._hitl_suggested`, `_meta._degradation_suggested`.
    - HITL overlay and DENY overlay as **hard‑coded** rules in `gate.py`.
  - No tier‑specific behavior; one global policy.
  - Limited explicit versioning; mainly for initial bring‑up.

- **v2 (current structured policy)**
  - Timeout guard overlays:
    - Fully **config‑gated** with env flags.
    - **Tier‑aware** behavior (R0–R3).
  - For any decision using timeout guard, trace exposes:
    - `timeout_guard_policy_version=v2` (or env value),
    - `timeout_guard_policy=v2 (risk_tier=R?)`,
    - `risk_tier=R? (source=req|env|default)`,
    - Structured `timeout_guard_reason=...` when overlays tighten.
  - Default behavior for `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION` **SHOULD** be `"v2"` once rollout is complete.

> Note: At code level, the policy version is read as a free string. What makes a version “v2” is the **combination** of:
> - Tier‑aware overlay table,
> - Reason code emission,
> - Trace format.  
> The env value exists so operations can explicitly pin or roll back behavior.

---

### 4. Rollout & Rollback Patterns

#### 4.1 Rollout (Canary → Full)

1. **Prepare**:
   - Ship new `gate.py` behavior behind:
     - `AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED`,
     - `AI_GATE_TIMEOUT_GUARD_HITL_OVERLAY_ENABLED`,
     - `AI_GATE_TIMEOUT_GUARD_DENY_OVERLAY_ENABLED`,
     - `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION`.
   - Default risk tier to `R2` to preserve existing behavior.
2. **Canary**:
   - Enable new policy version (e.g. `v2`) for a small fraction of traffic by:
     - Setting envs in a canary deployment only,
     - Or routing a subset of tenants/requests to the new version.
3. **Observe**:
   - Compare:
     - HITL rate,
     - DENY rate,
     - Evidence timeout/degradation distributions.
   - Use `timeout_guard_reason` and `risk_tier` trace lines to understand *why* decisions changed.
4. **Ramp up**:
   - Gradually expand coverage to full traffic once KPIs are stable.
   - Standardize env defaults (e.g. set `AI_GATE_TIMEOUT_GUARD_POLICY_VERSION=v2` cluster‑wide).

#### 4.2 Rollback

1. **Trigger**:
   - Detect regressions in:
     - Excess HITL / DENY rate,
     - Latency / availability,
     - Business KPIs.
2. **Action**:
   - Revert envs to previous combination (e.g. policy version `v1` or overlays disabled).
   - Because `gate.py` remains tighten‑only, rollback never relaxes **beyond** the original matrix behavior; it only disables additional tightening.
3. **Verification**:
   - Confirm trace shows old version:
     - `timeout_guard_policy_version=<old>`
     - `timeout_guard_policy=<old> (risk_tier=...)`

---

### 5. Observability & Replay

- **Trace as ground truth**
  - For any recorded decision, a full replay must be able to rely on:
    - Matrix version (`policy.matrix_version`),
    - Timeout guard policy version (`timeout_guard_policy_version`, `timeout_guard_policy`),
    - Risk tier and source,
    - Reason codes (`timeout_guard_reason=...`).
  - These fields, combined with stored Evidence + `_meta`, uniquely describe:
    - **Which policy** was in force,
    - **Which overlays** were allowed,
    - **Which overlay actually tightened** the decision.

- **No hidden sources**
  - All policy‑affecting knobs for timeout guard overlays must be:
    - Local (env / code),
    - Visible in trace,
    - Documented in this file.

---

### 6. Introducing a New Policy Version (Checklist)

When adding a new timeout guard policy version (e.g. `"v3"`):

1. **Design**
   - Specify:
     - Overlay behavior changes (by risk tier),
     - Any new `_meta` inputs (if applicable),
     - Any new reason codes (bounded set).
2. **Implement (in `gate.py` only)**
   - Keep:
     - Tighten‑only property,
     - Single decision source invariants,
     - `_meta` read‑only semantics.
   - Wire in:
     - Env‑gated behavior,
     - `timeout_guard_policy_version` reading,
     - `timeout_guard_policy=<version> (risk_tier=...)` trace.
3. **Test**
   - Add:
     - Tier‑specific behavior tests using stub pipeline,
     - Reason code tests,
     - Regression tests ensuring default behavior matches prior version when envs unchanged.
4. **Document**
   - Update:
     - This file with `"v3"` semantics,
     - `DECISION_CONTRACT.md` if new `_meta` or reason codes are introduced.
5. **Rollout**
   - Follow the rollout pattern in §4.1.

