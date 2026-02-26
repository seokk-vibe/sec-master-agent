from __future__ import annotations

from typing import Any, Dict, Optional

from PB.core.vllm_client import MasterAgentClient


class IntentClassifierService:
    _CHATGPT_PROVIDER_ALIASES = {"chatgpt", "openai"}
    _DEFAULT_CHATGPT_CLASSIFIER_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        vllm_client: MasterAgentClient,
        default_scenario_id: int = 19,
        classification_enabled: bool = True,
    ) -> None:
        self._vllm_client = vllm_client
        self._default_scenario_id = default_scenario_id
        self._classification_enabled = classification_enabled

    def _resolve_classifier_model_name(self, context: Optional[Dict[str, Any]]) -> Optional[str]:
        if not isinstance(context, dict):
            return None

        classifier_ctx = context.get("classifier")
        if not isinstance(classifier_ctx, dict):
            return None

        raw_model_name = classifier_ctx.get("model_name", classifier_ctx.get("modelName"))
        if isinstance(raw_model_name, str) and raw_model_name.strip():
            return raw_model_name.strip()

        raw_provider = classifier_ctx.get("provider")
        if isinstance(raw_provider, str) and raw_provider.strip().lower() in self._CHATGPT_PROVIDER_ALIASES:
            return self._DEFAULT_CHATGPT_CLASSIFIER_MODEL

        return None

    async def classify(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        if not self._classification_enabled:
            return self._default_scenario_id

        model_name_override = self._resolve_classifier_model_name(context)
        tool_id = await self._vllm_client.classify_intent(
            user_input=user_input,
            model_name_override=model_name_override,
        )
        if 1 <= tool_id <= 19:
            return tool_id
        return self._default_scenario_id
