from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class PolicyTestResponse(BaseModel):
    selected_model: str
    escalate_to_cloud: bool
    reason: str


class ModelsResponse(BaseModel):
    models: dict[str, str]


class RunAgentResponse(BaseModel):
    selected_model: str
    provider: str
    dry_run: bool
    output: str | None = None
    reason: str
