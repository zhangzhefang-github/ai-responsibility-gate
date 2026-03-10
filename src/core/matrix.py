import yaml
from typing import Optional, Dict

from .config import get_matrix_path
from .loop_guard import LoopState

class Matrix:
    def __init__(self, path: str):
        matrix_path = get_matrix_path(path)
        try:
            with open(matrix_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except FileNotFoundError as e:
            raise FileNotFoundError(
                f"Matrix file not found: {path}\n"
                f"Resolved to: {matrix_path}\n"
                f"Original error: {e}"
            ) from e
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in matrix file {path}: {e}") from e
        
        if not data or "version" not in data:
            raise ValueError(f"Invalid matrix file {path}: missing 'version' field")
        self.version = data["version"]
        self.defaults = data.get("defaults", {})
        self.rules = data.get("rules", [])
        self.thresholds = data.get("confidence_thresholds", {})
        self.type_upgrade_rules = data.get("type_upgrade_rules", [])
        # Task E: Load policy configurations
        self.missing_evidence_policy = data.get("missing_evidence_policy", {})
        self.conflict_resolution = data.get("conflict_resolution", {})
        # Store full data for access in gate
        self.data = data

    def get_default(self, resp_type: str) -> str:
        return self.defaults.get(resp_type, "")

    def match_rule(self, resp_type: str, action_type: str, risk_level: str) -> Optional[dict]:
        for rule in self.rules:
            match = rule.get("match", {})
            match_risk = match.get("risk_level")
            match_types = match.get("action_types", [])

            if match_risk and match_risk != risk_level:
                continue
            if match_types and action_type not in match_types:
                continue

            return rule
        return None

    def get_low_threshold(self) -> float:
        return self.thresholds.get("low", 0.6)

_matrices: dict[str, Matrix] = {}

def load_matrix(path: str) -> Matrix:
    if path not in _matrices:
        _matrices[path] = Matrix(path)
    return _matrices[path]


# Phase D: Minimal, repo-agnostic profile → matrix resolver (L1 ≤ 20 行)
# NOTE:
# - Keys are opaque profile strings carried via structured_input["profile"]
# - Values are matrix paths understood by existing load_matrix()
_PROFILE_MATRIX_MAP: Dict[str, str] = {
    # Demo-only profile used in examples/pr_gate_ai_review_loop/*
    "pr_review_loop": "matrices/pr_loop_demo.yaml",
}


def resolve_matrix_path(profile: Optional[str], default_path: str) -> str:
    """
    Resolve matrix path based on an optional profile string.

    Rules:
    - If profile is None/unknown → fallback to default_path (backward compatible)
    - If profile is known → return mapped matrix path
    """
    if not profile:
        return default_path
    return _PROFILE_MATRIX_MAP.get(profile, default_path)


def resolve_effective_matrix_path_for_loop(
    loop_state: Optional[LoopState],
    matrix: Matrix,
    base_path: str,
) -> str:
    """
    Pure function: resolve effective matrix path from loop_policy + loop_state.

    Rules (priority order):
    1. If loop_state is None or matrix has no loop_policy → return base_path
    2. If round_index >= max_rounds and churn_matrix_path present → return churn_matrix_path
    3. If nit_only_streak >= benign_streak_threshold and converged_matrix_path present → return converged_matrix_path
    4. Else → return base_path

    Paths in loop_policy are repo-root-relative (same as get_matrix_path).
    No side effects, no I/O, no trace/log.
    """
    if loop_state is None:
        return base_path

    policy = matrix.data.get("loop_policy")
    if not policy or not isinstance(policy, dict):
        return base_path

    max_rounds = policy.get("max_rounds")
    churn_path = policy.get("churn_matrix_path")
    if max_rounds is not None and churn_path and loop_state.round_index >= max_rounds:
        return churn_path

    threshold = policy.get("benign_streak_threshold")
    converged_path = policy.get("converged_matrix_path")
    if threshold is not None and converged_path and loop_state.nit_only_streak >= threshold:
        return converged_path

    return base_path
