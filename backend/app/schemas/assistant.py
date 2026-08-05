from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExplainRequest(BaseModel):
    planning_run_id: int = Field(gt=0)
    date_from: date | None = None
    date_to: date | None = None
    store_id: str | None = None
    decision_action_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
    )
    language: Literal["en", "ru"] = "en"

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to")

        if self.decision_action_id and (
            self.date_from or self.date_to or self.store_id
        ):
            raise ValueError(
                "decision_action_id cannot be combined with store/date filters"
            )

        return self
