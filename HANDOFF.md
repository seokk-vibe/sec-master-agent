# HANDOFF — QueryRequestDTO mcp 제거 + vllm → llm 리네이밍

## 작업 요약

클라이언트 요청 DTO에서 MCP 내부 구현 세부사항을 제거하고, vLLM 네이밍을 일반적인 LLM 네이밍으로 정리했다.

## 변경된 파일

### MCP 필드 제거
| 파일 | 변경 내용 |
|------|-----------|
| `PB/dto/schemas.py` | `MCPUserInfoDTO`, `MCPRequestContextDTO` 클래스 삭제, `QueryRequestDTO.mcp` 필드 삭제 |
| `PB/api/routes/query.py` | context 딕셔너리에서 `"mcp"` 항목 제거 |

### 파일 리네이밍
| Before | After |
|--------|-------|
| `PB/core/vllm_client.py` | `PB/core/llm_client.py` |
| `PB/dto/vllm_schemas.py` | `PB/dto/llm_schemas.py` |

### 클래스/변수 리네이밍
| Before | After |
|--------|-------|
| `MasterAgentClient` | `LLMClassifierClient` |
| `VLLMChatMessage` | `ChatMessage` |
| `VLLMChatCompletionRequestOut` | `ChatCompletionRequestOut` |
| `VLLMResponseMessageOut` | `ChatResponseMessageOut` |
| `VLLMChoiceOut` | `ChatChoiceOut` |
| `VLLMChatCompletionResponseOut` | `ChatCompletionResponseOut` |
| `get_master_agent_client()` | `get_llm_classifier_client()` |
| `_vllm_client` | `_llm_client` |
| `vllm_client=` (param) | `llm_client=` (param) |

### Settings 환경변수 리네이밍
| Before | After |
|--------|-------|
| `VLLM_SERVER_URL` | `LLM_SERVER_URL` |
| `VLLM_MODEL_NAME` | `LLM_MODEL_NAME` |
| `VLLM_TIMEOUT_SECONDS` | `LLM_TIMEOUT_SECONDS` |

### 참조 업데이트
| 파일 | 변경 내용 |
|------|-----------|
| `PB/core/settings.py` | `vllm_server_url` → `llm_server_url`, `vllm_model_name` → `llm_model_name`, `vllm_timeout_seconds` → `llm_timeout_seconds` |
| `PB/api/dependencies.py` | import 경로 + 함수명 + 파라미터명 업데이트 |
| `PB/services/intent_classifier.py` | import 경로 + `_vllm_client` → `_llm_client` |
| `PB/test/test_query_flow_smoke.py` | import 업데이트, 요청 JSON에서 `mcp` 블록 제거, scenario 2 테스트를 stub 모드로 변경, monkeypatch 경로 `PB.core.llm_client.post_json`으로 변경 |
| `CLAUDE.md` | vllm_client → llm_client 문서 반영 |

## 삭제된 파일
- `PB/core/vllm_client.py`
- `PB/dto/vllm_schemas.py`

## 테스트 결과
- `pytest PB/test/ -v` — 3개 smoke test 모두 통과
- `from PB.core.llm_client import LLMClassifierClient` — 정상
- `from PB.app import app` — 정상

## 후속 작업 참고
- `PB/core/mcp_adapters.py`의 `_CommonUserInfoToolAdapterBase.build_arguments()`는 여전히 `context["mcp"]`에서 `userInfo`를 읽는다. 클라이언트 요청에서 mcp를 제거했으므로, 실제 MCP 호출 시 `userInfo`를 서버 내부에서 주입하는 로직이 필요하다.
- `litellm_server_url` 필드명은 기존 유지 (LiteLLM은 별도 프록시 서비스를 가리키므로 구분이 필요)
