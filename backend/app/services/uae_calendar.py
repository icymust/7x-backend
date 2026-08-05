from datetime import date, datetime

UAE_WEEKEND_DAYS = {
    5,  # Saturday
    6,  # Sunday
}

UAE_PUBLIC_HOLIDAYS: dict[str, str] = {
    # "YYYY-MM-DD": "Official holiday name",
}


def _parse_date(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    return datetime.fromisoformat(value).date()


def get_uae_calendar_metadata(
    value: str | date | datetime,
) -> dict[str, bool | str | None]:
    parsed_date = _parse_date(value)
    date_key = parsed_date.isoformat()
    holiday_name = UAE_PUBLIC_HOLIDAYS.get(date_key)

    return {
        "is_weekend": parsed_date.weekday() in UAE_WEEKEND_DAYS,
        "is_public_holiday": holiday_name is not None,
        "holiday_name": holiday_name,
    }
