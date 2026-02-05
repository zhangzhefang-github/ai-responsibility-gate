from .models import ClassifierResult, ResponsibilityType

async def classify(text: str) -> ClassifierResult:
    operation_keywords = ["买", "卖", "操作", "执行", "交易"]
    is_operation = any(kw in text for kw in operation_keywords)

    if is_operation:
        return ClassifierResult(
            type=ResponsibilityType.EntitlementDecision,
            confidence=0.85,
            trigger_spans=["operation_keyword"]
        )

    return ClassifierResult(
        type=ResponsibilityType.Information,
        confidence=0.75,
        trigger_spans=["default"]
    )
