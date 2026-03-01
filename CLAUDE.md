# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI-based "master agent" that classifies user queries via LLM (LiteLLM/OpenAI-compatible) into 19 business scenarios, then dispatches matching MCP tool calls over JSON-RPC 2.0. The main application code lives in the `PB/` package.

## Tech Stack

- **Python 3.10+** (uses `match/case`, `X | Y` unions)
- **FastAPI** (async) with **Uvicorn**
- **Pydantic v2** for all data validation
- **httpx** (async, connection-pooled) for HTTP calls
- **LiteLLM** (OpenAI-compatible chat completions API) for intent classification (internal)
- **OpenAI SDK** (`openai>=1.0.0`, optional) for direct OpenAI API calls (external dev)
- **MCP** via JSON-RPC 2.0 over HTTP
- **PyYAML** for YAML config loading

## Commands

```bash
# Run the app (dev profile, default)
uvicorn PB.app:app --reload

# Run the app (ext profile, external network with OpenAI)
APP_PROFILE=ext OPENAI_API_KEY=sk-... uvicorn PB.app:app --reload

# Run the app (prd profile)
APP_PROFILE=prd uvicorn PB.app:app

# Run tests
pytest PB/test/

# Run a single test
pytest PB/test/test_query_flow_smoke.py::test_stub_flow_returns_stubbed_result -v
```

## Architecture

### Request Flow

```
POST /api/v1/query
  → QueryRequestDTO validation (Pydantic)
  → IntentClassifierService.classify() → LLM call → scenario_id (1-19)
  → get_scenario_spec(scenario_id) → ScenarioSpec from registry
  → MCPCaller.invoke(scenario, user_input, context) → JSON-RPC to MCP server
  → QueryResponseDTO → JSON response
```

### Key Modules

- **`PB/app.py`** — FastAPI app factory, CORS, router mounting, shutdown hook
- **`PB/api/routes/query.py`** — Single endpoint `POST /api/v1/query`
- **`PB/api/dependencies.py`** — DI wiring via `@lru_cache` factory functions; settings, callers, and services are app-scoped singletons
- **`PB/services/intent_classifier.py`** — Wraps LLM call for intent classification; supports per-request model override (e.g., `provider: "chatgpt"`)
- **`PB/services/query_orchestrator.py`** — Orchestrates classify → scenario lookup → MCP invoke
- **`PB/core/llm_caller.py`** — `LLMClassifierCallerProtocol` + two implementations: `LLMClassifierCaller` (httpx/LiteLLM) and `OpenAIClassifierCaller` (openai SDK); shared parser `parse_llm_classification_response`
- **`PB/core/mcp_caller.py`** — `MCPCallerProtocol` with two implementations: `StubMCPCaller` (offline dev) and `JsonRpcMCPCaller` (real)
- **`PB/core/mcp_adapters.py`** — Per-tool adapters that build typed argument payloads; registry maps tool names to adapters
- **`PB/core/requester.py`** — `HTTPClient` singleton managing the shared `httpx.AsyncClient` pool
- **`PB/core/settings.py`** — YAML(`config_{profile}.yaml`) + env var override, frozen `Settings` model
- **`PB/constant/scenarios.py`** — Registry of 19 `ScenarioSpec` entries; scenario 19 = general chat/fallback
- **`PB/constant/classification_prompt.py`** — System prompt template for LLM classification
- **`PB/dto/base.py`** — Six Pydantic base classes (`FrozenStrictModel`, `StrictModel`, `AllowExtraModel`, etc.) with intentional ConfigDict combinations

### Adding a New MCP Tool

1. Add a `ScenarioSpec` entry in `PB/constant/scenarios.py` with `mcp_tool_name` set
2. Create a Pydantic arguments schema in `PB/dto/mcp_tool_schemas.py`
3. Create an adapter class in `PB/core/mcp_adapters.py` implementing `MCPToolAdapterProtocol`
4. Register the adapter in the `_default_tool_adapters()` list

## Configuration

Config is loaded from `config_{profile}.yaml` with environment variables taking priority. The resolution order per setting is:

```
환경변수 (env var)  →  YAML 값  →  하드코딩 기본값
    (최우선)          (중간)        (최후 폴백)
```

### Profile

| Variable | Default | Purpose |
|---|---|---|
| `APP_PROFILE` | `dev` | Selects `config_{profile}.yaml` (`ext`, `dev`, `prd`) |

### Config files

- **`config_ext.yaml`** — 외부망 개발 환경 (`debug: true`, `mcp_stub_mode: true`, `llm_caller_type: openai`, OpenAI SDK 직접 호출)
- **`config_dev.yaml`** — 내부망 개발 환경 (`debug: true`, `mcp_stub_mode: true`, `llm_caller_type: litellm`, LLM direct via `llm_server_url`)
- **`config_prd.yaml`** — 내부망 운영 환경 (`debug: false`, `mcp_stub_mode: false`, `llm_caller_type: litellm`, LiteLLM proxy via `litellm_server_url`, `llm_timeout: 30s`)

### Environment variable overrides

Any setting in the YAML can be overridden by the corresponding environment variable:

| Env Variable | YAML Key | Default (dev) | Purpose |
|---|---|---|---|
| `APP_NAME` | `app_name` | `PB Backend` | Application name |
| `APP_VERSION` | `app_version` | `0.1.0` | Application version |
| `APP_DEBUG` | `debug` | `true` (dev) / `false` (prd) | Debug mode |
| `LITELLM_SERVER_URL` | `litellm_server_url` | `""` (dev) | LiteLLM proxy endpoint (preferred over LLM_SERVER_URL if set) |
| `LLM_SERVER_URL` | `llm_server_url` | `http://...:8150/v1/chat/completions` (dev) | Direct LLM endpoint |
| `LLM_MODEL_NAME` | `llm_model_name` | `Qwen2.5-72B-Instruct` | Default model |
| `LLM_TIMEOUT_SECONDS` | `llm_timeout_seconds` | `10.0` (dev) / `30.0` (prd) | LLM request timeout |
| `INTENT_CLASSIFICATION_ENABLED` | `intent_classification_enabled` | `true` | Toggle LLM classification |
| `DEFAULT_SCENARIO_ID` | `default_scenario_id` | `19` | Fallback scenario (general chat) |
| `LLM_CALLER_TYPE` | `llm_caller_type` | `"openai"` (ext) / `"litellm"` (dev, prd) | LLM caller implementation (`"litellm"` or `"openai"`) |
| `OPENAI_API_KEY` | `openai_api_key` | `""` | OpenAI API key (empty → env var `OPENAI_API_KEY` auto-detect) |
| `MCP_STUB_MODE` | `mcp_stub_mode` | `true` (dev) / `false` (prd) | Use StubMCPCaller (no real MCP calls) |
| `MCP_SERVER_URL` | `mcp_server_url` | `""` | MCP JSON-RPC server endpoint |
| `MCP_TIMEOUT_SECONDS` | `mcp_timeout_seconds` | `10.0` | MCP request timeout |

## Testing Patterns

- Tests use FastAPI `TestClient` with `app.dependency_overrides` to swap the orchestrator
- External HTTP calls are intercepted by monkeypatching `post_json` at the module level
- `MCP_STUB_MODE=true` (default in dev) allows the full stack to run without external services
- Smoke tests cover: stub flow, scenario 2 stub mode, LLM model override, shared parser, and OpenAI caller mock
