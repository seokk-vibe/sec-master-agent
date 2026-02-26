from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional

from pydantic import Field, field_validator

from PB.dto.base import (
    AllowExtraModel,
    AllowExtraPopulateByNameModel,
    StrictPopulateByNameModel,
)

if TYPE_CHECKING:
    from PB.constant.scenarios import ScenarioSpec


class MCPStrictModel(StrictPopulateByNameModel):
    pass


class GetAcctRightsStatusUserInfoIn(MCPStrictModel):
    gps_x: Optional[str] = Field(default=None, alias="gpsX")
    gps_y: Optional[str] = Field(default=None, alias="gpsY")
    login_level: Optional[str] = Field(default=None, alias="loginLevel")
    media_type: Optional[str] = Field(default=None, alias="mediaType")
    qust: Optional[str] = None
    cybid: Optional[str] = None
    udid: str
    token: str

    @field_validator(
        "gps_x",
        "gps_y",
        "login_level",
        "media_type",
        "qust",
        "cybid",
        "udid",
        "token",
        mode="before",
    )
    @classmethod
    def _coerce_to_string(cls, value: object) -> object:
        if value is None:
            return None
        return str(value)


class GetAcctRightsStatusArgumentsIn(MCPStrictModel):
    tool_step_id: str = Field(default="1", alias="toolStepId")
    session_key: str = Field(default="", alias="sessionKey")
    user_info: GetAcctRightsStatusUserInfoIn = Field(alias="userInfo")

    @field_validator("tool_step_id", "session_key", mode="before")
    @classmethod
    def _coerce_to_string(cls, value: object) -> object:
        if value is None:
            return ""
        return str(value)


class GetUnsettledAmountArgumentsIn(GetAcctRightsStatusArgumentsIn):
    """
    if-sec-api-004 기준 요청 인자.
    현재 문서상 shape가 if-sec-api-003과 동일하여 스키마를 재사용한다.
    """


class JsonRpcToolCallParams(MCPStrictModel):
    name: str
    arguments: Dict[str, Any]


class JsonRpcToolCallRequest(MCPStrictModel):
    jsonrpc: Literal["2.0"] = "2.0"
    method: Literal["tools/call"] = "tools/call"
    id: str
    params: JsonRpcToolCallParams


class JsonRpcErrorOut(AllowExtraModel):
    code: int
    message: str
    data: Optional[Any] = None


class MCPContentItemOut(AllowExtraModel):
    type: str
    text: Optional[str] = None


class MCPResultMetaOut(AllowExtraPopulateByNameModel):
    session_key: str = Field(alias="sessionKey")
    is_finished: bool = Field(alias="isFinished")
    tool_name: str = Field(alias="toolName")
    next_tool_step_id: Optional[str] = Field(default=None, alias="nextToolStepId")


class MCPToolCallResultOut(AllowExtraPopulateByNameModel):
    content: List[MCPContentItemOut]
    is_error: bool = Field(alias="isError")
    structured_content: Dict[str, Any] = Field(alias="structuredContent")
    meta: MCPResultMetaOut = Field(alias="_meta")


class JsonRpcToolCallResponseOut(AllowExtraModel):
    jsonrpc: Optional[str] = None
    id: Optional[Any] = None
    result: Optional[MCPToolCallResultOut] = None
    error: Optional[JsonRpcErrorOut] = None


MCPInvokeStatus = Literal[
    "stubbed",
    "pending",
    "unsupported_scenario",
    "not_configured",
    "invalid_request_context",
    "http_error",
    "transport_error",
    "invalid_response_schema",
    "rpc_error",
    "invalid_response",
    "business_error",
    "success",
]


class MCPInvokeResultOut(AllowExtraModel):
    status: MCPInvokeStatus
    interface_ready: bool
    tool_supported: bool

    scenario_id: int
    scenario_name: str
    route_key: str
    mcp_tool_name: Optional[str] = None

    # error / diagnostics
    message: Optional[str] = None
    request_payload: Optional[Dict[str, Any]] = None
    response: Optional[Dict[str, Any]] = None
    http_status_code: Optional[int] = None
    rpc_error: Optional[Dict[str, Any]] = None

    # normalized response fields
    jsonrpc: Optional[str] = None
    id: Optional[Any] = None
    is_error: Optional[bool] = None
    content: List[Dict[str, Any]] = Field(default_factory=list)
    structured_content: Optional[Dict[str, Any]] = None
    content_text_json: Optional[Any] = None
    meta: Dict[str, Any] = Field(default_factory=dict)
    session_key: Optional[str] = None
    is_finished: Optional[bool] = None
    tool_name: Optional[str] = None
    next_tool_step_id: Optional[str] = None

    # stub/debug fields (optional)
    user_input: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    next_action: Optional[str] = None

    @classmethod
    def for_scenario(
        cls,
        *,
        scenario: "ScenarioSpec",
        status: MCPInvokeStatus,
        interface_ready: bool,
        tool_supported: bool,
        **updates: Any,
    ) -> "MCPInvokeResultOut":
        payload: Dict[str, Any] = {
            "status": status,
            "interface_ready": interface_ready,
            "tool_supported": tool_supported,
            "scenario_id": scenario.id,
            "scenario_name": scenario.name,
            "route_key": scenario.route_key,
            "mcp_tool_name": scenario.mcp_tool_name,
            # error / diagnostics defaults
            "message": None,
            "request_payload": None,
            "response": None,
            "http_status_code": None,
            "rpc_error": None,
            # normalized response defaults
            "jsonrpc": None,
            "id": None,
            "is_error": None,
            "content": [],
            "structured_content": None,
            "content_text_json": None,
            "meta": {},
            "session_key": None,
            "is_finished": None,
            "tool_name": None,
            "next_tool_step_id": None,
        }
        payload.update(updates)
        return cls.model_validate(payload)
