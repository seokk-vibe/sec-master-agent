from __future__ import annotations

from typing import Dict, Optional

from PB.dto.base import FrozenStrictModel


class ScenarioSpec(FrozenStrictModel):
    id: int
    name: str
    route_key: str
    description: Optional[str] = None
    mcp_tool_name: Optional[str] = None


DEFAULT_SCENARIO_ID = 19


def _scenario(
    scenario_id: int,
    name: str,
    route_key: str,
    description: Optional[str] = None,
    mcp_tool_name: Optional[str] = None,
) -> ScenarioSpec:
    return ScenarioSpec(
        id=scenario_id,
        name=name,
        route_key=route_key,
        description=description,
        mcp_tool_name=mcp_tool_name,
    )


_SCENARIOS = [
    _scenario(
        1,
        "계좌 권리현황",
        "account_rights",
        "계좌 권리 관련 조회",
        mcp_tool_name="getAcctRightsStatusTool",
    ),
    _scenario(
        2,
        "미수금 안내",
        "receivables",
        "미수금 관련 안내",
        mcp_tool_name="getUnsettledAmountTool",
    ),
    _scenario(
        3,
        "담보2부족 현황안내",
        "collateral_shortage",
        "담보 부족 현황 안내",
        mcp_tool_name="getCollateralShortageTool",
    ),
    # IF-SEC-API-006(O): 툴 단계형 인터페이스로 현재 연동 범위 제외
    _scenario(4, "미수동결 현황안내", "receivable_freeze", "미수동결 현황 안내"),
    _scenario(
        5,
        "자동이체 오류현황",
        "auto_transfer_error",
        "자동이체 오류 조회",
        mcp_tool_name="getAutoTransferErrorTool",
    ),
    # IF-SEC-API-010(O): 툴 단계형 인터페이스로 현재 연동 범위 제외
    _scenario(6, "신한플러스 등급 및 포인트 조회", "shinhan_plus_grade", "신한플러스 등급/포인트 조회"),
    _scenario(
        7,
        "이벤트 신청 및 당첨현황 안내",
        "event_status",
        "이벤트 신청/당첨 현황",
        mcp_tool_name="getEventStatusTool",
    ),
    _scenario(
        8,
        "이체수수료 무료 쿠폰 조회",
        "transfer_fee_coupon",
        "수수료 무료 쿠폰 조회",
        mcp_tool_name="getTransferFeeCouponTool",
    ),
    # IF-SEC-API-015(O): 툴 단계형 인터페이스로 현재 연동 범위 제외
    _scenario(9, "탑스클럽 등급 조회", "tops_club_grade", "탑스클럽 등급 조회"),
    _scenario(
        10,
        "중요알림",
        "important_notice",
        "중요 알림 조회",
        mcp_tool_name="getImportantNoticeTool",
    ),
    # IF-SEC-API-017(O): 툴 단계형 인터페이스로 현재 연동 범위 제외
    _scenario(11, "입출금내역(계좌선택)", "deposit_withdrawal_history", "입출금 내역 조회"),
    _scenario(
        12,
        "증시일정",
        "market_schedule",
        "증시 일정 조회",
        mcp_tool_name="getMarketScheduleTool",
    ),
    _scenario(
        13,
        "투자플러스(구 스톡마켓)",
        "investment_plus",
        "투자플러스 조회",
        mcp_tool_name="getInvestmentPlusTool",
    ),
    _scenario(
        14,
        "환율 조회",
        "exchange_rate",
        "환율 조회",
        mcp_tool_name="getExchangeRateTool",
    ),
    _scenario(
        15,
        "섹터정보 조회",
        "sector_info",
        "섹터 정보 조회",
        mcp_tool_name="getSectorinfoTool",
    ),
    _scenario(
        16,
        "유튜브 조회",
        "youtube_search",
        "유튜브 관련 조회",
        mcp_tool_name="getYoutubeTool",
    ),
    _scenario(
        17,
        "지점찾기",
        "branch_locator",
        "지점 위치 조회",
        mcp_tool_name="getBranchFinderTool",
    ),
    _scenario(
        18,
        "날씨 조회",
        "weather_lookup",
        "날씨 조회",
        mcp_tool_name="getWeatherTool",
    ),
    _scenario(
        19,
        "일반대화(FAQ) 및 Chiplist 대화",
        "general_chat",
        "FAQ/일반대화",
        mcp_tool_name="commonChatTool",
    ),
]

MAX_SCENARIO_ID: int = len(_SCENARIOS)

SCENARIO_REGISTRY: Dict[int, ScenarioSpec] = {scenario.id: scenario for scenario in _SCENARIOS}


def get_scenario_spec(scenario_id: int) -> ScenarioSpec:
    return SCENARIO_REGISTRY.get(scenario_id, SCENARIO_REGISTRY[DEFAULT_SCENARIO_ID])
