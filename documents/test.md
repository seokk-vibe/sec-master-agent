
  직접 테스트할 때 팁

  - 구조만 확인하려면:
      - INTENT_CLASSIFICATION_ENABLED=false
      - DEFAULT_SCENARIO_ID=2
      - MCP_STUB_MODE=false
      - MCP_SERVER_URL=http://127.0.0.1:1 (없는 주소)
  - 이러면 실제 MCP는 실패해도 request_payload에 getUnsettledAmountTool이 생성됐는지 바로 볼 수 있음.


pytest -q PB/test/test_query_flow_smoke.py


INTENT_CLASSIFICATION_ENABLED=false \                      
  DEFAULT_SCENARIO_ID=2 \
  MCP_STUB_MODE=false \
  MCP_SERVER_URL=http://127.0.0.1:1 \
  MCP_TIMEOUT_SECONDS=0.2 \
  uvicorn PB.app:app --reload



  curl -s http://127.0.0.1:8000/api/v1/query \
    -H 'Content-Type: application/json' \
    -d '{
      "user_input":"미수금 알려줘",
      "mcp":{
        "userInfo":{
          "udid":"TEST-UDID",
          "token":"TEST-TOKEN"
        }
      }
    }'