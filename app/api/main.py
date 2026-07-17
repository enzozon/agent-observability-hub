"""FastAPI layer: validated input, rate limiting, pipeline execution and metrics."""
import os
import sqlite3
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.agents.analyst import AnalystAgent
from app.agents.collector import CollectorAgent
from app.agents.llm_client import StubLLMClient
from app.agents.writer import WriterAgent
from app.data.seed import seed_database
from app.guardrails.rate_limiter import RateLimiter, RateLimitExceeded
from app.observability.tracker import MetricsTracker
from app.orchestrator import Orchestrator
from app.schemas.models import TruckInsight


class AnalyzeRequest(BaseModel):
    period_days: int = Field(default=90, ge=1, le=3650)


class AnalyzeResponse(BaseModel):
    request_id: str
    status: str
    report: str
    alerts: tuple[str, ...]
    insights: tuple[TruckInsight, ...]


def _default_orchestrator(tracker: MetricsTracker) -> Orchestrator:
    conn = sqlite3.connect(os.getenv("DATABASE_PATH", ":memory:"), check_same_thread=False)
    seed_database(conn)
    return Orchestrator(
        collector=CollectorAgent(conn),
        analyst=AnalystAgent(),
        writer=WriterAgent(StubLLMClient()),
        tracker=tracker,
    )


def create_app(
    orchestrator: Orchestrator | None = None,
    tracker: MetricsTracker | None = None,
    rate_limiter: RateLimiter | None = None,
) -> FastAPI:
    tracker = tracker or MetricsTracker(os.getenv("METRICS_PATH", "metrics.jsonl"))
    orchestrator = orchestrator or _default_orchestrator(tracker)
    rate_limiter = rate_limiter or RateLimiter(
        max_calls=int(os.getenv("RATE_LIMIT_MAX_CALLS", "10")),
        window_seconds=float(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60")),
    )

    api = FastAPI(
        title="Agent Observability Hub",
        description="Multi-agent fleet cost analysis with guardrails and observability",
        version="0.1.0",
    )

    def enforce_rate_limit(request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        try:
            rate_limiter.acquire(key)
        except RateLimitExceeded as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(enforce_rate_limit)])
    def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
        state = orchestrator.run(request_id=str(uuid.uuid4()), period_days=body.period_days)
        if state.status != "reported":
            # error details stay in the metrics log; clients get a generic message
            raise HTTPException(status_code=502, detail="Pipeline failed to produce a report; see /metrics")
        return AnalyzeResponse(
            request_id=state.request_id,
            status=state.status,
            report=state.writer_output.report,
            alerts=state.analyst_output.alerts,
            insights=state.analyst_output.insights,
        )

    @api.get("/metrics")
    def metrics() -> dict:
        return tracker.summary()

    return api


app = create_app()
