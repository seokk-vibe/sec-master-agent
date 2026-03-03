from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Protocol, Type

from pydantic import BaseModel

from PB.dto.mcp_tool_schemas import (
    CommonChatArgumentsIn,
    GetAcctRightsStatusArgumentsIn,
    GetAutoTransferErrorArgumentsIn,
    GetBranchFinderArgumentsIn,
    GetCollateralShortageArgumentsIn,
    GetEventStatusArgumentsIn,
    GetExchangeRateArgumentsIn,
    GetImportantNoticeArgumentsIn,
    GetInvestmentPlusArgumentsIn,
    GetMarketScheduleArgumentsIn,
    GetSectorinfoArgumentsIn,
    GetTransferFeeCouponArgumentsIn,
    GetUnsettledAmountArgumentsIn,
    GetWeatherArgumentsIn,
    GetYoutubeArgumentsIn,
)


class MCPToolAdapterProtocol(Protocol):
    tool_name: str

    def build_arguments(self, context: Dict[str, Any]) -> BaseModel:
        ...


class _CommonUserInfoToolAdapterBase:
    """
    IF-SEC-API X(단일 단계) 대상 tools/call 요청 인자 공통 구현.
    기본 구조:
      - toolStepId
      - sessionKey
      - userInfo
      - (optional) userInput / userChipInput
    """

    tool_name: str
    arguments_model: Type[BaseModel]

    def build_arguments(self, context: Dict[str, Any]) -> BaseModel:
        mcp_ctx = context.get("mcp") or {}
        if not isinstance(mcp_ctx, dict):
            raise ValueError("context.mcp must be an object")

        payload: Dict[str, Any] = {
            "toolStepId": mcp_ctx.get("tool_step_id") or mcp_ctx.get("toolStepId") or "1",
            "sessionKey": mcp_ctx.get("session_key") or mcp_ctx.get("sessionKey") or "",
            "userInfo": mcp_ctx.get("user_info") or mcp_ctx.get("userInfo"),
        }

        user_input = mcp_ctx.get("user_input") or mcp_ctx.get("userInput")
        if user_input is not None:
            payload["userInput"] = user_input

        user_chip_input = mcp_ctx.get("user_chip_input") or mcp_ctx.get("userChipInput")
        if user_chip_input is not None:
            payload["userChipInput"] = user_chip_input

        return self.arguments_model.model_validate(payload)


class GetAcctRightsStatusToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getAcctRightsStatusTool"
    arguments_model = GetAcctRightsStatusArgumentsIn


class GetUnsettledAmountToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getUnsettledAmountTool"
    arguments_model = GetUnsettledAmountArgumentsIn


class GetCollateralShortageToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getCollateralShortageTool"
    arguments_model = GetCollateralShortageArgumentsIn


class GetAutoTransferErrorToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getAutoTransferErrorTool"
    arguments_model = GetAutoTransferErrorArgumentsIn


class GetEventStatusToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getEventStatusTool"
    arguments_model = GetEventStatusArgumentsIn


class GetTransferFeeCouponToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getTransferFeeCouponTool"
    arguments_model = GetTransferFeeCouponArgumentsIn


class GetImportantNoticeToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getImportantNoticeTool"
    arguments_model = GetImportantNoticeArgumentsIn


class GetMarketScheduleToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getMarketScheduleTool"
    arguments_model = GetMarketScheduleArgumentsIn


class GetInvestmentPlusToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getInvestmentPlusTool"
    arguments_model = GetInvestmentPlusArgumentsIn


class GetExchangeRateToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getExchangeRateTool"
    arguments_model = GetExchangeRateArgumentsIn


class GetSectorinfoToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getSectorinfoTool"
    arguments_model = GetSectorinfoArgumentsIn


class GetYoutubeToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getYoutubeTool"
    arguments_model = GetYoutubeArgumentsIn


class GetBranchFinderToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getBranchFinderTool"
    arguments_model = GetBranchFinderArgumentsIn


class GetWeatherToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "getWeatherTool"
    arguments_model = GetWeatherArgumentsIn


class CommonChatToolAdapter(_CommonUserInfoToolAdapterBase):
    tool_name = "commonChatTool"
    arguments_model = CommonChatArgumentsIn


def build_default_mcp_tool_adapters() -> Dict[str, MCPToolAdapterProtocol]:
    registered_adapters: list[MCPToolAdapterProtocol] = [
        GetAcctRightsStatusToolAdapter(),
        GetUnsettledAmountToolAdapter(),
        GetCollateralShortageToolAdapter(),
        GetAutoTransferErrorToolAdapter(),
        GetEventStatusToolAdapter(),
        GetTransferFeeCouponToolAdapter(),
        GetImportantNoticeToolAdapter(),
        GetMarketScheduleToolAdapter(),
        GetInvestmentPlusToolAdapter(),
        GetExchangeRateToolAdapter(),
        GetSectorinfoToolAdapter(),
        GetYoutubeToolAdapter(),
        GetBranchFinderToolAdapter(),
        GetWeatherToolAdapter(),
        CommonChatToolAdapter(),
    ]
    return {adapter.tool_name: adapter for adapter in registered_adapters}


def get_tool_adapter(
    adapters: Mapping[str, MCPToolAdapterProtocol],
    tool_name: Optional[str],
) -> Optional[MCPToolAdapterProtocol]:
    if not tool_name:
        return None
    return adapters.get(tool_name)
