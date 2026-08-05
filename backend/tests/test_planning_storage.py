from datetime import date
from hashlib import sha256
from unittest.mock import MagicMock

import pytest
from sqlalchemy.orm import Session

from app.models import Dataset, PlanningRun
from app.services.planning_storage import save_planning_result


def test_saves_new_dataset_and_planning_run():
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    def assign_dataset_id():
        dataset = session.add.call_args.args[0]
        dataset.id = 10

    def assign_planning_run_id(planning_run):
        planning_run.id = 20

    session.flush.side_effect = assign_dataset_id
    session.refresh.side_effect = assign_planning_run_id

    dataset, planning_run = save_planning_result(
        session,
        filename="sample.xlsx",
        file_content=b"excel-content",
        normalized_data=[{"store_id": "DXB-001"}],
        planning_date=date(2026, 8, 1),
        target_utilization=0.85,
        result={"plan": [], "calendar": []},
    )

    assert isinstance(dataset, Dataset)
    assert dataset.id == 10
    assert dataset.filename == "sample.xlsx"
    assert dataset.checksum == sha256(b"excel-content").hexdigest()
    assert dataset.validation_status == "valid"

    assert isinstance(planning_run, PlanningRun)
    assert planning_run.id == 20
    assert planning_run.dataset_id == 10
    assert planning_run.model_version == "baseline-v1"

    session.flush.assert_called_once()
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


def test_reuses_existing_dataset():
    session = MagicMock(spec=Session)

    existing_dataset = Dataset(
        filename="sample.xlsx",
        checksum="existing-checksum",
        normalized_data=[],
        validation_status="valid",
    )
    existing_dataset.id = 7

    session.scalar.return_value = existing_dataset

    def assign_planning_run_id(planning_run):
        planning_run.id = 8

    session.refresh.side_effect = assign_planning_run_id

    dataset, planning_run = save_planning_result(
        session,
        filename="sample.xlsx",
        file_content=b"excel-content",
        normalized_data=[],
        planning_date=date(2026, 8, 1),
        target_utilization=0.85,
        result={"plan": [], "calendar": []},
    )

    assert dataset is existing_dataset
    assert planning_run.dataset_id == 7

    session.flush.assert_not_called()
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_rolls_back_when_save_fails():
    session = MagicMock(spec=Session)

    existing_dataset = Dataset(
        filename="sample.xlsx",
        checksum="existing-checksum",
        normalized_data=[],
        validation_status="valid",
    )
    existing_dataset.id = 7

    session.scalar.return_value = existing_dataset
    session.commit.side_effect = RuntimeError("Database error")

    with pytest.raises(RuntimeError, match="Database error"):
        save_planning_result(
            session,
            filename="sample.xlsx",
            file_content=b"excel-content",
            normalized_data=[],
            planning_date=date(2026, 8, 1),
            target_utilization=0.85,
            result={"plan": [], "calendar": []},
        )

    session.rollback.assert_called_once()
