from __future__ import annotations

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from PB.api.dependencies import get_query_orchestrator_service
from PB.dto.schemas import (
    ClassificationResultDTO,
    MCPInvocationResultDTO,
    QueryRequestDTO,
    QueryResponseDTO,
)
from PB.services.query_orchestrator import QueryOrchestratorService

router = APIRouter(prefix="/v1", tags=["query"])


def _model_dump_safe(model: Optional[BaseModel]) -> dict:
    if model is None:
        return {}
    return model.model_dump(exclude_none=True)


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/query", response_model=QueryResponseDTO)
async def classify_and_route_query(
    body: QueryRequestDTO,
    orchestrator: QueryOrchestratorService = Depends(get_query_orchestrator_service),
) -> QueryResponseDTO:
    request_id = str(uuid4())

    result = await orchestrator.handle_query(
        user_input=body.user_input,
        context={
            "request_id": request_id,
            "user_id": body.user_id,
            "session_id": body.session_id,
            "metadata": body.metadata,
            "classifier": _model_dump_safe(body.classifier),
        },
    )
    mcp_result = result.mcp_result

    return QueryResponseDTO(
        request_id=request_id,
        user_input=body.user_input,
        classification=ClassificationResultDTO(
            scenario_id=result.scenario.id,
            scenario_name=result.scenario.name,
            route_key=result.scenario.route_key,
            description=result.scenario.description,
        ),
        mcp=MCPInvocationResultDTO(
            payload=mcp_result,
        ),
    )
