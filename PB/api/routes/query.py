from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends

from PB.api.dependencies import get_query_orchestrator_service
from PB.dto.schemas import (
    ClassificationResultDTO,
    MCPInvocationResultDTO,
    QueryRequestDTO,
    QueryResponseDTO,
)
from PB.services.query_orchestrator import QueryOrchestratorService

router = APIRouter(prefix="/v1", tags=["query"])


def _model_dump_safe(model: object) -> dict:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)  # pydantic v2
    if hasattr(model, "dict"):
        return model.dict(exclude_none=True)  # pydantic v1 fallback
    return {}


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
            "mcp": _model_dump_safe(body.mcp),
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
            interface_ready=mcp_result.interface_ready,
            route_key=mcp_result.route_key,
            status=mcp_result.status,
            payload=mcp_result,
        ),
    )
