from __future__ import annotations

import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import sys
from typing import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

# pytest 실행 환경에 따라 프로젝트 루트가 sys.path에 없을 수 있어 보정한다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PB.api.dependencies import get_query_orchestrator_service
from PB.app import app
from PB.constant.scenarios import get_scenario_spec
from PB.core.llm_caller import LLMClassifierCaller, OpenAIClassifierCaller, parse_llm_classification_response
from PB.core.mcp_caller import StubMCPCaller
from PB.services.intent_classifier import IntentClassifierService
from PB.services.query_orchestrator import QueryOrchestratorService


def _build_orchestrator(
    *,
    scenario_id: int,
    mcp_caller,
    classification_enabled: bool = False,
    llm_server_url: str = "",
    llm_model_name: str = "test-model",
) -> QueryOrchestratorService:
    classifier = IntentClassifierService(
        llm_caller=LLMClassifierCaller(
            server_url=llm_server_url,
            model_name=llm_model_name,
            default_scenario_id=scenario_id,
        ),
        default_scenario_id=scenario_id,
        classification_enabled=classification_enabled,
    )
    return QueryOrchestratorService(
        classifier=classifier,
        mcp_caller=mcp_caller,
    )


@contextmanager
def _override_orchestrator(orchestrator: QueryOrchestratorService) -> Iterator[TestClient]:
    app.dependency_overrides[get_query_orchestrator_service] = lambda: orchestrator
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def test_query_endpoint_stub_flow_returns_stubbed_payload() -> None:
    orchestrator = _build_orchestrator(
        scenario_id=19,
        mcp_caller=StubMCPCaller(interface_ready=False, stub_mode=True),
    )

    with _override_orchestrator(orchestrator) as client:
        response = client.post(
            "/api/v1/query",
            json={"user_input": "안녕?"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["classification"]["scenario_id"] == 19
    assert data["classification"]["route_key"] == "general_chat"
    assert data["mcp"]["payload"]["status"] == "stubbed"
    assert data["mcp"]["payload"]["route_key"] == "general_chat"


def test_query_endpoint_scenario2_stub_mode_returns_stubbed_payload() -> None:
    orchestrator = _build_orchestrator(
        scenario_id=2,
        mcp_caller=StubMCPCaller(interface_ready=False, stub_mode=True),
    )

    with _override_orchestrator(orchestrator) as client:
        response = client.post(
            "/api/v1/query",
            json={"user_input": "미수금 알려줘"},
        )

    assert response.status_code == 200
    data = response.json()

    assert data["classification"]["scenario_id"] == 2
    assert data["classification"]["route_key"] == "receivables"
    assert data["mcp"]["payload"]["status"] == "stubbed"
    assert data["mcp"]["payload"]["mcp_tool_name"] == "getUnsettledAmountTool"


@pytest.mark.parametrize(
    ("scenario_id", "tool_name"),
    [
        (1, "getAcctRightsStatusTool"),
        (2, "getUnsettledAmountTool"),
        (3, "getCollateralShortageTool"),
        (5, "getAutoTransferErrorTool"),
        (7, "getEventStatusTool"),
        (8, "getTransferFeeCouponTool"),
        (10, "getImportantNoticeTool"),
        (12, "getMarketScheduleTool"),
        (13, "getInvestmentPlusTool"),
        (14, "getExchangeRateTool"),
        (15, "getSectorinfoTool"),
        (16, "getYoutubeTool"),
        (17, "getBranchFinderTool"),
        (18, "getWeatherTool"),
        (19, "commonChatTool"),
    ],
)
def test_stub_mcp_builds_mock_request_response_for_x_scenarios(
    scenario_id: int,
    tool_name: str,
) -> None:
    caller = StubMCPCaller(interface_ready=True, stub_mode=True)
    scenario = get_scenario_spec(scenario_id)

    result = asyncio.run(
        caller.invoke(
            scenario=scenario,
            user_input="목업 응답 테스트",
            context={"request_id": "req-test"},
        )
    )

    assert result.status == "stubbed"
    assert result.tool_supported is True
    assert result.mcp_tool_name == tool_name
    assert result.request_payload is not None
    assert result.request_payload["method"] == "tools/call"
    assert result.request_payload["params"]["name"] == tool_name
    assert result.response is not None
    assert result.response["result"]["_meta"]["toolName"] == tool_name
    assert result.structured_content is not None
    assert result.content
    assert isinstance(result.content_text_json, dict)


def test_stub_mcp_returns_not_supported_for_o_scenario() -> None:
    caller = StubMCPCaller(interface_ready=True, stub_mode=True)
    # 시나리오 4 = IF-SEC-API-006 (툴 단계 O, 현재 연동 범위 제외)
    scenario = get_scenario_spec(4)

    result = asyncio.run(
        caller.invoke(
            scenario=scenario,
            user_input="미수동결 상태 알려줘",
            context={"request_id": "req-o-scenario"},
        )
    )

    assert result.status == "stubbed"
    assert result.tool_supported is False
    assert result.request_payload is None
    assert result.response is None


def test_query_endpoint_classifier_model_override_uses_selected_chatgpt_model(monkeypatch) -> None:
    captured: dict = {}

    async def fake_llm_post_json(url: str, *, headers=None, json_data=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json_data
        request = httpx.Request("POST", url)
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": "19",
                    }
                }
            ]
        }
        return httpx.Response(
            200,
            request=request,
            content=json.dumps(response_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

    monkeypatch.setattr("PB.core.llm_caller.post_json", fake_llm_post_json)

    orchestrator = _build_orchestrator(
        scenario_id=19,
        mcp_caller=StubMCPCaller(interface_ready=False, stub_mode=True),
        classification_enabled=True,
        llm_server_url="http://litellm.local/v1/chat/completions",
        llm_model_name="fallback-model",
    )

    with _override_orchestrator(orchestrator) as client:
        response = client.post(
            "/api/v1/query",
            json={
                "user_input": "질문 분류 테스트",
                "classifier": {
                    "provider": "chatgpt",
                    "modelName": "gpt-4o-mini",
                },
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["classification"]["scenario_id"] == 19
    assert data["mcp"]["payload"]["status"] == "stubbed"

    # 사용자 선택 classifier.modelName 이 LLM 분류 요청 payload.model 로 반영되어야 한다.
    assert captured["url"] == "http://litellm.local/v1/chat/completions"
    assert captured["json"]["model"] == "gpt-4o-mini"


def test_parse_llm_classification_response_extracts_scenario_id() -> None:
    """공유 파서 parse_llm_classification_response가 정상적으로 시나리오 ID를 추출하는지 검증한다."""
    response_data = {
        "choices": [{"message": {"content": "5"}}],
    }
    scenario_id, raw_content, fallback_used = parse_llm_classification_response(response_data, 19)
    assert scenario_id == 5
    assert raw_content == "5"
    assert fallback_used is False


def test_parse_llm_classification_response_fallback_on_invalid() -> None:
    """파싱 불가능한 응답에서 폴백 시나리오 ID를 반환하는지 검증한다."""
    response_data = {
        "choices": [{"message": {"content": "I don't know"}}],
    }
    scenario_id, raw_content, fallback_used = parse_llm_classification_response(response_data, 19)
    assert scenario_id == 19
    assert fallback_used is True


def test_openai_classifier_caller_parses_scenario_id(monkeypatch) -> None:
    """OpenAIClassifierCaller가 SDK 응답에서 시나리오 ID를 올바르게 파싱하는지 검증한다."""
    import types

    # openai.AsyncOpenAI를 mock으로 대체
    mock_module = types.ModuleType("openai")

    class _MockCompletion:
        def model_dump(self):
            return {"choices": [{"message": {"content": "7"}}]}

    class _MockCompletions:
        async def create(self, **kwargs):
            return _MockCompletion()

    class _MockChat:
        def __init__(self):
            self.completions = _MockCompletions()

    class MockAsyncOpenAI:
        def __init__(self, **kwargs):
            self.chat = _MockChat()

    mock_module.AsyncOpenAI = MockAsyncOpenAI
    monkeypatch.setitem(sys.modules, "openai", mock_module)

    caller = OpenAIClassifierCaller(
        model_name="gpt-4o-mini",
        api_key="sk-test",
        default_scenario_id=19,
    )

    result = asyncio.run(caller.classify_intent("테스트 질문"))
    assert result == 7
