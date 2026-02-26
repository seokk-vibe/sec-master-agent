from __future__ import annotations

from typing import Any, Dict, Optional

from PB.constant.scenarios import ScenarioSpec, get_scenario_spec
from PB.core.mcp_client import MCPClientProtocol
from PB.dto.base import FrozenStrictModel
from PB.dto.mcp_tool_schemas import MCPInvokeResultOut
from PB.services.intent_classifier import IntentClassifierService


class QueryOrchestratorResult(FrozenStrictModel):
    scenario: ScenarioSpec
    mcp_result: MCPInvokeResultOut


class QueryOrchestratorService:
    def __init__(
        self,
        classifier: IntentClassifierService,
        mcp_client: MCPClientProtocol,
    ) -> None:
        self._classifier = classifier
        self._mcp_client = mcp_client

    async def handle_query(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> QueryOrchestratorResult:
        scenario_id = await self._classifier.classify(user_input=user_input, context=context)
        scenario = get_scenario_spec(scenario_id)
        mcp_result = await self._mcp_client.invoke(
            scenario=scenario,
            user_input=user_input,
            context=context,
        )
        return QueryOrchestratorResult(scenario=scenario, mcp_result=mcp_result)
