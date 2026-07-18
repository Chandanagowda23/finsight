"""JWT auth + demo role-based access (customer vs staff)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from api.config import get_settings

security = HTTPBearer(auto_error=False)


class Role(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"


class TokenUser(BaseModel):
    username: str
    role: Role
    customer_id: str | None = None
    staff_id: str | None = None


def _users() -> dict[str, dict]:
    s = get_settings()
    return {
        s.demo_customer_user: {
            "password": s.demo_customer_pass,
            "role": Role.CUSTOMER,
            "customer_id": "CUST-1001",
        },
        s.demo_staff_user: {
            "password": s.demo_staff_pass,
            "role": Role.STAFF,
            "staff_id": "STAFF-42",
        },
    }


def authenticate(username: str, password: str) -> TokenUser | None:
    user = _users().get(username)
    if not user or user["password"] != password:
        return None
    return TokenUser(
        username=username,
        role=user["role"],
        customer_id=user.get("customer_id"),
        staff_id=user.get("staff_id"),
    )


def create_access_token(user: TokenUser) -> str:
    s = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=s.access_token_expire_minutes)
    payload = {
        "sub": user.username,
        "role": user.role.value,
        "customer_id": user.customer_id,
        "staff_id": user.staff_id,
        "exp": expire,
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> TokenUser:
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
        return TokenUser(
            username=payload["sub"],
            role=Role(payload["role"]),
            customer_id=payload.get("customer_id"),
            staff_id=payload.get("staff_id"),
        )
    except (JWTError, KeyError, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> TokenUser:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return decode_token(creds.credentials)


async def require_customer(user: Annotated[TokenUser, Depends(get_current_user)]) -> TokenUser:
    if user.role != Role.CUSTOMER:
        raise HTTPException(status_code=403, detail="Customer role required")
    return user


async def require_staff(user: Annotated[TokenUser, Depends(get_current_user)]) -> TokenUser:
    if user.role != Role.STAFF:
        raise HTTPException(status_code=403, detail="Staff role required")
    return user
