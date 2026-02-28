from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from PB.dto.base import PopulateByNameModel, StrictPopulateByNameModel
from PB.dto.mcp_tool_schemas import MCPInvokeResultOut


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
