import yaml
from ..core.config import get_config_path

with open(get_config_path("risk_keywords.yaml"), encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f)

DISCLAIMER = CONFIG["disclaimer_templates"]["default"]

def generate_with_disclaimer(content: str) -> str:
    return f"{content}\n\n{DISCLAIMER}"
