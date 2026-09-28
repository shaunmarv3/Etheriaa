# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Etheria v2: an India-aware AI health assistant (triage + health information, not a clinician). It is a from-scratch rebuild of the v1 backend, plus a copy of the v1 Next.js frontend with Clerk removed. It is a portfolio and learning project: synthetic data only, no real users.

**The design spec is the source of truth:** `docs/superpowers/specs/2026-09-28-etheria-v2-design.md`. Read the relevant section before building anything. If a decision changes, update the spec in the same change.

## Current state

- Spec approved 2026-09-28. Plans live in `docs/superpowers/plans/`; workflow: plan per milestone -> execute task-by-task -> milestones M0-M7 (spec section 17).
- M0 done (`docs/spikes/m0-results.md`). M1 done: settings, logging, error shape, schema with RLS and partitions, auth, health/readiness, test harness, import contracts.
- M2 done (plan `docs/superpowers/plans/2026-09-28-m2-knowledge.md`): medical API clients (`medical_apis/`), knowledge services (`knowledge/`: resolver, interactions, condition explorer), seeder (`seed/`), curated YAML (`seed/data/`, `safety/red_flags.yaml`), real counts in `docs/NUMBERS.md`. The curated YAML still needs the owner's review.
- M3 done (plan `docs/superpowers/plans/2026-09-28-m3-ingestion.md`): `POST/GET/DELETE /upload/` + download (`api/routers/upload.py`), encrypted `FileStore`, `IngestDocumentWorkflow` + `IngestionActivities` (`ingestion/`), `llm/registry.py` + `prompts/*.md`, BGE embeddings (`retrieval/embedding.py`), synthetic fixtures (`tests/fixtures/reports/`, regenerate with `generate.py`), extraction eval 54/54 (`docs/evals/extraction.md`). Tesseract is not installed yet (owner action; scanned uploads fail with `ocr_unavailable` until it is).
- Next: M4 (reasoning graph).
- Remote: `origin` = https://github.com/shaunmarv3/etheria-v2, branch `main`.

## Hard rules

