from typing import Protocol

from app.clients.gpt import GPTClassifier
from app.clients.jev import LiveJev, MockJev
from app.config import Settings
from app.models import AgentResponse, Classification, Decision, Route
from app.tools import execute_tool


class PrimaryClassifier(Protocol):
    def classify(self, message: str) -> Classification: ...


class FallbackClassifier(Protocol):
    def classify(self, message: str) -> Route: ...


class Agent:
    def __init__(
        self,
        settings: Settings,
        primary: PrimaryClassifier,
        fallback: FallbackClassifier | None = None,
    ):
        self.settings = settings
        self.primary = primary
        self.fallback = fallback

    def run(self, message: str) -> AgentResponse:
        classification = None
        route: Route | str = "human_review"
        source, reason = "human_review", "primary_error"
        try:
            classification = Classification.model_validate(self.primary.classify(message))
        except Exception:
            # Never return provider errors, credentials, or the original message.
            pass
        if classification is not None:
            if classification.confidence >= self.settings.high_confidence:
                route = classification.route
                source = "mock_jev" if self.settings.jev_mode == "mock" else "jev"
                reason = "high_confidence"
            elif classification.confidence < self.settings.low_confidence:
                reason = "low_confidence"
            elif self.fallback is None:
                reason = "fallback_not_configured"
            else:
                try:
                    route = Route(self.fallback.classify(message))
                    source, reason = "gpt_fallback", "fallback_classified"
                except Exception:
                    route = "human_review"
                    reason = "fallback_error"
        return AgentResponse(
            decision=Decision(route=route, source=source, reason=reason),
            jev_mode=self.settings.jev_mode,
            jev=classification,
            action=execute_tool(route),
        )


def build_agent(settings: Settings) -> Agent:
    primary = MockJev() if settings.jev_mode == "mock" else LiveJev(settings)
    fallback = (
        GPTClassifier(settings)
        if settings.openai_model and settings.openai_secret_version
        else None
    )
    return Agent(settings, primary, fallback)
