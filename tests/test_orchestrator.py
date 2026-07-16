"""Integration tests for the full pipeline: Collector -> Analyst -> Writer."""
import pytest

from app.agents.analyst import AnalystAgent
from app.agents.collector import CollectorAgent
from app.agents.writer import WriterAgent
from app.orchestrator import Orchestrator


@pytest.fixture
def orchestrator(seeded_conn, stub_llm, tracker):
    return Orchestrator(
        collector=CollectorAgent(seeded_conn),
        analyst=AnalystAgent(),
        writer=WriterAgent(stub_llm),
        tracker=tracker,
    )


class TestPipelineHappyPath:
    def test_full_pipeline_reaches_reported_status(self, orchestrator):
        state = orchestrator.run(request_id="req-1", period_days=90)
        assert state.status == "reported"
        assert state.collector_output is not None
        assert state.analyst_output is not None
        assert state.writer_output is not None
        assert state.errors == ()

    def test_report_mentions_highest_cost_truck(self, orchestrator):
        state = orchestrator.run(request_id="req-2", period_days=90)
        assert state.analyst_output.highest_cost_per_km_plate in state.writer_output.report

    def test_metrics_recorded_for_all_three_agents(self, orchestrator, tracker):
        orchestrator.run(request_id="req-3", period_days=90)
        summary = tracker.summary()
        assert set(summary) >= {"collector", "analyst", "writer"}
        assert summary["writer"]["total_cost_usd"] > 0.0


class TestPipelineFailurePath:
    def test_writer_failure_yields_failed_state_not_exception(self, seeded_conn, broken_llm, tracker):
        orchestrator = Orchestrator(
            collector=CollectorAgent(seeded_conn),
            analyst=AnalystAgent(),
            writer=WriterAgent(broken_llm),
            tracker=tracker,
        )
        state = orchestrator.run(request_id="req-4", period_days=90)
        assert state.status == "failed"
        assert state.writer_output is None
        assert len(state.errors) == 1
        # partial progress is preserved for debugging
        assert state.analyst_output is not None

    def test_failed_agent_still_tracked_in_metrics(self, seeded_conn, broken_llm, tracker):
        orchestrator = Orchestrator(
            collector=CollectorAgent(seeded_conn),
            analyst=AnalystAgent(),
            writer=WriterAgent(broken_llm),
            tracker=tracker,
        )
        orchestrator.run(request_id="req-5", period_days=90)
        assert tracker.summary()["writer"]["error_rate"] == 1.0
