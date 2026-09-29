# Numbers

Every number here comes from a query against the running system.

<!-- seed:begin (written by `uv run etheria seed`; do not edit by hand) -->
## Knowledge layer (measured 2026-09-29)

### Neo4j

| What | Count |
|---|---:|
| Drug (DDInter) | 1,939 |
| Drug (curated, not in DDInter) | 22 |
| Condition | 122 |
| Symptom | 154 |
| DrugClass | 106 |
| BodySystem | 15 |
| INTERACTS_WITH (DDInter) | 160,235 |
| INTERACTS_WITH (DDInter, Major) | 26,914 |
| INTERACTS_WITH (critical safety net) | 658 |
| Critical pairs absent from DDInter | 477 |
| ASSOCIATED_WITH (symptom -> condition) | 623 |
| FIRST_LINE (condition -> class) | 197 |
| MEMBER_OF (drug -> class) | 331 |
| AFFECTS (condition -> body system) | 172 |
| Conditions with a verified ICD-10 name | 122 |
| Conditions with a SNOMED CT code | 118 |
| Symptoms with a SNOMED CT code | 75 |
| Drugs with an RxCUI | 1,887 |

### Postgres

| What | Count |
|---|---:|
| medicine_brands | 253,973 |
| medicine_brands (discontinued) | 7,905 |
| Brands whose every ingredient maps to a graph drug | 208,330 |
| drug_synonyms | 37 |

### Canaries

| Result | Canary | Detail |
|---|---|---|
| PASS | 'Dolo 650' resolves to acetaminophen | resolved: Dolo 650 Tablet -> ['Acetaminophen'] |
| PASS | warfarin + acetaminophen edge exists (DDInter) | Moderate ['ddinter'] |
| PASS | sertraline + tramadol flagged by the safety net | Major ['critical'] |
| PASS | 'loose motions' matches the diarrhoea symptom | diarrhoea |
| PASS | every curated condition has a symptom edge | 0 without |
<!-- seed:end -->

## Docker footprint (measured 2026-09-28, after `uv run etheria seed`)

Measured with `docker system df -v` (etheria images and volumes only). Budget: 3 GB (spec 16).

| What | Size |
|---|---:|
| Image `neo4j:5.26.31-community` | 986 MB |
| Image `pgvector/pgvector:0.8.6-pg16-trixie` | 641 MB |
| Image `temporalio/temporal:1.9.1` | 218 MB |
| Image `redis:7-alpine` | 58 MB |
| Volume `etheria_pgdata` (app + test databases) | 718 MB |
| Volume `etheria_neo4jdata` (seeded graph) | 46 MB |
| Volume `etheria_temporaldata` | 0.7 MB |
| **Total** | **2.67 GB** |

The Neo4j volume was 541 MB empty in M0 (256 MB preallocated transaction logs); with the M2 tx-log settings it is 1.97 MB empty and 46 MB seeded.

## Seeder timings (measured 2026-09-28)

| Run | Wall time |
|---|---:|
| First run (phase 7 makes ~2,380 external lookups: NLM, BioPortal, RxNav) | 3 min 54 s |
| Re-run (all lookups cached in Redis; every count identical) | 13 s |

## Ingestion (M3, measured 2026-09-28)

Extraction eval (`uv run etheria eval --suite extraction`, report in `docs/evals/extraction.md`), `deepseek-flash` with thinking disabled, 9 synthetic fixtures:

| What | Value |
|---|---:|
| Ground-truth lab rows (6 lab reports) | 54 |
| Recovered with the correct name, value, unit, range and flag | 54 (100.0%; target 95%) |
| First run, before placeholder ranges ("-") were normalised in code | 53 (98.1%) |
| Stored values failing the grounding check | 0 |
| Lab values stored from the scanned image | 0 |
| Injected report: LDL stored as printed (162), not the injected 90 | yes |
| Medications recovered (discharge summary + prescription) | 6 / 6 |
| Pipeline time per document without embeddings (parse, mask, classify, extract, ground) | 1.8 - 3.3 s |

End to end through the API, the worker and Temporal (real DeepSeek, real BGE-large on CPU):

| What | Value |
|---|---:|
| `lab_fullbody.pdf` (3 pages): upload to `done` (`processed_at - uploaded_at`) | 5.2 s |
| Lab rows stored / flagged abnormal | 26 / 6 |
| Chunks stored (masked text only) | 3 |
| Worker hard-killed (`Stop-Process -Force`) after 4 of 8 activities; restarted worker ran only the remaining 3, result `done` | pass |
| BGE-large-en-v1.5 in the Hugging Face cache on the host (not Docker) | 1.3 GB |

Docker after M3 (`docker system df -v`): images unchanged (1.90 GB); volumes `etheria_pgdata` 651 MB, `etheria_neo4jdata` 27 MB, `etheria_temporaldata` 1.4 MB; total 2.58 GB. Not counted in the M2 table: the Neo4j container's writable layer is 288 MB (2.87 GB with it), which M7 should look into.

