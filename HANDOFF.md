# HANDOFF — OpenAI SDK caller 추가 + 3-프로파일 설정 체계

## 작업 요약

외부망 개발 환경에서 LiteLLM 프록시 없이 OpenAI API를 직접 호출할 수 있도록 `openai` SDK 기반 caller를 추가했다.
설정 프로파일을 `ext`(외부망) / `dev`(내부망 개발) / `prd`(내부망 운영) 3개로 분리하고,
실제 설정 파일은 `.gitignore`로 제외하여 비밀값 유출을 방지한다.

## 변경된 파일

### 신규 파일
| 파일 | 설명 |
|------|------|
| `config_example.yaml` | 커밋되는 설정 템플릿 (비밀값 없음) |
| `config_ext.yaml` | 외부망 개발 설정 (`.gitignore`, 커밋 안 됨) |

### 수정된 파일
| 파일 | 변경 내용 |
|------|-----------|
| `requirements.txt` | `openai>=1.0.0` 추가 |
| `PB/core/llm_caller.py` | `LLMClassifierCallerProtocol` 추가, `parse_llm_classification_response()` 모듈 함수로 추출, `OpenAIClassifierCaller` 클래스 추가, 두 caller에 INFO/WARNING 로깅 추가 |
| `PB/core/settings.py` | `llm_caller_type`, `openai_api_key` 필드 추가 |
| `PB/api/dependencies.py` | `get_llm_classifier_caller()` 반환 타입 `LLMClassifierCallerProtocol`로 변경, `llm_caller_type`에 따라 OpenAI/LiteLLM caller 분기 |
| `PB/services/intent_classifier.py` | 타입힌트 `LLMClassifierCaller` → `LLMClassifierCallerProtocol` |
| `PB/app.py` | `PB` 네임스페이스 로거 설정 추가 (StreamHandler, debug 레벨 연동) |
| `PB/test/test_query_flow_smoke.py` | import 추가, 공유 파서 테스트 2개 + OpenAI caller mock 테스트 1개 추가 (총 6개) |
| `config_dev.yaml` | `llm_caller_type: "litellm"`, `openai_api_key: ""` 추가, git 추적 제거 |
| `config_prd.yaml` | `llm_caller_type: "litellm"`, `openai_api_key: ""` 추가 |
| `.gitignore` | `config_dev.yaml`, `config_ext.yaml`, `config_prd.yaml` 추가 |
| `CLAUDE.md` | 3-프로파일 체계, OpenAI SDK, 로깅, config_example.yaml 문서 반영 |

## 설정 프로파일 체계

| 프로파일 | 파일 | 용도 | `llm_caller_type` | 커밋 여부 |
|----------|------|------|--------------------|-----------|
| — | `config_example.yaml` | 템플릿 | `openai` | O |
| `ext` | `config_ext.yaml` | 외부망 개발 | `openai` | X |
| `dev` | `config_dev.yaml` | 내부망 개발 | `litellm` | X |
| `prd` | `config_prd.yaml` | 내부망 운영 | `litellm` | X |

새 환경 세팅: `cp config_example.yaml config_{profile}.yaml` 후 값 수정.

## 아키텍처 변경

### LLM Caller 이중화

```
LLMClassifierCallerProtocol (Protocol)
  ├── LLMClassifierCaller        — httpx/post_json 기반 (LiteLLM 프록시, 내부망)
  └── OpenAIClassifierCaller     — openai SDK 기반 (OpenAI API 직접, 외부망)
```

- 공유 파서 `parse_llm_classification_response()` — 두 caller 모두 동일 파싱 로직 사용
- `OpenAIClassifierCaller`는 `openai` 패키지를 `__init__`에서 lazy import → prd에서 미설치 시에도 모듈 로딩 정상

### DI 분기 (`dependencies.py`)

```python
if settings.llm_caller_type == "openai":
    return OpenAIClassifierCaller(...)
else:
    return LLMClassifierCaller(...)
```

## 테스트 결과

- `pytest PB/test/ -v` — 6개 테스트 모두 통과
- 실제 OpenAI API 호출 검증 완료 (`APP_PROFILE=ext`, gpt-4o-mini, scenario 분류 정상)

## 후속 작업 참고

- `config_prd.yaml`은 `.gitignore`에 추가했으나, 이미 이전 커밋에서 추적 중이므로 `git rm --cached config_prd.yaml`이 필요할 수 있음
- OpenAI SDK는 자체적으로 2회 자동 재시도 + 커넥션 풀링을 내장하고 있어, caller의 3회 재시도와 이중 보호됨
