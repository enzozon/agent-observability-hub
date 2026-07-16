"""Collector agent: queries fleet data from SQLite for a given period."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

from app.schemas.models import CollectorOutput, CostRecord, MaintenanceRecord, Truck


class CollectorAgent:
    name = "collector"

    def __init__(self, conn: sqlite3.Connection):
        self._conn = conn

    def run(self, period_days: int) -> CollectorOutput:
        if period_days < 1:
            raise ValueError("period_days must be >= 1")
        cutoff = (date.today() - timedelta(days=period_days)).isoformat()

        trucks = tuple(
            Truck(id=r[0], plate=r[1], model=r[2], year=r[3], km_total=r[4])
            for r in self._conn.execute("SELECT id, plate, model, year, km_total FROM trucks ORDER BY id")
        )
        costs = tuple(
            CostRecord(truck_id=r[0], category=r[1], amount=r[2], incurred_on=date.fromisoformat(r[3]))
            for r in self._conn.execute(
                "SELECT truck_id, category, amount, incurred_on FROM costs WHERE incurred_on >= ?", (cutoff,)
            )
        )
        maintenances = tuple(
            MaintenanceRecord(truck_id=r[0], description=r[1], cost=r[2], performed_on=date.fromisoformat(r[3]))
            for r in self._conn.execute(
                "SELECT truck_id, description, cost, performed_on FROM maintenances WHERE performed_on >= ?",
                (cutoff,),
            )
        )
        return CollectorOutput(
            trucks=trucks,
            costs=costs,
            maintenances=maintenances,
            period_days=period_days,
            collected_at=datetime.now(timezone.utc),
        )
