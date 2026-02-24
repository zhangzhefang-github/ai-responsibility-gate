"""
Helper functions for gate decision pipeline.

These functions are pure utilities and do NOT handle Decision enum or decision strings.
They operate on intermediate states (indices, evidence objects).
"""
import time
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import yaml
from enum import Enum

from ..evidence.knowledge import collect as collect_knowledge
from ..evidence.risk import collect as collect_risk
from ..evidence.permission import collect as collect_permission
from ..evidence.tool import collect as collect_tool
from ..evidence.routing import collect as collect_routing
from .models import Evidence, GateContext


# =============================================================================
# Feature Flags (Task 1.3: Placeholder & Toggle Only, No Behavior Changes)
# =============================================================================

# Feature flag for evidence timeout guard gradual rollout.
# When False: All timeout guard, circuit breaker, and quality labeling logic is disabled.
# When True: Timeout guard behavior is enabled (requires tasks 2.x-12.x to be implemented).
#
# Default: False (disabled until fully implemented and tested)
#
# This flag can be overridden via environment variable:
#   export AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED=true
#
# Implementation note: This flag is a PLACEHOLDER in Task 1.3.
# It MUST NOT be consumed to change any behavior until tasks 2.x+ are implemented.
_EVIDENCE_TIMEOUT_GUARD_ENABLED_DEFAULT = False


def is_evidence_timeout_guard_enabled() -> bool:
    """Check if evidence timeout guard feature is enabled.

    This feature flag controls whether evidence timeout guards, circuit breaker,
    and quality labeling are active.

    Returns:
        True if enabled, False otherwise.

    Note:
        In Task 1.3, this function only returns the default value.
        It will be consumed in later tasks (5.x, 6.x) to conditionally enable
        timeout guard behavior.

    Environment Variable:
        AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED: Set to "true" or "1" to enable
    """
    import os

    # Check environment variable override
    env_value = os.getenv("AI_GATE_EVIDENCE_TIMEOUT_GUARD_ENABLED", "").lower()
    if env_value in ("true", "1", "yes", "on"):
        return True
    if env_value in ("false", "0", "no", "off"):
        return False

    # No override, use default
    return _EVIDENCE_TIMEOUT_GUARD_ENABLED_DEFAULT


# =============================================================================
# Evidence Timeout Configuration (Task 1.2: Config Loading & Validation Only)
# =============================================================================

@dataclass(frozen=True)
class EvidenceTimeoutConfig:
    """Loaded and validated evidence timeout configuration.

    This config is loaded at startup and validated with fail-fast semantics.
    All timeout values are in milliseconds.
    """
    # Per-provider base timeouts (ms)
    provider_timeouts: Dict[str, int]

    # Risk tier multipliers (e.g., {"R0": 0.5, "R1": 1.0, ...})
    risk_tier_multipliers: Dict[str, float]

    # Overall collection deadline (ms)
    overall_deadline_ms: int

    # Safe maximum limits (for validation)
    max_timeout_ms: int
    min_timeout_ms: int
    min_overall_deadline_ms: int

    # Critical providers by risk tier (e.g., {"R2": ["risk", "permission"]})
    critical_providers: Dict[str, List[str]]

    # Circuit breaker settings
    circuit_breaker_timeout_threshold: int
    circuit_breaker_initial_cooldown_ms: int
    circuit_breaker_backoff_multiplier: float
    circuit_breaker_max_cooldown_ms: int
    circuit_breaker_half_open_max_probes: int


# Global config instance (loaded once at startup)
_evidence_timeout_config: Optional[EvidenceTimeoutConfig] = None


