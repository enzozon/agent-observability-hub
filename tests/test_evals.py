"""Tests for the mini eval harness."""
from app.agents.analyst import AnalystAgent
from app.agents.collector import CollectorAgent
from app.agents.writer import WriterAgent
from app.orchestrator import Orchestrator
from evals.harness import CASES, run_evals
from tests.conftest import BrokenLLM


def build_orchestrator(seeded_conn, llm, tracker):
    return Orchestrator(
        collector=CollectorAgent(seeded_conn),
        analyst=AnalystAgent(),
        writer=WriterAgent(llm),
        tracker=tracker,
    )


class TestEvalHarness:
    def test_has_between_5_and_10_cases(self):
        assert 5 <= len(CASES) <= 10

    def test_all_cases_pass_with_healthy_pipeline(self, seeded_conn, stub_llm, tracker):
        report = run_evals(build_orchestrator(seeded_conn, stub_llm, tracker), tracker)
        failed = [r for r in report.results if not r.passed]
        assert report.failed == 0, f"failed cases: {[r.name for r in failed]}"
        assert report.passed == len(CASES)

    def test_broken_pipeline_is_detected_not_raised(self, seeded_conn, tracker):
        report = run_evals(build_orchestrator(seeded_conn, BrokenLLM(), tracker), tracker)
        assert report.failed > 0  # evals must catch the regression, not crash
