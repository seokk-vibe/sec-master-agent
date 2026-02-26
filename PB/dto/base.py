from __future__ import annotations

from pydantic import BaseModel, ConfigDict

"""
`PB` 전역에서 사용하는 Pydantic 공통 베이스 모델.

팀 규칙:
- 데이터/DTO/값 객체는 각 모델마다 `model_config = ConfigDict(...)`를 반복하기보다
  이 공통 베이스를 우선 사용한다.
- 동작/전략/서비스 클래스(예: adapter, client, service)는 스키마 검증이 실제로
  필요하지 않으면 일반 Python 클래스로 유지한다.

선택 기준:
- `FrozenStrictModel`
  : 불변 설정/값 객체 (예: settings, registry item, 결과 래퍼)
- `StrictModel`
  : 알 수 없는 필드를 거부해야 하는 요청/명령 payload
- `PopulateByNameModel`
  : snake_case / camelCase alias 입력을 유연하게 받는 DTO
- `StrictPopulateByNameModel`
  : alias 입력 허용 + 알 수 없는 필드 거부
- `AllowExtraModel`
  : 외부 응답처럼 provider가 필드를 추가할 수 있는 모델
- `AllowExtraPopulateByNameModel`
  : alias 입력 허용 + 외부 추가 필드 허용
"""


class FrozenStrictModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PopulateByNameModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class StrictPopulateByNameModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AllowExtraModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AllowExtraPopulateByNameModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
