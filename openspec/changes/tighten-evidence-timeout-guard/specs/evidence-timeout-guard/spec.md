# Evidence Timeout Guard Specification

## ADDED Requirements

### Requirement: Per-provider timeout budget

The system SHALL enforce a deterministic timeout budget for each evidence provider during collection.

#### Scenario: Provider timeout enforced
- **WHEN** an evidence provider (tool, risk, permission, routing, knowledge) exceeds its configured timeout budget
- **THEN** the system SHALL mark that provider's evidence as TIMEOUT and continue with other providers
- **AND** the system SHALL NOT allow the timeout to exceed the maximum configured budget for that provider type

### Requirement: Risk-tiered timeout policies

The system SHALL apply different timeout budgets based on the risk tier of the request context.

#### Scenario: Lower timeout for low-risk requests
- **WHEN** a request has risk_level R0 and an evidence provider times out
- **THEN** the system SHALL use a shorter timeout budget (e.g., 50ms) before marking as TIMEOUT
- **AND** the system SHALL NOT trigger risk escalation solely due to this timeout

#### Scenario: Longer timeout for high-risk requests
- **WHEN** a request has risk_level R2 or R3 and an evidence provider times out
- **THEN** the system SHALL use a longer timeout budget (e.g., 200ms) before marking as TIMEOUT
- **AND** the system SHALL allow more time for critical evidence collection in high-risk scenarios

### Requirement: Overall evidence collection deadline

The system SHALL enforce an overall deadline for evidence collection to prevent unbounded total latency when multiple providers are invoked.

#### Scenario: Overall deadline stops evidence collection
- **WHEN** the overall evidence deadline is reached during collection
- **THEN** the system SHALL stop waiting for remaining providers
- **AND** any unfinished providers SHALL be recorded with quality="TIMEOUT" (or equivalent metadata)
- **AND** the decision pipeline SHALL proceed deterministically using available evidence

### Requirement: Timeout cancellation semantics

The system SHALL cancel or abort the underlying provider operation when a timeout budget is exceeded to prevent resource leaks and tail-latency amplification.

#### Scenario: Provider operation is cancelled on timeout
- **WHEN** a provider exceeds its timeout budget
- **THEN** the system SHALL signal cancellation to the provider operation (e.g., deadline propagation / task cancellation)
- **AND** the system SHALL NOT continue consuming resources for that provider beyond the timeout point

### Requirement: Critical evidence provider classification

The system SHALL define a deterministic classification for "critical" evidence providers per risk tier.

#### Scenario: Critical providers are configured
- **WHEN** the system evaluates evidence providers for a given risk_level
- **THEN** the system SHALL determine critical providers from configuration or provider metadata (not ad-hoc heuristics)
- **AND** the classification SHALL be auditable (provider_id, risk_level, critical=true/false)

#### Scenario: Non-critical provider timeout does not tighten by itself
- **WHEN** a non-critical provider times out
- **THEN** the system SHALL record the timeout in evidence metadata
- **AND** the system SHALL NOT tighten the decision solely due to that non-critical timeout

### Requirement: Timeout values are configuration-driven

The system SHALL treat numeric timeout values in documentation as examples and derive effective budgets from configuration.

#### Scenario: Example values do not hard-code behavior
- **WHEN** the spec references example budgets (e.g., 50ms/200ms/80ms)
- **THEN** the runtime behavior SHALL be determined by configured budgets and safe defaults
- **AND** the system SHALL allow overrides within safe maximum limits

### Requirement: Timeout evidence records are auditable

The system SHALL record sufficient metadata for each timed-out provider to support audit and postmortems.

#### Scenario: Timeout metadata is recorded
- **WHEN** a provider is marked with quality="TIMEOUT"
- **THEN** the evidence metadata SHALL include at least: provider_id, timeout_budget_ms, elapsed_ms, and whether the timeout impacted the final decision

### Requirement: Evidence quality labeling

The system SHALL label each evidence provider's outcome with a standardized quality indicator.

#### Scenario: OK label for successful collection
- **WHEN** an evidence provider completes successfully within its timeout budget
- **THEN** the system SHALL label that evidence with quality="OK"

#### Scenario: TIMEOUT label for exceeded budget
- **WHEN** an evidence provider exceeds its timeout budget
- **THEN** the system SHALL label that evidence with quality="TIMEOUT"
- **AND** the system SHALL include the timeout duration in the evidence metadata

#### Scenario: ERROR label for provider failure
- **WHEN** an evidence provider throws an exception or returns an error
- **THEN** the system SHALL label that evidence with quality="ERROR"
- **AND** the system SHALL include the error message in the evidence metadata

#### Scenario: DEGRADED label for partial fallback
- **WHEN** an evidence provider returns incomplete or cached data due to degradation
- **THEN** the system SHALL label that evidence with quality="DEGRADED"
- **AND** the system SHALL indicate which fields are fallback values in the evidence metadata

### Requirement: Evidence quality propagation to decision context

The system SHALL propagate evidence quality labels into the final decision context for explainability and auditability.

#### Scenario: Decision response includes evidence quality summary
- **WHEN** a decision is produced by the gate
- **THEN** the DecisionResponse SHALL include an evidence_quality_summary field
- **AND** this field SHALL list each provider's quality label (OK/TIMEOUT/ERROR/DEGRADED)

#### Scenario: Audit log includes evidence status
- **WHEN** a decision is logged for audit purposes
- **THEN** the audit log SHALL include the quality status of each evidence provider
- **AND** the log SHALL indicate which providers, if any, timed out or failed

### Requirement: Fail-closed timeout handling

The system SHALL remain fail-closed when evidence providers time out, but without causing cascading HITL escalation.

#### Scenario: Timeout does not auto-escalate to HITL
- **WHEN** one or more evidence providers time out (but the request is otherwise low-risk)
- **THEN** the system SHALL NOT automatically escalate the decision to HITL solely due to timeouts
- **AND** the system SHALL use the remaining available evidence to make the decision

#### Scenario: Missing high-risk evidence still tightens
- **WHEN** a request has risk_level R2 or R3 and a critical evidence provider (e.g., risk, permission) times out
- **THEN** the system SHALL apply missing evidence policy to tighten the decision
- **AND** the system SHALL mark the decision with a reason indicating the timeout

### Requirement: Configurable timeout budgets

The system SHALL provide configuration mechanisms to define timeout budgets per provider type and risk tier.

#### Scenario: Default timeout budgets
- **WHEN** the system starts without custom timeout configuration
- **THEN** the system SHALL use safe default timeout budgets (e.g., 80ms per provider)
- **AND** the defaults SHALL prevent any single provider from blocking the entire decision pipeline

#### Scenario: Custom timeout overrides
- **WHEN** an administrator configures custom timeout budgets for specific providers or risk tiers
- **THEN** the system SHALL apply the custom budgets instead of defaults
- **AND** the system SHALL validate that custom budgets are within safe maximum limits
