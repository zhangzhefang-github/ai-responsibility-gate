import yaml
from typing import Optional
from .config import get_matrix_path

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
