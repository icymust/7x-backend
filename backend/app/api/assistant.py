from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.engines.explanation_context import build_explanation_context
from app.models import PlanningRun
from app.schemas.assistant import ExplainRequest
from app.services.llm_service import request_llm_explanation

router = APIRouter(
    prefix="/api/assistant",
    tags=["assistant"],
)


@router.post("/explain")
def explain_planning_run(
    request: ExplainRequest,
    db: Session = Depends(get_db),
):
    planning_run = db.get(PlanningRun, request.planning_run_id)

    if planning_run is None:
        raise HTTPException(
            status_code=404,
            detail="Planning run not found",
        )

    context = build_explanation_context(
        planning_run.result.get("plan", []),
        planning_run_id=planning_run.id,
        dataset_id=planning_run.dataset_id,
        filename=planning_run.result.get("filename"),
        model_version=planning_run.model_version,
        date_from=request.date_from,
        date_to=request.date_to,
        store_id=request.store_id,
    )

    message = request_llm_explanation(
        context,
        request.language,
    )

    return {
        "source": "ollama" if message else "structured_fallback",
        "language": request.language,
        "message": message,
        "context": context,
    }
