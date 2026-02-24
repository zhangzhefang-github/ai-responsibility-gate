# AI Responsibility Gate: Phase E One-Pager

---

**🌐 Language / 语言**: [English](PHASE_E_ONEPAGER.md) | [中文](PHASE_E_ONEPAGER_CN.md)

---

## Problem Statement

**AI Review × AI Coding Loop Does Not Converge**

When AI reviewer and AI coding agent interact in a loop:
- Reviewer suggests changes (70% low-value nits/style)
- Coder implements changes, sometimes introducing new issues
- Loop continues indefinitely without convergence
- No clear authority to say "stop" or "approve"

**Root Cause**: Attention scheduling problem - who decides when the loop is "good enough"?

---

## Solution Architecture

**Gate as Single Decision Authority**

```
AI Reviewer → Signals → Risk Evidence → Matrix Rules → GATE DECISION
     ↑                                                        │
     └────────────────────────────────────────────────────────┘
                      (Only termination point)
```

### Key Components

1. **Signals Dictionary** (Finite, Auditable)
   - `SECURITY_BOUNDARY`, `BUILD_CHAIN`, `BUG_RISK`, `LOW_VALUE_NITS`, etc.
   - All AI outputs mapped to these signals
   - Unknown → `UNKNOWN_SIGNAL` (fail-closed)

2. **Risk Evidence** (Tighten-Only, Unchanged)
   - Signals → Risk Level (R0/R1/R2/R3)
   - Semantic folding, never relaxes
   - **NO modifications to `src/evidence/risk.py`**

3. **Matrix Rules** (Policy Layer)
   - `(risk_level, action_type) → decision`
   - R3 + READ → HITL (high-risk escalation)
   - R0 + READ → ALLOW (converged, via matrix path switching)
   - Default → ONLY_SUGGEST (continue loop)

4. **Matrix Path Switching** (Demo Layer)
   - Round 1-2: `matrix_path="matrices/pr_loop_demo.yaml"` → ONLY_SUGGEST
   - Round 3+: `matrix_path="matrices/pr_loop_phase_e.yaml"` → ALLOW

5. **Core Gate** (Single Authority, Unchanged in Phase E)
   - **Only** component that creates Decision enum
   - Accepts `matrix_path` parameter (existing API)
   - Tighten-only enforcement (no relax possible)
   - Deterministic, auditable, repo-agnostic

---

## Convergence Strategy (Configurable)

### Threshold-Based Convergence

```
Round 1: LOW_VALUE_NITS → R0 → matrix=pr_loop_demo.yaml → ONLY_SUGGEST
Round 2: LOW_VALUE_NITS → R0 → matrix=pr_loop_demo.yaml → ONLY_SUGGEST
Round 3: LOW_VALUE_NITS → R0 → matrix=pr_loop_phase_e.yaml → ALLOW
```

### Why This Works

- **N is configurable**: Change `BENIGN_STREAK_THRESHOLD` in demo code
- **Decision is policy-driven**: Matrix path → matrix → decision
- **NO core modifications**: `src/core/*` and `src/evidence/*` unchanged
- **Gate is final authority**: All decisions flow through `core_decide(matrix_path=...)`

---

## Demo Evidence

### Benign Scenario (Converges)

```
Round 1: Matrix=pr_loop_demo.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ONLY_SUGGEST
Round 2: Matrix=pr_loop_demo.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ONLY_SUGGEST
Round 3: Matrix=pr_loop_phase_e.yaml, Signals=[LOW_VALUE_NITS], Risk=R0, Decision=ALLOW
✅ Gate terminated the loop (converged after 3 benign rounds)
```

### High-Risk Scenario (Escalates)

```
Round 1: Matrix=pr_loop_demo.yaml, Signals=[SECURITY_BOUNDARY, BUILD_CHAIN], Risk=R3, Decision=HITL
⚠️  Gate terminated the loop (high-risk signals detected)
```

---

## Architecture Invariants

| Invariant | How It's Enforced |
|-----------|-------------------|
| **Single Decision Authority** | Only `gate.py` can create Decision enum |
| **Tighten-Only** | `evaluate_loop_guard()` and overlays are enforced as tighten-only |
| **Repo-Agnostic** | Core doesn't know PR/GitHub concepts |
| **Deterministic** | Fixed seeds → reproducible behavior |
| **Auditable** | All rules in YAML, trace logging available |
| **No Core Mods (Phase E scope)** | For Phase E demo, all policy lives in examples/ layer and uses existing `matrix_path` parameter; later responsibility phases MAY evolve `gate.py` while keeping these invariants |

---

## Key Design Decisions

### 1. Matrix Path Switching (vs Profile or Strategy Signals)

**Problem**: How to implement "N rounds → ALLOW" without modifying `src/core/*` or `src/evidence/*`?

**Solution**: Demo layer switches `matrix_path` based on `nit_only_streak`:
- `< N rounds`: `matrix_path="matrices/pr_loop_demo.yaml"` → ONLY_SUGGEST
- `>= N rounds`: `matrix_path="matrices/pr_loop_phase_e.yaml"` → ALLOW

