"""
Configuration path management.

Centralizes all file path resolution to avoid hardcoded relative paths
that depend on working directory.
"""
from pathlib import Path
import os

# Calculate project root: go up from src/core/config.py -> src -> project root
_PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Directory paths
CONFIG_DIR = _PROJECT_ROOT / "config"
MATRICES_DIR = _PROJECT_ROOT / "matrices"
TOOLS_DIR = _PROJECT_ROOT / "tools"
DATA_DIR = _PROJECT_ROOT / "data"

# Support environment variable override (for testing/deployment)
if os.getenv("AI_RESPONSIBILITY_GATE_CONFIG_DIR"):
    CONFIG_DIR = Path(os.getenv("AI_RESPONSIBILITY_GATE_CONFIG_DIR")).resolve()
if os.getenv("AI_RESPONSIBILITY_GATE_MATRICES_DIR"):
    MATRICES_DIR = Path(os.getenv("AI_RESPONSIBILITY_GATE_MATRICES_DIR")).resolve()

def get_config_path(filename: str) -> Path:
    """Get absolute path to a config file."""
    path = CONFIG_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {path}\n"
            f"Config directory: {CONFIG_DIR}\n"
            f"Project root: {_PROJECT_ROOT}"
        )
    return path

def get_matrix_path(filename: str) -> Path:
    """Get absolute path to a matrix file."""
    # Support both relative paths (like "matrices/v0.1.yaml") and filenames
    if "/" in filename or "\\" in filename:
        # Relative path from project root
        path = _PROJECT_ROOT / filename
    else:
        # Just filename, look in matrices directory
        path = MATRICES_DIR / filename
    
    if not path.exists():
        raise FileNotFoundError(
            f"Matrix file not found: {path}\n"
            f"Matrices directory: {MATRICES_DIR}\n"
            f"Project root: {_PROJECT_ROOT}"
        )
    return path

def get_tools_path(filename: str) -> Path:
    """Get absolute path to a tools catalog file."""
    path = TOOLS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Tools file not found: {path}\n"
            f"Tools directory: {TOOLS_DIR}\n"
            f"Project root: {_PROJECT_ROOT}"
        )
    return path

def get_project_root() -> Path:
    """Get the project root directory."""
    return _PROJECT_ROOT
