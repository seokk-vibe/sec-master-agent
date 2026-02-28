from __future__ import annotations

from typing import List, Optional

from PB.dto.base import AllowExtraModel, StrictModel


class ChatMessage(AllowExtraModel):
    role: str
    content: str


class ChatCompletionRequestOut(StrictModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: int
    temperature: float
    top_p: float
    stream: bool


class ChatResponseMessageOut(AllowExtraModel):
    content: Optional[str] = None


class ChatChoiceOut(AllowExtraModel):
    message: ChatResponseMessageOut


class ChatCompletionResponseOut(AllowExtraModel):
    choices: List[ChatChoiceOut]
