# Evidence Timeout Guard - Technical Design

## Context

### Current State

The AI Responsibility Gate system follows a strict **"single source of decision"** architecture:

- **Decision Source**: Only `src/core/gate.py` can create `Decision` enum values (ALLOW, ONLY_SUGGEST, HITL, DENY)
- **Evidence Layer Role**: `src/evidence/*` providers (tool, risk, permission, routing, knowledge) are **explain-only** — they return `Evidence(provider, available, data)` but never make decisions
- **Fail-Closed Posture**: Risk evaluation (`risk.py`) follows **tighten-only** semantics — risk levels only increase (R0→R1→R2→R3), never decrease

**Architectural Invariant**: `gate.py` contains NO timeout enforcement, NO circuit breaker logic, NO quality label computation. These are ALL implemented in `src/core/gate_helpers.py` (or equivalent helper module). `gate.py` ONLY calls helpers and aggregates results.

### Problem

When evidence providers time out or degrade:
1. **Current behavior**: Slow/failed providers trigger missing evidence policy → risk tightening → HITL escalation
2. **Cascade risk**: Multiple provider timeouts can cause queue buildup → "HITL storm"
3. **No visibility**: No way to distinguish "timeout" from "genuine high risk" in audit logs
4. **No guardrails**: No throttling for chronically failing providers, leading to resource waste

### Constraints

