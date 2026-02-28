# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI-based "master agent" that classifies user queries via LLM (vLLM/LiteLLM) into 19 business scenarios, then dispatches matching MCP tool calls over JSON-RPC 2.0. The main application code lives in the `PB/` package.

## Tech Stack

- **Python 3.10+** (uses `match/case`, `X | Y` unions)
- **FastAPI** (async) with **Uvicorn**
- **Pydantic v2** for all data validation
- **httpx** (async, connection-pooled) for HTTP calls
- **vLLM / LiteLLM** (OpenAI-compatible chat completions API) for intent classification
- **MCP** via JSON-RPC 2.0 over HTTP

## Commands

```bash
# Run the app
uvicorn PB.app:app --reload

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
  → MCPClient.invoke(scenario, user_input, context) → JSON-RPC to MCP server
  → QueryResponseDTO → JSON response
```

### Key Modules

- **`PB/app.py`** — FastAPI app factory, CORS, router mounting, shutdown hook
- **`PB/api/routes/query.py`** — Single endpoint `POST /api/v1/query`
- **`PB/api/dependencies.py`** — DI wiring via `@lru_cache` factory functions; settings, clients, and services are app-scoped singletons
- **`PB/services/intent_classifier.py`** — Wraps LLM call for intent classification; supports per-request model override (e.g., `provider: "chatgpt"`)
- **`PB/services/query_orchestrator.py`** — Orchestrates classify → scenario lookup → MCP invoke
- **`PB/core/vllm_client.py`** — `MasterAgentClient` handles LLM chat completion calls with retry (2x, 0.5s sleep)
- **`PB/core/mcp_client.py`** — `MCPClientProtocol` with two implementations: `StubMCPClient` (offline dev) and `JsonRpcMCPClient` (real)
- **`PB/core/mcp_adapters.py`** — Per-tool adapters that build typed argument payloads; registry maps tool names to adapters
- **`PB/core/requester.py`** — `HTTPClient` singleton managing the shared `httpx.AsyncClient` pool
- **`PB/core/settings.py`** — All config from env vars, frozen `Settings` model
- **`PB/constant/scenarios.py`** — Registry of 19 `ScenarioSpec` entries; scenario 19 = general chat/fallback
- **`PB/constant/classification_prompt.py`** — System prompt template for LLM classification
- **`PB/dto/base.py`** — Six Pydantic base classes (`FrozenStrictModel`, `StrictModel`, `AllowExtraModel`, etc.) with intentional ConfigDict combinations

### Adding a New MCP Tool

1. Add a `ScenarioSpec` entry in `PB/constant/scenarios.py` with `mcp_tool_name` set
2. Create a Pydantic arguments schema in `PB/dto/mcp_tool_schemas.py`
3. Create an adapter class in `PB/core/mcp_adapters.py` implementing `MCPToolAdapterProtocol`
4. Register the adapter in the `_default_tool_adapters()` list

## Configuration

All config is via environment variables (no YAML loading in PB module). Key variables:

| Variable | Default | Purpose |
|---|---|---|
| `VLLM_SERVER_URL` | `http://172.17.102.34:8150/v1/chat/completions` | vLLM endpoint |
| `LITELLM_SERVER_URL` | `""` | LiteLLM proxy (preferred over vLLM if set) |
| `VLLM_MODEL_NAME` | `Qwen2.5-72B-Instruct` | Default model |
| `MCP_STUB_MODE` | `true` | Use StubMCPClient (no real MCP calls) |
| `MCP_SERVER_URL` | `""` | MCP JSON-RPC server endpoint |
| `INTENT_CLASSIFICATION_ENABLED` | `true` | Toggle LLM classification |
| `DEFAULT_SCENARIO_ID` | `19` | Fallback scenario (general chat) |

## Testing Patterns

- Tests use FastAPI `TestClient` with `app.dependency_overrides` to swap the orchestrator
- External HTTP calls are intercepted by monkeypatching `post_json` at the module level
- `MCP_STUB_MODE=true` (default) allows the full stack to run without external services
- Three smoke tests cover: stub flow, real MCP with mocked HTTP, and LLM model override
