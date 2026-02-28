from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from PB.constant.classification_prompt import build_master_agent_system_prompt
from PB.constant.scenarios import MAX_SCENARIO_ID
from PB.core.requester import post_json
from PB.dto.base import FrozenStrictModel
from PB.dto.vllm_schemas import (
    VLLMChatCompletionRequestOut,
    VLLMChatCompletionResponseOut,
    VLLMChatMessage,
)


class IntentClassificationMeta(FrozenStrictModel):
    scenario_id: int
    raw_content: Optional[str] = None
    fallback_used: bool = False
    error: Optional[str] = None


class MasterAgentClient:
    """
    vLLM/LiteLLM(OpenAI-compatible chat completions) 기반 분류 클라이언트.
    현재 단계에서는 질문 분류(1~19)만 담당한다.
    """

    def __init__(
        self,
        server_url: str,
        model_name: str,
        timeout: float = 30.0,
        default_scenario_id: int = 19,
    ) -> None:
        self.server_url = server_url
        self.model_name = model_name
        self.timeout = timeout
        self.default_scenario_id = default_scenario_id
        self.headers = {"Content-Type": "application/json"}

    async def classify_intent(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> int:
        meta = await self.classify_intent_with_meta(
            user_input=user_input,
            max_attempts=max_attempts,
            model_name_override=model_name_override,
        )
        return meta.scenario_id

    async def classify_intent_with_meta(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> IntentClassificationMeta:
        if not self.server_url:
            return IntentClassificationMeta(
                scenario_id=self.default_scenario_id,
                fallback_used=True,
                error="vLLM server URL is empty",
            )

        payload = self._build_payload(user_input, model_name_override=model_name_override)

        for attempt in range(max_attempts):
            try:
                response = await post_json(
                    self.server_url,
                    json_data=payload.model_dump(),
                    headers=self.headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                scenario_id, raw_content, fallback_used = self._parse_response(response.json())
                return IntentClassificationMeta(
                    scenario_id=scenario_id,
                    raw_content=raw_content,
                    fallback_used=fallback_used,
                )
            except Exception as exc:  # pragma: no cover - 네트워크 예외는 런타임 의존
                if attempt >= max_attempts - 1:
                    return IntentClassificationMeta(
                        scenario_id=self.default_scenario_id,
                        fallback_used=True,
                        error=str(exc),
                    )
                await asyncio.sleep(0.5)

        return IntentClassificationMeta(
            scenario_id=self.default_scenario_id,
            fallback_used=True,
            error="unexpected classification loop exit",
        )

    def _build_payload(
        self,
        user_input: str,
        model_name_override: Optional[str] = None,
    ) -> VLLMChatCompletionRequestOut:
        prompt = build_master_agent_system_prompt(user_input)
        model_name = (
            model_name_override.strip()
            if isinstance(model_name_override, str) and model_name_override.strip()
            else self.model_name
        )
        return VLLMChatCompletionRequestOut(
            model=model_name,
            messages=[
                VLLMChatMessage(role="system", content=prompt),
                VLLMChatMessage(role="user", content=""),
            ],
            max_tokens=10,
            temperature=0.0,
            top_p=0.1,
            stream=False,
        )

    def _parse_response(self, response_data: Dict[str, Any]) -> Tuple[int, Optional[str], bool]:
        raw_content: Optional[str] = None
        try:
            parsed = VLLMChatCompletionResponseOut.model_validate(response_data)
            content = parsed.choices[0].message.content
            raw_content = str(content).strip() if content is not None else ""
            for token in raw_content.replace("\n", " ").split():
                digits = "".join(ch for ch in token if ch.isdigit())
                if digits:
                    candidate = int(digits)
                    if 1 <= candidate <= MAX_SCENARIO_ID:
                        return candidate, raw_content, False

            only_digits = "".join(ch for ch in raw_content if ch.isdigit())
            if only_digits:
                candidate = int(only_digits)
                if 1 <= candidate <= 19:
                    return candidate, raw_content, False
        except (ValidationError, IndexError, TypeError, ValueError):
            pass

        return self.default_scenario_id, raw_content, True