**Benefit**:
- No modifications to core or evidence layers
- Uses existing `core_decide(matrix_path=...)` API
- All policy configuration stays in examples/

### 2. Why Separate Risk + Policy?

**Risk Layer**: Semantic folding (signals → risk), domain-agnostic, **unchanged**.
**Policy Layer**: Domain-specific rules (matrix → decision), configurable per environment.

### 3. Risk vs Convergence: Orthogonal Dimensions

**Risk Level** (`R0`-`R3`) measures **how dangerous** the current change is:
- `R0`: Benign (only low-value nits/style)
- `R1`: Low risk (minor issues)
- `R2`: Medium risk (bug risk, structural concerns)
- `R3`: High risk (security boundary, build chain compromise)

**Convergence State** (`nit_only_streak`) measures **whether automation is worthwhile**:
- `< N` consecutive benign rounds: Continue loop (ONLY_SUGGEST)
- `>= N` consecutive benign rounds: Terminate (ALLOW)

**Key Insight**: These are **orthogonal dimensions**:
- High-risk (`R3`) should **always** escalate to HITL, regardless of convergence state
- Low-risk (`R0`) may still continue looping if convergence not yet reached
- `matrix_path` is a **policy selection mechanism**, NOT a risk substitute

**Invariants** (must hold for ALL matrices):

| Invariant | Rationale |
|-----------|-----------|
| **R3 → HITL (never ALLOW)** | High-risk changes always require human review, regardless of how many rounds have passed |
| **R2 → Conservative by default** | Medium-risk changes should not auto-allow unless explicitly configured |
| **Tighten-only is never violated** | Matrix switching cannot relax from higher to lower risk |
| **max_rounds is efficiency threshold, not quality proof** | Reaching max_rounds triggers escalation (HITL), NOT automatic approval |

**Example Decision Matrix**:

| Risk Level | Convergence | Matrix Path | Decision |
|------------|-------------|-------------|----------|
| R0 | `< N` rounds | `pr_loop_demo.yaml` | ONLY_SUGGEST |
| R0 | `>= N` rounds | `pr_loop_phase_e.yaml` | ALLOW |
| R1 | Any | Any | ONLY_SUGGEST (conservative) |
| R2 | Any | Any | ONLY_SUGGEST or HITL (never ALLOW by default) |
| R3 | Any | Any | HITL (invariant, never ALLOW) |
| Any | `max_rounds` | `pr_loop_churn.yaml` | HITL (efficiency escalation) |

### 4. Why "Tighten-Only"?

**Safety**: Never relax from high-risk to low-risk automatically.
**Auditability**: Risk can only increase, making post-mortem analysis simpler.

### 4. Why Finite Signals Dictionary?

**Containment**: AI outputs mapped to finite set (won't explode).
**Governance**: Each signal documented with evidence examples.
**Maintainability**: Adding new signal is structured process (YAML + optional matrix rule).

---

## Running the Demo

```bash
# Run the demo
python examples/pr_gate_ai_review_loop/demo_phase_e.py

# Run tests
pytest tests/test_demo_contract_smoke.py -v
```

### Expected Test Results

```
tests/test_demo_contract_smoke.py::test_signals_allowlist_contains_all_used_signals PASSED
tests/test_demo_contract_smoke.py::test_reviewer_stub_produces_extractable_signals PASSED
tests/test_demo_contract_smoke.py::test_is_nit_only_correctly_identifies_benign_rounds PASSED
tests/test_demo_contract_smoke.py::test_normalize_signals_is_deterministic PASSED
tests/test_demo_contract_smoke.py::test_normalize_signals_handles_edge_cases PASSED
tests/test_demo_contract_smoke.py::test_high_risk_scenario_produces_expected_signals PASSED
tests/test_demo_contract_smoke.py::test_demo_scenario_seeds_produce_deterministic_results PASSED
```

---

## Files Modified/Created

| File | Change |
|------|--------|
| `examples/pr_gate_ai_review_loop/demo_phase_e.py` | NEW: Matrix path switching |
| `matrices/pr_loop_phase_e.yaml` | NEW: Converged state matrix |
| `tests/test_demo_contract_smoke.py` | NEW: Signal chain tests |
| `examples/pr_gate_ai_review_loop/README.md` | MODIFIED: Phase E section |
| `examples/pr_gate_ai_review_loop/ai_reviewer_stub.py` | MODIFIED: Deterministic signal generation |
| `docs/PHASE_E_ONEPAGER.md` | NEW: This document |

**Important**: `src/core/*` and `src/evidence/*` were NOT modified.

---

## Summary

**Phase E proves**: Even when AI components oscillate or regress, the system remains stable because:
1. Gate is the **only** decision authority
2. Convergence is **policy-configurable** via matrix path switching
3. Architecture enforces **tighten-only** safety
4. All decisions are **deterministic** and **auditable**
5. **NO modifications** to `src/core/*` or `src/evidence/*` required

**The result**: A responsibility gate that scales with AI automation while maintaining human control over high-risk decisions.
