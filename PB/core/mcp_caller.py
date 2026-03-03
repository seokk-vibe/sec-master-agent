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


# ---------------------------------------------------------------------------
# 공유 헬퍼 함수 (StubMCPCaller / JsonRpcMCPCaller 공통)
# ---------------------------------------------------------------------------

def _build_rpc_id(context: Dict[str, Any]) -> str:
    request_id = context.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        return request_id
    return str(uuid4())


def _format_validation_error(exc: ValidationError) -> str:
    items = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()))
        msg = err.get("msg", "invalid value")
        if loc:
            items.append(f"{loc}: {msg}")
        else:
            items.append(msg)
    return "; ".join(items) or "invalid MCP payload"


def _build_arguments(
    tool_adapters: Dict[str, MCPToolAdapterProtocol],
    scenario: ScenarioSpec,
    context: Dict[str, Any],
) -> tuple[Optional[BaseModel], Optional[str]]:
    if not scenario.mcp_tool_name:
        return None, "scenario.mcp_tool_name is required"

    adapter = get_tool_adapter(tool_adapters, scenario.mcp_tool_name)
    if adapter is None:
        return None, f"no request schema is registered for tool '{scenario.mcp_tool_name}'"

    try:
        return adapter.build_arguments(context), None
    except ValueError as exc:
        return None, str(exc)
    except ValidationError as exc:
        return None, _format_validation_error(exc)


def _build_request_payload(
    rpc_id: str,
    tool_name: Optional[str],
    arguments: BaseModel,
) -> Dict[str, Any]:
    payload_model = JsonRpcToolCallRequest(
        id=rpc_id,
        params=JsonRpcToolCallParams(
            name=tool_name or "",
            arguments=arguments.model_dump(by_alias=True, exclude_none=True),
        ),
    )
    return payload_model.model_dump(by_alias=True, exclude_none=True)


