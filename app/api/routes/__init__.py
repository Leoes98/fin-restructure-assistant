from __future__ import annotations

from fastapi import APIRouter

from . import evaluation, health, report

router = APIRouter()
router.include_router(health.router)
router.include_router(evaluation.router)
router.include_router(report.router)

__all__ = ["router"]
