# 简单口令鉴权：校验请求头 Authorization: Bearer <口令>。
from fastapi import Header, HTTPException
from app.core.config import settings

async def require_auth(authorization: str | None = Header(default=None)) -> None:
    """校验演示口令；缺失或错误一律 401。"""
    expected = f"Bearer {settings.DEMO_PASSWORD}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="未授权：演示口令缺失或错误")
