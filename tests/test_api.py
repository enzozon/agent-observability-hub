"""Integration tests for the FastAPI layer (rate limiting, validation, metrics)."""
import pytest
from fastapi.testclient import TestClient

from app.agents.analyst import AnalystAgent
from app.agents.collector import CollectorAgent
from app.agents.writer import WriterAgent
from app.api.main import create_app
from app.guardrails.rate_limiter import RateLimiter
from app.orchestrator import Orchestrator


def make_client(seeded_conn, llm, tracker, max_calls: int = 100) -> TestClient:
    orchestrator = Orchestrator(
        collector=CollectorAgent(seeded_conn),
        analyst=AnalystAgent(),
        writer=WriterAgent(llm),
        tracker=tracker,
    )
    app = create_app(
        orchestrator=orchestrator,
        tracker=tracker,
        rate_limiter=RateLimiter(max_calls=max_calls, window_seconds=60),
    )
    return TestClient(app)


@pytest.fixture
def client(seeded_conn, stub_llm, tracker):
    return make_client(seeded_conn, stub_llm, tracker)


class TestHealth:
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestAnalyze:
    def test_analyze_returns_full_report(self, client):
        response = client.post("/analyze", json={"period_days": 90})
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "reported"
        assert len(body["report"]) >= 50
        assert body["request_id"]
        assert len(body["insights"]) == 5

    def test_rejects_zero_period(self, client):
        assert client.post("/analyze", json={"period_days": 0}).status_code == 422

    def test_rejects_non_integer_period(self, client):
        assert client.post("/analyze", json={"period_days": "many"}).status_code == 422

    def test_rejects_period_over_limit(self, client):
        assert client.post("/analyze", json={"period_days": 99999}).status_code == 422

    def test_pipeline_failure_returns_502(self, seeded_conn, broken_llm, tracker):
        client = make_client(seeded_conn, broken_llm, tracker)
        response = client.post("/analyze", json={"period_days": 90})
        assert response.status_code == 502
        assert response.json()["detail"]


class TestRateLimit:
    def test_requests_over_limit_get_429(self, seeded_conn, stub_llm, tracker):
        client = make_client(seeded_conn, stub_llm, tracker, max_calls=2)
        assert client.post("/analyze", json={"period_days": 90}).status_code == 200
        assert client.post("/analyze", json={"period_days": 90}).status_code == 200
        assert client.post("/analyze", json={"period_days": 90}).status_code == 429


class TestMetrics:
    def test_metrics_expose_per_agent_summary(self, client):
        client.post("/analyze", json={"period_days": 90})
        response = client.get("/metrics")
        assert response.status_code == 200
        body = response.json()
        assert set(body) >= {"collector", "analyst", "writer"}
        assert body["writer"]["calls"] == 1
