from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.agent import Agent, build_agent
from app.config import Settings
from app.models import AgentRequest, AgentResponse


def create_app(settings: Settings | None = None, agent: Agent | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runner = agent or build_agent(settings)
    api = FastAPI(title="野球ルール ミニAIエージェント", version="0.2.0")

    @api.exception_handler(RequestValidationError)
    async def invalid_request(request, exc):
        # Default validation errors echo the supplied message. Omit input and context.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {key: error[key] for key in ("loc", "msg", "type")} for error in exc.errors()
                ]
            },
        )

    @api.get("/health")
    def health():
        # Liveness, not verification of external account access.
        return {
            "status": "ok",
            "jev_mode": settings.jev_mode,
            "gpt_fallback_enabled": runner.fallback is not None,
            "scope": "全軟連 学童部",
        }

    @api.post("/agent", response_model=AgentResponse)
    def classify(request: AgentRequest):
        return runner.run(request.message)

    return api


app = create_app()
