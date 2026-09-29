from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.agent import Agent, build_agent
from app.clients.gpt import GPTClassifier
from app.clients.jev import LiveJev
from app.config import Settings
from app.main import create_app
from app.models import Classification, Route


def classified(confidence=0.9):
    return Classification(
        route=Route.AWS,
        confidence=confidence,
        probabilities={"aws": 0.9, "snowflake": 0.04, "datadog": 0.04, "general": 0.02},
    )


@pytest.mark.parametrize(
    "confidence,source,reason,calls",
    [
        (0.85, "mock_jev", "high_confidence", 0),
        (0.8499, "gpt_fallback", "fallback_classified", 1),
        (0.55, "gpt_fallback", "fallback_classified", 1),
        (0.5499, "human_review", "low_confidence", 0),
    ],
)
def test_threshold_boundaries(confidence, source, reason, calls):
    primary = Mock(classify=Mock(return_value=classified(confidence)))
    fallback = Mock(classify=Mock(return_value=Route.DATADOG))
    result = Agent(Settings(), primary, fallback).run("test")
    assert result.decision.source == source
    assert result.decision.reason == reason
    assert fallback.classify.call_count == calls
    expected = (
        "datadog_tool" if calls else "human_review" if source == "human_review" else "aws_tool"
    )
    assert result.action.tool == expected
    assert result.action.simulated


def test_missing_fallback_does_not_require_keys():
    result = build_agent(Settings()).run("AthenaでS3のデータを検索したい")
    assert result.decision.route == "human_review"
    assert result.decision.reason == "fallback_not_configured"


@pytest.mark.parametrize("stage", ["primary", "fallback"])
def test_provider_errors_are_not_exposed(stage):
    primary = Mock(classify=Mock(return_value=classified(0.7)))
    fallback = Mock(classify=Mock(return_value=Route.AWS))
    target = primary if stage == "primary" else fallback
    target.classify.side_effect = RuntimeError("SECRET_PROVIDER_TOKEN confidential-message")
    result = Agent(Settings(), primary, fallback).run("confidential-message")
    assert result.decision.route == "human_review"
    assert result.decision.reason == f"{stage}_error"
    assert "SECRET_PROVIDER_TOKEN" not in result.model_dump_json()
    assert "confidential-message" not in result.model_dump_json()


@pytest.mark.parametrize("stage", ["primary", "fallback"])
def test_invalid_provider_route_does_not_execute_tool(stage):
    primary = Mock(classify=Mock(return_value=classified(0.7)))
    fallback = Mock(classify=Mock(return_value=Route.AWS))
    if stage == "primary":
        primary.classify.return_value = {
            "route": "delete_database",
            "confidence": 1,
            "probabilities": {},
        }
    else:
        fallback.classify.return_value = "delete_database"
    result = Agent(Settings(), primary, fallback).run("test")
    assert result.decision.reason == f"{stage}_error"
    assert result.action.tool == "human_review"


@pytest.mark.parametrize(
    "message,expected",
    [
        ("AWS S3 RDS Athena IAMの相談", "aws"),
        ("Snowflake Warehouse Roleの相談", "snowflake"),
        ("Datadog Monitor Metric Alertの相談", "datadog"),
        ("こんにちは", "general"),
        ("I am William", "general"),
    ],
)
def test_mock_dispatch(message, expected):
    result = build_agent(Settings()).run(message)
    assert result.decision.route == expected
    assert result.decision.source == "mock_jev"
    assert result.action.status == "simulated"


def test_ambiguous_mock_requires_review():
    result = build_agent(Settings()).run("AWSとSnowflakeとDatadogの相談")
    assert result.decision.reason == "low_confidence"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "  \n"},
        {"message": "a" * 4001},
        {"message": 123},
        {"message": "AWS", "command": "delete"},
    ],
)
def test_invalid_http_input(payload):
    with TestClient(create_app(Settings())) as client:
        assert client.post("/agent", json=payload).status_code == 422


def test_http_health_docs_and_agent():
    with TestClient(create_app(Settings())) as client:
        assert client.get("/health").json() == {
            "status": "ok",
            "jev_mode": "mock",
            "gpt_fallback_enabled": False,
            "tools_mode": "dummy",
        }
        assert client.get("/docs").status_code == 200
        result = client.post("/agent", json={"message": "AWS S3 RDS Athena IAMの相談"})
        assert result.status_code == 200
        assert result.json()["action"]["tool"] == "aws_tool"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"high_confidence": 0.5},
        {"low_confidence": -0.1},
        {"high_confidence": 1.1},
        {"jev_mode": "invalid"},
        {"timeout_seconds": float("nan")},
    ],
)
def test_invalid_settings(kwargs):
    with pytest.raises(ValueError):
        Settings(**kwargs)


def test_live_jev_adapter_uses_official_sdk_contract(monkeypatch):
    import typesafe_sdk

    client = Mock()
    client.system_one.return_value = SimpleNamespace(
        choices={
            "route": SimpleNamespace(
                choice="aws", confidence=0.9, probabilities=classified().probabilities
            )
        }
    )
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=manager)
    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", factory)
    monkeypatch.setattr("app.clients.jev.load_api_key", lambda _: "test-key")
    result = LiveJev(Settings(jev_mode="live")).classify("AWS")
    assert result.route == Route.AWS
    question = client.system_one.call_args.kwargs["questions"]["route"]
    assert isinstance(question, typesafe_sdk.Choice)
    assert set(question.criteria) == {r.value for r in Route}
    assert factory.call_args.kwargs["timeout"] == 20


@pytest.mark.parametrize("parsed,raises", [(None, True), (Route.SNOWFLAKE, False)])
def test_gpt_structured_output_and_refusal(monkeypatch, parsed, raises):
    import openai

    client = Mock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(route=parsed) if parsed else None
    )
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(openai, "OpenAI", Mock(return_value=manager))
    monkeypatch.setattr("app.clients.gpt.load_api_key", lambda _: "test-key")
    adapter = GPTClassifier(Settings(openai_model="configured-model"))
    if raises:
        with pytest.raises(ValueError):
            adapter.classify("test")
    else:
        assert adapter.classify("test") == Route.SNOWFLAKE
    assert client.responses.parse.call_args.kwargs["store"] is False


def test_invalid_probabilities():
    with pytest.raises(ValueError):
        Classification(
            route="aws",
            confidence=0.9,
            probabilities={
                "aws": float("nan"),
                "snowflake": 0.04,
                "datadog": 0.04,
                "general": 0.02,
            },
        )
