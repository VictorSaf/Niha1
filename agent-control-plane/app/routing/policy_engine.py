from dataclasses import dataclass


@dataclass
class PolicyContext:
    task_type: str
    requires_tool_calling: bool = False
    requires_json: bool = False
    sensitivity_level: str = "internal"
    timeout_seconds: int | None = None
    confidence_score: float | None = None
    structured_output_valid: bool = True


@dataclass
class RoutingDecision:
    selected_model: str
    escalate_to_cloud: bool
    reason: str


def route_model(context: PolicyContext) -> RoutingDecision:
    if context.requires_tool_calling and context.requires_json:
        return RoutingDecision(
            selected_model="tools-strict",
            escalate_to_cloud=False,
            reason="strict-structured-output",
        )

    if context.task_type == "coding":
        return RoutingDecision(
            selected_model="coder-main",
            escalate_to_cloud=False,
            reason="coding-task",
        )

    if context.task_type in {"quick_coding", "autocomplete"}:
        return RoutingDecision(
            selected_model="coder-fast",
            escalate_to_cloud=False,
            reason="low-latency-coding",
        )

    if context.task_type in {"debug_complex", "architecture", "hard_reasoning"}:
        return RoutingDecision(
            selected_model="reasoner",
            escalate_to_cloud=False,
            reason="reasoning-task",
        )

    return RoutingDecision(
        selected_model="qwen3-default",
        escalate_to_cloud=False,
        reason="default-route",
    )
