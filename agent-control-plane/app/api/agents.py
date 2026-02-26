from fastapi import APIRouter, HTTPException

from app.config import settings
from app.agents.registry import DEFAULT_AGENT_MODELS
from app.providers.ollama_client import OllamaClient
from app.routing.policy_engine import PolicyContext, route_model
from app.routing.evaluator import evaluate_fallback
from app.schemas.requests import PolicyTestRequest, RunAgentRequest
from app.schemas.responses import ModelsResponse, PolicyTestResponse, RunAgentResponse

router = APIRouter(prefix="/v1/agents", tags=["agents"])


@router.post("/policies/test", response_model=PolicyTestResponse)
async def test_policy(payload: PolicyTestRequest) -> PolicyTestResponse:
    decision = route_model(
        PolicyContext(
            task_type=payload.task_type,
            requires_tool_calling=payload.requires_tool_calling,
            requires_json=payload.requires_json,
            sensitivity_level=payload.sensitivity_level,
        )
    )

    return PolicyTestResponse(
        selected_model=decision.selected_model,
        escalate_to_cloud=decision.escalate_to_cloud,
        reason=decision.reason,
    )


@router.get("/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    return ModelsResponse(models=DEFAULT_AGENT_MODELS)


@router.post("/run", response_model=RunAgentResponse)
async def run_agent(payload: RunAgentRequest) -> RunAgentResponse:
    context = PolicyContext(
        task_type=payload.task_type,
        requires_tool_calling=payload.requires_tool_calling,
        requires_json=payload.requires_json,
        sensitivity_level=payload.sensitivity_level,
        timeout_seconds=payload.timeout_seconds,
        confidence_score=payload.confidence_score,
        structured_output_valid=payload.structured_output_valid,
    )
    decision = route_model(context)
    fallback = evaluate_fallback(
        context=context,
        timeout_threshold_seconds=settings.fallback_timeout_seconds,
        confidence_threshold=settings.fallback_confidence_threshold,
    )

    selected_model = decision.selected_model
    if fallback.escalate_to_cloud:
        return RunAgentResponse(
            selected_model=selected_model,
            provider="cloud-fallback",
            dry_run=False,
            reason=fallback.reason,
        )

    if payload.dry_run:
        return RunAgentResponse(
            selected_model=selected_model,
            provider="ollama",
            dry_run=True,
            reason=decision.reason,
        )

    final_prompt = payload.prompt
    if payload.context:
        final_prompt = f"Context:\n{payload.context}\n\nTask:\n{payload.prompt}"

    client = OllamaClient()
    try:
        output = await client.generate(model=selected_model, prompt=final_prompt)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return RunAgentResponse(
        selected_model=selected_model,
        provider="ollama",
        dry_run=False,
        output=output,
        reason=decision.reason,
    )
