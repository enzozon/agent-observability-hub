# TDD Evidence Report — agent-observability-hub

**Source plan:** nenhum `*.plan.md`; jornadas derivadas do prompt do usuário nesta sessão de TDD.

## User journeys

1. Como gestor de frota, quero pedir uma análise de custos por período e receber um relatório em linguagem natural, para decidir onde cortar custos.
2. Como operador, quero ver latência, custo estimado e taxa de erro por agente, para diagnosticar a pipeline.
3. Como engenheiro, quero que output malformado de LLM seja retentado e depois falhe de forma tipada, para nunca propagar dado inválido.
4. Como engenheiro, quero um eval harness determinístico, para detectar regressões de coerência dos agentes.

## Task report (RED → GREEN por batch)

| Batch | Escopo | RED (comando/evidência) | GREEN (comando/evidência) | Commits |
|-------|--------|--------------------------|---------------------------|---------|
| 1 | Schemas Pydantic + guardrails | `pytest tests/test_schemas.py tests/test_guardrails.py` → `ModuleNotFoundError: No module named 'app'` (coleta interrompida) | mesmo alvo → `32 passed` | `fe0d263` (test), `768c980` (feat) |
| 2 | Agentes + orquestrador + observabilidade | `pytest tests/test_agents.py tests/test_observability.py tests/test_orchestrator.py` → `ModuleNotFoundError: No module named 'app.agents'` | `pytest` → `58 passed` | `d29104b` (test), `5a03280` (feat) |
| 3 | API FastAPI + eval harness | `pytest tests/test_api.py tests/test_evals.py` → 2 errors na coleta (módulos ausentes) | `pytest` → `69 passed` (após fix de `check_same_thread` na fixture) | `758f2b9` (test), commit feat subsequente |

Falha intermediária real durante GREEN do batch 3: endpoints síncronos do TestClient rodam em worker thread e a conexão SQLite da fixture era single-thread → 3 testes com 502. Correção na raiz (fixture compartilhada `tests/conftest.py`, `check_same_thread=False`), não nos testes.

## Test specification (amostra das garantias)

| # | Garantia | Teste | Tipo | Resultado |
|---|----------|-------|------|-----------|
| 1 | Estado da pipeline é imutável; handoffs criam cópias | `test_schemas.py::TestPipelineState::test_state_is_immutable_and_copies_do_not_mutate_original` | unit | PASS |
| 2 | Rate limiter bloqueia a chamada acima do limite e libera após a janela | `test_guardrails.py::TestRateLimiter` | unit | PASS |
| 3 | Padrões de prompt injection são bloqueados antes do LLM | `test_agents.py::TestWriterAgent::test_blocks_injected_content_before_calling_llm` | unit | PASS |
| 4 | Output inválido de LLM: 1 retry, depois `LLMParseError` | `test_agents.py::TestWriterAgent::test_retries_once_on_parse_failure` / `test_raises_after_retry_exhausted` | unit | PASS |
| 5 | Falha de estágio vira estado `failed` com progresso parcial, não exceção | `test_orchestrator.py::TestPipelineFailurePath` | integration | PASS |
| 6 | Métricas registram latência/custo/erro por agente em JSONL | `test_observability.py` | unit | PASS |
| 7 | API rejeita períodos inválidos (422), aplica rate limit (429) e não vaza erro interno (502 genérico) | `test_api.py` | integration | PASS |
| 8 | 9 cenários de eval passam com pipeline saudável e detectam pipeline quebrada | `test_evals.py` | eval | PASS |

## Coverage

`pytest --cov --cov-report=term` → **94% total** (390 stmts, 25 miss). Gap intencional: `evals/harness.py:main()` (70% — entrypoint CLI, exercitado manualmente: `python -m evals.harness` → `9/9 eval cases passed`).

## Merge evidence

Checkpoints RED/GREEN preservados como commits separados no branch `main` (sem squash).
