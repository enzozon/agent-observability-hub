"""Explicit orchestration: Collector -> Analyst -> Writer with shared immutable state.

Each handoff produces a new PipelineState copy; a stage failure yields a
`failed` state (with partial progress preserved) instead of an exception.
"""
from app.agents.analyst import AnalystAgent
from app.agents.collector import CollectorAgent
from app.agents.writer import WriterAgent
from app.observability.tracker import MetricsTracker, estimate_llm_cost
from app.schemas.models import PipelineState


class Orchestrator:
    def __init__(
        self,
        collector: CollectorAgent,
        analyst: AnalystAgent,
        writer: WriterAgent,
        tracker: MetricsTracker,
    ):
        self._collector = collector
        self._analyst = analyst
        self._writer = writer
        self._tracker = tracker

    def run(self, request_id: str, period_days: int) -> PipelineState:
        state = PipelineState(request_id=request_id, period_days=period_days)
        try:
            with self._tracker.track(self._collector.name):
                collected = self._collector.run(state.period_days)
            state = state.model_copy(update={"collector_output": collected, "status": "collected"})

            with self._tracker.track(self._analyst.name):
                analysis = self._analyst.run(collected)
            state = state.model_copy(update={"analyst_output": analysis, "status": "analyzed"})

            with self._tracker.track(self._writer.name) as span:
                report = self._writer.run(analysis)
                span.set_cost(
                    estimate_llm_cost(self._writer.last_prompt_chars, self._writer.last_completion_chars)
                )
            return state.model_copy(update={"writer_output": report, "status": "reported"})
        except Exception as exc:
            return state.model_copy(
                update={"status": "failed", "errors": state.errors + (f"{type(exc).__name__}: {exc}",)}
            )
