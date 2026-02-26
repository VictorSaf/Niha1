from dataclasses import dataclass

from app.routing.policy_engine import PolicyContext

SENSITIVE_LEVELS = {"restricted", "secret"}


@dataclass
class FallbackDecision:
    escalate_to_cloud: bool
    reason: str


def evaluate_fallback(
    context: PolicyContext,
    timeout_threshold_seconds: int,
    confidence_threshold: float,
) -> FallbackDecision:
    if context.sensitivity_level in SENSITIVE_LEVELS:
        return FallbackDecision(False, "sensitive-data-local-only")

    if context.structured_output_valid is False:
        return FallbackDecision(True, "invalid-structured-output")

    if context.timeout_seconds is not None and context.timeout_seconds > timeout_threshold_seconds:
        return FallbackDecision(True, "local-timeout")

    if context.confidence_score is not None and context.confidence_score < confidence_threshold:
        return FallbackDecision(True, "low-confidence")

    return FallbackDecision(False, "local-success")
