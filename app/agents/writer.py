"""Writer agent: turns the analysis into a natural-language report via an LLM."""
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from app.agents.llm_client import DRAFT_MARKER, LLMClient
from app.guardrails.content_validator import validate_content
from app.guardrails.llm_parser import LLMParseError, parse_llm_output
from app.schemas.models import AnalystOutput, WriterOutput

MAX_PARSE_RETRIES = 1


class _ReportPayload(BaseModel):
    report: str = Field(min_length=50)


class WriterAgent:
    name = "writer"

    def __init__(self, llm: LLMClient):
        self._llm = llm
        self.last_prompt_chars = 0
        self.last_completion_chars = 0

    def run(self, analysis: AnalystOutput) -> WriterOutput:
        draft = self._draft(analysis)
        validate_content(draft)  # guardrail: never send unvalidated content to the LLM
        prompt = (
            "Voce e um redator de relatorios de frota. Revise e retorne o relatorio abaixo "
            'como JSON no formato {"report": "<texto>"}.\n'
            f"{DRAFT_MARKER}\n{draft}"
        )
        payload = self._complete_with_retry(prompt)
        return WriterOutput(report=payload.report, generated_at=datetime.now(timezone.utc))

    def _complete_with_retry(self, prompt: str) -> _ReportPayload:
        attempts = MAX_PARSE_RETRIES + 1
        for attempt in range(1, attempts + 1):
            raw = self._llm.complete(prompt)
            self.last_prompt_chars = len(prompt)
            self.last_completion_chars = len(raw)
            try:
                return parse_llm_output(raw, _ReportPayload)
            except LLMParseError:
                if attempt == attempts:
                    raise
        raise AssertionError("unreachable")

    @staticmethod
    def _draft(analysis: AnalystOutput) -> str:
        worst = next(i for i in analysis.insights if i.plate == analysis.highest_cost_per_km_plate)
        ranking = sorted(analysis.insights, key=lambda i: i.cost_per_km, reverse=True)
        lines = [
            "Relatorio de custos da frota.",
            f"Custo total da frota no periodo: R$ {analysis.total_fleet_cost:,.2f}.",
            f"O veiculo com maior custo por km e {worst.plate} (R$ {worst.cost_per_km:.2f}/km).",
            "Ranking de custo por km: "
            + "; ".join(f"{i.plate}: R$ {i.cost_per_km:.2f}/km" for i in ranking)
            + ".",
        ]
        if analysis.alerts:
            lines.append("Alertas: " + " | ".join(analysis.alerts) + ".")
        else:
            lines.append("Nenhum alerta de manutencao no periodo.")
        return "\n".join(lines)