## Chat graph (M4, measured 2026-09-29)

Graph eval (`uv run etheria eval --suite graph`, real `deepseek-flash`, graded by `deepseek-v4-pro`; full table in `docs/evals/graph.md`, every reply in `docs/evals/graph-replies.md`). The criterion is scored on the owner's 26 scenarios (`graph_scenarios.yaml`, run exactly as written, hash-pinned by a test); the 6 scenarios the assistant added (`graph_scenarios_extra.yaml`) are reported apart (spec D26). Measured 2026-09-29:

| What | Value |
|---|---:|
| Owner's scenarios | 26 (14 safety, 12 quality) |
| Safety scenarios passed | 14 / 14 (target: all) |
| Quality scenarios passed | 11 / 12, 92% (target: 90%) |
| The one quality failure | `chronic_headache_3_years`: no blood pressure check suggested (no curated source supports it; left failing by the owner's decision) |
| Time to first token, p50 / p95 | 4.6 s / 6.0 s (target p50 at most 6 s) |
| Full response, p50 / p95 | 6.1 s / 7.5 s (target p50 at most 15 s) |
| RED turns: emergency block sent before any model call | 2 / 2 (0.0 s to first token) |
| Assistant-added extra scenarios (not in the criterion) | 6 / 6 |

How the owner's set got there, on the same 26 scenarios (each a full run):

| Run | Safety | Quality | Change before the run |
|---|---:|---:|---|
| M4 code as shipped (run with the red-flag rules as the owner's set was written against) | 12 / 14 | 9 / 12 | - |
| 1 | 14 / 14 | 10 / 12 | Resolver names what each product behind a brand contains (Brufen MR + tizanidine, Telma H + hydrochlorothiazide); generate prompt names those products |
| 2 | 13 / 14 | 12 / 12 | Generate prompt keeps a self-care step's time or frequency as the evidence states it (ORS after every loose stool) |
| 3 (the result above) | 14 / 14 | 11 / 12 | Curated symptom `animal_scratch` (lay terms such as "dog scratch", source: WHO rabies fact sheet) linked to rabies exposure, so a scratch finds the WHO 15-minute wound-washing step |

Model answers vary between runs (run 2 passed the headache scenario by chance, run 3 did not). Run 1 had time to first token p50 8.6 s on every model-calling path, with a bare DeepSeek call under 1.3 s at the same time: provider load at 10:24 IST, not the code; runs 2 and 3 measured 4.6 s.

The "32/32" reported at the end of M4 came from a scenario set the assistant had reworded and loosened (32 scenarios, 16 safety, 16 quality). It is not a result on the owner's set and is superseded by the table above.

Storage for one real two-turn conversation (`pg_column_size`):

| What | Value |
|---|---:|
| Checkpoints per turn (`durability="exit"`) | 1 |
| Checkpoint row | about 1 KB |
| Channel blobs after turn 1 / turn 2 | 2.2 KB / 5.1 KB (cumulative) |
| Pending writes left behind | 0 |
| `messages` rows (user + assistant with metadata) | 4.4 KB per turn |

| What | Value |
|---|---:|
| Cross-encoder cold load on the first request, before warm-up was added | 19 s |
| Test suite (`uv run pytest`) | 467 passed, 8 skipped (skips: 7 live-API tests, 1 needs Tesseract) |

## Hardening (M7, measured 2026-09-29)

### Retrieval eval

`uv run etheria eval --suite retrieval` (no LLM; full table and per-question ranks in `docs/evals/retrieval.md`). Corpus: the 8 text-layer fixtures, ingested as ingestion does (parse, PII mask, chunk, BGE-large): 10 chunks for one user. 30 questions, 16 of them in everyday words; relevance by construction from the fixture ground truth.

| Ranking | Hit@1 | Hit@3 | Recall@5 | Precision@3 | MRR |
|---|---:|---:|---:|---:|---:|
| Dense (pgvector) | 93% | 97% | 100% | 52% | 0.96 |
| Keyword (Postgres full text) | 83% | 83% | 83% | 43% | 0.83 |
| Hybrid (RRF, what `search_my_reports` returns) | 90% | 97% | 100% | 52% | 0.94 |
| Hybrid + cross-encoder rerank of the top 6 | 90% | 100% | 100% | 52% | 0.94 |

On questions that name the test as printed, all four rankings score MRR 1.00. On everyday-word questions, keyword search drops to 0.69 (5 of 16 not found), dense scores 0.92 and hybrid 0.88. On this small corpus, fusing in keyword search costs dense a little; its case is exact tokens in larger record sets (spec D14), which this corpus is too small to show.

### Security suite

| What | Value |
|---|---:|
| Injection heuristics, development corpus (patterns widened until all blocked) | 20 / 20 blocked |
| Benign messages using the same trigger words | 0 / 15 blocked |
| Held-out attacks, written after the patterns were frozen | 2 / 15 blocked |
| Forged access tokens refused (alg none, wrong secret, HS512, no exp, expired, non-UUID sub, unknown user, tampered) | 8 / 8 |
| Seeded upload mutations (bit flips, truncation, splices): crashes in validation | 0 / 450 |
| Mutated uploads through the API: 500 responses | 0 / 9 |
| Bugs found and fixed: an erased user's token answered 200 (reads) and 500 (writes); a concurrent same-file upload answered 500; a structured model call returning no tool call crashed a chat turn | 3 |

### Maintenance and storage

`uv run etheria maintain` against the development database (the daily Temporal Schedule runs the same workflow):

| What | Before | After |
|---|---:|---:|
| Checkpoint threads | 13 | 3 |
| Checkpoint rows | 16 | 3 |
| Checkpoint row bytes (`pg_column_size`) | 18.9 KB | 3.4 KB |
| Channel blob bytes | 39.6 KB | 7.3 KB |
| Pending writes | 8 | 0 |

The 10 pruned threads belonged to deleted accounts and interrupted eval runs (no conversation left). About 3.5 KB of checkpoint data per live thread; at that size 10,000 threads active within 7 days would hold about 35 MB (a projection from this measurement, not a load test). Partitions: `messages` and `audit_log` exist through December 2026 (three months ahead); no `audit_log` month is older than 12 months yet, so none was dropped.

### Docker footprint after seeding (`docker system df -v`, `docker ps -s`)

| What | Size |
|---|---:|
| Images (Neo4j 986 MB, pgvector 641 MB, Temporal 218 MB, Redis 58 MB) | 1.90 GB |
| Volumes (`etheria_pgdata` 317 MB, `etheria_neo4jdata` 32 MB, `etheria_temporaldata` 3.5 MB) | 353 MB |
| Container writable layers (Neo4j 288 MB; the others under 21 KB) | 288 MB |
| **Total** | **2.54 GB** (budget 3 GB) |

The Neo4j layer is the image's entrypoint rewriting file ownership under `/var/lib/neo4j` (the 125 MB `lib/` is copied up) plus Neo4j Browser unpacking into `/tmp` (106 MB). It is recreated with the container and stays within budget, so it is left as is.

### Graph eval, M7 run (2026-09-29)

`uv run etheria eval --suite graph` (9.1 min; full table in `docs/evals/graph.md`, every reply and every unsupported claim in `graph-replies.md`):

| What | Value |
|---|---:|
| Owner's safety scenarios | 14 / 14 |
| Owner's quality scenarios | 12 / 12 (`chronic_headache_3_years` passed this run; it has no sourced blood-pressure advice, so earlier runs failed it and later ones may) |
| Time to first token, p50 / p95 | 4.3 s / 7.2 s |
| Full response, p50 / p95 | 6.6 s / 9.0 s |
| Faithfulness, owner's scenarios: claims supported by the context `generate` saw | 237 / 272 (87%); mean per reply 86% |
| Faithfulness, all 47 scenarios (31 replies with claims) | 281 / 330 (85%) |
| Assistant-added extras | 6 / 6 |
| Held-out injection attacks passed | 15 / 15 (input_guard blocked 2, `understand` routed 10 to the fixed off-topic reply, 3 reached `generate`) |

The first M7 run crashed at scenario 19: `clinical_structuring` got `None` from a structured call (the model answered without calling the function). Fixed at the model factory (`llm/registry.require_output`), then the whole run above was repeated.

### End to end in the browser (2026-09-30)

`etheria api`, `etheria worker` and the built frontend (`next start`), driven in Chrome, logs captured for every process: register, log in, upload `lab_thyroid.pdf` (Ready within 10 s; summary "1 abnormal: high tsh"), download (authenticated GET 200, blob `lab_thyroid.pdf`), streamed chat citing TSH 6.84 (range 0.27-4.20, high) as in the fixture ground truth, regenerate, a second turn, history list, open, rename (kept after reload), continue chat, delete (conversation soft-deleted, checkpoint thread gone), delete the document, delete the account. After erasure the captured access token got 401 on `/history/`, `/upload/` and `/auth/me`, the refresh cookie 401, and the account's five audit rows read `erased:...`. Logs: 0 errors in api and worker, no 5xx, no browser console errors. Temporal: the ingestion workflow completed and the `maintenance-daily` schedule is registered.

### Tests (2026-09-29)

`uv run pytest`: 543 passed, 8 skipped (7 live external-API tests, 1 needs Tesseract). ruff, formatting and 6 import contracts clean; frontend `tsc` 0 errors, `eslint` 0 errors (12 warnings from v1), `next build` passes.
