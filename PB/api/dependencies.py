"""
DI(Dependency Injection) 팩토리 모듈.

FastAPI의 Depends()에서 사용할 싱글턴 객체들을 생성·관리한다.
모든 팩토리 함수는 @lru_cache로 감싸져 있어 앱 수명 동안 단 한 번만 인스턴스를 생성한다.

의존성 그래프:
  Settings
    ├─ LLMClassifierCaller (llm_caller)
    │     └─ IntentClassifierService
    └─ MCPClient (Stub 또는 JsonRpc)
          └─ QueryOrchestratorService  ← classifier + mcp_caller 조합
"""
from __future__ import annotations

from functools import lru_cache

from PB.core.llm_caller import (
    LLMClassifierCaller,
    LLMClassifierCallerProtocol,
    OpenAIClassifierCaller,
)
from PB.core.mcp_caller import JsonRpcMCPCaller, MCPCallerProtocol, StubMCPCaller
from PB.core.settings import Settings, load_settings
from PB.services.intent_classifier import IntentClassifierService
from PB.services.query_orchestrator import QueryOrchestratorService


@lru_cache
def get_settings() -> Settings:
    """환경변수로부터 Settings 객체를 로드하여 싱글턴으로 캐싱한다."""
    return load_settings()


@lru_cache
def get_llm_classifier_caller() -> LLMClassifierCallerProtocol:
    """LLM 호출을 담당하는 클라이언트를 생성한다.

    llm_caller_type에 따라 구현체를 선택한다:
      - "openai" → OpenAIClassifierCaller (openai SDK, 외부망 개발용)
      - 그 외    → LLMClassifierCaller    (httpx/post_json, LiteLLM 프록시)
    """
    settings = get_settings()
    if settings.llm_caller_type == "openai":
        return OpenAIClassifierCaller(
            model_name=settings.llm_model_name,
            api_key=settings.openai_api_key,
            timeout=settings.llm_timeout_seconds,
            default_scenario_id=settings.default_scenario_id,
        )
    return LLMClassifierCaller(
        server_url=settings.litellm_server_url or settings.llm_server_url,
        model_name=settings.llm_model_name,
        timeout=settings.llm_timeout_seconds,
        default_scenario_id=settings.default_scenario_id,
    )


@lru_cache
def get_mcp_caller() -> MCPCallerProtocol:
    """MCP 클라이언트를 생성한다.

    MCP_STUB_MODE=true  → StubMCPCaller  (외부 MCP 서버 없이 로컬 개발용)
    MCP_STUB_MODE=false → JsonRpcMCPCaller (실제 JSON-RPC 호출)
    """
    settings = get_settings()
    if settings.mcp_stub_mode:
        return StubMCPCaller(interface_ready=False, stub_mode=True)
    return JsonRpcMCPCaller(
        server_url=settings.mcp_server_url,
        timeout=settings.mcp_timeout_seconds,
    )


@lru_cache
def get_intent_classifier_service() -> IntentClassifierService:
    """사용자 질의를 19개 시나리오 중 하나로 분류하는 서비스를 생성한다.

    classification_enabled=false이면 LLM 호출 없이
    default_scenario_id(기본 19번, 일반 대화)를 즉시 반환한다.
    """
    settings = get_settings()
    return IntentClassifierService(
        llm_caller=get_llm_classifier_caller(),
        default_scenario_id=settings.default_scenario_id,
        classification_enabled=settings.intent_classification_enabled,
    )


@lru_cache
def get_query_orchestrator_service() -> QueryOrchestratorService:
    """질의 처리 전체 흐름을 조율하는 오케스트레이터 서비스를 생성한다.

    내부적으로 classifier(의도 분류) → scenario 조회 → MCP 호출 순서로 동작한다.
    """
    return QueryOrchestratorService(
        classifier=get_intent_classifier_service(),
        mcp_caller=get_mcp_caller(),
    )
