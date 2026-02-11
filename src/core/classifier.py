from .models import ClassifierResult, ResponsibilityType, GateContext


async def classify(ctx: GateContext) -> ClassifierResult:
    """
    Phase C: Classifier over GateContext instead of raw text.

    - Existing business path: still uses ctx.text and keyword heuristics.
    - Future scenarios (e.g., PR) can use ctx.structured_input or ctx.context
      without changing this signature.
    """
    text = ctx.text or ""

    # Existing business heuristic: detect \"operation\"-like intents.
    operation_keywords = ["买", "卖", "操作", "执行", "交易"]
    is_operation = any(kw in text for kw in operation_keywords)

    if is_operation:
        return ClassifierResult(
            type=ResponsibilityType.EntitlementDecision,
            confidence=0.85,
            trigger_spans=["operation_keyword"],
        )

    # Default: informational request.
    return ClassifierResult(
        type=ResponsibilityType.Information,
        confidence=0.75,
        trigger_spans=["default"],
    )
