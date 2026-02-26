from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Protocol, Type

from pydantic import BaseModel

from PB.dto.mcp_tool_schemas import (
    GetAcctRightsStatusArgumentsIn,
    GetUnsettledAmountArgumentsIn,
)


class MCPToolAdapterProtocol(Protocol):
    tool_name: str

    def build_arguments(self, context: Dict[str, Any]) -> BaseModel:
        ...


class _CommonUserInfoToolAdapterBase:
    """
    if-sec-api-003/004 계열 tools/call 요청 인자 공통 구현.
    실제 사용 시에는 툴별 명시 adapter 클래스를 사용한다.
    (toolStepId/sessionKey/userInfo)
    """

    tool_name: str
    arguments_model: Type[BaseModel]

    def build_arguments(self, context: Dict[str, Any]) -> BaseModel:
        mcp_ctx = context.get("mcp") or {}
        if not isinstance(mcp_ctx, dict):
            raise ValueError("context.mcp must be an object")

        user_info = mcp_ctx.get("user_info")
        if user_info is None:
            user_info = mcp_ctx.get("userInfo")

        payload = {
            "toolStepId": mcp_ctx.get("tool_step_id", mcp_ctx.get("toolStepId", "1")),
            "sessionKey": mcp_ctx.get("session_key", mcp_ctx.get("sessionKey", "")) or "",
            "userInfo": user_info,
        }
        return self.arguments_model.model_validate(payload)


class GetAcctRightsStatusToolAdapter(_CommonUserInfoToolAdapterBase):
    """if-sec-api-003.md / 시나리오 1 (계좌 권리현황)."""

    tool_name = "getAcctRightsStatusTool"
    arguments_model = GetAcctRightsStatusArgumentsIn


class GetUnsettledAmountToolAdapter(_CommonUserInfoToolAdapterBase):
    """if-sec-api-004.md / 시나리오 2 (미수금 안내)."""

    tool_name = "getUnsettledAmountTool"
    arguments_model = GetUnsettledAmountArgumentsIn


def build_default_mcp_tool_adapters() -> Dict[str, MCPToolAdapterProtocol]:
    registered_adapters: list[MCPToolAdapterProtocol] = [
        GetAcctRightsStatusToolAdapter(),
        GetUnsettledAmountToolAdapter(),
    ]
    adapters: Dict[str, MCPToolAdapterProtocol] = {
        adapter.tool_name: adapter for adapter in registered_adapters
    }
    return adapters


def get_tool_adapter(
    adapters: Mapping[str, MCPToolAdapterProtocol],
    tool_name: Optional[str],
) -> Optional[MCPToolAdapterProtocol]:
    if not tool_name:
        return None
    return adapters.get(tool_name)
