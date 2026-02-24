## Why

Evidence provider(s) occasionally time out or degrade. In our current fail-closed posture, slow/failed Evidence can trigger risk tightening and HITL escalation, which can cascade into queue buildup and a system-wide "HITL storm". We need deterministic timeout guards and graceful degradation to keep the system controllable under partial Evidence failures.

## What Changes

- Introduce tiered timeouts and a deterministic "evidence timeout guard" policy for Evidence collection (per-provider and per-risk-tier).
- Add circuit-breaker style throttling / backoff for repeatedly timing-out evidence providers to prevent amplification.
- Add evidence outcome labeling (e.g., OK / TIMEOUT / ERROR / DEGRADED) and propagate it into the final decision context (explain-only; does not create a second decision source).
- Add observability: metrics + structured logs for evidence latency, timeout rate, fallback rate, and HITL escalation causes.
- Provide safe defaults and configuration knobs (but keep "single source of decision" in gate; no split decision-making).

## Capabilities

### New Capabilities
- `evidence-timeout-guard`: Deterministic timeout budget + per-provider enforcement + fallback behavior for evidence collection.
- `evidence-provider-circuit-breaker`: Backoff/throttling for repeated evidence failures to avoid cascading HITL escalation.
- `evidence-quality-labeling`: Standardized evidence status/quality labels surfaced to the decision context and audit logs (explain-only).

### Modified Capabilities
- (none)

## Impact

- Affected modules: evidence collection layer (providers, aggregation), gate decision context assembly, and observability/logging.
- Behavior changes: under evidence timeout/degradation, the system remains fail-closed but avoids "escalation storms" via bounded timeouts, throttling, and clear evidence status reporting.
- APIs/config: may introduce new config keys for timeout budgets and provider policies; no breaking public API expected.
- Testing: add unit tests for timeout policy + integration tests simulating slow/failing providers; add regression test for "HITL storm prevention" scenario.
