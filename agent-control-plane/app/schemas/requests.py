from pydantic import BaseModel, Field


class PolicyTestRequest(BaseModel):
    task_type: str = Field(min_length=1)
    requires_tool_calling: bool = False
    requires_json: bool = False
    sensitivity_level: str = "internal"


class RunAgentRequest(BaseModel):
    project_id: str = Field(min_length=1)
    task_type: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    context: str | None = None
    requires_tool_calling: bool = False
    requires_json: bool = False
    sensitivity_level: str = "internal"
    timeout_seconds: int | None = None
    confidence_score: float | None = None
    structured_output_valid: bool = True
    dry_run: bool = False
