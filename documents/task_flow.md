  흐름

  - FastAPI가 요청 수신: PB/app.py, PB/api/routes/query.py:34
  - 라우터가 오케스트레이터 호출: PB/services/query_orchestrator.py:29
  - 오케스트레이터가 LLM 분류 호출: PB/services/intent_classifier.py, PB/core/vllm_client.py
  - 분류 결과(ScenarioSpec)로 MCP 호출: PB/core/mcp_client.py:87
  - MCP 요청 인자 변환은 tool adapter가 담당: PB/core/mcp_adapters.py\

  코드 읽는 순서 (요청 -> 응답)

  1. 앱 진입점

  - PB/app.py:12 FastAPI 앱 생성
  - PB/app.py:26 /api prefix로 라우터 등록
  - PB/api/__init__.py:5 query_router 포함

  2. 실제 엔드포인트

  - PB/api/routes/query.py:34 POST /api/v1/query
  - PB/api/routes/query.py:36 요청 바디를 QueryRequestDTO로 파싱
  - 요청 DTO 정의는 PB/dto/schemas.py:40
  - MCP 컨텍스트 DTO는 PB/dto/schemas.py:22
  - userInfo DTO는 PB/dto/schemas.py:11

  3. 라우터에서 오케스트레이터 호출

  - PB/api/routes/query.py:39 request_id 생성
  - PB/api/routes/query.py:41 orchestrator.handle_query(...) 호출
  - PB/api/routes/query.py:43~PB/api/routes/query.py:49
      - 라우터 입력을 내부 context dict로 정리 (request_id, session_id, metadata, mcp)

  4. DI(의존성 주입)로 서비스 조립

  - PB/api/routes/query.py:37 Depends(get_query_orchestrator_service)
  - PB/api/dependencies.py:48 오케스트레이터 생성
  - PB/api/dependencies.py:39 분류 서비스 생성
  - PB/api/dependencies.py:28 MCP client 생성 (Stub vs JsonRpc)
  - PB/api/dependencies.py:31 MCP_STUB_MODE=true면 StubMCPClient
  - 설정 로딩은 PB/core/settings.py:50
  - 환경변수 플래그 정의는 PB/core/settings.py:62 (INTENT_CLASSIFICATION_ENABLED), PB/core/settings.py:64 (MCP_STUB_MODE)

  5. 오케스트레이터가 분류 + MCP 호출을 순서대로 수행

  - PB/services/query_orchestrator.py:26 handle_query(...)
  - PB/services/query_orchestrator.py:31 분류 호출
  - PB/services/query_orchestrator.py:32 scenario_id -> ScenarioSpec 매핑
  - PB/services/query_orchestrator.py:33 MCP 호출
  - 반환 타입은 PB/services/query_orchestrator.py:12 QueryOrchestratorResult (스키마 객체)

  6. 분류 단계 (LLM / fallback)

  - PB/services/intent_classifier.py:17 classify(...)
  - PB/services/intent_classifier.py:18 분류 비활성화면 default_scenario_id 바로 반환
  - PB/services/intent_classifier.py:21 활성화면 MasterAgentClient.classify_intent(...)
  - PB/core/vllm_client.py:61 vLLM 요청 payload 생성 후 전송
  - PB/core/vllm_client.py:95 요청 스키마 생성 (VLLMChatCompletionRequestOut)
  - PB/core/vllm_client.py:66 공통 post_json(...) 사용
  - PB/core/vllm_client.py:109 응답 파싱/시나리오 번호 추출
  - 실패 시 default 시나리오 fallback (PB/core/vllm_client.py:82)

  7. 시나리오 매핑 (업무 시나리오 -> route_key / MCP tool)

  - PB/constant/scenarios.py:35 시나리오 목록
  - PB/constant/scenarios.py:41 시나리오 1 -> getAcctRightsStatusTool
  - PB/constant/scenarios.py:48 시나리오 2 -> getUnsettledAmountTool
  - PB/constant/scenarios.py:72 get_scenario_spec(...)

  8. MCP 호출 단계 (공통 클라이언트 + 시나리오별 adapter)

  - PB/core/mcp_client.py:87 JsonRpcMCPClient.invoke(...)
  - PB/core/mcp_client.py:95 scenario.mcp_tool_name 없으면 unsupported_scenario
  - PB/core/mcp_client.py:105 MCP_SERVER_URL 없으면 not_configured
  - PB/core/mcp_client.py:114 adapter로 요청 인자 생성
  - PB/core/mcp_client.py:172 _build_arguments_for_scenario(...)
  - PB/core/mcp_client.py:180 get_tool_adapter(...)로 tool별 adapter 조회

  9. Adapter가 “시나리오별 입력 shape”를 만든다

  - PB/core/mcp_adapters.py:13 MCPToolAdapterProtocol
  - PB/core/mcp_adapters.py:47 시나리오 1 adapter (GetAcctRightsStatusToolAdapter)
  - PB/core/mcp_adapters.py:54 시나리오 2 adapter (GetUnsettledAmountToolAdapter)
  - PB/core/mcp_adapters.py:61 기본 registry 생성
  - PB/core/mcp_adapters.py:30 context["mcp"]에서 toolStepId/sessionKey/userInfo 추출
  - 요청 스키마 검증:
      - PB/dto/mcp_tool_schemas.py:49 GetAcctRightsStatusArgumentsIn
      - PB/dto/mcp_tool_schemas.py:62 GetUnsettledAmountArgumentsIn (003 shape 재사용)

  10. JSON-RPC payload 생성 + HTTP 전송 (공통 transport)

  - PB/core/mcp_client.py:191 _build_request_payload(...)
  - PB/dto/mcp_tool_schemas.py:69 JsonRpcToolCallParams
  - PB/dto/mcp_tool_schemas.py:74 JsonRpcToolCallRequest
  - PB/core/mcp_client.py:132 post_json(...) 전송
  - PB/core/requester.py:169 post_json(...)
  - PB/core/requester.py:147 send_request(...)
  - PB/core/requester.py:84 HTTPClient (공통 httpx.AsyncClient 풀)

  11. MCP 응답 정규화 (스키마 기반)

  - PB/core/mcp_client.py:160 _normalize_response(...) 호출
  - PB/core/mcp_client.py:225 JSON-RPC 응답 스키마 검증
  - PB/dto/mcp_tool_schemas.py:106 JsonRpcToolCallResponseOut
  - 오류 케이스도 상태값으로 통일:
      - http_error, transport_error, rpc_error, invalid_response_schema 등 (PB/dto/mcp_tool_schemas.py:113)
  - 최종 MCP 결과 스키마:
      - PB/dto/mcp_tool_schemas.py:129 MCPInvokeResultOut
      - PB/dto/mcp_tool_schemas.py:164 for_scenario(...) 팩토리로 기본 필드/규격 통일

  12. 라우터에서 최종 응답 DTO 구성

  - PB/api/routes/query.py:51 mcp_result (이제 dict가 아니라 스키마 객체)
  - PB/api/routes/query.py:53 QueryResponseDTO 생성
  - PB/dto/schemas.py:65 최종 응답 DTO 구조
  - PB/api/routes/query.py:62 MCPInvocationResultDTO.payload=mcp_result

  13. 종료 시 HTTP 풀 정리

  - PB/app.py:34 shutdown hook
  - PB/core/requester.py:141 HTTPClient.close_client()


 요약 (한 줄로)

  - FastAPI가 QueryRequestDTO로 입력 검증 -> QueryOrchestratorService가 LLM 분류 -> ScenarioSpec 조회 -> MCP adapter가 시나리오별 요청 인자 생성 -> JsonRpcMCPClient가 공통 JSON-RPC 호출/정규화 -> QueryResponseDTO로 응답 반환.
