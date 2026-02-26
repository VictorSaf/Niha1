from app.routing.evaluator import evaluate_fallback
from app.routing.policy_engine import PolicyContext


def test_fallback_escalates_on_low_confidence() -> None:
    context = PolicyContext(task_type="analysis", confidence_score=0.5)

    result = evaluate_fallback(context, timeout_threshold_seconds=45, confidence_threshold=0.7)

    assert result.escalate_to_cloud is True
    assert result.reason == "low-confidence"


def test_fallback_blocks_escalation_for_sensitive_data() -> None:
    context = PolicyContext(
        task_type="analysis",
        confidence_score=0.5,
        sensitivity_level="restricted",
    )

    result = evaluate_fallback(context, timeout_threshold_seconds=45, confidence_threshold=0.7)

    assert result.escalate_to_cloud is False
    assert result.reason == "sensitive-data-local-only"
