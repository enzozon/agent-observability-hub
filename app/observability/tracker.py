"""Metrics tracker: logs latency, estimated cost and errors per agent call (JSONL)."""
import json
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# Reference prices (USD per million tokens) and chars-per-token heuristic.
PRICE_INPUT_PER_MTOK = 3.0
PRICE_OUTPUT_PER_MTOK = 15.0
CHARS_PER_TOKEN = 4


def estimate_llm_cost(prompt_chars: int, completion_chars: int) -> float:
    input_tokens = prompt_chars / CHARS_PER_TOKEN
    output_tokens = completion_chars / CHARS_PER_TOKEN
    return (input_tokens * PRICE_INPUT_PER_MTOK + output_tokens * PRICE_OUTPUT_PER_MTOK) / 1_000_000


class Span:
    def __init__(self) -> None:
        self.cost_usd = 0.0

    def set_cost(self, cost_usd: float) -> None:
        self.cost_usd = cost_usd


class MetricsTracker:
    def __init__(self, path: Path | str):
        self.path = Path(path)

    @contextmanager
    def track(self, agent_name: str):
        span = Span()
        start = time.perf_counter()
        try:
            yield span
        except Exception as exc:
            self._record(agent_name, start, span, success=False, error=f"{type(exc).__name__}: {exc}")
            raise
        self._record(agent_name, start, span, success=True, error=None)

    def _record(self, agent: str, start: float, span: Span, success: bool, error: str | None) -> None:
        record = {
            "agent": agent,
            "latency_ms": round((time.perf_counter() - start) * 1000, 3),
            "cost_usd": span.cost_usd,
            "success": success,
            "error": error,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def summary(self) -> dict[str, dict[str, float | int]]:
        if not self.path.exists():
            return {}
        per_agent: dict[str, list[dict]] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            per_agent.setdefault(record["agent"], []).append(record)
        return {
            agent: {
                "calls": len(records),
                "error_rate": sum(1 for r in records if not r["success"]) / len(records),
                "avg_latency_ms": sum(r["latency_ms"] for r in records) / len(records),
                "total_cost_usd": sum(r["cost_usd"] for r in records),
            }
            for agent, records in per_agent.items()
        }
