"""Shared fixtures. LLM calls are always mocked/stubbed — no API credits spent."""
import sqlite3

import pytest

from app.agents.llm_client import StubLLMClient
from app.data.seed import seed_database
from app.observability.tracker import MetricsTracker


@pytest.fixture
def seeded_conn():
    conn = sqlite3.connect(":memory:")
    seed_database(conn)
    yield conn
    conn.close()


@pytest.fixture
def stub_llm():
    return StubLLMClient()


@pytest.fixture
def tracker(tmp_path):
    return MetricsTracker(tmp_path / "metrics.jsonl")


class BrokenLLM:
    """Always returns unparseable output."""

    def complete(self, prompt: str) -> str:
        return "sorry, I cannot produce JSON today"


class FlakyLLM:
    """Fails the first N calls, then behaves like the stub."""

    def __init__(self, failures: int = 1):
        self.failures = failures
        self.calls = 0
        self._stub = StubLLMClient()

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self.calls <= self.failures:
            return "{broken json"
        return self._stub.complete(prompt)


@pytest.fixture
def broken_llm():
    return BrokenLLM()


@pytest.fixture
def flaky_llm():
    return FlakyLLM(failures=1)
