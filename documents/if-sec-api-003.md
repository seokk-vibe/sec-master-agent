Interface ID	getAcctRightsStatusTool			Interface 명		계좌 권리현황	
설명	계좌 권리현황 						
Interface구분	MCP			포트			
요청포맷	JSON-RPC			서버 응담 포맷		JSON-RPC	
구분	TYPE	항목명	항목설명	필수여부	타입(길이)	길이	비고
Request	body	jsonrpc	프로토콜 버전	Y	String		2.0
    body	method	method	Y	String		mcp 표준 고정
    body	id	id	Y	String		mcp에서 채번
    body	params		Y	Object		툴 호출 시 전달 인자값
    body	    name	툴 고유 이름	Y	String		getAcctRightsStatusTool
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


request 예시
{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "id": "7a1ccb13-4",
    "params": {
        "name": "getAcctRightsStatusTool",
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

response 예시
{
    "jsonrpc": "2.0",
    "id": "7a1ccb13-4",
    "result": {
        "content": [{
                "type": "text",
                "text": "{\"type\":\"dynamic\",\"data\":[{\"templateCode\":\"textSimple\",\"data\":{\"message\":\"계좌권리사항이 없어요.\"}}]}"
            }
        ],
        "isError": false,
        "structuredContent": {
            "type": "dynamic",
            "data": [{
                    "templateCode": "textSimple",
                    "data": {
                        "message": "계좌권리사항이 없어요."
                    }
                }
            ]
        },
        "_meta": {
            "sessionKey": "gw1_web0d7907e034c97a919dce4cdcc0910",
            "isFinished": true,
            "toolName": "getAcctRightsStatusTool"
        }
    }
}


답변템플릿 : 권한 형식 발생
{
    "type": "dynamic",
    "data": [{
            "templateCode": "textSimple",
            "data": {
                "message": "총 2건의 계좌권리가 발생했어요!"
            }
        }, {
            "templateCode": "slideBox",
            "moreData": {
                "autoMore": "auto",
                "displayText": "계좌권리현황 더 보기",
                "link": {
                    "web": "ns://7600_ap7600M00"
                }
            },
            "data": [{
                    "templateCode": "cardInfo",
                    "data": {
                        "title": "권리발생",
                        "tableData": {
                            "계좌번호": "012-34-***890",
                            "발생종목": "stbd_nm (rght_tp_nm)",
                            "세부정보": "rght_detl_tp_nm"
                        },
                        "buttons": [{
                                "displayText": "계좌권리현황 확인하기",
                                "type": "link",
                                "link": {
                                    "web": "ns://7600_ap7600M00"
                                }
                            }
                        ]
                    }
                }, {
                    "templateCode": "cardInfo",
                    "data": {
                        "title": "권리발생",
                        "tableData": {
                            "계좌번호": "012-34-***890",
                            "발생종목": "stbd_nm2 (rght_tp_nm2)",
                            "세부정보": "rght_detl_tp_nm2"
                        },
                        "buttons": [{
                                "displayText": "계좌권리현황 확인하기",
                                "type": "link",
                                "link": {
                                    "web": "ns://7600_ap7600M00"
                                }
                            }
                    }
                }
        }
}

답변 템플릿 : 에러
{ 
    "templateCode": "textSimple",
    "data": {
        "message": "잠시 후 다시 시도해주세요"
    }
}

답변 템플릿 : 권리 발생 없을 시
{
    "type": "dynamic",
    "data": [{
            "templateCode": "textSimple",
            "data": {
                "message": "계좌권리사항이 없어요."
            }
        }
    ]
}