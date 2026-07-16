"""Mini eval harness: deterministic scenarios that validate agent coherence.

Run standalone with: python -m evals.harness
"""
import sqlite3
from dataclasses import dataclass
from typing import Callable

from app.observability.tracker import MetricsTracker
from app.orchestrator import Orchestrator
from app.schemas.models import PipelineState

# Expected values derived from the deterministic seed dataset (app/data/seed.py).
EXPECTED_WORST_PLATE = "RTX3C33"
EXPECTED_FLEET_TOTAL_90D = 87_800.0
EXPECTED_FLEET_TOTAL_500D = 95_900.0
EXPECTED_WORST_COST_PER_KM = 34_500.0 / 310_000.0

Check = Callable[[PipelineState, dict], bool]


@dataclass(frozen=True)
class EvalCase:
    name: str
    description: str
    period_days: int
    check: Check


@dataclass(frozen=True)
class EvalResult:
    name: str
    passed: bool
    detail: str | None = None


@dataclass(frozen=True)
class EvalReport:
    results: tuple[EvalResult, ...]

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.passed)

    @property
    def failed(self) -> int:
        return len(self.results) - self.passed


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        "pipeline_completes",
        "Pipeline reaches 'reported' status with no errors",
        90,
        lambda s, m: s.status == "reported" and s.errors == (),
    ),
    EvalCase(
        "worst_truck_identified",
        f"Analyst flags {EXPECTED_WORST_PLATE} as highest cost/km in 90 days",
        90,
        lambda s, m: s.analyst_output.highest_cost_per_km_plate == EXPECTED_WORST_PLATE,
    ),
    EvalCase(
        "cost_per_km_math",
        "Worst truck cost/km matches hand-computed value",
        90,
        lambda s, m: abs(
            max(s.analyst_output.insights, key=lambda i: i.cost_per_km).cost_per_km
            - EXPECTED_WORST_COST_PER_KM
        ) < 0.001,
    ),
    EvalCase(
        "fleet_total_90_days",
        "Total fleet cost for 90 days matches the seed dataset",
        90,
        lambda s, m: abs(s.analyst_output.total_fleet_cost - EXPECTED_FLEET_TOTAL_90D) < 1.0,
    ),
    EvalCase(
        "period_filter_widens_total",
        "A 500-day window includes older records and a larger total",
        500,
        lambda s, m: abs(s.analyst_output.total_fleet_cost - EXPECTED_FLEET_TOTAL_500D) < 1.0,
    ),
    EvalCase(
        "maintenance_spike_alert",
        f"Alert raised for {EXPECTED_WORST_PLATE} (3 maintenances in window)",
        90,
        lambda s, m: any(EXPECTED_WORST_PLATE in a for a in s.analyst_output.alerts),
    ),
    EvalCase(
        "report_mentions_worst_truck",
        "Final NL report names the highest cost/km truck",
        90,
        lambda s, m: s.analyst_output.highest_cost_per_km_plate in s.writer_output.report,
    ),
    EvalCase(
        "report_is_substantial",
        "Final report has at least 200 characters of content",
        90,
        lambda s, m: len(s.writer_output.report) >= 200,
    ),
    EvalCase(
        "all_agents_healthy_in_metrics",
        "Metrics show zero error rate for the three agents",
        90,
        lambda s, m: all(m.get(a, {}).get("error_rate", 1.0) == 0.0 for a in ("collector", "analyst", "writer")),
    ),
)


def run_evals(orchestrator: Orchestrator, tracker: MetricsTracker) -> EvalReport:
    results = []
    for case in CASES:
        state = orchestrator.run(request_id=f"eval-{case.name}", period_days=case.period_days)
        try:
            ok = bool(case.check(state, tracker.summary()))
            detail = None if ok else f"check failed (pipeline status: {state.status})"
        except Exception as exc:
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        results.append(EvalResult(name=case.name, passed=ok, detail=detail))
    return EvalReport(results=tuple(results))


def main() -> int:
    from app.agents.analyst import AnalystAgent
    from app.agents.collector import CollectorAgent
    from app.agents.llm_client import StubLLMClient
    from app.agents.writer import WriterAgent
    from app.data.seed import seed_database

    conn = sqlite3.connect(":memory:")
    seed_database(conn)
    tracker = MetricsTracker("metrics.jsonl")
    orchestrator = Orchestrator(
        collector=CollectorAgent(conn),
        analyst=AnalystAgent(),
        writer=WriterAgent(StubLLMClient()),
        tracker=tracker,
    )
    report = run_evals(orchestrator, tracker)
    for result in report.results:
        status = "PASS" if result.passed else "FAIL"
        line = f"[{status}] {result.name}"
        if result.detail:
            line += f" — {result.detail}"
        print(line)
    print(f"\n{report.passed}/{len(report.results)} eval cases passed")
    return 0 if report.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
