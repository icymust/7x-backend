from app.services.uae_calendar import (
    UAE_PUBLIC_HOLIDAYS,
    get_uae_calendar_metadata,
)


def test_marks_saturday_as_uae_weekend():
    result = get_uae_calendar_metadata("2026-08-01")

    assert result == {
        "is_weekend": True,
        "is_public_holiday": False,
        "holiday_name": None,
    }


def test_marks_monday_as_workday():
    result = get_uae_calendar_metadata("2026-08-03")

    assert result["is_weekend"] is False


def test_marks_configured_public_holiday(monkeypatch):
    monkeypatch.setitem(
        UAE_PUBLIC_HOLIDAYS,
        "2026-08-03",
        "Official holiday",
    )

    result = get_uae_calendar_metadata("2026-08-03")

    assert result == {
        "is_weekend": False,
        "is_public_holiday": True,
        "holiday_name": "Official holiday",
    }
