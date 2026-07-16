"""Structured input/output contracts for every agent in the pipeline."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CostCategory = Literal["fuel", "maintenance", "tires", "tolls"]
PipelineStatus = Literal["pending", "collected", "analyzed", "reported", "failed"]


class Truck(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: int
    plate: str = Field(min_length=7, max_length=8)
    model: str
    year: int = Field(ge=1980, le=2030)
    km_total: float = Field(gt=0)


class CostRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    truck_id: int
    category: CostCategory
    amount: float = Field(gt=0)
    incurred_on: date


class MaintenanceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    truck_id: int
    description: str
    cost: float = Field(ge=0)
    performed_on: date


class CollectorOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    trucks: tuple[Truck, ...]
    costs: tuple[CostRecord, ...]
    maintenances: tuple[MaintenanceRecord, ...]
    period_days: int = Field(gt=0)
    collected_at: datetime


class TruckInsight(BaseModel):
    model_config = ConfigDict(frozen=True)

    truck_id: int
    plate: str
    total_cost: float = Field(ge=0)
    cost_per_km: float = Field(ge=0)
    maintenance_count: int = Field(ge=0)


class AnalystOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    insights: tuple[TruckInsight, ...]
    highest_cost_per_km_plate: str
    total_fleet_cost: float = Field(ge=0)
    alerts: tuple[str, ...] = ()


class WriterOutput(BaseModel):
    model_config = ConfigDict(frozen=True)

    report: str = Field(min_length=50)
    generated_at: datetime


class PipelineState(BaseModel):
    """Shared state handed off between agents. Frozen: each handoff produces a new copy."""

    model_config = ConfigDict(frozen=True)

    request_id: str
    period_days: int = Field(gt=0, le=3650)
    status: PipelineStatus = "pending"
    collector_output: CollectorOutput | None = None
    analyst_output: AnalystOutput | None = None
    writer_output: WriterOutput | None = None
    errors: tuple[str, ...] = ()
