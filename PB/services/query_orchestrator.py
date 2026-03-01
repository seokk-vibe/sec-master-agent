"""
질의 오케스트레이터 서비스.

사용자 질의 한 건의 전체 처리 파이프라인을 조율한다.
  1) IntentClassifierService로 의도(시나리오) 분류
  2) 시나리오 ID → ScenarioSpec 조회
  3) MCP 클라이언트로 해당 도구 호출
  4) 결과를 QueryOrchestratorResult로 묶어 반환
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from PB.constant.scenarios import ScenarioSpec, get_scenario_spec
from PB.core.mcp_caller import MCPCallerProtocol
from PB.dto.base import FrozenStrictModel
from PB.dto.mcp_tool_schemas import MCPInvokeResultOut
from PB.services.intent_classifier import IntentClassifierService


class QueryOrchestratorResult(FrozenStrictModel):
    """오케스트레이터의 최종 반환 값. 분류된 시나리오와 MCP 호출 결과를 함께 담는다."""

    scenario: ScenarioSpec       # 분류된 시나리오 정보 (도구 이름, 설명 등)
    mcp_result: MCPInvokeResultOut  # MCP 도구 호출 결과 (응답 데이터)


class QueryOrchestratorService:
    """질의 처리 파이프라인을 조율하는 서비스.

    classifier로 의도를 분류한 뒤, 해당 시나리오의 MCP 도구를 호출하고
    결과를 하나의 DTO로 묶어 반환한다.
    """

    def __init__(
        self,
        classifier: IntentClassifierService,
        mcp_caller: MCPCallerProtocol,
    ) -> None:
        self._classifier = classifier   # 의도 분류 서비스 (LLM 기반)
        self._mcp_caller = mcp_caller    # MCP 도구 호출자 (Stub 또는 실제)

    async def handle_query(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> QueryOrchestratorResult:
        """사용자 질의를 받아 분류 → 시나리오 조회 → MCP 호출 → 결과 반환까지 수행한다."""
        # 1단계: LLM으로 사용자 질의를 19개 시나리오 중 하나로 분류
        scenario_id = await self._classifier.classify(user_input=user_input, context=context)

        # 2단계: 시나리오 ID로 ScenarioSpec(도구 이름·설명 등) 조회
        scenario = get_scenario_spec(scenario_id)

        # 3단계: 해당 시나리오의 MCP 도구를 JSON-RPC로 호출
        mcp_result = await self._mcp_caller.invoke(
            scenario=scenario,
            user_input=user_input,
            context=context,
        )

        return QueryOrchestratorResult(scenario=scenario, mcp_result=mcp_result)
