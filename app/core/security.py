from typing import Optional

from fastapi import Header, HTTPException

from app.core.config import settings


async def require_admin_token(x_admin_token: Optional[str] = Header(default=None)) -> None:
    """Require X-Admin-Token when ADMIN_TOKEN is configured."""
    expected = settings.admin.token.strip()
    if not expected:
        return
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")