class MCPCallerProtocol(Protocol):
    async def invoke(
        self,
        scenario: ScenarioSpec,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> MCPInvokeResultOut:
        ...


class StubMCPCaller:
    """
    문서 기준 MCP request/response를 로컬 목업으로 생성하는 호출자.

    - `툴 단계 존재여부 = X` 대상은 실제 JSON-RPC payload shape로 request/response를 구성한다.
    - 실제 MCP 서버가 없으므로 tool별 mock structuredContent를 반환한다.
    """

    DEFAULT_STUB_USER_INFO: Dict[str, str] = {
        "gpsX": "37.567787",
        "gpsY": "126.983757",
        "loginLevel": "2",
        "mediaType": "3b",
        "qust": "",
        "cybid": "TEST",
        "udid": "stub-udid",
        "token": "stub-token",
    }

    MOCK_MESSAGE_BY_TOOL: Dict[str, str] = {
        "getAcctRightsStatusTool": "계좌 권리현황 목업 응답입니다.",
        "getUnsettledAmountTool": "미수금 안내 목업 응답입니다.",
        "getCollateralShortageTool": "담보부족 현황안내 목업 응답입니다.",
        "getAutoTransferErrorTool": "자동이체 오류현황 목업 응답입니다.",
        "getEventStatusTool": "이벤트 신청/당첨현황 목업 응답입니다.",
        "getTransferFeeCouponTool": "이체수수료 무료 쿠폰 조회 목업 응답입니다.",
        "getImportantNoticeTool": "중요알림 조회 목업 응답입니다.",
        "getMarketScheduleTool": "증시일정 조회 목업 응답입니다.",
        "getInvestmentPlusTool": "투자플러스 조회 목업 응답입니다.",
        "getExchangeRateTool": "환율 조회 목업 응답입니다.",
        "getSectorinfoTool": "섹터정보 조회 목업 응답입니다.",
        "getYoutubeTool": "유튜브 조회 목업 응답입니다.",
        "getBranchFinderTool": "지점찾기 조회 목업 응답입니다.",
        "getWeatherTool": "날씨 조회 목업 응답입니다.",
        "commonChatTool": "일반대화(FAQ/Chip) 목업 응답입니다.",
    }

    def __init__(
        self,
        interface_ready: bool = True,
        stub_mode: bool = True,
        tool_adapters: Optional[Dict[str, MCPToolAdapterProtocol]] = None,
    ) -> None:
        self.interface_ready = interface_ready
        self.stub_mode = stub_mode
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
                status="stubbed" if self.stub_mode else "pending",
                interface_ready=self.interface_ready,
                tool_supported=False,
                user_input=user_input,
                context=ctx,
                next_action="register mcp_tool_name for this scenario if interface is ready",
            )

        ctx = self._with_default_mcp_context(ctx, user_input)
        arguments, validation_error = _build_arguments(self._tool_adapters, scenario, ctx)
        if validation_error is not None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_request_context",
                interface_ready=self.interface_ready,
                tool_supported=True,
                message=validation_error,
                user_input=user_input,
                context=ctx,
            )

        rpc_id = _build_rpc_id(ctx)
        request_payload = _build_request_payload(
            rpc_id=rpc_id,
            tool_name=scenario.mcp_tool_name,
            arguments=arguments,
        )
        response_payload = self._build_mock_response(
            scenario=scenario,
            rpc_id=rpc_id,
            user_input=user_input,
            context=ctx,
        )

        parsed, parse_error = self._parse_response(response_payload)
        if parse_error is not None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_response_schema",
                interface_ready=self.interface_ready,
                tool_supported=True,
                message=parse_error,
                request_payload=request_payload,
                response=response_payload,
                user_input=user_input,
                context=ctx,
            )

        assert parsed is not None  # for type checkers
        result = parsed.result
        if result is None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_response",
                interface_ready=self.interface_ready,
                tool_supported=True,
                message="JSON-RPC result is missing or not an object",
                request_payload=request_payload,
                response=response_payload,
                user_input=user_input,
                context=ctx,
            )

        content = [item.model_dump(exclude_none=True) for item in result.content]
        structured_content = result.structured_content
        meta = result.meta.model_dump(by_alias=True, exclude_none=True)

        content_text_json = None
        if content:
            first_item = content[0]
            if isinstance(first_item, dict):
                text_value = first_item.get("text")
                if isinstance(text_value, str):
                    try:
                        content_text_json = json.loads(text_value)
                    except json.JSONDecodeError:
                        content_text_json = None

        return MCPInvokeResultOut.for_scenario(
            scenario=scenario,
            status="stubbed" if self.stub_mode else "pending",
            interface_ready=self.interface_ready,
            tool_supported=True,
            request_payload=request_payload,
            response=response_payload,
            jsonrpc=parsed.jsonrpc,
            id=parsed.id,
            is_error=result.is_error,
            content=content,
            structured_content=structured_content,
            content_text_json=content_text_json,
            meta=meta,
            session_key=result.meta.session_key,
            is_finished=result.meta.is_finished,
            tool_name=result.meta.tool_name,
            next_tool_step_id=result.meta.next_tool_step_id,
            user_input=user_input,
            context=ctx,
            next_action="switch mcp_stub_mode=false and set MCP_SERVER_URL to use real MCP",
        )

    def _with_default_mcp_context(self, context: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        merged_context = dict(context)

        mcp_ctx = merged_context.get("mcp")
        if not isinstance(mcp_ctx, dict):
            metadata = merged_context.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("mcp"), dict):
                mcp_ctx = metadata.get("mcp")
            else:
                mcp_ctx = {}
        mcp_ctx = dict(mcp_ctx)

        user_info = mcp_ctx.get("user_info") or mcp_ctx.get("userInfo")
        normalized_user_info = dict(self.DEFAULT_STUB_USER_INFO)
        if isinstance(user_info, dict):
            normalized_user_info.update(user_info)
        mcp_ctx["user_info"] = normalized_user_info

        user_chip_input = mcp_ctx.get("user_chip_input") or mcp_ctx.get("userChipInput")
        if user_chip_input is None:
            mcp_ctx["user_chip_input"] = {
                "type": "query",
                "displayText": user_input[:50] if user_input else "기본 질의",
            }

        merged_context["mcp"] = mcp_ctx
        return merged_context

    def _build_mock_response(
        self,
        *,
        scenario: ScenarioSpec,
        rpc_id: str,
        user_input: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        tool_name = scenario.mcp_tool_name or ""
        structured_content = self._build_mock_structured_content(
            tool_name=tool_name,
            scenario_name=scenario.name,
            user_input=user_input,
            context=context,
        )

        mcp_ctx = context.get("mcp") if isinstance(context.get("mcp"), dict) else {}
        session_key = mcp_ctx.get("session_key") or mcp_ctx.get("sessionKey") or f"stub-{tool_name}"
        if not isinstance(session_key, str):
            session_key = str(session_key)

        return {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(structured_content, ensure_ascii=False),
                    }
                ],
                "isError": False,
                "structuredContent": structured_content,
                "_meta": {
                    "sessionKey": session_key,
                    "isFinished": True,
                    "toolName": tool_name,
                },
            },
        }

    def _build_mock_structured_content(
        self,
        *,
        tool_name: str,
        scenario_name: str,
        user_input: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        message = self.MOCK_MESSAGE_BY_TOOL.get(tool_name, f"{scenario_name} 목업 응답입니다.")
        chip_display = None
        mcp_ctx = context.get("mcp")
        if isinstance(mcp_ctx, dict):
            chip = mcp_ctx.get("user_chip_input") or mcp_ctx.get("userChipInput")
            if isinstance(chip, dict):
                chip_display = chip.get("displayText")

        if tool_name == "getWeatherTool" and isinstance(chip_display, str) and chip_display.strip():
            message = f"{chip_display.strip()} 기준 날씨 목업 응답입니다."
        elif tool_name == "commonChatTool":
            message = f"{message} (질의: {user_input})"

        content_type = "common" if tool_name == "commonChatTool" else "dynamic"
        return {
            "type": content_type,
            "data": [
                {
                    "templateCode": "textSimple",
                    "data": {"message": message},
                }
            ],
        }

    def _parse_response(
        self,
        response_data: Dict[str, Any],
    ) -> tuple[Optional[JsonRpcToolCallResponseOut], Optional[str]]:
        try:
            return JsonRpcToolCallResponseOut.model_validate(response_data), None
        except ValidationError as exc:
            return None, _format_validation_error(exc)


class JsonRpcMCPCaller:
    """
    MCP(JSON-RPC) 통신 호출자.

    현재 구현 범위:
    - `tools/call` 메서드 호출
    - IF-SEC-API 문서 기반 `params.name`, `params.arguments` 구성
    - 등록된 tool adapter 기준 요청 인자 검증 및 직렬화
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

        arguments, validation_error = _build_arguments(self._tool_adapters, scenario, ctx)
        if validation_error is not None:
            return MCPInvokeResultOut.for_scenario(
                scenario=scenario,
                status="invalid_request_context",
                interface_ready=True,
                tool_supported=True,
                message=validation_error,
            )

        rpc_id = _build_rpc_id(ctx)
        payload = _build_request_payload(
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
                message=_format_validation_error(exc),
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
