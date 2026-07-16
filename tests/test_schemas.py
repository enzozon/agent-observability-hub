"""Unit tests for Pydantic schemas — agent input/output contracts."""
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.schemas.models import (
    AnalystOutput,
    CollectorOutput,
    CostRecord,
    MaintenanceRecord,
    PipelineState,
    Truck,
    TruckInsight,
    WriterOutput,
)


def make_truck(**overrides) -> Truck:
    data = {"id": 1, "plate": "ABC1D23", "model": "Volvo FH 540", "year": 2022, "km_total": 150000.0}
    data.update(overrides)
    return Truck(**data)


class TestTruck:
    def test_valid_truck_is_created(self):
        truck = make_truck()
        assert truck.plate == "ABC1D23"
        assert truck.km_total == 150000.0

    def test_rejects_year_before_1980(self):
        with pytest.raises(ValidationError):
            make_truck(year=1950)

    def test_rejects_zero_km(self):
        with pytest.raises(ValidationError):
            make_truck(km_total=0)

    def test_rejects_short_plate(self):
        with pytest.raises(ValidationError):
            make_truck(plate="AB1")

    def test_truck_is_immutable(self):
        truck = make_truck()
        with pytest.raises(ValidationError):
            truck.plate = "XYZ9Z99"


class TestCostRecord:
    def test_valid_cost_record(self):
        record = CostRecord(truck_id=1, category="fuel", amount=1200.50, incurred_on=date(2026, 1, 15))
        assert record.category == "fuel"

    def test_rejects_unknown_category(self):
        with pytest.raises(ValidationError):
            CostRecord(truck_id=1, category="bribes", amount=10.0, incurred_on=date(2026, 1, 15))

    def test_rejects_negative_amount(self):
        with pytest.raises(ValidationError):
            CostRecord(truck_id=1, category="fuel", amount=-5.0, incurred_on=date(2026, 1, 15))


class TestCollectorOutput:
    def test_holds_collected_data(self):
        output = CollectorOutput(
            trucks=[make_truck()],
            costs=[CostRecord(truck_id=1, category="fuel", amount=100.0, incurred_on=date(2026, 1, 15))],
            maintenances=[MaintenanceRecord(truck_id=1, description="Oil change", cost=350.0, performed_on=date(2026, 1, 10))],
            period_days=90,
            collected_at=datetime.now(timezone.utc),
        )
        assert len(output.trucks) == 1
        assert output.period_days == 90

    def test_rejects_non_positive_period(self):
        with pytest.raises(ValidationError):
            CollectorOutput(trucks=[], costs=[], maintenances=[], period_days=0, collected_at=datetime.now(timezone.utc))


class TestAnalystOutput:
    def test_valid_analysis(self):
        insight = TruckInsight(truck_id=1, plate="ABC1D23", total_cost=5000.0, cost_per_km=0.35, maintenance_count=2)
        output = AnalystOutput(
            insights=[insight],
            highest_cost_per_km_plate="ABC1D23",
            total_fleet_cost=5000.0,
            alerts=["Truck ABC1D23 maintenance spike"],
        )
        assert output.insights[0].cost_per_km == 0.35

    def test_rejects_negative_cost_per_km(self):
        with pytest.raises(ValidationError):
            TruckInsight(truck_id=1, plate="ABC1D23", total_cost=1.0, cost_per_km=-0.1, maintenance_count=0)


class TestWriterOutput:
    def test_rejects_report_shorter_than_50_chars(self):
        with pytest.raises(ValidationError):
            WriterOutput(report="too short", generated_at=datetime.now(timezone.utc))

    def test_accepts_full_report(self):
        report = "Fleet cost report: truck ABC1D23 has the highest cost per km in the analyzed period."
        output = WriterOutput(report=report, generated_at=datetime.now(timezone.utc))
        assert "ABC1D23" in output.report


class TestPipelineState:
    def test_defaults_to_pending_with_no_outputs(self):
        state = PipelineState(request_id="req-1", period_days=90)
        assert state.status == "pending"
        assert state.collector_output is None
        assert state.errors == ()

    def test_rejects_invalid_status(self):
        with pytest.raises(ValidationError):
            PipelineState(request_id="req-1", period_days=90, status="exploded")

    def test_state_is_immutable_and_copies_do_not_mutate_original(self):
        state = PipelineState(request_id="req-1", period_days=90)
        updated = state.model_copy(update={"status": "collected"})
        assert state.status == "pending"
        assert updated.status == "collected"

    def test_rejects_period_over_ten_years(self):
        with pytest.raises(ValidationError):
            PipelineState(request_id="req-1", period_days=4000)
