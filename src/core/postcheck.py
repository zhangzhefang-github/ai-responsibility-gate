import yaml
from .models import Explanation, PostcheckResult, PostcheckIssue
from .config import get_config_path

with open(get_config_path("risk_keywords.yaml"), encoding="utf-8") as f:
    RISK_CONFIG = yaml.safe_load(f)

GUARANTEE_KEYWORDS = RISK_CONFIG["guarantee_claim_keywords"]
DISCLAIMER = RISK_CONFIG["disclaimer_templates"]["default"]

def postcheck(text: str, requires_disclaimer: bool, is_input: bool) -> PostcheckResult:
    issues = []

    has_guarantee = any(kw in text for kw in GUARANTEE_KEYWORDS)
    if has_guarantee:
        issues.append(PostcheckIssue(
            code="GUARANTEE_KEYWORD_IN_TEXT",
            severity="critical",
            description="Guarantee keyword found in text"
        ))

    if not is_input and requires_disclaimer and DISCLAIMER not in text:
        issues.append(PostcheckIssue(
            code="MISSING_DISCLAIMER",
            severity="error",
            description="Disclaimer required but not found"
        ))

    return PostcheckResult(
        passed=len(issues) == 0,
        issues=issues
    )