- **Never modify anything under `D:\Etheria\`.** `D:\Etheria\etheria` (v1 frontend) and `D:\Etheria\etheria-backend\etheria-backend` (v1 backend) are read-only references. Port code by reading them and writing into this repo. The frontend is copied into `frontend/`, never edited in place.
- **Product safety rules** (spec 4.6). Never diagnose, never prescribe or give doses, always append the disclaimer. Emergencies route to India numbers: 112, 108 (ambulance), Tele-MANAS 14416. Never state that a drug combination is safe: a missing interaction is reported as "not found, confirm with a pharmacist". Never extract numeric lab values from OCR'd images.
- **Docs describe only what the code does.** v1's README described a LangGraph system that did not exist. In v2, `docs/ARCHITECTURE.md` embeds a diagram generated from the compiled graph, and every number in `docs/NUMBERS.md` comes from a query against the running system.
- **Docker runs infrastructure only** (Postgres+pgvector, Neo4j, Redis, the Temporal dev server), with a total budget of 3 GB. v1 reached about 40 GB. The Python app runs natively via `uv`, torch is the CPU-only wheel, and model weights never go into images.
- **DDInter data is never committed.** It has no licence. The seeder downloads it and verifies checksums (`data/` is gitignored).
- Copy API keys from v1's `.env` only with the owner's explicit permission.

## Planned commands (from the spec; update this section as milestones land)

```bash
docker compose -f infra/docker-compose.yml up -d   # Postgres, Neo4j, Redis, Temporal (UI :8233)
cd backend && uv run etheria migrate               # alembic upgrade head (owner role)
uv run pytest -m "not integration"                 # unit tests, no docker needed
uv run pytest                                      # everything (needs docker infra)
cd backend && uv sync                              # Python 3.12, uv + pyproject + lockfile
uv run etheria api            # FastAPI + in-process LangGraph chat graph
uv run etheria worker         # Temporal worker: ingestion (loads BGE-large, ~25 s)
uv run etheria seed           # knowledge layer: 8 phases + canaries -> docs/NUMBERS.md (idempotent)
uv run etheria seed --verify-only   # counts + canaries only; --skip-codes skips external lookups
uv run etheria eval --suite extraction   # extraction eval, real DeepSeek (opt-in, costs cents) -> docs/evals/
uv run etheria graph-diagram  # regenerate the Mermaid diagram in docs/ARCHITECTURE.md
uv run pytest tests/unit/test_x.py::test_name     # single test
uv run pytest tests/live --live                   # real external APIs + curated source URLs (opt-in)
uv run ruff check . && uv run lint-imports        # lint + module-boundary contracts
```

## Architecture (big picture)

Modular monolith with two processes: `api` (FastAPI + LangGraph in-process) and `worker` (Temporal). Package: `backend/src/etheria/`. Import-linter enforces the dependency rules in spec 3.3: nothing imports `api`, and `ingestion` never imports `graph`.

**Chat graph** (spec 4). A deterministic guardrail shell wraps a bounded, tool-calling retrieval agent:
`load_context -> input_guard -> [summarize] -> understand -> (retrieval_agent || triage) -> rerank_evidence -> (generate || clinical_structuring) -> finalize`.
Invariants that span many files:
- **User identity lives only in the trusted runtime context** (`ChatContext`, read through `Runtime` / `ToolRuntime`). It never appears in model-visible state or tool arguments, so a model or injected text cannot reach another user's data. RLS in Postgres backs this up.
- **The `messages` table is the system of record.** LangGraph checkpoints are only execution state: `durability="exit"`, `finalize` empties the per-turn `turn` field, and idle threads are pruned. Regenerate forks from the previous turn's checkpoint, falling back to rebuilding the thread from `messages`.
- **Triage rules can only raise the level, and failures default to YELLOW.** For RED, code emits the emergency block before the first model token. `StreamGuard` filters generated sentences deterministically. The LLM audit runs afterwards and is non-blocking; it is for measurement.
- **Caching covers public layers only** (medical API responses, query embeddings, knowledge-graph lookups). Never cache answers or anything user-scoped.
- **`llm/registry.py` is the only place that maps nodes to models:** `deepseek-flash` (thinking disabled) for structured, tool and streamed generation nodes, `deepseek-v4-pro` for the post-hoc audit. The owner has only a DeepSeek key; the voice provider is decided at M5 start.

**Ingestion** (spec 5). A Temporal workflow runs parse -> PII mask (Aadhaar, Indian phone numbers) -> classify -> per-type extraction -> validate -> chunk/embed -> store. The LLM parses and code judges: every extracted number must appear verbatim in the source text (grounding check), and the abnormal flags are computed by code. Rule: normalise into tables what we query by field; store in JSONB what we only display.

**Knowledge layer** (spec 6). Neo4j holds curated India-common conditions and symptoms plus DDInter interactions (`INTERACTS_WITH {severity, source}`), with a curated critical-interaction safety net. Postgres holds the 253,973 Indian brand names (`medicine_brands`, trigram fuzzy match) and `drug_synonyms` (paracetamol -> acetaminophen). Brand names are a lookup, not a graph traversal. Drugs are keyed by `Drug.key` (normalised name); 22 India-common drugs DDInter lacks are curated `extra_drugs` so the class-level safety net covers them. Curated nodes and edges carry a namespace `ns` ("main"): Neo4j Community has one database, so integration tests load into their own namespace and clean up, never touching the seeded graph.

**Frontend contract.** SSE event shapes and REST responses must match `frontend/src/lib/types.ts` exactly. For example, `Citation.relevanceScore` is camel-case while the `AgentTrace` keys are snake_case. Contract tests pin this. Endpoints kept, cut and never built are listed in spec section 10.

## Library notes (verified against installed versions, 2026-09)

LangChain 1.4.0 / LangGraph 1.2.11: do not write 0.x-era code.
- `langchain.agents.create_agent(...)` returns a `CompiledStateGraph`. `AgentExecutor` and `initialize_agent` no longer exist.
- Agent bounds: `ModelCallLimitMiddleware(run_limit=..., exit_behavior="end")`, `ToolCallLimitMiddleware(run_limit=...)`.
- Join parallel branches with a waiting edge, `add_edge(["a", "b"], "join")`. It runs once, after all listed branches finish.
- `invoke`/`astream` accept `context=` and `durability="sync"|"async"|"exit"`. `add_node` accepts `retry_policy`, `timeout` and `defer`.
- Checkpointer: `langgraph-checkpoint-postgres` 3.1.x (`AsyncPostgresSaver`) implements `adelete_thread` but NOT `aprune` (raises `NotImplementedError`, verified in M0). Pruning = delete the thread + rebuild from `messages`.
- `ToolCallLimitMiddleware` defaults to `exit_behavior="continue"`; `ModelCallLimitMiddleware` defaults to `"end"`.
- DeepSeek: `ChatDeepSeek(model="deepseek-flash", extra_body={"thinking": {"type": "disabled"}})`; thinking is on by default. `with_structured_output(..., method="function_calling")` scored 10/10 in M0.
- Custom stream events: `langgraph.config.get_stream_writer()`. Test fakes: `GenericFakeChatModel`.
- NLM's RxNav drug-interaction API was retired on 2024-01-02. Use RxNav for name normalisation only; interactions come from DDInter.

## Environment notes

- Windows 11, Git Bash plus PowerShell. The console is cp1252: `print()` of non-ASCII characters (such as box-drawing) crashes, so keep script output ASCII.
- A very long Bash heredoc fails with `ENAMETOOLONG`; write large files with the Write tool.
- psycopg async cannot run on Windows' default ProactorEventLoop. Entry points use `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)`; pytest uses the selector policy (M1 conftest).
- Infra host ports: Postgres 5433, Redis 6380 (5432 / 6379 are taken by the owner's native PostgreSQL 18 service and a WSL Redis). Neo4j 7474/7687, Temporal 7233, UI 8233.
- Runtime data (uploads, seed downloads) lives in `backend/data/`, which is gitignored. Curated YAML in `src/etheria/seed/data/` is committed.
- The owner is learning LangGraph through this build (lab: `D:\agenticshi\langgraph-lab`). When implementing graph pieces, briefly name the LangGraph concept being used.
