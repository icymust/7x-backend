from datetime import date
from hashlib import sha256
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Dataset, PlanningRun


def save_planning_result(
    session: Session,
    *,
    filename: str,
    file_content: bytes,
    normalized_data: list[dict[str, Any]],
    planning_date: date,
    target_utilization: float,
    result: dict[str, Any],
    model_version: str = "baseline-v1",
) -> tuple[Dataset, PlanningRun]:
    checksum = sha256(file_content).hexdigest()

    dataset = session.scalar(select(Dataset).where(Dataset.checksum == checksum))

    try:
        if dataset is None:
            dataset = Dataset(
                filename=filename,
                checksum=checksum,
                normalized_data=normalized_data,
                validation_status="valid",
            )
            session.add(dataset)
            session.flush()

        planning_run = PlanningRun(
            dataset_id=dataset.id,
            planning_date=planning_date,
            target_utilization=target_utilization,
            model_version=model_version,
            result=result,
        )

        session.add(planning_run)
        session.commit()
        session.refresh(planning_run)

        return dataset, planning_run
    except Exception:
        session.rollback()
        raise