def _load_yaml_config(config_path: Path) -> Dict[str, Any]:
    """Load YAML config file with error handling.

    Args:
        config_path: Path to evidence_timeouts.yaml

    Returns:
        Parsed YAML dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config is invalid YAML
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Evidence timeout config not found: {config_path}\n"
            f"Create this file or disable evidence_timeout_guard_enabled feature flag."
        )

    with open(config_path, "r") as f:
        try:
            return yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML in {config_path}: {e}")


def _validate_timeout_range(value: Any, field_name: str, min_val: int, max_val: int) -> int:
    """Validate a timeout value is within safe range.

    Args:
        value: The timeout value from config (may be string like "80ms" or int)
        field_name: Field name for error messages
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Validated integer timeout in milliseconds

    Raises:
        ValueError: If value is invalid or out of range
    """
    # Parse "80ms" format to int
    if isinstance(value, str):
        if value.lower().endswith("ms"):
            value = value[:-2].strip()
        try:
            value = int(value)
        except ValueError:
            raise ValueError(f"{field_name} must be an integer or 'Xms' format, got: {value}")

    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number, got: {type(value).__name__}")

    value_int = int(value)

    if value_int < min_val:
        raise ValueError(f"{field_name} ({value_int}ms) is below minimum ({min_val}ms)")
    if value_int > max_val:
        raise ValueError(f"{field_name} ({value_int}ms) exceeds maximum ({max_val}ms)")

    return value_int


def _parse_multiplier(value: Any, field_name: str) -> float:
    """Parse a multiplier value (e.g., "1.5x" -> 1.5).

    Args:
        value: The multiplier from config (may be float or string like "1.5x")
        field_name: Field name for error messages

    Returns:
        Validated float multiplier

    Raises:
        ValueError: If value is invalid
    """
    if isinstance(value, str):
        if value.lower().endswith("x"):
            value = value[:-1].strip()
        try:
            value = float(value)
        except ValueError:
            raise ValueError(f"{field_name} must be a number or 'X.x' format, got: {value}")

    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number, got: {type(value).__name__}")

    multiplier = float(value)
    if multiplier <= 0:
        raise ValueError(f"{field_name} must be positive, got: {multiplier}")

    return multiplier


def load_evidence_timeout_config(config_path: Path = None) -> EvidenceTimeoutConfig:
    """Load and validate evidence timeout configuration.

    This function performs fail-fast validation of all configuration values.
    If validation fails, it raises an exception to prevent startup with invalid config.

    Args:
        config_path: Path to evidence_timeouts.yaml. If None, uses default path.

    Returns:
        Validated EvidenceTimeoutConfig instance

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config values are invalid or out of safe range
        yaml.YAMLError: If config is invalid YAML
    """
    global _evidence_timeout_config

    if _evidence_timeout_config is not None:
        return _evidence_timeout_config

    if config_path is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "evidence_timeouts.yaml"

    raw = _load_yaml_config(config_path)

    # Validate and parse provider_timeouts
    provider_timeouts_raw = raw.get("provider_timeouts", {})
    if not isinstance(provider_timeouts_raw, dict):
        raise ValueError("provider_timeouts must be a dictionary")

    provider_timeouts = {}
    for provider, timeout in provider_timeouts_raw.items():
        validated_timeout = _validate_timeout_range(
            timeout,
            f"provider_timeouts.{provider}",
            min_val=10,   # Will be overridden by config min_timeout_ms
            max_val=5000  # Will be overridden by config max_timeout_ms
        )
        provider_timeouts[provider] = validated_timeout

    # Ensure 'default' provider exists
    if "default" not in provider_timeouts:
        raise ValueError("provider_timeouts must include a 'default' entry")

    # Validate and parse risk_tier_multipliers
    risk_tiers_raw = raw.get("risk_tier_multipliers", {})
    if not isinstance(risk_tiers_raw, dict):
        raise ValueError("risk_tier_multipliers must be a dictionary")

    required_tiers = ["R0", "R1", "R2", "R3"]
    risk_tier_multipliers = {}
    for tier in required_tiers:
        if tier not in risk_tiers_raw:
            raise ValueError(f"risk_tier_multipliers must include '{tier}'")
        risk_tier_multipliers[tier] = _parse_multiplier(risk_tiers_raw[tier], f"risk_tier_multipliers.{tier}")

    # Validate safe maximum limits from config
    max_timeout_ms = _validate_timeout_range(
        raw.get("max_timeout_ms", 5000),
        "max_timeout_ms",
        min_val=100,
        max_val=60000  # Absolute hard limit
    )

    min_timeout_ms = _validate_timeout_range(
        raw.get("min_timeout_ms", 10),
        "min_timeout_ms",
        min_val=1,
        max_val=1000
    )

    min_overall_deadline_ms = _validate_timeout_range(
        raw.get("min_overall_deadline_ms", 200),
        "min_overall_deadline_ms",
        min_val=50,
        max_val=5000
    )

    # Re-validate all provider timeouts against configured limits
    for provider, timeout in provider_timeouts.items():
        if timeout < min_timeout_ms:
            raise ValueError(
                f"provider_timeouts.{provider} ({timeout}ms) is below configured minimum ({min_timeout_ms}ms)"
            )
        if timeout > max_timeout_ms:
            raise ValueError(
                f"provider_timeouts.{provider} ({timeout}ms) exceeds configured maximum ({max_timeout_ms}ms)"
            )

    # Validate overall_deadline_ms
    overall_deadline_ms = _validate_timeout_range(
        raw.get("overall_deadline_ms", 500),
        "overall_deadline_ms",
        min_val=min_overall_deadline_ms,
        max_val=10000
    )

    # Validate critical_providers
    critical_providers_raw = raw.get("critical_providers", {})
    if not isinstance(critical_providers_raw, dict):
        raise ValueError("critical_providers must be a dictionary")

    critical_providers = {}
    for tier, providers in critical_providers_raw.items():
        if tier not in required_tiers:
            raise ValueError(f"critical_providers has unknown tier: {tier}")
        if not isinstance(providers, list):
            raise ValueError(f"critical_providers.{tier} must be a list")
        if not all(isinstance(p, str) for p in providers):
            raise ValueError(f"critical_providers.{tier} must contain only strings")
        critical_providers[tier] = providers

    # Validate circuit_breaker config
    cb_raw = raw.get("circuit_breaker", {})
    if not isinstance(cb_raw, dict):
        raise ValueError("circuit_breaker must be a dictionary")

    circuit_breaker_timeout_threshold = int(cb_raw.get("timeout_threshold", 3))
    if circuit_breaker_timeout_threshold < 1 or circuit_breaker_timeout_threshold > 10:
        raise ValueError("circuit_breaker.timeout_threshold must be between 1 and 10")

    circuit_breaker_initial_cooldown_ms = _validate_timeout_range(
        cb_raw.get("initial_cooldown_ms", 30000),
        "circuit_breaker.initial_cooldown_ms",
        min_val=1000,
        max_val=300000  # 5 minutes
    )

    circuit_breaker_backoff_multiplier = _parse_multiplier(
        cb_raw.get("backoff_multiplier", 2.0),
        "circuit_breaker.backoff_multiplier"
    )
    if circuit_breaker_backoff_multiplier < 1.0 or circuit_breaker_backoff_multiplier > 10.0:
        raise ValueError("circuit_breaker.backoff_multiplier must be between 1.0 and 10.0")

    circuit_breaker_max_cooldown_ms = _validate_timeout_range(
        cb_raw.get("max_cooldown_ms", 60000),
        "circuit_breaker.max_cooldown_ms",
        min_val=5000,
        max_val=3600000  # 1 hour
    )

    circuit_breaker_half_open_max_probes = int(cb_raw.get("half_open_max_probes", 1))
    if circuit_breaker_half_open_max_probes < 1 or circuit_breaker_half_open_max_probes > 10:
        raise ValueError("circuit_breaker.half_open_max_probes must be between 1 and 10")

    # Create validated config instance
    _evidence_timeout_config = EvidenceTimeoutConfig(
        provider_timeouts=provider_timeouts,
        risk_tier_multipliers=risk_tier_multipliers,
        overall_deadline_ms=overall_deadline_ms,
        max_timeout_ms=max_timeout_ms,
        min_timeout_ms=min_timeout_ms,
        min_overall_deadline_ms=min_overall_deadline_ms,
        critical_providers=critical_providers,
        circuit_breaker_timeout_threshold=circuit_breaker_timeout_threshold,
        circuit_breaker_initial_cooldown_ms=circuit_breaker_initial_cooldown_ms,
        circuit_breaker_backoff_multiplier=circuit_breaker_backoff_multiplier,
        circuit_breaker_max_cooldown_ms=circuit_breaker_max_cooldown_ms,
        circuit_breaker_half_open_max_probes=circuit_breaker_half_open_max_probes,
    )

    return _evidence_timeout_config


def get_evidence_timeout_config() -> Optional[EvidenceTimeoutConfig]:
    """Get the loaded evidence timeout configuration.

    Returns:
        EvidenceTimeoutConfig instance, or None if not yet loaded.

    Note:
        This function does NOT load the config. Call load_evidence_timeout_config()
        first to load and validate the configuration.
    """
    return _evidence_timeout_config

# =============================================================================
# Circuit Breaker State Machine (Task 2.1: Class Definition Only, Pure State)
# =============================================================================

class CircuitBreakerState(Enum):
    """Circuit breaker states for evidence provider health tracking.

    State transitions:
        CLOSED -> OPEN: After consecutive_timeout_threshold timeouts
        OPEN -> HALF_OPEN: After cooldown period expires
        HALF-OPEN -> CLOSED: On successful probe
        HALF-OPEN -> OPEN: On probe timeout
    """
    CLOSED = "CLOSED"       # Normal operation, provider is healthy
    OPEN = "OPEN"           # Provider is throttled, skip calls
    HALF_OPEN = "HALF_OPEN"  # Testing if provider recovered


@dataclass(frozen=True)
class CircuitBreakerTransition:
    """Immutable event representing a circuit breaker state transition.

    This event is emitted on every state transition for metrics and observability.
    The frozen=True parameter ensures immutability (events cannot be modified
    after creation).

    Attributes:
        provider_id: Identifier for the evidence provider
        from_state: Previous circuit breaker state
        to_state: New circuit breaker state
        timestamp_ms: When the transition occurred (milliseconds)
        open_count: Number of times circuit has opened (for backoff correlation)
        cooldown_duration_ms: For transitions to OPEN, the cooldown duration (0 otherwise)
    """
    provider_id: str
    from_state: CircuitBreakerState
    to_state: CircuitBreakerState
    timestamp_ms: int
    open_count: int
    cooldown_duration_ms: int = 0


@dataclass(frozen=True)
class CircuitBreakerSnapshot:
    """Immutable snapshot of circuit breaker state for testing/observability.

    This class provides read-only access to circuit breaker state without
    exposing internal mutation methods. The frozen=True parameter ensures
    immutability (attempts to modify fields will raise an exception).
    """
    provider_id: str
    state: CircuitBreakerState
    consecutive_timeouts: int
    consecutive_successes: int
    open_count: int  # Number of times circuit has opened (for backoff calculation)
    last_state_change_ms: int  # Timestamp of last state transition
    cooldown_expires_at_ms: int  # When OPEN state will transition to HALF_OPEN


class CircuitBreaker:
    """Circuit breaker for evidence provider health tracking.

    This class implements a pure state machine that tracks provider health
    and prevents cascade failures by throttling chronically failing providers.

    Key behaviors:
    - Tracks consecutive timeouts to detect chronic failures
    - Transitions to OPEN state after threshold is exceeded
    - Tracks cooldown period before allowing probe requests
    - Resets to CLOSED on successful recovery

    Thread-safety: This class is NOT thread-safe. In async environments,
    ensure all calls to a given CircuitBreaker instance happen within
    the same async context or use external synchronization.

    Implementation note (Task 2.1 scope):
    - This class ONLY defines the state machine and basic state transitions.
    - Methods like should_call_provider() and exponential backoff calculation
      are implemented in later tasks (2.2, 2.3).
    """

    def __init__(
        self,
        provider_id: str,
        timeout_threshold: int = 3,
        initial_cooldown_ms: int = 30000,
        backoff_multiplier: float = 2.0,
        max_cooldown_ms: int = 60000,
        half_open_max_probes: int = 1,
        transition_emitter=None,  # Optional callback for transition events
    ):
        """Initialize a new circuit breaker for a provider.

        Args:
            provider_id: Unique identifier for this evidence provider
            timeout_threshold: Number of consecutive timeouts before opening circuit
            initial_cooldown_ms: Initial cooldown duration when circuit opens (ms)
            backoff_multiplier: Multiplier for exponential backoff on successive opens
            max_cooldown_ms: Maximum cooldown duration (ms)
            half_open_max_probes: Maximum concurrent probes in HALF-OPEN state
            transition_emitter: Optional callable(transition) for emitting transition events
        """
        self._provider_id = provider_id
        self._timeout_threshold = timeout_threshold
        self._initial_cooldown_ms = initial_cooldown_ms
        self._backoff_multiplier = backoff_multiplier
        self._max_cooldown_ms = max_cooldown_ms
        self._half_open_max_probes = half_open_max_probes
        self._transition_emitter = transition_emitter

        # State fields
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_timeouts = 0
        self._consecutive_successes = 0
        self._open_count = 0  # Number of times circuit has opened (for backoff)
        self._last_state_change_ms = 0
        self._cooldown_expires_at_ms = 0  # Timestamp when OPEN -> HALF_OPEN

        # HALF-OPEN probe concurrency control
        self._half_open_probe_count = 0  # Number of active probes in HALF-OPEN state

    @property
    def provider_id(self) -> str:
        """Get the provider ID for this circuit breaker."""
        return self._provider_id

    @property
    def state(self) -> CircuitBreakerState:
        """Get the current circuit breaker state."""
        return self._state

    @property
    def consecutive_timeouts(self) -> int:
        """Get the current consecutive timeout count."""
        return self._consecutive_timeouts

    @property
    def consecutive_successes(self) -> int:
        """Get the current consecutive success count."""
        return self._consecutive_successes

    @property
    def open_count(self) -> int:
        """Get the number of times the circuit has opened."""
        return self._open_count

    @property
    def last_state_change_ms(self) -> int:
        """Get the timestamp of the last state change."""
        return self._last_state_change_ms

    @property
    def cooldown_expires_at_ms(self) -> int:
        """Get the timestamp when the current cooldown expires."""
        return self._cooldown_expires_at_ms

    def get_snapshot(self) -> CircuitBreakerSnapshot:
        """Get an immutable snapshot of the current state.

        Returns:
            CircuitBreakerSnapshot with current state fields
        """
        return CircuitBreakerSnapshot(
            provider_id=self._provider_id,
            state=self._state,
            consecutive_timeouts=self._consecutive_timeouts,
            consecutive_successes=self._consecutive_successes,
            open_count=self._open_count,
            last_state_change_ms=self._last_state_change_ms,
            cooldown_expires_at_ms=self._cooldown_expires_at_ms,
        )

    def should_call_provider(self, now_ms: int) -> bool:
        """Check if a provider should be called based on circuit breaker state.

        This method implements probe concurrency control for HALF-OPEN state.
        It does NOT execute any provider calls, only returns a boolean indicating
        whether a call is allowed.

        State-based decision logic:
        - CLOSED: Always allow calls (provider is healthy)
        - OPEN: Skip calls if cooldown hasn't expired; transition to HALF_OPEN if expired
        - HALF_OPEN: Allow only limited number of concurrent probe calls

        Args:
            now_ms: Current timestamp in milliseconds

        Returns:
            True if provider should be called, False if should be skipped

        Note:
            This method may trigger state transitions (OPEN -> HALF_OPEN) when cooldown expires.
            Probe success/failure is tracked separately via record_success() and record_timeout().
        """
        if self._state == CircuitBreakerState.CLOSED:
            # Provider is healthy, always allow calls
            return True

        elif self._state == CircuitBreakerState.OPEN:
            # Provider is throttled, check if cooldown has expired
            if now_ms >= self._cooldown_expires_at_ms:
                # Cooldown expired, transition to HALF_OPEN for probe
                self._transition_to_half_open(now_ms)
                # Allow the first probe call
                self._half_open_probe_count += 1
                return True
            else:
                # Still in cooldown, skip provider
                return False

        elif self._state == CircuitBreakerState.HALF_OPEN:
            # Probe state: allow limited concurrent probes
            if self._half_open_probe_count < self._half_open_max_probes:
                self._half_open_probe_count += 1
                return True
            else:
                # Too many concurrent probes, skip additional calls
                return False

        # Fallback (should never reach here)
        return False

    def _emit_transition(self, from_state: CircuitBreakerState, cooldown_ms: int = 0) -> None:
        """Emit a transition event if an emitter callback is configured.

        This is called internally by state transition methods to notify observers
        of circuit breaker state changes.

        Args:
            from_state: The state we're transitioning from
            cooldown_ms: For transitions to OPEN, the cooldown duration (default 0)
        """
        if self._transition_emitter is not None:
            transition = CircuitBreakerTransition(
                provider_id=self._provider_id,
                from_state=from_state,
                to_state=self._state,
                timestamp_ms=self._last_state_change_ms,
                open_count=self._open_count,
                cooldown_duration_ms=cooldown_ms,
            )
            self._transition_emitter(transition)

    def record_timeout(self, now_ms: int) -> None:
        """Record a timeout event for this provider.

        This may trigger a state transition from CLOSED -> OPEN if the
        consecutive timeout threshold is exceeded.

        Args:
            now_ms: Current timestamp in milliseconds
        """
        # Decrement probe count BEFORE state transition if in HALF_OPEN
        if self._state == CircuitBreakerState.HALF_OPEN and self._half_open_probe_count > 0:
            self._half_open_probe_count -= 1

        self._consecutive_timeouts += 1
        self._consecutive_successes = 0

        # Check if we should open the circuit
        if self._state == CircuitBreakerState.CLOSED and self._consecutive_timeouts >= self._timeout_threshold:
            self._transition_to_open(now_ms)
        elif self._state == CircuitBreakerState.HALF_OPEN:
            # Probe failed, go back to OPEN
            self._transition_to_open(now_ms)

    def record_success(self, now_ms: int) -> None:
        """Record a successful response from this provider.

        This may trigger a state transition from HALF_OPEN -> CLOSED
        or reset timeout counters in CLOSED state.

        Args:
            now_ms: Current timestamp in milliseconds
        """
        # Decrement probe count BEFORE state transition if in HALF_OPEN
        if self._state == CircuitBreakerState.HALF_OPEN and self._half_open_probe_count > 0:
            self._half_open_probe_count -= 1

        self._consecutive_timeouts = 0
        self._consecutive_successes += 1

        if self._state == CircuitBreakerState.HALF_OPEN:
            # Probe succeeded, close the circuit
            self._transition_to_closed(now_ms)

    def _transition_to_open(self, now_ms: int) -> None:
        """Transition to OPEN state and calculate cooldown period with exponential backoff.

        The cooldown duration increases exponentially with each successive OPEN state
        to prevent aggressive retry against chronically failing providers.

        Cooldown calculation:
            base = initial_cooldown_ms
            multiplier = backoff_multiplier ^ (open_count - 1)
            cooldown = min(base * multiplier, max_cooldown_ms)

        Examples (with initial=30s, multiplier=2.0, max=60s):
            1st open: 30s (30 * 2^0 = 30)
            2nd open: 60s (30 * 2^1 = 60)
            3rd open: 60s (30 * 2^2 = 120, capped at 60)

        Args:
            now_ms: Current timestamp in milliseconds
        """
        from_state = self._state
        self._state = CircuitBreakerState.OPEN
        self._open_count += 1
        self._last_state_change_ms = now_ms

        # Reset probe count when entering OPEN state
        self._half_open_probe_count = 0

        # Calculate exponential backoff: initial_cooldown * (multiplier ^ (open_count - 1))
        # But cap at max_cooldown_ms
        backoff_exponent = max(0, self._open_count - 1)
        cooldown_ms = self._initial_cooldown_ms * (self._backoff_multiplier ** backoff_exponent)
        cooldown_ms = min(cooldown_ms, self._max_cooldown_ms)

        self._cooldown_expires_at_ms = now_ms + int(cooldown_ms)

        # Emit transition event (Task 2.4)
        self._emit_transition(from_state, cooldown_ms=int(cooldown_ms))

    def _transition_to_half_open(self, now_ms: int) -> None:
        """Transition to HALF_OPEN state for testing.

        Args:
            now_ms: Current timestamp in milliseconds
        """
        from_state = self._state
        self._state = CircuitBreakerState.HALF_OPEN
        self._last_state_change_ms = now_ms
        # Reset probe count when entering HALF_OPEN (will be incremented by should_call_provider)
        self._half_open_probe_count = 0

        # Emit transition event (Task 2.4)
        self._emit_transition(from_state)

    def _transition_to_closed(self, now_ms: int) -> None:
        """Transition to CLOSED state (recovered).

        Args:
            now_ms: Current timestamp in milliseconds
        """
        from_state = self._state
        self._state = CircuitBreakerState.CLOSED
        self._consecutive_timeouts = 0
        self._consecutive_successes = 0
        self._last_state_change_ms = now_ms
        self._cooldown_expires_at_ms = 0
        # Reset probe count when recovering to CLOSED
        self._half_open_probe_count = 0

        # Emit transition event (Task 2.4)
        self._emit_transition(from_state)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"CircuitBreaker("
            f"provider_id={self._provider_id}, "
            f"state={self._state.value}, "
            f"consecutive_timeouts={self._consecutive_timeouts}, "
            f"open_count={self._open_count}, "
            f"cooldown_expires_at={self._cooldown_expires_at_ms}"
            f")"
        )


# =============================================================================
# Circuit Breaker Registry (Task 2.5: In-Memory Only, Non-Concurrent)
# =============================================================================

# In-memory registry mapping provider_id -> CircuitBreaker instance.
# This registry is intentionally NOT thread-safe and matches the CircuitBreaker
# class's non-thread-safe semantics. Callers are responsible for ensuring
# appropriate single-threaded / single-task usage per provider.
_circuit_breakers_by_provider: Dict[str, CircuitBreaker] = {}


def get_or_create_circuit_breaker_for_provider(
    provider_id: str,
    timeout_threshold: Optional[int] = None,
    initial_cooldown_ms: Optional[int] = None,
    backoff_multiplier: Optional[float] = None,
    max_cooldown_ms: Optional[int] = None,
    half_open_max_probes: Optional[int] = None,
    transition_emitter=None,
) -> CircuitBreaker:
    """Get or create a CircuitBreaker instance for a provider.

    This registry is purely in-memory and does NOT perform any I/O, metrics
    emission, or configuration loading. It only manages the lifecycle of
    CircuitBreaker instances keyed by provider_id.

    Concurrency:
        This function is NOT thread-safe and does not use any locking. It is
        intended to be used in the same single-threaded / single-task context
        as the CircuitBreaker instances it manages.

    Parameter semantics:
        - On first creation for a given provider_id, optional constructor
          parameters (timeout_threshold, initial_cooldown_ms, backoff_multiplier,
          max_cooldown_ms, half_open_max_probes, transition_emitter) are applied
          to the new CircuitBreaker instance.
        - On subsequent calls for the same provider_id, ALL constructor
          parameters are ignored and the existing instance is returned as-is.

    Args:
        provider_id: Unique identifier for the evidence provider.
        timeout_threshold: Optional override for consecutive timeout threshold.
        initial_cooldown_ms: Optional override for initial cooldown duration (ms).
        backoff_multiplier: Optional override for exponential backoff multiplier.
        max_cooldown_ms: Optional override for maximum cooldown duration (ms).
        half_open_max_probes: Optional override for HALF-OPEN max probes.
        transition_emitter: Optional callable to receive transition events.

    Returns:
        CircuitBreaker: The existing or newly created circuit breaker instance
        for the given provider_id.
    """
    existing = _circuit_breakers_by_provider.get(provider_id)
    if existing is not None:
        return existing

    kwargs: Dict[str, Any] = {}
    if timeout_threshold is not None:
        kwargs["timeout_threshold"] = timeout_threshold
    if initial_cooldown_ms is not None:
        kwargs["initial_cooldown_ms"] = initial_cooldown_ms
    if backoff_multiplier is not None:
        kwargs["backoff_multiplier"] = backoff_multiplier
    if max_cooldown_ms is not None:
        kwargs["max_cooldown_ms"] = max_cooldown_ms
    if half_open_max_probes is not None:
        kwargs["half_open_max_probes"] = half_open_max_probes
    if transition_emitter is not None:
        kwargs["transition_emitter"] = transition_emitter

    breaker = CircuitBreaker(provider_id=provider_id, **kwargs)
    _circuit_breakers_by_provider[provider_id] = breaker
    return breaker


def _reset_circuit_breaker_registry_for_testing() -> None:
    """Reset the in-memory circuit breaker registry (TESTS ONLY).

    This function is intended solely for use in unit/integration tests to
    ensure isolation between test cases. It MUST NOT be called from production
    code paths.
    """
    _circuit_breakers_by_provider.clear()


# =============================================================================
# Legacy Helper Functions (Pre-Task 2.x)
# =============================================================================

# Decision index constants (no decision strings here)
DECISION_IDX_MIN = 0
DECISION_IDX_MAX = 3


def tighten_one_step(current_index: int, steps: int = 1) -> int:
    """Tighten decision by moving index forward."""
    new_index = min(current_index + steps, DECISION_IDX_MAX)
    return new_index

def extract_evidence(result) -> Evidence:
    """Extract Evidence from result, handling exceptions."""
    if isinstance(result, Exception):
        return Evidence(provider="unknown", available=False, data={})
    return result

async def collect_all_evidence(ctx: GateContext, trace: List[str]) -> dict:
    """Concurrently collect all evidence with timeout."""
    if is_evidence_timeout_guard_enabled():
        now_ms = int(time.time() * 1000)
        circuit_breakers: Dict[str, CircuitBreaker] = {}
        for provider_id in ("tool", "routing", "knowledge", "risk", "permission"):
            circuit_breakers[provider_id] = get_or_create_circuit_breaker_for_provider(provider_id)
        evidence_tasks = []
        metas: List[tuple] = []
        providers = (
            ("tool", collect_tool),
            ("routing", collect_routing),
            ("knowledge", collect_knowledge),
            ("risk", collect_risk),
            ("permission", collect_permission),
        )
        for provider_id, collect_fn in providers:
            if circuit_breakers[provider_id].should_call_provider(now_ms):
                evidence_tasks.append(asyncio.wait_for(collect_fn(ctx), timeout=0.08))
                metas.append((provider_id, circuit_breakers[provider_id], False))
            else:
                evidence_tasks.append(
                    asyncio.sleep(0, result=Evidence(provider=provider_id, available=False, data={}))
                )
                metas.append((provider_id, circuit_breakers[provider_id], True))
    else:
        evidence_tasks = [
            asyncio.wait_for(collect_tool(ctx), timeout=0.08),
            asyncio.wait_for(collect_routing(ctx), timeout=0.08),
            asyncio.wait_for(collect_knowledge(ctx), timeout=0.08),
            asyncio.wait_for(collect_risk(ctx), timeout=0.08),
            asyncio.wait_for(collect_permission(ctx), timeout=0.08),
        ]
        metas = None

    start_time = time.perf_counter()
    evidence_results = await asyncio.gather(*evidence_tasks, return_exceptions=True)
    total_time = (time.perf_counter() - start_time) * 1000

    if is_evidence_timeout_guard_enabled() and metas is not None:
        for i, (provider_id, breaker, skipped) in enumerate(metas):
            if skipped:
                continue
            result = evidence_results[i]
            if isinstance(result, asyncio.TimeoutError):
                breaker.record_timeout(now_ms)
            elif isinstance(result, Exception):
                breaker.record_timeout(now_ms)
            else:
                if getattr(result, "available", False) is True:
                    breaker.record_success(now_ms)

    if is_evidence_timeout_guard_enabled():
        provider_ids = ("tool", "routing", "knowledge", "risk", "permission")
        normalized = []
        for i in range(5):
            result = evidence_results[i]
            pid = provider_ids[i]
            if isinstance(result, asyncio.TimeoutError):
                normalized.append(
                    Evidence(
                        provider=pid,
                        available=False,
                        data={"_outcome": "TIMEOUT", "_timeout_budget_exceeded": True},
                    )
                )
            elif isinstance(result, Exception):
                normalized.append(
                    Evidence(
                        provider=pid,
                        available=False,
                        data={"_outcome": "ERROR", "_timeout_budget_exceeded": True},
                    )
                )
            else:
                if getattr(result, "available", False) is True:
                    normalized.append(
                        Evidence(
                            provider=result.provider,
                            available=result.available,
                            data={**result.data, "_outcome": "OK", "_timeout_budget_exceeded": False},
                        )
                    )
                else:
                    # Missing / skipped evidence keeps existing semantics:
                    # available=False, no outcome or budget flags.
                    normalized.append(result)
        tool_ev, routing_ev, knowledge_ev, risk_ev, permission_ev = normalized
    else:
        tool_ev = extract_evidence(evidence_results[0])
        routing_ev = extract_evidence(evidence_results[1])
        knowledge_ev = extract_evidence(evidence_results[2])
        risk_ev = extract_evidence(evidence_results[3])
        permission_ev = extract_evidence(evidence_results[4])

    # Aggregate-level degradation / HITL suggestion labels (explain-only).
    meta: Optional[Dict[str, Any]] = None
    if is_evidence_timeout_guard_enabled():
        budget_exceeded_count = 0
        for ev in (tool_ev, routing_ev, knowledge_ev, risk_ev, permission_ev):
            if ev.data.get("_timeout_budget_exceeded") is True:
                budget_exceeded_count += 1

        meta = {
            "_degradation_suggested": budget_exceeded_count >= 1,
            "_hitl_suggested": budget_exceeded_count >= 2,
        }

    if trace:
        trace.append(f"[TRACE] 2. Evidence Collection (concurrent, {total_time:.0f}ms):")
        trace.append(f"[TRACE]   - tool: {'ok' if tool_ev.available else 'missing/timeout'}")
        if tool_ev.available and tool_ev.data.get("tool_id"):
            trace.append(f"[TRACE]     tool_id={tool_ev.data['tool_id']}, action_type={tool_ev.data['action_type']}")
        trace.append(f"[TRACE]   - routing: {'ok' if routing_ev.available else 'missing'}")
        if routing_ev.available and routing_ev.data.get("hinted_tools"):
            hinted = routing_ev.data.get("hinted_tools", [])
            conf = routing_ev.data.get("confidence", 0.0)
            trace.append(f"[TRACE]     hinted_tools={[h['tool_id'] for h in hinted]}, confidence={conf:.2f}")
        trace.append(f"[TRACE]   - knowledge: {'ok' if knowledge_ev.available else 'missing'}")
        trace.append(f"[TRACE]   - risk: {'ok' if risk_ev.available else 'missing'}")
        if risk_ev.available:
            trace.append(f"[TRACE]     rules_hit={risk_ev.data.get('rules_hit', [])}")
            trace.append(f"[TRACE]     risk_level={risk_ev.data.get('risk_level', '')}")
        trace.append(f"[TRACE]   - permission: {'ok' if permission_ev.available else 'missing/timeout'}")
        if permission_ev.available:
            trace.append(f"[TRACE]     has_access={permission_ev.data.get('has_access')}, reason={permission_ev.data.get('reason_code')}")

    result: Dict[str, Any] = {
        "tool": tool_ev,
        "routing": routing_ev,
        "knowledge": knowledge_ev,
        "risk": risk_ev,
        "permission": permission_ev,
    }
    # Only attach meta when timeout guard feature is enabled.
    if meta is not None:
        result["_meta"] = meta

    return result

# Import asyncio for evidence collection
import asyncio
