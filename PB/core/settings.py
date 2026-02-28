from __future__ import annotations

import os
from functools import lru_cache

from PB.dto.base import FrozenStrictModel


def _get_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings(FrozenStrictModel):
    app_name: str
    app_version: str
    debug: bool
    litellm_server_url: str
    llm_server_url: str
    llm_model_name: str
    llm_timeout_seconds: float
    intent_classification_enabled: bool
    default_scenario_id: int
    mcp_stub_mode: bool
    mcp_server_url: str
    mcp_timeout_seconds: float


@lru_cache
def load_settings() -> Settings:
    return Settings(
        app_name=os.getenv("APP_NAME", "PB Backend"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        debug=_get_bool_env("APP_DEBUG", False),
        litellm_server_url=os.getenv("LITELLM_SERVER_URL", ""),
        llm_server_url=os.getenv(
            "LLM_SERVER_URL",
            "http://172.17.102.34:8150/v1/chat/completions",
        ),
        llm_model_name=os.getenv("LLM_MODEL_NAME", "Qwen2.5-72B-Instruct"),
        llm_timeout_seconds=_get_float_env("LLM_TIMEOUT_SECONDS", 10.0),
        intent_classification_enabled=_get_bool_env("INTENT_CLASSIFICATION_ENABLED", True),
        default_scenario_id=_get_int_env("DEFAULT_SCENARIO_ID", 19),
        mcp_stub_mode=_get_bool_env("MCP_STUB_MODE", True),
        mcp_server_url=os.getenv("MCP_SERVER_URL", ""),
        mcp_timeout_seconds=_get_float_env("MCP_TIMEOUT_SECONDS", 10.0),
    )
