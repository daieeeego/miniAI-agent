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
from app.tools import execute_tool, parse_pitch_question, pitch_count

PROBABILITIES = {
    "pitch_count": 0.9,
    "game_rules": 0.02,
    "substitution": 0.02,
    "scoring": 0.02,
    "play_rules": 0.02,
    "general": 0.02,
}


def classified(confidence=0.9):
    return Classification(
        route=Route.PITCH_COUNT,
        confidence=confidence,
        probabilities=PROBABILITIES,
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
    fallback = Mock(classify=Mock(return_value=Route.GAME_RULES))
    result = Agent(Settings(), primary, fallback).run("test")
    assert result.decision.source == source
    assert result.decision.reason == reason
    assert fallback.classify.call_count == calls
    expected = (
        "game_rules" if calls else "human_review" if source == "human_review" else "pitch_count"
    )
    assert result.action.tool == expected


def test_missing_fallback_does_not_require_keys():
    result = build_agent(Settings()).run("インフィールドフライの条件は？")
    assert result.decision.route == "human_review"
    assert result.decision.reason == "fallback_not_configured"


@pytest.mark.parametrize("stage", ["primary", "fallback"])
def test_provider_errors_are_not_exposed(stage):
    primary = Mock(classify=Mock(return_value=classified(0.7)))
    fallback = Mock(classify=Mock(return_value=Route.GAME_RULES))
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
    fallback = Mock(classify=Mock(return_value=Route.GAME_RULES))
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
        ("4年生のピッチャーが今日45球投げました。あと何球？", "pitch_count"),
        ("タイブレークと延長のルールは？", "game_rules"),
        ("一度交代した選手は再出場できる？", "substitution"),
        ("スコアブックの記号の書き方", "scoring"),
        ("こんにちは", "general"),
    ],
)
def test_mock_dispatch(message, expected):
    result = build_agent(Settings()).run(message)
    assert result.decision.route == expected
    assert result.decision.source == "mock_jev"
    assert result.action.tool == expected


def test_ambiguous_mock_requires_review():
    result = build_agent(Settings()).run("ボークは球数に入る？")
    assert result.decision.reason == "low_confidence"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"message": ""},
        {"message": "  \n"},
        {"message": "a" * 4001},
        {"message": 123},
        {"message": "球数", "command": "delete"},
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
            "scope": "全軟連 学童部",
        }
        assert client.get("/docs").status_code == 200
        message = "5年生の投手が今日70球投げた。まだ投げられる？"
        result = client.post("/agent", json={"message": message})
        assert result.status_code == 200
        assert result.json()["action"]["tool"] == "pitch_count"
        assert result.json()["action"]["sources"]


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
                choice="pitch_count", confidence=0.9, probabilities=PROBABILITIES
            )
        }
    )
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=manager)
    monkeypatch.setattr(typesafe_sdk, "TypeSafeClient", factory)
    monkeypatch.setattr("app.clients.jev.load_api_key", lambda _: "test-key")
    result = LiveJev(Settings(jev_mode="live")).classify("球数")
    assert result.route == Route.PITCH_COUNT
    question = client.system_one.call_args.kwargs["questions"]["route"]
    assert isinstance(question, typesafe_sdk.Choice)
    assert set(question.criteria) == {r.value for r in Route}
    assert factory.call_args.kwargs["timeout"] == 20


@pytest.mark.parametrize("parsed,raises", [(None, True), (Route.SCORING, False)])
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
        assert adapter.classify("test") == Route.SCORING
    assert client.responses.parse.call_args.kwargs["store"] is False


def test_invalid_probabilities():
    with pytest.raises(ValueError):
        Classification(
            route="pitch_count",
            confidence=0.9,
            probabilities={**PROBABILITIES, "pitch_count": float("nan")},
        )


def test_gpt_prompt_lists_every_route(monkeypatch):
    import openai

    client = Mock()
    client.responses.parse.return_value = SimpleNamespace(
        output_parsed=SimpleNamespace(route=Route.GENERAL)
    )
    manager = Mock()
    manager.__enter__ = Mock(return_value=client)
    manager.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(openai, "OpenAI", Mock(return_value=manager))
    monkeypatch.setattr("app.clients.gpt.load_api_key", lambda _: "test-key")
    GPTClassifier(Settings(openai_model="configured-model")).classify("test")
    prompt = client.responses.parse.call_args.kwargs["input"][0]["content"]
    assert all(route.value in prompt for route in Route)


@pytest.mark.parametrize(
    "message,expected",
    [
        ("4年生が今日45球投げた", (4, 45, None)),
        ("小６で今週150球、今日30球", (6, 30, 150)),
        ("５年生は何球まで？", (5, None, None)),
        ("今日20球", (None, 20, None)),
        ("2026年の規定で4年生が今日30球", (4, 30, None)),
        ("今日1000球", (None, None, None)),
    ],
)
def test_parse_pitch_question(message, expected):
    assert parse_pitch_question(message) == expected


@pytest.mark.parametrize(
    "message,included",
    [
        ("4年生が今日45球投げた", ["1日60球", "今日あと15球"]),
        ("5年生が今日45球投げた", ["1日70球", "今日あと25球"]),
        ("6年生が今日70球投げた", ["今日あと0球", "上限に達しています"]),
        ("4年生で今週170球、今日30球", ["今日あと30球", "今週あと10球", "少ない方"]),
        ("何球まで投げられる？", ["1日70球", "1日60球"]),
        ("今日20球投げた", ["学年がわからない"]),
    ],
)
def test_pitch_count_answers(message, included):
    result = pitch_count(message)
    assert result.status == "answered"
    assert len(result.sources) == 2
    for text in included:
        assert text in result.message


@pytest.mark.parametrize("route", [r for r in Route if r != Route.PITCH_COUNT])
def test_fixed_answers_never_guess_tournament_rules(route):
    result = execute_tool(route, "test")
    assert result.status in {"check_tournament_rules", "not_covered"}
    assert result.tool == route.value
