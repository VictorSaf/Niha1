from app.routing.policy_engine import PolicyContext, route_model


def test_route_model_uses_coder_for_coding_tasks() -> None:
    context = PolicyContext(task_type="coding")

    route = route_model(context)

    assert route.selected_model == "coder-main"
    assert route.escalate_to_cloud is False


def test_route_model_uses_tools_strict_for_json_tool_tasks() -> None:
    context = PolicyContext(
        task_type="analysis",
        requires_tool_calling=True,
        requires_json=True,
    )

    route = route_model(context)

    assert route.selected_model == "tools-strict"
