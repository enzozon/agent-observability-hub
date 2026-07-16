"""Unit tests for the metrics tracker: latency, estimated cost, error rate."""
import json

import pytest

from app.observability.tracker import MetricsTracker, estimate_llm_cost


class TestTrack:
    def test_records_successful_call(self, tracker):
        with tracker.track("collector"):
            pass
        summary = tracker.summary()
        assert summary["collector"]["calls"] == 1
        assert summary["collector"]["error_rate"] == 0.0
        assert summary["collector"]["avg_latency_ms"] >= 0.0

    def test_records_error_and_reraises(self, tracker):
        with pytest.raises(ValueError):
            with tracker.track("analyst"):
                raise ValueError("boom")
        summary = tracker.summary()
        assert summary["analyst"]["calls"] == 1
        assert summary["analyst"]["error_rate"] == 1.0

    def test_error_rate_aggregates_across_calls(self, tracker):
        with tracker.track("writer"):
            pass
        with pytest.raises(RuntimeError):
            with tracker.track("writer"):
                raise RuntimeError("fail")
        assert tracker.summary()["writer"]["error_rate"] == pytest.approx(0.5)

    def test_span_cost_is_recorded(self, tracker):
        with tracker.track("writer") as span:
            span.set_cost(0.0123)
        assert tracker.summary()["writer"]["total_cost_usd"] == pytest.approx(0.0123)

    def test_writes_one_jsonl_line_per_call(self, tracker):
        with tracker.track("collector"):
            pass
        with tracker.track("analyst"):
            pass
        lines = tracker.path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        record = json.loads(lines[0])
        assert set(record) >= {"agent", "latency_ms", "cost_usd", "success", "ts"}


class TestCostEstimation:
    def test_known_char_counts_give_known_cost(self):
        # 4000 chars ~= 1000 tokens each side: 1000/1M * $3 + 1000/1M * $15 = $0.018
        assert estimate_llm_cost(prompt_chars=4000, completion_chars=4000) == pytest.approx(0.018)

    def test_zero_usage_costs_nothing(self):
        assert estimate_llm_cost(prompt_chars=0, completion_chars=0) == 0.0
