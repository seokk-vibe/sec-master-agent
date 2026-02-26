from __future__ import annotations

from typing import Protocol

from PB.constant.classification_prompt import MASTER_AGENT_SYSTEM_PROMPT_TEMPLATE


class SupportsIntentClassification(Protocol):
    async def classify_intent(self, user_input: str, retries: int = 2) -> int:
        ...


async def route_intent(
    user_input: str,
    vllm_client: SupportsIntentClassification,
    retries: int = 2,
) -> int:
    """
    사용자 질문을 받아, 1~19 중 가장 적합한 시나리오 ID를 반환한다.
    실패 시 19(일반대화)로 폴백한다.

    참고: 신규 코드에서는 `PB.core.vllm_client.MasterAgentClient.classify_intent`
    를 직접 사용해도 된다. 본 함수는 기존 호출부 호환용으로 유지한다.
    """
    try:
        tool_id = await vllm_client.classify_intent(user_input=user_input, retries=retries)
        if isinstance(tool_id, int) and 1 <= tool_id <= 19:
            return tool_id
    except Exception as exc:  # pragma: no cover - 런타임 로깅용
        print(f"[Master Agent] 분류 실패: {exc}, 폴백 19번 시나리오")
    return 19


def build_classification_prompt(user_input: str) -> str:
    """기존 스크립트/테스트에서 재사용할 수 있는 프롬프트 렌더러."""
    return MASTER_AGENT_SYSTEM_PROMPT_TEMPLATE.format(user_input=user_input)