**Constitutional Red Lines** (Amendment #001 and core architecture):
1. ✅ Evidence providers MUST NOT create `Decision` enum
2. ✅ Evidence providers MUST NOT introduce a second decision source
3. ✅ Tighten-only invariant MUST be preserved (risk never relaxes)
4. ✅ Only `gate.py` can produce the final `DecisionResponse`

**Layer Boundaries**:
- ✅ Evidence layer: `src/evidence/*` — can add timeout logic, but must remain explain-only
- ✅ Core utilities: `src/core/gate_helpers.py` — ALL timeout/circuit breaker/quality logic implementation
- ✅ Core decision: `src/core/gate.py` — ONLY calls helpers and computes Decision; contains NO timeout/breaker/quality judgment logic
- ✅ Policy layer: `config/*.yaml` — can add timeout configuration, but not decision logic

---

## Goals / Non-Goals

### Goals

1. **Deterministic timeout guards**: Per-provider and overall collection deadline enforcement
2. **Graceful degradation**: System remains controllable under partial evidence failures
3. **Circuit breaker throttling**: Prevent cascade "HITL storms" from chronically failing providers
4. **Explainability**: Evidence quality labels (OK/TIMEOUT/ERROR/DEGRADED) in decision context and audit logs
5. **Observability**: Metrics and logs for evidence latency, timeout rate, fallback rate

### Non-Goals

1. ❌ **DO NOT** allow evidence quality labels to modify `Decision` enum directly
2. ❌ **DO NOT** allow evidence timeout/degraded/circuit breaker to set `primary_reason`
3. ❌ **DO NOT** introduce a second decision source in evidence layer
4. ❌ **DO NOT** relax tighten-only invariant (risk never decreases)
5. ❌ **DO NOT** modify `gate.py` to add timeout/breaker/quality judgment logic
6. ❌ **DO NOT** change matrix lookup or risk evaluation semantics
7. ❌ **DO NOT** allow `primary_reason` values derived from evidence quality (e.g., "EVIDENCE_TIMEOUT")

---

## Decisions

### D1: Timeout Enforcement in Evidence Aggregation Layer

**Decision**: All timeout / circuit breaker / quality labeling implementation is located in `src/core/gate_helpers.py` (or equivalent helper module). `gate.py` only acts as caller and Decision compute; it contains NO timeout/breaker/quality judgment logic.

**Rationale**:
- `gate.py` remains a pure decision engine: matrix lookup → risk evaluation → Decision enum
- `gate_helpers.py` handles all evidence collection orchestration: timeout enforcement, circuit breaker logic, quality normalization
- Clear separation: helpers "collect evidence", gate "decides"
- Preserves testability: timeout logic can be tested without invoking gate.py

**Alternatives Considered**:
- **Alternative A**: Implement timeout enforcement in each individual provider
  - ❌ Rejected: Difficult to coordinate overall deadline, scattered timeout logic across providers
- **Alternative B**: Add timeout/circuit breaker logic directly into `gate.py`
  - ❌ Rejected: Violates single responsibility principle; gate.py should only decide, not orchestrate evidence collection

**Implementation Location**:
- `src/core/gate_helpers.py`: Add `collect_evidence_with_timeout()`, `CircuitBreaker` class, and quality normalization functions
- `src/core/gate.py`: Calls helper functions, consumes `Evidence` results (including quality labels), but does NOT enforce timeouts or track circuit breaker state
- Uses `asyncio.wait_for()` or `asyncio.timeout()` per provider in helper, NOT in gate.py

---

### D2: Circuit Breaker State is Evidence-Level, Not Decision-Level

**Decision**: Circuit breaker state (CLOSED/OPEN/HALF-OPEN) is tracked per `provider_id` in the evidence aggregation layer, NOT in the decision logic.

**Rationale**:
- Keeps decision logic (`gate.py`) free from provider health tracking concerns
- Circuit breaker only affects "should we call this provider?", not "what decision do we make?"
- Preserves single source of decision: gate.py still decides, just with fewer available providers

**State Machine**:
```
CLOSED (normal) → timeout threshold exceeded → OPEN (skip provider, cooldown)
OPEN → cooldown expires → HALF-OPEN (allow single probe)
HALF-OPEN → probe success → CLOSED; probe timeout → OPEN
```

**Implementation Location**:
- `src/core/gate_helpers.py`: Add `CircuitBreaker` class with `should_call_provider(provider_id)` method
- State stored in-memory per provider instance (not in database for simplicity)
- Metrics emitted on state transitions

**Critical Guard**: Circuit breaker does NOT affect decision logic — it only controls whether to call a provider. If all providers are skipped, missing evidence policy STILL applies (fail-closed).

---

### D3: Evidence Quality Labels are Explain-Only Metadata

**Decision**: Evidence quality labels (OK/TIMEOUT/ERROR/DEGRADED) are added to `Evidence.data` and propagated to `DecisionResponse.explanation`, but NEVER used to compute `Decision` enum directly.

**Rationale**:
- Quality labels serve auditability and debugging, not decision-making
- Prevents second decision source: decision is still matrix lookup + risk evaluation
- Aligns with evidence layer's explain-only role

**Propagation Path**:
```
Evidence.data["quality"] → gate_helpers.py aggregates → Explanation.evidence_quality_summary → DecisionResponse.explanation
                                                                      ↓
                                                                  audit logs
```

**Primary Responsibility Cutting**:
- `Decision.primary_reason`: Can ONLY come from matrix lookup + risk evaluation in `gate.py`
- Evidence timeout/degraded/circuit breaker: ONLY propagated to `Explanation.evidence_quality_summary`, `Explanation.evidence_degradation_flags`, and audit metadata
- **FORBIDDEN**: Any code path where evidence quality fields (quality="TIMEOUT", skip_reason="circuit_open", etc.) directly or indirectly set `Decision.primary_reason`
- **FORBIDDEN**: Any code path where evidence quality fields influence matrix rule matching or risk level calculation

**Example Valid Usage**:
```
✅ VALID: explanation.evidence_quality_summary = {"tool": "OK", "risk": "TIMEOUT", "permission": "OK"}
✅ VALID: explanation.evidence_degradation_flags = ["risk_provider_timeout"]
✅ VALID: audit log includes "risk_provider_timeout_ms=250, skip_reason=circuit_open"

❌ FORBIDDEN: if evidence["risk"].quality == "TIMEOUT": primary_reason = "EVIDENCE_TIMEOUT"
❌ FORBIDDEN: primary_reason = f"EVIDENCE_TIMEOUT_{provider_id}"
❌ FORBIDDEN: Decision is computed based on evidence quality labels (matrix lookup + risk evaluation ONLY)
```

**Critical Guard**: Evidence quality is EXPLAIN-ONLY metadata for understanding WHY a decision was made. It does NOT participate in computing WHAT decision is made. The decision is STILL matrix lookup + risk evaluation, unchanged.

---

### D4: Risk-Tiered Timeout Budgets Preserve Tighten-Only

**Decision**: Timeout budgets vary by risk tier (R0=short, R3=long), but this does NOT relax tighten-only invariant.

**Rationale**:
- High-risk requests (R2/R3) justify more time for evidence collection (critical to get right)
- Low-risk requests (R0/R1) use shorter timeouts to prevent queue buildup
- BUT: timeout outcome (TIMEOUT label) does NOT automatically lower risk level

**Tighten-Only Preservation**:
- R0 + provider timeout → risk STAYS R0 (not relaxed to R0 just because provider timed out)
- R2 + provider timeout → risk MAY STAY R2 or tighten to R3 (if critical provider)
- Missing evidence policy STILL applies: if risk/permission provider times out on R2/R3 request → tighten

**Implementation**:
- `config/evidence_timeouts.yaml` maps `risk_level → timeout_budget_ms`
- Default: R0=50ms, R1=80ms, R2=150ms, R3=200ms (configurable)
- Overall deadline: sum of per-provider budgets + safety margin (e.g., 500ms)

---

### D5: Configuration-Driven Timeout Values

**Decision**: Numeric timeout values in specs (50ms, 200ms, etc.) are EXAMPLES only. Actual budgets come from configuration files with safe maximum limits enforced.

**Rationale**:
- Allows operators to tune timeouts based on deployment without code changes
- Prevents hard-coded magic numbers that cannot adapt to environment
- Safe maximum limits prevent accidentally setting 1-hour timeouts

**Implementation**:
- `config/evidence_timeouts.yaml`:
  ```yaml
  provider_timeouts:
    default: 80ms
    tool: 100ms
    risk: 50ms
    permission: 80ms
    routing: 30ms
    knowledge: 200ms
  risk_tier_multipliers:
    R0: 0.5x
    R1: 1.0x
    R2: 1.5x
    R3: 2.0x
  overall_deadline_ms: 500
  max_timeout_ms: 5000
  ```
- Validation on load: reject configs where `max_timeout_ms > 5000` or `overall_deadline < 200ms`

---

### D6: Critical Provider Classification is Configurable

**Decision**: "Critical" providers (whose timeout triggers tightening) are defined in configuration, NOT hard-coded.

**Rationale**:
- Different deployments may have different critical providers (e.g., permission for finance, knowledge for healthcare)
- Avoids hard-coded assumptions in code about which providers are "essential"
- Audit trail of which providers are critical for which risk tiers

**Implementation**:
- `config/evidence_timeouts.yaml`:
  ```yaml
  critical_providers:
    R2: [risk, permission]
    R3: [risk, permission, tool]
  ```
- If a non-critical provider times out on R2 request → record TIMEOUT, do NOT tighten
- If a critical provider times out on R2 request → record TIMEOUT + apply missing evidence policy (may tighten)

---

## Risks / Trade-offs

### Risk 1: Evidence Quality Labels Could Be Misused as Second Decision Source

**Risk**: Future developers might be tempted to use `quality="TIMEOUT"` to directly flip ALLOW → HITL, creating a second decision path.

**Mitigation**:
1. **Architectural guard**: All evidence quality code includes comments explaining "explain-only, not for decision"
2. **Test guard**: `tests/test_no_evidence_modifications.py` checks that evidence layer doesn't reference `Decision` enum
3. **Documentation**: ARCHITECTURE_LAYERS.md explicitly states "evidence quality is metadata, not decision logic"
4. **Review process**: PRs that add `if quality == "TIMEOUT": decision = HITL` are rejected as constitutional violations

---

### Risk 2: Circuit Breaker Could Hide Genuine System Issues

**Risk**: If a provider is always OPEN, operators might not notice it's consistently failing.

**Mitigation**:
1. **Observability**: Metrics emitted on every state transition (provider_id, from_state, to_state, timestamp)
2. **Alerting**: Circuit breaker state persisted in metrics dashboard (e.g., Prometheus counter `circuit_breaker_state_total{provider_id="risk", state="OPEN"}`)
3. **Audit logs**: When provider is skipped due to OPEN circuit, log includes `skip_reason="circuit_open", remaining_cooldown_ms`
4. **Half-open probe logging**: Probe attempts are logged with outcome (success/failure)

---

### Risk 3: Timeout Cancellation May Leak Resources

**Risk**: If provider doesn't respect cancellation signal (e.g., long-running DB query without timeout check), resource leaks accumulate.

**Mitigation**:
1. **Timeout enforcement**: Use `asyncio.wait_for(evidence.collect(), timeout=budget)` which propagulates cancellation
2. **Best practices documentation**: Provider authors encouraged to use `asyncio.shield()` checkpoints for long operations
3. **Monitoring**: Metric for "provider_cancellation_dangling_ms" to detect providers that don't cancel promptly
4. **Fallback**: If provider doesn't respect cancellation, still enforce overall deadline to prevent unbounded latency

---

### Risk 4: Overall Deadline May Cause Partial Evidence

**Risk**: If overall deadline expires, some providers may be marked TIMEOUT even though they would have succeeded quickly.

**Trade-off**:
- Acceptable because: System must remain deterministic and avoid unbounded latency
- Mitigated by: Overall deadline is generous (500ms) compared to per-provider budgets (sum + margin)
- Mitigated by: Priority providers (risk, permission) get longer budgets, more likely to complete

---

### Risk 5: Configuration Complexity Could Lead to Misconfiguration

**Risk**: Too many timeout knobs (per-provider, per-risk-tier, overall, max) might confuse operators.

**Mitigation**:
1. **Safe defaults**: System works out-of-the-box with sensible defaults (80ms per provider, 500ms overall)
2. **Validation on load**: Config is validated at startup; reject invalid values (negative, <10ms, >5000ms)
3. **Documentation**: Clear examples in config file comments explaining trade-offs
4. **Observability**: Metric for "effective_timeout_ms" per provider so operators can see what's being used

---

## Migration Plan

### Phase 1: Infrastructure Changes (No Behavior Change)

1. Add `CircuitBreaker` class to `src/core/gate_helpers.py` (disabled by default via feature flag)
2. Add timeout enforcement wrapper `collect_evidence_with_timeout()` (disabled)
3. Add quality label normalization in evidence aggregation (disabled)
4. Add metrics emission for circuit breaker state and evidence quality (disabled)

### Phase 2: Enable in Canary Mode

1. Set feature flag `evidence_timeout_guard_enabled=true` for 1% of requests
2. Compare HITL rate before/after to ensure no regression
3. Verify metrics are emitted correctly
4. Check audit logs include new `quality` fields

### Phase 3: Full Rollout

1. Gradually increase percentage to 100% over 1-2 weeks
2. Monitor for "HITL storm prevention" (fewer queue buildups during provider degradation)
3. Enable circuit breaker for providers that show chronic timeouts
4. Document operational runbooks for handling circuit breaker alerts

### Rollback Strategy

- **Immediate rollback**: Set feature flag to `false` to disable all timeout guards
- **Partial rollback**: Disable circuit breaker for specific provider if too aggressive
- **Config rollback**: Revert `config/evidence_timeouts.yaml` to previous version if timeouts are too aggressive

---

## Open Questions

1. **Q: Should circuit breaker state persist across restarts?**
   - **A**: Out of scope for MVP. In-memory state is sufficient. Future enhancement could persist to Redis for durability.

2. **Q: How to handle providers that internally call other providers (nested evidence collection)?**
   - **A**: Out of scope for MVP. Current design assumes flat provider structure. Future enhancement could add "sub-provider" timeout budgets.

3. **Q: Should timeout override matrix decisions (e.g., R0 + timeout → HITL directly)?**
   - **A**: NO. This would violate single source of decision. Timeout is evidence quality metadata, not a decision input. Matrix lookup + risk evaluation STILL applies.

4. **Q: What if all providers timeout?**
   - **A**: Missing evidence policy applies. If risk/permission providers are "critical" and timeout, decision tightens (R2→R3, HITL). This preserves fail-closed posture.

5. **Q: Should we expose "confidence score" for degraded evidence?**
   - **A**: Out of scope. Quality labels (OK/TIMEOUT/ERROR/DEGRADED) are sufficient for explainability. Confidence scores would require defining semantic thresholds which is domain-specific.
