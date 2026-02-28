from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sys
from typing import Iterator

import httpx
from fastapi.testclient import TestClient

# pytest 실행 환경에 따라 프로젝트 루트가 sys.path에 없을 수 있어 보정한다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PB.api.dependencies import get_query_orchestrator_service
from PB.app import app
from PB.core.llm_client import LLMClassifierClient
from PB.core.mcp_client import StubMCPClient
from PB.services.intent_classifier import IntentClassifierService
from PB.services.query_orchestrator import QueryOrchestratorService


def _build_orchestrator(
    *,
    scenario_id: int,
    mcp_client,
    classification_enabled: bool = False,
    llm_server_url: str = "",
    llm_model_name: str = "test-model",
) -> QueryOrchestratorService:
    classifier = IntentClassifierService(
        llm_client=LLMClassifierClient(
            server_url=llm_server_url,
            model_name=llm_model_name,
            default_scenario_id=scenario_id,
        ),
        default_scenario_id=scenario_id,
        classification_enabled=classification_enabled,
    )
    return QueryOrchestratorService(
        classifier=classifier,
        mcp_client=mcp_client,
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
        mcp_client=StubMCPClient(interface_ready=False, stub_mode=True),
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
        mcp_client=StubMCPClient(interface_ready=False, stub_mode=True),
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

    monkeypatch.setattr("PB.core.llm_client.post_json", fake_llm_post_json)

    orchestrator = _build_orchestrator(
        scenario_id=19,
        mcp_client=StubMCPClient(interface_ready=False, stub_mode=True),
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
