"""FinSight FastAPI gateway — auth, rate limit, customer + staff routers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.audit import get_engine
from api.auth import TokenUser, authenticate, create_access_token, get_current_user
from api.config import get_settings
from api.routers import customer, staff
from observability.langfuse_setup import init_observability
from retrieval.ingest import ingest

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_engine()
    init_observability()
    try:
        n = ingest(reset=True)
        log.info("startup_ingest", chunks=n)
    except Exception as e:
        log.warning("startup_ingest_failed", error=str(e))
    yield


app = FastAPI(
    title="FinSight API",
    description="Multi-Agent RAG Platform for Banking — customer assistant + staff co-pilot",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(customer.router, prefix="/api/v1")
app.include_router(staff.router, prefix="/api/v1")


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    customer_id: str | None = None
    staff_id: str | None = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "finsight",
        "llm_provider": settings.llm_provider,
        "lightweight_mode": settings.lightweight_mode,
    }


@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    user = authenticate(body.username, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token(user)
    return LoginResponse(
        access_token=token,
        role=user.role.value,
        username=user.username,
        customer_id=user.customer_id,
        staff_id=user.staff_id,
    )


@app.get("/api/v1/me")
async def me(user: Annotated[TokenUser, Depends(get_current_user)]) -> dict:
    return user.model_dump()
