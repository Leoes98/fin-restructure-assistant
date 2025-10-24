from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ai.report_generator import ReportGenerator
from app.api.deps import get_report_generator, require_api_key
from app.schemas.report_request import ReportRequest
from app.schemas.report_response import ReportResponse

router = APIRouter(prefix="/v1", tags=["report"], dependencies=[Depends(require_api_key)])


@router.post("/report", response_model=ReportResponse, summary="Generar informe en PDF con IA")
async def create_report(
    payload: ReportRequest,
    generator: ReportGenerator = Depends(get_report_generator),
) -> ReportResponse:
    result = await generator.generate(payload.customer_id)
    return ReportResponse(
        customer_id=result.customer_id,
        report_url=result.url,
        blob_path=result.blob_path,
        run_id=result.run_id,
        generated_at=result.generated_at,
    )
