from __future__ import annotations

from typing import List, Optional

from PB.dto.base import AllowExtraModel, StrictModel


class VLLMChatMessage(AllowExtraModel):
    role: str
    content: str


class VLLMChatCompletionRequestOut(StrictModel):
    model: str
    messages: List[VLLMChatMessage]
    max_tokens: int
    temperature: float
    top_p: float
    stream: bool


class VLLMResponseMessageOut(AllowExtraModel):
    content: Optional[str] = None


class VLLMChoiceOut(AllowExtraModel):
    message: VLLMResponseMessageOut


class VLLMChatCompletionResponseOut(AllowExtraModel):
    choices: List[VLLMChoiceOut]
