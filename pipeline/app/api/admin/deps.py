from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_session
from app.settings import get_settings

SessionDep = Annotated[Session, Depends(get_session)]


def require_admin(authorization: Annotated[str | None, Header()] = None) -> None:
    settings = get_settings()
    expected = f"Bearer {settings.admin_secret}"
    if authorization is None or not secrets.compare_digest(authorization, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="admin credentials required",
        )
