from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.api.deps import SessionDep
from app.settings import get_settings

__all__ = ["SessionDep", "require_admin"]


def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.admin_secret}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin credentials required",
        )
