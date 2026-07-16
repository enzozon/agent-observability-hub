"""Analyst agent: turns raw fleet data into per-truck insights and alerts."""
from app.schemas.models import AnalystOutput, CollectorOutput, TruckInsight

MAINTENANCE_SPIKE_THRESHOLD = 3


class NoFleetDataError(Exception):
    """Raised when there is no truck data to analyze."""


class AnalystAgent:
    name = "analyst"

    def run(self, collected: CollectorOutput) -> AnalystOutput:
        if not collected.trucks:
            raise NoFleetDataError("Collector returned no trucks; nothing to analyze")

        insights = []
        for truck in collected.trucks:
            cost_total = sum(c.amount for c in collected.costs if c.truck_id == truck.id)
            maint = [m for m in collected.maintenances if m.truck_id == truck.id]
            total = cost_total + sum(m.cost for m in maint)
            insights.append(
                TruckInsight(
                    truck_id=truck.id,
                    plate=truck.plate,
                    total_cost=total,
                    cost_per_km=total / truck.km_total,
                    maintenance_count=len(maint),
                )
            )

        worst = max(insights, key=lambda i: i.cost_per_km)
        alerts = tuple(
            f"Caminhao {i.plate} com pico de manutencao: {i.maintenance_count} servicos no periodo"
            for i in insights
            if i.maintenance_count >= MAINTENANCE_SPIKE_THRESHOLD
        )
        return AnalystOutput(
            insights=tuple(insights),
            highest_cost_per_km_plate=worst.plate,
            total_fleet_cost=sum(i.total_cost for i in insights),
            alerts=alerts,
        )
