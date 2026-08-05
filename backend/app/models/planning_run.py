from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PlanningRun(Base):
    __tablename__ = "planning_runs"

    id: Mapped[int] = mapped_column(primary_key=True)

    dataset_id: Mapped[int] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        index=True,
    )

    planning_date: Mapped[date] = mapped_column(Date)
    target_utilization: Mapped[float] = mapped_column(Float)

    model_version: Mapped[str] = mapped_column(
        String(64),
        default="baseline-v1",
    )

    result: Mapped[dict[str, Any]] = mapped_column(JSONB)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
