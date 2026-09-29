import math
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Route(str, Enum):
    AWS = "aws"
    SNOWFLAKE = "snowflake"
    DATADOG = "datadog"
    GENERAL = "general"


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must contain non-whitespace characters")
        return value.strip()


class Classification(BaseModel):
    route: Route
    confidence: float = Field(ge=0, le=1, allow_inf_nan=False)
    probabilities: dict[Route, float]

    @model_validator(mode="after")
    def valid_distribution(self):
        values = list(self.probabilities.values())
        if set(self.probabilities) != set(Route):
            raise ValueError("all four route probabilities are required")
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in values):
            raise ValueError("invalid probabilities")
        if not math.isclose(sum(values), 1, abs_tol=0.02):
            raise ValueError("probabilities must sum to one")
        return self


class GPTDecision(BaseModel):
    route: Route


class Decision(BaseModel):
    route: Route | str
    source: str
    reason: str


class ActionResult(BaseModel):
    tool: str
    status: str
    message: str
    simulated: bool = True


class AgentResponse(BaseModel):
    decision: Decision
    jev_mode: str
    jev: Classification | None
    action: ActionResult
