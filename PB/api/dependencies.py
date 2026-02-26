from __future__ import annotations

from functools import lru_cache

from PB.core.mcp_client import JsonRpcMCPClient, MCPClientProtocol, StubMCPClient
from PB.core.settings import Settings, load_settings
from PB.core.vllm_client import MasterAgentClient
from PB.services.intent_classifier import IntentClassifierService
from PB.services.query_orchestrator import QueryOrchestratorService


@lru_cache
def get_settings() -> Settings:
    return load_settings()


@lru_cache
def get_master_agent_client() -> MasterAgentClient:
    settings = get_settings()
    return MasterAgentClient(
        server_url=settings.litellm_server_url or settings.vllm_server_url,
        model_name=settings.vllm_model_name,
        timeout=settings.vllm_timeout_seconds,
        default_scenario_id=settings.default_scenario_id,
    )


@lru_cache
def get_mcp_client() -> MCPClientProtocol:
    settings = get_settings()
    if settings.mcp_stub_mode:
        return StubMCPClient(interface_ready=False, stub_mode=True)
    return JsonRpcMCPClient(
        server_url=settings.mcp_server_url,
        timeout=settings.mcp_timeout_seconds,
    )


def get_intent_classifier_service() -> IntentClassifierService:
    settings = get_settings()
    return IntentClassifierService(
        vllm_client=get_master_agent_client(),
        default_scenario_id=settings.default_scenario_id,
        classification_enabled=settings.intent_classification_enabled,
    )


def get_query_orchestrator_service() -> QueryOrchestratorService:
    return QueryOrchestratorService(
        classifier=get_intent_classifier_service(),
        mcp_client=get_mcp_client(),
    )
