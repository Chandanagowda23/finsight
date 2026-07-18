"""Customer-facing chat & account endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from agents.orchestrator import run_orchestrator
from api.auth import TokenUser, require_customer
from api.rate_limit import rate_limit_dependency

router = APIRouter(prefix="/customer", tags=["customer"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    history: list[dict[str, str]] = Field(default_factory=list)


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
    trace: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(rate_limit_dependency)])
async def customer_chat(
    body: ChatRequest,
    user: Annotated[TokenUser, Depends(require_customer)],
) -> ChatResponse:
    result = await run_orchestrator(
        message=body.message,
        role="customer",
        customer_id=user.customer_id,
        session_id=body.session_id,
        history=body.history,
    )
    return ChatResponse(**result)  # type: ignore[arg-type]
