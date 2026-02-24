# Evidence Quality Labeling Specification

## ADDED Requirements

### Requirement: Standardized evidence quality labels

The system SHALL use a standardized set of quality labels to indicate the outcome of each evidence provider collection.

#### Scenario: Label enumeration
- **WHEN** labeling evidence provider outcomes
- **THEN** the system SHALL use one of the following quality labels:
  - OK: Collection successful within timeout budget
  - TIMEOUT: Provider exceeded timeout budget
  - ERROR: Provider threw an exception or returned an error
  - DEGRADED: Provider returned incomplete or cached data

### Requirement: Quality label in Evidence data structure

The system SHALL include the quality label in each Evidence object's data field.

#### Scenario: Quality field in Evidence
- **WHEN** an evidence provider returns an Evidence object
- **THEN** the Evidence.data dictionary SHALL include a "quality" field with one of the standardized labels (OK/TIMEOUT/ERROR/DEGRADED)

#### Scenario: Quality metadata for TIMEOUT
- **WHEN** an evidence provider is labeled with quality="TIMEOUT"
- **THEN** the Evidence.data SHALL include a "timeout_duration_ms" field indicating how long the provider took before timing out

#### Scenario: Quality metadata for ERROR
- **WHEN** an evidence provider is labeled with quality="ERROR"
- **THEN** the Evidence.data SHALL include an "error_message" field with the exception or error details

#### Scenario: Quality metadata for DEGRADED
- **WHEN** an evidence provider is labeled with quality="DEGRADED"
- **THEN** the Evidence.data SHALL include a "degraded_fields" array listing which fields are fallback values
- **AND** the system SHALL indicate the source of fallback data (e.g., "cache", "default", "last_known_good")

### Requirement: Evidence quality propagation to decision explanation

The system SHALL include evidence quality information in the decision explanation for auditability.

#### Scenario: Explanation includes quality summary
- **WHEN** a DecisionResponse is generated
- **THEN** the Explanation.evidence_used field SHALL reflect which evidence providers were used
- **AND** the system SHALL add an "evidence_quality" field to the Explanation listing each provider's quality label

#### Scenario: Primary reason reflects evidence quality
- **WHEN** a decision is influenced by evidence timeouts or failures
- **THEN** the DecisionResponse.primary_reason SHALL indicate if evidence degradation affected the decision
- **AND** the reason SHALL be descriptive (e.g., "EVIDENCE_TIMEOUT", "EVIDENCE_DEGRADED")

### Requirement: Evidence quality in audit logs

The system SHALL include evidence quality information in structured audit logs.

#### Scenario: Audit log includes quality summary
- **WHEN** a decision is logged
- **THEN** the audit log SHALL include an "evidence_providers" array
- **AND** each entry SHALL include provider name, quality label, and latency_ms

#### Scenario: Audit log indicates timeout impact
- **WHEN** one or more evidence providers timed out
- **THEN** the audit log SHALL include a "timeout_impact" field indicating whether the timeout affected the final decision
- **AND** the field SHALL be one of: "none", "tightened", "escalated_to_hitl"

### Requirement: Evidence quality does not create second decision source

The system SHALL use evidence quality labels for explainability and audit only, not as a secondary decision mechanism.

#### Scenario: Quality is explain-only
- **WHEN** evidence quality labels are added to the decision context
- **THEN** the labels SHALL NOT be used to independently modify the Decision enum
- **AND** the system SHALL only use quality labels for traceability, explanation, and audit purposes

#### Scenario: Single source of decision preserved
- **WHEN** evidence quality labels are propagated
- **THEN** the Decision enum SHALL still be determined solely by gate.py using matrix lookup and risk evaluation
- **AND** evidence quality SHALL NOT introduce a parallel decision path

### Requirement: Default quality label for legacy providers

The system SHALL ensure every Evidence object has a quality label, even if the provider does not explicitly set it.

#### Scenario: Missing quality is normalized
- **WHEN** an evidence provider returns an Evidence object without a "quality" field
- **THEN** the system SHALL normalize it to quality="OK"
- **AND** the system SHALL still record latency_ms for observability

### Requirement: Consistent evidence quality schema across outputs

The system SHALL use a consistent schema for evidence quality across DecisionResponse, Explanation, and audit logs.

#### Scenario: Same provider keys across outputs
- **WHEN** evidence quality is emitted in response and audit log
- **THEN** the provider identifiers and quality labels SHALL be consistent across all outputs
- **AND** consumers SHALL be able to correlate them via provider_id
