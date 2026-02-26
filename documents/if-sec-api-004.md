Interface ID	getUnsettledAmountTool			Interface 명		미수금 안내	
설명	미수금 안내						
Interface구분	MCP			포트			
요청포맷	JSON-RPC			서버 응담 포맷		JSON-RPC	
구분	TYPE	항목명	항목설명	필수여부	타입(길이)	길이	비고
Request	body	jsonrpc	프로토콜 버전	Y	String		2.0
    body	method	method	Y	String		mcp 표준 고정
    body	id	id	Y	String		mcp에서 채번
    body	params	params	Y	Object		툴 호출 시 전달 인자값
    body	    name	툴 고유 이름	Y	String		getUnsettledAmountTool
    body	    toolStepId	툴 단계 정보	Y	String		"최초 호출 시 1로 세팅한다.

최초 이후부터는 응답의 nextToolStepId를 세팅한다."
    body	    sessionKey	봇 대화세션키	N	String		"최초 호출 후 답변에 sessionKey가 리턴 되며, 
다음 거래부터는 sessionKey를 필수로 입력한다."
    body	    userInfo	사용자 정보	Y	Object		MTS 로그인 시 봇엔진으로 전달되는 사용자 정보
    body	        gpsX	사용자 위치 정보(위도)	N	String		MTS 에서 전달하는 인자값
    body	        gpsY	사용자 위치 정보(경도)	N	String		MTS 에서 전달하는 인자값
    body	        loginLevel	loginLevel	N	String		MTS 에서 전달하는 인자값
    body	        mediaType	mediaType	N	String		MTS 에서 전달하는 인자값
    body	        qust	qust	N	String		MTS 에서 전달하는 인자값
    body	        cybid	사이버 ID	N	String		MTS 에서 전달하는 인자값
    body	        udid	udid	Y	String		MTS 에서 전달하는 인자값
    body	        token	token	Y	String		MTS 에서 전달하는 인자값

Request 예시
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": "7a1ccb13-4",
    "params": {
        "name": "getUnsettledAmountTool",
        "arguments": {
            "toolStepId": "1",
            "sessionKey": "",
            "userInfo": {
                "gpsX": "37.567787",
                "gpsY": "126.983757",
                "loginLevel": "2",
                "mediaType": "3b",
                "qust": "",
                "cybid": "TEST",
                "udid": "1DDFC6B1%2DEF27%2D47CB%2D9F7A%2DE7328657B1DD",
                "token": "20251215134137861928201IBULR9FF9TR5BJUCGJ5YLYMQ0BA4WEH6AV1FZW4R24Q6J5Z3MSGE1NSIM5QNNXMKOSLAFZ4JOV453"
            }
        }
    }
}


Response	body	jsonrpc	프로토콜 버전	Y	String		2.0
    body	id	MCP 거래 고유 아이디	Y	String		요청 시 받은 ID를 그대로 전달한다.
    body	result	결과 데이터	Y	String		툴 호출 결과
    body	    content	mcp 컨텐츠	Y	Array		LLM에게 보여줄 데이터 리스트
    body	        type	mcp 컨텐츠 타입	Y	String		데이터의 종류, text(글자)만 지원
    body	        text	답변 데이터 (jsonString)	Y	String		답변 템플릿, jsonString 포멧으로 전달
    body	    isError	답변 성공실패 여부	Y	Boolean		답변 성공실패 여부
    body	    structuredContent	답변 데이터 (json)	Y	Object		답변 템플릿, json 포멧으로 전달
    body	    _meta	메타데이터	Y	Object		세션키 및 툴 상태 정보
    body	        sessionKey	대화세션키	Y	String		다음 툴 호출 시 세션키를 세팅하여 전달한다.
    body	        isFinished	시나리오 종료여부	Y	Boolean		시나리오 종료여부
    body	        toolName	툴이름	Y	String		현재 호출 tool 정보
    body	        nextToolStepId	시나리오 다음 단계	N	String		다음 시나리오 단계가 존재할 경우

    Response 예시
    {
    "jsonrpc": "2.0",
    "id": "7a1ccb13-4",
    "result":
    {
        "content": [{
                "type": "text",
                "text": "{\"type\":\"dynamic\",\"data\":[{\"templateCode\":\"textSimple\",\"data\":{\"message\":\"미수금이 발생된 계좌가 없어요.\"}},{\"templateCode\":\"textSimple\",\"data\":{\"message\":\"미수금이 생겼을 때 변제하는 방법을 알려드릴게요. \\n\\n미수 발생 당일 오후까지 미수금이 변제되지않\\n으면 16:10분경에 익일반대매매 SMS를 발송\\n하며, 발생일 당일까지 미수금 변제가 되어야 합니다.\\n\\n① 반대매매와 미수 동결을 막기 위한 경우\\n- 미수금액(마이너스 금액)이 발생한 결제 당일 22시 전까지 현금 입금\\n\\n② 반대매매만 막는 경우(미수동결과 연체료 발생)\\n- 결제일 현금 입금이 아닌 주식 매도로 변제 (전일/당일 매도에 따라 반대매매 여부 달라짐)\\n\\n※ 제휴은행계좌의 입금방법\\n- 예수금방식 : 증권계좌와 연결된 은행계좌에 입금\\n- 이체방식 : [은행연계 계좌이체]의 (은행-&gt;당사)메뉴를 통한 이체\\n\\n※ 잔고의 D 예수금, D+1 예수금, D+2 예수금을 확인해 보세요.\",\"buttons\":[{\"displayText\":\"미수 사용신청\",\"type\":\"link\",\"link\":{\"web\":\"ns://8365_ap8365M00\"}},{\"displayText\":\"국내주식 잔고\",\"type\":\"link\",\"link\":{\"web\":\"ns://4100_az4700M00\"}}]}},{\"templateCode\":\"chipList\",\"data\":[{\"displayText\":\"미수거래 정의\",\"type\":\"query\",\"suggestion\":{\"suggestionType\":\"INTENT\",\"source\":\"미수거래 정의\",\"target\":\"91313\"}},{\"displayText\":\"반대매매 정의\",\"type\":\"query\",\"suggestion\":{\"suggestionType\":\"INTENT\",\"source\":\"반대매매 정의\",\"target\":\"91095\"}},{\"displayText\":\"연체이자율\",\"type\":\"query\",\"suggestion\":{\"suggestionType\":\"INTENT\",\"source\":\"연체이자율\",\"target\":\"91301\"}},{\"displayText\":\"미수 사용 설정\",\"type\":\"query\",\"suggestion\":{\"suggestionType\":\"INTENT\",\"source\":\"미수 사용 설정\",\"target\":\"91309\"}},{\"displayText\":\"입금 방법\",\"type\":\"query\",\"suggestion\":{\"suggestionType\":\"INTENT\",\"source\":\"입금 방법\",\"target\":\"91387\"}}]}]}"
            }
        }
    }