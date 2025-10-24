from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("", summary="Service healthcheck")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
