"""Staff co-pilot, compliance, fraud, and HITL queue endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from agents.orchestrator import run_orchestrator
from api.audit import list_hitl, resolve_hitl
from api.auth import TokenUser, require_staff
from api.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/staff", tags=["staff"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)
    mode: str = Field(
        default="auto",
        description="auto | compliance | fraud | copilot",
    )


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    intent: str | None = None
    route: str | None = None
    abstained: bool = False
    grounded: bool = False
    citations: list[str] = Field(default_factory=list)
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    require_hitl: bool = False
    hitl_id: str | None = None
    compliance_flags: list[str] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    trace: list[dict[str, Any]] = Field(default_factory=list)


class HITLResolveRequest(BaseModel):
    approve: bool
    notes: str = ""


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_dependency)])
async def staff_chat(
    body: ChatRequest,
    user: Annotated[TokenUser, Depends(require_staff)],
) -> ChatResponse:
    message = body.message
    if body.mode == "compliance":
        message = f"[compliance lookup] {message}"
    elif body.mode == "fraud":
        message = f"[fraud alert triage] {message}"
    elif body.mode == "copilot":
        message = f"[suggest response / co-pilot] {message}"

    result = await run_orchestrator(
        message=message,
        role="staff",
        staff_id=user.staff_id,
        session_id=body.session_id,
        history=body.history,
    )
    return ChatResponse(**result)  # type: ignore[arg-type]


@router.get("/hitl")
async def get_hitl_queue(
    user: Annotated[TokenUser, Depends(require_staff)],
    status: str | None = "pending",
) -> list[dict[str, Any]]:
    _ = user
    return list_hitl(status=status)


@router.post("/hitl/{item_id}/resolve")
async def resolve_hitl_item(
    item_id: str,
    body: HITLResolveRequest,
    user: Annotated[TokenUser, Depends(require_staff)],
) -> dict[str, Any]:
    try:
        return resolve_hitl(
            item_id,
            reviewer=user.username,
            approve=body.approve,
            notes=body.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
