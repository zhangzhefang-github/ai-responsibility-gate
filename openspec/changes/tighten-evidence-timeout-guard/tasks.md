# Implementation Tasks

## Phase 3 – Gate decision overlays

- [x] Task 3.3: Fail-closed DENY overlay in `gate.py` (Evidence → Explanation → Decision chain frozen)

## 1. Configuration Foundation

- [ ] 1.1 Create `config/evidence_timeouts.yaml` with provider timeouts, risk tier multipliers, critical providers, and circuit breaker thresholds
- [ ] 1.2 Add configuration loading and validation in `src/core/gate_helpers.py` with safe maximum limits (max_timeout_ms <= 5000)
- [ ] 1.3 Add feature flag `evidence_timeout_guard_enabled` for gradual rollout

## 2. Circuit Breaker Infrastructure

- [ ] 2.1 Implement `CircuitBreaker` class in `src/core/gate_helpers.py` with CLOSED/OPEN/HALF-OPEN state machine
- [ ] 2.2 Add consecutive timeout counter and exponential backoff calculation to `CircuitBreaker`
- [ ] 2.3 Implement `should_call_provider(provider_id)` method with probe concurrency control for HALF-OPEN state
- [ ] 2.4 Add state transition metrics emission (provider_id, from_state, to_state, timestamp)
- [x] 2.5 Add in-memory circuit breaker registry per provider instance

## 3. Timeout Enforcement Wrapper

- [ ] 3.1 Implement `collect_evidence_with_timeout()` function using `asyncio.wait_for()` or `asyncio.timeout()`
- [ ] 3.2 Add per-provider timeout budget calculation based on config (base timeout × risk tier multiplier)
- [ ] 3.3 Add overall deadline enforcement with safety margin (500ms default)
- [ ] 3.4 Add timeout duration tracking for evidence metadata (timeout_duration_ms field)
- [ ] 3.5 Add cancellation propagation for cancelled tasks

## 4. Evidence Quality Labeling

- [ ] 4.1 Add quality label enumeration (OK/TIMEOUT/ERROR/DEGRADED) to evidence models
- [ ] 4.2 Implement quality label normalization for legacy providers (missing quality → "OK")
- [ ] 4.3 Add timeout exception handling to set quality="TIMEOUT" with timeout_duration_ms
- [ ] 4.4 Add error exception handling to set quality="ERROR" with error_message
- [ ] 4.5 Add degraded handling to set quality="DEGRADED" with degraded_fields and fallback_source
- [ ] 4.6 Add skip_reason="circuit_open" for providers skipped by circuit breaker

## 5. Gate Helper Integration

- [ ] 5.1 Create `collect_all_evidence_with_guards()` function in `gate_helpers.py` that orchestrates collection with timeout and circuit breaker
- [ ] 5.2 Add evidence quality aggregation and summary generation
- [ ] 5.3 Add critical provider checking and missing evidence policy integration
- [ ] 5.4 Ensure ALL timeout/breaker/quality logic is in gate_helpers.py, NOT in gate.py (architectural guard)

## 6. Gate.py Integration (Decision Layer Only)

- [ ] 6.1 Modify `gate.py` to call `collect_all_evidence_with_guards()` instead of direct provider collection
- [ ] 6.2 Update `DecisionResponse.explanation` to include `evidence_quality_summary` and `evidence_degradation_flags`
- [ ] 6.3 Add audit log fields for evidence provider outcomes (provider_name, quality, latency_ms, skip_reason)
- [ ] 6.4 Verify gate.py contains NO timeout/breaker/quality judgment logic (only calls helpers and computes Decision)
- [ ] 6.5 Verify evidence quality does NOT influence Decision enum or primary_reason (architectural test)

## 7. Observability and Metrics

- [ ] 7.1 Add metrics for evidence latency per provider (evidence_latency_ms{provider_id})
- [ ] 7.2 Add metrics for timeout rate per provider (evidence_timeout_total{provider_id})
- [ ] 7.3 Add metrics for circuit breaker state transitions (circuit_breaker_state_total{provider_id, state})
- [ ] 7.4 Add structured logging for evidence quality summary in decision context
- [ ] 7.5 Add audit log field for timeout_impact (none/tightened/escalated_to_hitl)

## 8. Testing - Unit Tests

- [ ] 8.1 Add tests for `CircuitBreaker` state transitions (CLOSED → OPEN → HALF-OPEN → CLOSED)
- [ ] 8.2 Add tests for exponential backoff calculation and maximum capping
- [ ] 8.3 Add tests for timeout enforcement with `asyncio.wait_for()` and cancellation propagation
- [ ] 8.4 Add tests for evidence quality label normalization (missing quality → "OK")
- [ ] 8.5 Add tests for critical provider timeout triggering missing evidence policy
- [ ] 8.6 Add tests for circuit breaker skipped provider evidence with skip_reason="circuit_open"

## 9. Testing - Integration Tests

- [ ] 9.1 Add integration test for slow provider timeout with quality="TIMEOUT" label
- [ ] 9.2 Add integration test for circuit breaker opening after threshold and provider skipping
- [ ] 9.3 Add integration test for overall deadline enforcement causing partial evidence
- [ ] 9.4 Add integration test for degraded evidence with fallback data and quality="DEGRADED"
- [ ] 9.5 Add regression test for "HITL storm prevention" scenario (circuit breaker prevents cascade)

## 10. Testing - Architectural Guards

- [ ] 10.1 Add test `test_no_evidence_modifications.py` ensuring evidence layer doesn't reference `Decision` enum
- [ ] 10.2 Add test verifying evidence quality fields never set `Decision.primary_reason`
- [ ] 10.3 Add test verifying evidence quality fields never influence matrix rule matching
- [ ] 10.4 Add test verifying gate.py contains no timeout/breaker/quality judgment logic
- [ ] 10.5 Add test verifying tighten-only invariant is preserved (timeout never relaxes risk level)

## 11. Documentation

- [ ] 11.1 Update `ARCHITECTURE_LAYERS.md` with evidence timeout guard and circuit breaker responsibilities
- [ ] 11.2 Add operational runbook for handling circuit breaker alerts and provider degradation
- [ ] 11.3 Update config/evidence_timeouts.yaml with clear comments explaining trade-offs
- [ ] 11.4 Document migration plan for canary rollout and rollback procedures

## 12. Canary Rollout

- [ ] 12.1 Enable feature flag for 1% of requests and compare HITL rate before/after
- [ ] 12.2 Verify metrics are emitted correctly (latency, timeout rate, circuit breaker state)
- [ ] 12.3 Verify audit logs include new quality fields and skip_reason
- [ ] 12.4 Gradually increase percentage to 100% over 1-2 weeks while monitoring HITL storm prevention
