# MCP Adapter Architecture (PB)

## 목적

`mcp_client` 안에 시나리오별 분기(`if tool == ...`)가 쌓이지 않도록,
공통 JSON-RPC 호출 로직과 툴별 데이터 변환 로직을 분리하기 위한 구조를 정의한다.

핵심 목표:

- 공통 클라이언트(`PB/core/mcp_client.py`)는 HTTP/JSON-RPC 전송과 공통 에러 처리만 담당
- 시나리오/툴별 요청/응답 규격 차이는 별도 모듈에서 관리
- 스키마(Pydantic)를 기준으로 in/out 규격을 검증


## `adapter` 이란?

이 문맥에서 `adapter`는 "툴별 데이터 변환기"를 뜻한다.

- encode: 내부 `context` -> 툴별 `arguments` 스키마
- decode: (향후 확장) 툴 응답 -> 시나리오별 구조화 응답 스키마/도메인 객체

원래 용어는 `coder/decoder`에서 왔고, 여기서는 요청/응답 양쪽 변환 계층 의미로 사용한다.

참고:
- 이름이 낯설면 `adapter`, `mapper`, `translator`로 바꿔도 구조는 동일하다.


## 왜 도입했나

기존 문제:

- `mcp_client` 내부에 시나리오별 요청 조립 로직이 직접 들어감
- 시나리오 추가 시 `mcp_client` 본체를 계속 수정해야 함
- 문서와 실제 규격이 약간만 달라도 분기/예외가 빠르게 복잡해짐

도입 후 장점:

- `mcp_client`는 공통 전송 계층으로 유지
- 툴 추가 시 스키마 + adapter 등록만 하면 됨
- 규격 검증 실패가 Pydantic 단계에서 일관되게 처리됨


## 현재 구성 요소

### 1) 공통 클라이언트

- `PB/core/mcp_client.py`

역할:

- JSON-RPC request envelope 생성
- HTTP 요청 전송 (`PB/core/requester.py`의 공통 transport 사용)
- 공통 응답 파싱 / 에러 처리
- 최종 `MCPInvokeResultOut` 반환


### 2) 툴별 adapter 레지스트리

- `PB/core/mcp_adapters.py`

역할:

- `tool_name -> adapter` 매핑 관리
- 각 adapter가 `context`를 받아 툴별 `arguments` 스키마를 생성

현재 구현:

- `GetAcctRightsStatusToolAdapter` (if-sec-api-003 / 시나리오 1)
- `GetUnsettledAmountToolAdapter` (if-sec-api-004 / 시나리오 2)
- 내부 공통 구현: `_CommonUserInfoToolAdapterBase`
  - `toolStepId`, `sessionKey`, `userInfo` 형태를 사용하는 MCP tool 공통 로직


### 3) 스키마 정의

- `PB/dto/mcp_tool_schemas.py`

역할:

- 툴별 요청 스키마 (`GetAcctRightsStatusArgumentsIn`, `GetUnsettledAmountArgumentsIn`)
- 공통 JSON-RPC 요청/응답 스키마
- 공통 MCP 호출 결과 스키마 (`MCPInvokeResultOut`)


## 현재 등록된 툴

- `getAcctRightsStatusTool` (시나리오 1: 계좌 권리현황)
- `getUnsettledAmountTool` (시나리오 2: 미수금 안내)

둘 다 현재 문서 기준 요청 shape가 동일하여 내부적으로 `_CommonUserInfoToolAdapterBase` 공통 로직을 재사용한다.


## 데이터 흐름 (요청 기준)

1. API 요청 수신 (`/api/v1/query`)
2. 분류 결과로 `ScenarioSpec` 결정
3. `JsonRpcMCPClient.invoke(...)`
4. `scenario.mcp_tool_name`으로 adapter lookup
5. adapter가 `context["mcp"]` -> 툴별 `arguments` 스키마 생성/검증
6. `mcp_client`가 JSON-RPC envelope 생성 및 전송
7. 응답을 공통 스키마로 파싱
8. `MCPInvokeResultOut` 반환


## 새 시나리오(MCP tool) 추가 절차

1. 인터페이스 문서 확인

- 툴명(`params.name`)
- 요청 `arguments` 필드 구조
- 응답 템플릿/메타 구조

2. `ScenarioSpec`에 `mcp_tool_name` 연결

- 파일: `PB/constant/scenarios.py`

3. 요청 스키마 추가

- 파일: `PB/dto/mcp_tool_schemas.py`
- 기존 스키마와 shape가 같으면 상속/재사용 가능

4. adapter 등록

- 파일: `PB/core/mcp_adapters.py`
- 기존 `_CommonUserInfoToolAdapterBase` 공통 로직을 재사용할 수 있으면 툴별 명시 adapter 클래스를 추가
- shape가 다르면 새 adapter 클래스 추가

5. (권장) 응답 스키마 추가

- 템플릿이 고정적이면 `structured_content`를 시나리오별 스키마로 분리


## 언제 새 adapter가 필요한가

다음 중 하나라도 해당되면 새 adapter 클래스 분리 권장:

- `arguments` 필드 구조가 다름 (예: `userInfo` 외 추가 필수 필드)
- 필드 값 전처리 규칙이 다름
- 컨텍스트 소스가 다름 (`context.metadata`, `session` 등)
- 요청 유효성 검증 규칙이 툴마다 크게 다름


## 현재 구조의 한계 / 다음 개선점

현재는 요청쪽 adapter 분리가 중심이고,
응답 `structured_content` 상세 타입은 일부 `Dict[str, Any]`로 유지 중이다.

다음 단계:

- 시나리오별 응답 decoder(adapter의 decode 파트) 추가
- `structured_content` 템플릿별 스키마 정의
- fixture 기반 테스트 추가 (success / rpc_error / invalid schema)
