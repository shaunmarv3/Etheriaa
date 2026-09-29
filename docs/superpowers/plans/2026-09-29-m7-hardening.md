# M7 Hardening - plan (one session, closes the project)

Exit: every success criterion in spec 1.2 holds (spec 17), the RAG evals exist, and the docs, spec, memory and Build Guide all say the same thing. Everything below runs in this one session, on main, in this order. Code first, then one pass of live runs, then docs, then close-out.

## Where 1.2 stands today

| # | Criterion | Status |
|---|---|---|
| 1 | compose + api + worker up; Docker <= 3 GB after seeding | 2.67 GB in M2; re-measure (Neo4j writable layer 288 MB since) |
| 2 | Frontend end-to-end flow | Done in M6 (Chrome) |
| 3 | Generated graph diagram in `ARCHITECTURE.md` | Done in M4; regenerate |
| 4 | Extraction eval >= 95% | 54/54 (M3) |
| 5 | Graph eval | Owner's 26: 14/14 safety, 11/12 quality (M4) |
| 6 | Seeder canaries + counts | Done in M2; re-run `--verify-only` |
| 7 | Security tests | Partial: RLS, cross-user API 404s, rate limits, token reuse exist |
| 8 | Latency p50 TTFT <= 6 s, full <= 15 s | 4.6 s / 6.1 s (M4); re-measured in phase B |

## Phase A - code (TDD, unit + integration tests, one commit per step)

A1. **Maintenance** (spec 3, 4.8, 7, 11.2). New `maintenance/` module: activities + a `MaintenanceWorkflow`.
   - `ensure_monthly_partitions` for `messages` and `audit_log`, 3 months ahead (they stop at Dec 2026 today).
   - Drop `audit_log` partitions older than 12 months (owner role; the app role cannot drop).
   - Prune checkpoint threads idle > 7 days and threads of deleted conversations (`adelete_thread`).
   - `uv run etheria maintain` runs it once; the worker registers a daily Temporal Schedule. Tests use a fixed clock.

A2. **Security suite** (`tests/security/`, criterion 7). Fill the gaps, do not duplicate existing tests:
   - Tool-level isolation: a tool run with user A's context never returns user B's rows.
   - Upload fuzzing: wrong magic bytes, encrypted PDF, oversize, page limit, decompression bomb, empty file.
   - Injection corpus: `input_guard` over a fixed corpus; the injected-report fixture is not obeyed (graph fake).
   - Fix the concurrent same-file upload 500 (known M3 bug).

A3. **Retrieval eval** (`--suite retrieval`). Golden queries over the synthetic reports, golden chunks known by construction. Hit@k, Recall@k, Precision@k, MRR for hybrid search alone vs hybrid + rerank. No LLM, deterministic; a unit test pins the metric maths.

A4. **Faithfulness in the graph eval.** Record each turn's evidence; `deepseek-v4-pro` splits the reply into claims and checks each against that evidence (the RAGAS method, in-house: no new dependency, no OpenAI key). Score = supported / all claims, per scenario and overall. Reported next to, not inside, the owner's criterion. The owner's 26 stay untouched (hash-pinned).
   Skipped, with the reason written in the report: answer correctness and context recall (no short golden answers), answer relevancy (the graph eval grades the free-text expectations), null-query refusal (covered by the out-of-graph scenarios and the no-evidence rule).

## Phase B - live runs (stack up once; stop api/worker/frontend before the full pytest run, RAM)

B1. `docker compose up -d`, `etheria migrate`, `etheria seed --verify-only` (criterion 6).
B2. `etheria maintain` against the real DB; readiness still green.
B3. `etheria eval --suite retrieval` -> `docs/evals/retrieval.md`.
B4. `etheria eval --suite graph` once (~6 min, cents): criterion 5, latency (criterion 8), faithfulness. Scores reported as they come out.
B5. Storage: N synthetic conversations -> checkpoint bytes per thread before and after pruning; Docker disk after seeding, Neo4j writable layer looked at (criterion 1).
B6. Full `pytest`, ruff, lint-imports, frontend `tsc` / `eslint` / `next build`.

## Phase C - docs (only what the code does, numbers only from phase B)

C1. `docs/NUMBERS.md`: every phase B number.
C2. `docs/SECURITY.md`: threat model as built (spec 11.1), DPDP Rule 6 mapping, breach runbook (72-hour Board intimation, Rule 7), processors (DeepSeek), known limitations stated plainly (access token valid up to 15 min after logout; login limiter per IP+email; multipart read before the 10 MB check; StreamGuard 200-char flush; other open M3/M4/M6 minors).
C3. `docs/ARCHITECTURE.md`: regenerated diagram, the maintenance schedule, the eval suites.
C4. Spec: 1.2 ticked with evidence, section 15 gains the retrieval eval and faithfulness, M7 marked done, a decision row for the RAG evals. CLAUDE.md: state = project complete, new commands.

## Phase D - close-out

D1. Commit, push main.
D2. Handover memory updated: project done, what stays open.
D3. Build Guide doc: M7 section (rubric shape), challenge rows, numbers rows (retrieval metrics, faithfulness), eval Q&As (RAG vs agentic evals), roadmap 7/7, changelog row.

## Owner actions (theirs, not blocking)

- Install Tesseract: `winget install UB-Mannheim.TesseractOCR` (then scanned uploads work; before B4 if you want it in the run).
- Review the curated YAML (`seed/data/*.yaml`, `safety/red_flags.yaml`, `safety/drug_cautions.yaml`).
- Answer the doc comment: lead the pitch with AI safety or backend engineering?
