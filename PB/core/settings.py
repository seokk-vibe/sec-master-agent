"""
설정 로더.

YAML 파일(config_dev.yaml / config_prd.yaml)을 기본값으로 읽고,
동일 키의 환경변수가 있으면 환경변수 값으로 덮어쓴다.

프로파일 결정 순서:
  1) 환경변수 APP_PROFILE (예: dev, prd)
  2) 미지정 시 기본값 "dev"

YAML 파일 탐색 경로:
  프로젝트 루트의 config_{profile}.yaml
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict

import yaml

from PB.dto.base import FrozenStrictModel

# 프로젝트 루트: PB/core/settings.py → 2단계 상위
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _load_yaml(profile: str) -> Dict[str, Any]:
    """config_{profile}.yaml 파일을 읽어 딕셔너리로 반환한다.

    파일이 없거나 비어있으면 빈 딕셔너리를 반환한다.
    """
    config_path = _PROJECT_ROOT / f"config_{profile}.yaml"
    if not config_path.is_file():
        return {}
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _resolve(yaml_cfg: Dict[str, Any], env_key: str, yaml_key: str, default: Any) -> Any:
    """환경변수 우선, YAML 폴백, 최종 기본값 순으로 설정값을 결정한다."""
    env_val = os.getenv(env_key)
    if env_val is not None:
        return env_val
    return yaml_cfg.get(yaml_key, default)


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "t", "yes", "y", "on"}
    return bool(value)


def _to_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


class Settings(FrozenStrictModel):
    profile: str
    app_name: str
    app_version: str
    debug: bool
    litellm_server_url: str
    llm_server_url: str
    llm_model_name: str
    llm_timeout_seconds: float
    intent_classification_enabled: bool
    default_scenario_id: int
    llm_caller_type: str
    openai_api_key: str
    mcp_stub_mode: bool
    mcp_server_url: str
    mcp_timeout_seconds: float


@lru_cache
def load_settings() -> Settings:
    """프로파일에 해당하는 YAML을 로드한 뒤, 환경변수로 덮어써서 Settings를 생성한다."""
    profile = os.getenv("APP_PROFILE", "dev").strip().lower()
    cfg = _load_yaml(profile)

    return Settings(
        profile=profile,
        app_name=str(_resolve(cfg, "APP_NAME", "app_name", "PB Backend")),
        app_version=str(_resolve(cfg, "APP_VERSION", "app_version", "0.1.0")),
        debug=_to_bool(_resolve(cfg, "APP_DEBUG", "debug", False)),
        litellm_server_url=str(_resolve(cfg, "LITELLM_SERVER_URL", "litellm_server_url", "http://172.17.102.34:8150/v1/chat/completions")),
        llm_server_url=str(_resolve(
            cfg, "LLM_SERVER_URL", "llm_server_url",
            "",
        )),
        llm_model_name=str(_resolve(cfg, "LLM_MODEL_NAME", "llm_model_name", "Qwen2.5-72B-Instruct")),
        llm_timeout_seconds=_to_float(
            _resolve(cfg, "LLM_TIMEOUT_SECONDS", "llm_timeout_seconds", 10.0), 10.0,
        ),
        intent_classification_enabled=_to_bool(
            _resolve(cfg, "INTENT_CLASSIFICATION_ENABLED", "intent_classification_enabled", True),
        ),
        default_scenario_id=_to_int(
            _resolve(cfg, "DEFAULT_SCENARIO_ID", "default_scenario_id", 19), 19,
        ),
        llm_caller_type=str(_resolve(cfg, "LLM_CALLER_TYPE", "llm_caller_type", "litellm")),
        openai_api_key=str(_resolve(cfg, "OPENAI_API_KEY", "openai_api_key", "")),
        mcp_stub_mode=_to_bool(_resolve(cfg, "MCP_STUB_MODE", "mcp_stub_mode", True)),
        mcp_server_url=str(_resolve(cfg, "MCP_SERVER_URL", "mcp_server_url", "")),
        mcp_timeout_seconds=_to_float(
            _resolve(cfg, "MCP_TIMEOUT_SECONDS", "mcp_timeout_seconds", 10.0), 10.0,
        ),
    )
