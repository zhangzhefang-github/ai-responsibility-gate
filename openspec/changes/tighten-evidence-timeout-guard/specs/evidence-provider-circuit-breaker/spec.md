# Evidence Provider Circuit Breaker Specification

## ADDED Requirements

### Requirement: Circuit breaker state tracking

The system SHALL track consecutive timeouts for each evidence provider to detect chronic failures.

#### Scenario: Circuit breaker closed (normal operation)
- **WHEN** an evidence provider has fewer than the configured timeout threshold (e.g., 3 consecutive timeouts)
- **THEN** the circuit breaker state SHALL be CLOSED
- **AND** the system SHALL allow requests to that provider normally

#### Scenario: Circuit breaker opens after threshold
- **WHEN** an evidence provider exceeds the configured timeout threshold (e.g., 3 consecutive timeouts)
- **THEN** the circuit breaker state SHALL transition to OPEN
- **AND** the system SHALL skip that provider for a configured cooldown period

#### Scenario: Circuit breaker half-open after cooldown
- **WHEN** the cooldown period expires for a provider in OPEN state
- **THEN** the circuit breaker state SHALL transition to HALF-OPEN
- **AND** the system SHALL allow a single probe request to test if the provider has recovered

### Requirement: Circuit breaker backoff and throttling

The system SHALL apply exponential backoff and throttling for evidence providers in OPEN circuit state.

#### Scenario: Exponential backoff duration
- **WHEN** a provider's circuit breaker opens
- **THEN** the cooldown period SHALL increase exponentially with each successive OPEN state
- **AND** the backoff multiplier SHALL be configurable (default: 2x)

#### Scenario: Maximum backoff limit
- **WHEN** the calculated backoff duration exceeds the configured maximum (e.g., 60 seconds)
- **THEN** the system SHALL cap the cooldown at the maximum duration
- **AND** the system SHALL NOT allow indefinite backoff growth

### Requirement: Circuit breaker reset on success

The system SHALL reset the circuit breaker state when a provider successfully responds.

#### Scenario: Reset on successful response in HALF-OPEN state
- **WHEN** a provider in HALF-OPEN state returns a successful response
- **THEN** the circuit breaker state SHALL transition to CLOSED
- **AND** the consecutive timeout counter SHALL reset to zero

#### Scenario: Reset on successful response in OPEN state
- **WHEN** a provider in OPEN state returns a successful response (via manual probe or timeout expiry)
- **THEN** the circuit breaker state SHALL transition to CLOSED
- **AND** the system SHALL resume normal requests to that provider

### Requirement: Circuit breaker observability

The system SHALL provide visibility into circuit breaker state transitions and provider availability.

#### Scenario: Circuit breaker state in metrics
- **WHEN** a circuit breaker state transition occurs
- **THEN** the system SHALL emit a metric recording the transition (provider_id, from_state, to_state, timestamp)
- **AND** the metric SHALL be queryable for monitoring and alerting

#### Scenario: Provider availability in logs
- **WHEN** an evidence provider is skipped due to an OPEN circuit breaker
- **THEN** the system SHALL log a warning indicating the provider is in circuit breaker cooldown
- **AND** the log SHALL include the provider name, consecutive timeout count, and remaining cooldown time

### Requirement: Circuit breaker configuration

The system SHALL allow configuration of circuit breaker thresholds and policies per provider type.

#### Scenario: Provider-specific circuit breaker thresholds
- **WHEN** an administrator configures different timeout thresholds for different providers
- **THEN** the system SHALL apply the provider-specific thresholds instead of global defaults
- **AND** the system SHALL validate that thresholds are within safe minimum and maximum bounds

#### Scenario: Global circuit breaker defaults
- **WHEN** no provider-specific circuit breaker configuration is provided
- **THEN** the system SHALL use global default thresholds (e.g., 3 consecutive timeouts, 30s cooldown)
- **AND** the defaults SHALL be conservative enough to prevent cascade failures while allowing reasonable recovery time

### Requirement: Provider identity for circuit breaker

The system SHALL define a stable `provider_id` for each evidence provider instance for circuit breaker tracking and observability.

#### Scenario: provider_id is stable across requests
- **WHEN** the same evidence provider is invoked across multiple requests
- **THEN** the system SHALL use the same `provider_id` for timeout counters and circuit breaker state
- **AND** the `provider_id` SHALL be included in metrics and logs for state transitions

### Requirement: Half-open probe concurrency control

The system SHALL ensure that in HALF-OPEN state, only a single probe attempt is executed per provider per cooldown window.

#### Scenario: Only one probe is allowed
- **WHEN** multiple concurrent requests arrive while a provider is in HALF-OPEN
- **THEN** the system SHALL allow only one request to perform the probe
- **AND** other requests SHALL treat the provider as unavailable until the probe outcome is known

### Requirement: Skipped provider produces auditable evidence result

The system SHALL record an auditable evidence result when a provider is skipped due to an OPEN circuit breaker.

#### Scenario: Skipped provider is labeled and logged
- **WHEN** a provider is skipped because its circuit breaker is OPEN
- **THEN** the system SHALL record an evidence outcome for that provider with a skip indicator in metadata (e.g., `skip_reason="circuit_open"`)
- **AND** the audit log SHALL include the skip reason and remaining cooldown time
