from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ExplainRequest(BaseModel):
    planning_run_id: int = Field(gt=0)
    date_from: date | None = None
    date_to: date | None = None
    store_id: str | None = None
    language: Literal["en", "ru"] = "en"

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from cannot be later than date_to")

        return self
