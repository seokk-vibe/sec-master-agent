"""
LLM 분류 호출자 (인프라 레이어).

외부 LLM API(OpenAI-compatible chat completions)를 호출하여
사용자 질의를 시나리오 ID(1~19)로 변환하는 역할을 담당한다.

레이어 구분:
  - Caller (이 모듈) : 외부 API 호출·재시도·응답 파싱 등 인프라 관심사
  - Service (intent_classifier) : 분류 활성화 여부·폴백 등 비즈니스 정책

두 가지 구현체를 제공한다:
  - LLMClassifierCaller  : httpx(post_json) 기반 — LiteLLM 프록시 또는 직접 호출
  - OpenAIClassifierCaller: openai SDK 기반 — 외부망에서 OpenAI API 직접 호출
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Protocol, Tuple

logger = logging.getLogger(__name__)

from pydantic import ValidationError

from PB.constant.classification_prompt import CLASSIFICATION_SYSTEM_PROMPT
from PB.constant.scenarios import MAX_SCENARIO_ID
from PB.core.requester import post_json
from PB.dto.base import FrozenStrictModel
from PB.dto.llm_schemas import (
    ChatCompletionRequestOut,
    ChatCompletionResponseOut,
    ChatMessage,
)


class IntentClassificationMeta(FrozenStrictModel):
    """LLM 분류 호출의 결과 메타데이터.

    단순 scenario_id뿐 아니라 디버깅·로깅에 필요한 부가 정보를 함께 담는다.
    """

    scenario_id: int                    # 분류된 시나리오 번호 (1~19)
    raw_content: Optional[str] = None   # LLM이 실제로 반환한 원문 텍스트
    fallback_used: bool = False         # 폴백(기본 시나리오)이 사용되었는지 여부
    error: Optional[str] = None         # 에러 발생 시 원인 메시지


# ---------------------------------------------------------------------------
# Protocol — 두 caller 모두 이 인터페이스를 만족한다.
# ---------------------------------------------------------------------------

class LLMClassifierCallerProtocol(Protocol):
    """LLM 의도 분류 호출자가 구현해야 하는 인터페이스."""

    async def classify_intent(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> int: ...

    async def classify_intent_with_meta(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> IntentClassificationMeta: ...


# ---------------------------------------------------------------------------
# 공유 파서 — 두 caller가 동일하게 사용하는 응답 파싱 로직
# ---------------------------------------------------------------------------

def parse_llm_classification_response(
    response_data: Dict[str, Any],
    default_scenario_id: int,
) -> Tuple[int, Optional[str], bool]:
    """LLM 응답 JSON(dict)에서 시나리오 ID를 추출한다.

    파싱 전략:
      1) 응답 텍스트를 토큰 단위로 순회하며 유효 범위(1~MAX) 숫자를 찾는다.
      2) 토큰에서 못 찾으면, 전체 텍스트에서 숫자만 추출하여 재시도한다.
      3) 모두 실패하면 default_scenario_id로 폴백한다.

    Returns:
        (scenario_id, raw_content, fallback_used) 튜플
    """
    raw_content: Optional[str] = None
    try:
        parsed = ChatCompletionResponseOut.model_validate(response_data)
        content = parsed.choices[0].message.content
        raw_content = str(content).strip() if content is not None else ""

        # 전략 1: 공백 기준 토큰에서 숫자 추출
        for token in raw_content.replace("\n", " ").split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if digits:
                candidate = int(digits)
                if 1 <= candidate <= MAX_SCENARIO_ID:
                    return candidate, raw_content, False

        # 전략 2: 전체 텍스트에서 숫자만 이어붙여 시도
        only_digits = "".join(ch for ch in raw_content if ch.isdigit())
        if only_digits:
            candidate = int(only_digits)
            if 1 <= candidate <= 19:
                return candidate, raw_content, False
    except (ValidationError, IndexError, TypeError, ValueError):
        pass

    return default_scenario_id, raw_content, True


# ---------------------------------------------------------------------------
# 구현체 1: httpx(post_json) 기반 — LiteLLM 프록시 또는 직접 호출
# ---------------------------------------------------------------------------

class LLMClassifierCaller:
    """LLM API를 호출하여 의도 분류를 수행하는 인프라 호출자.

    책임:
      - 분류용 프롬프트 페이로드 조립 (_build_payload)
      - post_json을 통한 LLM API 호출 + 재시도 (최대 3회, 0.5초 간격)
      - LLM 응답에서 시나리오 ID 숫자 파싱
      - 모든 실패 경로에서 default_scenario_id로 안전하게 폴백
    """

    def __init__(
        self,
        server_url: str,
        model_name: str,
        timeout: float = 30.0,
        default_scenario_id: int = 19,
    ) -> None:
        self.server_url = server_url              # LLM 엔드포인트 URL
        self.model_name = model_name              # 기본 모델명 (예: Qwen2.5-72B-Instruct)
        self.timeout = timeout                    # HTTP 요청 타임아웃 (초)
        self.default_scenario_id = default_scenario_id  # 분류 실패 시 폴백 시나리오
        self.headers = {"Content-Type": "application/json"}

    async def classify_intent(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> int:
        """시나리오 ID만 필요할 때 사용하는 간편 메서드."""
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
        """LLM API를 호출하여 의도를 분류하고, 메타데이터와 함께 반환한다.

        실패 시에도 예외를 던지지 않고 fallback_used=True로 안전하게 반환한다.
        """
        # URL이 비어있으면 호출 자체를 건너뛰고 폴백
        if not self.server_url:
            return IntentClassificationMeta(
                scenario_id=self.default_scenario_id,
                fallback_used=True,
                error="LLM server URL is empty",
            )

        payload = self._build_payload(user_input, model_name_override=model_name_override)

        # 재시도 루프: 네트워크·서버 오류에 대비하여 최대 max_attempts회 시도
        for attempt in range(max_attempts):
            try:
                response = await post_json(
                    self.server_url,
                    json_data=payload.model_dump(),
                    headers=self.headers,
                    timeout=self.timeout,
                )
                response.raise_for_status()
                response_data = response.json()
                logger.info(
                    "[LLMClassifierCaller] LLM 응답 수신 | model=%s | response=%s",
                    payload.model, response_data,
                )
                scenario_id, raw_content, fallback_used = parse_llm_classification_response(
                    response_data, self.default_scenario_id,
                )
                logger.info(
                    "[LLMClassifierCaller] 분류 결과 | scenario_id=%d | raw_content=%s | fallback=%s",
                    scenario_id, raw_content, fallback_used,
                )
                return IntentClassificationMeta(
                    scenario_id=scenario_id,
                    raw_content=raw_content,
                    fallback_used=fallback_used,
                )
            except Exception as exc:  # pragma: no cover - 네트워크 예외는 런타임 의존
                logger.warning(
                    "[LLMClassifierCaller] 호출 실패 (attempt %d/%d) | error=%s: %s",
                    attempt + 1, max_attempts, type(exc).__name__, exc,
                )
                if attempt >= max_attempts - 1:
                    return IntentClassificationMeta(
                        scenario_id=self.default_scenario_id,
                        fallback_used=True,
                        error=str(exc),
                    )
                await asyncio.sleep(0.5)

        # 이론상 도달하지 않지만, 안전장치로 폴백 반환
        return IntentClassificationMeta(
            scenario_id=self.default_scenario_id,
            fallback_used=True,
            error="unexpected classification loop exit",
        )

    def _build_payload(
        self,
        user_input: str,
        model_name_override: Optional[str] = None,
    ) -> ChatCompletionRequestOut:
        """OpenAI chat completions 형식의 요청 페이로드를 조립한다.

        model_name_override가 주어지면 기본 모델 대신 해당 모델을 사용한다.
        temperature=0.0, top_p=0.1로 결정적(deterministic) 응답을 유도한다.
        """
        model_name = (
            model_name_override.strip()
            if isinstance(model_name_override, str) and model_name_override.strip()
            else self.model_name
        )
        return ChatCompletionRequestOut(
            model=model_name,
            messages=[
                ChatMessage(role="system", content=CLASSIFICATION_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_input),
            ],
            max_tokens=10,       # 시나리오 번호(1~2자리)만 기대하므로 최소한으로 설정
            temperature=0.0,
            top_p=0.1,
            stream=False,
        )


# ---------------------------------------------------------------------------
# 구현체 2: openai SDK 기반 — 외부망에서 OpenAI API 직접 호출
# ---------------------------------------------------------------------------

class OpenAIClassifierCaller:
    """OpenAI SDK(openai.AsyncOpenAI)를 사용하여 의도 분류를 수행하는 호출자.

    외부망 개발 환경에서 LiteLLM 프록시 없이 OpenAI API를 직접 호출할 때 사용한다.
    openai 패키지는 __init__에서 lazy import하여 prd 환경에서 미설치 시에도 에러를 방지한다.
    """

    def __init__(
        self,
        model_name: str,
        api_key: str = "",
        timeout: float = 30.0,
        default_scenario_id: int = 19,
    ) -> None:
        import openai  # lazy import — prd에서 openai 미설치 시 여기서만 실패

        self.model_name = model_name
        self.timeout = timeout
        self.default_scenario_id = default_scenario_id
        self._client = openai.AsyncOpenAI(
            api_key=api_key or None,  # 빈 문자열이면 None → 환경변수 OPENAI_API_KEY 자동 감지
            timeout=timeout,
        )

    async def classify_intent(
        self,
        user_input: str,
        max_attempts: int = 3,
        model_name_override: Optional[str] = None,
    ) -> int:
        """시나리오 ID만 필요할 때 사용하는 간편 메서드."""
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
        """OpenAI SDK를 통해 의도를 분류하고, 메타데이터와 함께 반환한다."""
        model_name = (
            model_name_override.strip()
            if isinstance(model_name_override, str) and model_name_override.strip()
            else self.model_name
        )

        for attempt in range(max_attempts):
            try:
                completion = await self._client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                        {"role": "user", "content": user_input},
                    ],
                    max_tokens=10,
                    temperature=0.0,
                    top_p=0.1,
                    stream=False,
                )
                # SDK 응답을 dict로 변환하여 공유 파서에 전달
                response_data = completion.model_dump()
                logger.info(
                    "[OpenAIClassifierCaller] OpenAI 응답 수신 | model=%s | response=%s",
                    model_name, response_data,
                )
                scenario_id, raw_content, fallback_used = parse_llm_classification_response(
                    response_data, self.default_scenario_id,
                )
                logger.info(
                    "[OpenAIClassifierCaller] 분류 결과 | scenario_id=%d | raw_content=%s | fallback=%s",
                    scenario_id, raw_content, fallback_used,
                )
                return IntentClassificationMeta(
                    scenario_id=scenario_id,
                    raw_content=raw_content,
                    fallback_used=fallback_used,
                )
            except Exception as exc:
                logger.warning(
                    "[OpenAIClassifierCaller] 호출 실패 (attempt %d/%d) | error=%s: %s",
                    attempt + 1, max_attempts, type(exc).__name__, exc,
                )
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
