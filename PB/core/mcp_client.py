from __future__ import annotations

import json
from typing import Any, Dict, Optional, Protocol
from uuid import uuid4

import httpx
from pydantic import BaseModel, ValidationError

from PB.constant.scenarios import ScenarioSpec
from PB.core.mcp_adapters import (
    MCPToolAdapterProtocol,
    build_default_mcp_tool_adapters,
    get_tool_adapter,
)
from PB.core.requester import post_json
from PB.dto.mcp_tool_schemas import (
    MCPInvokeResultOut,
    JsonRpcToolCallParams,
    JsonRpcToolCallRequest,
    JsonRpcToolCallResponseOut,
)


class MCPClientProtocol(Protocol):
    async def invoke(
        self,
        scenario: ScenarioSpec,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPInvokeResultOut:
        ...


class StubMCPClient:
    """
    MCP 인터페이스 문서가 들어오기 전까지 사용할 스텁 구현.
    추후 실제 MCP request/response 규격에 맞춰 `invoke` 내부만 교체하면 된다.
    """

    def __init__(self, interface_ready: bool = False, stub_mode: bool = True) -> None:
        self.interface_ready = interface_ready
        self.stub_mode = stub_mode

    async def invoke(
        self,
        scenario: ScenarioSpec,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPInvokeResultOut:
        # TODO: MCP 인터페이스 문서 수신 후 실제 호출 로직 구현
        return MCPInvokeResultOut.for_scenario(
            scenario=scenario,
            status="stubbed" if self.stub_mode else "pending",
            interface_ready=self.interface_ready,
            tool_supported=bool(scenario.mcp_tool_name),
            user_input=user_input,
            context=context or {},
            next_action="replace StubMCPClient.invoke with actual MCP client call",
        )


class JsonRpcMCPClient:
    """
    MCP(JSON-RPC) 통신 클라이언트.

    현재 구현 범위:
    - `tools/call` 메서드 호출
    - if-sec-api-003 규격 기반 `params.name`, `params.arguments`
    - 시나리오 1번(getAcctRightsStatusTool) 실제 매핑
    """

    JSONRPC_VERSION = "2.0"
    TOOLS_CALL_METHOD = "tools/call"

    def __init__(
        self,
        server_url: str,
        timeout: float = 10.0,
        tool_adapters: Optional[Dict[str, MCPToolAdapterProtocol]] = None,
    ) -> None:
        self.server_url = server_url
        self.timeout = timeout
        self._headers = {"Content-Type": "application/json"}
        self._tool_adapters = tool_adapters or build_default_mcp_tool_adapters()

    async def invoke(
        self,
        scenario: ScenarioSpec,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPInvokeResultOut:
        ctx = context or {}

        if not scenario.mcp_tool_name:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="unsupported_scenario",
                interface_ready=True,
                tool_supported=False,
                mcp_tool_name=None,
                message="MCP tool mapping not registered for this scenario yet",
            )

        if not self.server_url:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="not_configured",
                interface_ready=True,
                tool_supported=True,
                message="MCP_SERVER_URL is empty",
            )

        arguments, validation_error = self._build_arguments_for_scenario(scenario, ctx)
        if validation_error is not None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_request_context",
                interface_ready=True,
                tool_supported=True,
                message=validation_error,
            )

        rpc_id = self._build_rpc_id(ctx)
        payload = self._build_request_payload(
            rpc_id=rpc_id,
            tool_name=scenario.mcp_tool_name,
            arguments=arguments,
        )

        try:
            response = await post_json(
                self.server_url,
                json_data=payload,
                headers=self._headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            response_data = response.json()
        except httpx.HTTPStatusError as exc:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="http_error",
                interface_ready=True,
                tool_supported=True,
                http_status_code=exc.response.status_code,
                message=str(exc),
                request_payload=payload,
            )
        except Exception as exc:  # pragma: no cover - 네트워크 의존
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="transport_error",
                interface_ready=True,
                tool_supported=True,
                message=str(exc),
                request_payload=payload,
            )

        return self._normalize_response(
            scenario=scenario,
            request_payload=payload,
            response_data=response_data,
        )

    def _build_rpc_id(self, context: Dict[str, Any]) -> str:
        request_id = context.get("request_id")
        if isinstance(request_id, str) and request_id.strip():
            return request_id
        return str(uuid4())

    def _build_arguments_for_scenario(
        self,
        scenario: ScenarioSpec,
        context: Dict[str, Any],
    ) -> tuple[Optional[BaseModel], Optional[str]]:
        if not scenario.mcp_tool_name:
            return None, "scenario.mcp_tool_name is required"

        adapter = get_tool_adapter(self._tool_adapters, scenario.mcp_tool_name)
        if adapter is None:
            return None, f"no request schema is registered for tool '{scenario.mcp_tool_name}'"

        try:
            return adapter.build_arguments(context), None
        except ValueError as exc:
            return None, str(exc)
        except ValidationError as exc:
            return None, self._format_validation_error(exc)

    def _build_request_payload(
        self,
        rpc_id: str,
        tool_name: Optional[str],
        arguments: BaseModel,
    ) -> Dict[str, Any]:
        payload_model = JsonRpcToolCallRequest(
            id=rpc_id,
            params=JsonRpcToolCallParams(
                name=tool_name or "",
                # 문서 표는 params 직하위로 설명하지만 request 예시는 arguments 중첩 구조이므로 예시를 따른다.
                arguments=arguments.model_dump(by_alias=True, exclude_none=True),
            ),
        )
        return payload_model.model_dump(by_alias=True, exclude_none=True)

    def _format_validation_error(self, exc: ValidationError) -> str:
        items = []
        for err in exc.errors():
            loc = ".".join(str(part) for part in err.get("loc", ()))
            msg = err.get("msg", "invalid value")
            if loc:
                items.append(f"{loc}: {msg}")
            else:
                items.append(msg)
        return "; ".join(items) or "invalid MCP request context"

    def _normalize_response(
        self,
        scenario: ScenarioSpec,
        request_payload: Dict[str, Any],
        response_data: Dict[str, Any],
    ) -> MCPInvokeResultOut:
        try:
            parsed = JsonRpcToolCallResponseOut.model_validate(response_data)
        except ValidationError as exc:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_response_schema",
                interface_ready=True,
                tool_supported=True,
                request_payload=request_payload,
                response=response_data,
                message=self._format_validation_error(exc),
            )

        if parsed.error is not None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="rpc_error",
                interface_ready=True,
                tool_supported=True,
                request_payload=request_payload,
                response=response_data,
                rpc_error=parsed.error.model_dump(exclude_none=True),
            )

        if parsed.result is None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_response",
                interface_ready=True,
                tool_supported=True,
                request_payload=request_payload,
                response=response_data,
                message="JSON-RPC result is missing or not an object",
            )

        result = parsed.result
        content = [item.model_dump(exclude_none=True) for item in result.content]
        structured_content = result.structured_content
        meta = result.meta.model_dump(by_alias=True, exclude_none=True)
        is_error = result.is_error

        content_text_json = None
        if content:
            first_item = content[0]
            if isinstance(first_item, dict) and first_item.get("type") == "text":
                text_value = first_item.get("text")
                if isinstance(text_value, str):
                    try:
                        content_text_json = json.loads(text_value)
                    except json.JSONDecodeError:
                        content_text_json = None

        return MCPInvokeResultOut.for_scenario(
            scenario=scenario,
            status="business_error" if is_error else "success",
            interface_ready=True,
            tool_supported=True,
            request_payload=request_payload,
            response=response_data,
            jsonrpc=parsed.jsonrpc,
            id=parsed.id,
            is_error=is_error,
            content=content,
            structured_content=structured_content,
            content_text_json=content_text_json,
            meta=meta,
            session_key=result.meta.session_key,
            is_finished=result.meta.is_finished,
            tool_name=result.meta.tool_name,
            next_tool_step_id=result.meta.next_tool_step_id,
        )
