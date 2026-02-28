from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from PB.dto.base import PopulateByNameModel, StrictPopulateByNameModel
from PB.dto.mcp_tool_schemas import MCPInvokeResultOut


class MCPUserInfoDTO(PopulateByNameModel):
    gps_x: Optional[str] = Field(default=None, alias="gpsX", description="위도")
    gps_y: Optional[str] = Field(default=None, alias="gpsY", description="경도")
    login_level: Optional[str] = Field(default=None, alias="loginLevel", description="MTS 전달 loginLevel")
    media_type: Optional[str] = Field(default=None, alias="mediaType", description="MTS 전달 mediaType")
    qust: Optional[str] = Field(default=None, description="MTS 전달 qust")
    cybid: Optional[str] = Field(default=None, description="사이버 ID")
    udid: Optional[str] = Field(default=None, description="단말 UDID (툴에 따라 필수)")
    token: Optional[str] = Field(default=None, description="인증 토큰 (툴에 따라 필수)")


class MCPRequestContextDTO(PopulateByNameModel):
    tool_step_id: str = Field(
        default="1",
        alias="toolStepId",
        description="최초 호출은 1, 이후 응답 nextToolStepId 사용",
    )
    session_key: Optional[str] = Field(
        default=None,
        alias="sessionKey",
        description="이전 MCP 응답의 sessionKey",
    )
    user_info: Optional[MCPUserInfoDTO] = Field(
        default=None,
        alias="userInfo",
        description="MTS 전달 사용자 정보",
    )


class ClassifierLLMOptionsDTO(PopulateByNameModel):
    provider: Optional[str] = Field(
        default=None,
        description="분류용 LLM 제공자 선택값 (예: chatgpt, vllm, litellm)",
    )
    model_name: Optional[str] = Field(
        default=None,
        alias="modelName",
        description="분류 요청에 사용할 모델명 (LiteLLM/OpenAI-compatible endpoint의 model 값)",
    )


class QueryRequestDTO(StrictPopulateByNameModel):
    user_input: str = Field(..., min_length=1, max_length=4000, description="프론트에서 전달받는 사용자 질의문")
    user_id: Optional[str] = Field(default=None, description="선택값: 사용자 식별자")
    session_id: Optional[str] = Field(default=None, description="선택값: 세션 식별자")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="선택값: 프론트 부가 컨텍스트")
    classifier: Optional[ClassifierLLMOptionsDTO] = Field(
        default=None,
        description="분류 단계에서 사용할 LLM(provider/model) 선택 옵션",
    )
    mcp: Optional[MCPRequestContextDTO] = Field(
        default=None,
        description="MCP tools/call 인터페이스에 전달할 컨텍스트",
    )


class ClassificationResultDTO(BaseModel):
    scenario_id: int
    scenario_name: str
    route_key: str
    description: Optional[str] = None


class MCPInvocationResultDTO(BaseModel):
    payload: MCPInvokeResultOut


class QueryResponseDTO(BaseModel):
    request_id: str
    user_input: str
    classification: ClassificationResultDTO
    mcp: MCPInvocationResultDTO
