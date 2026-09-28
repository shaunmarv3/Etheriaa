# Numbers

Every number here comes from a query against the running system.

<!-- seed:begin (written by `uv run etheria seed`; do not edit by hand) -->
## Knowledge layer (measured 2026-09-28)

### Neo4j

| What | Count |
|---|---:|
| Drug (DDInter) | 1,939 |
| Drug (curated, not in DDInter) | 22 |
| Condition | 122 |
| Symptom | 153 |
| DrugClass | 106 |
| BodySystem | 15 |
| INTERACTS_WITH (DDInter) | 160,235 |
| INTERACTS_WITH (DDInter, Major) | 26,914 |
| INTERACTS_WITH (critical safety net) | 658 |
| Critical pairs absent from DDInter | 477 |
| ASSOCIATED_WITH (symptom -> condition) | 622 |
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

Graph eval (`uv run etheria eval --suite graph`, real `deepseek-flash`, graded by `deepseek-v4-pro`; full table in `docs/evals/graph.md`, every reply in `docs/evals/graph-replies.md`):

| What | Value |
|---|---:|
| Scenarios | 32 (16 safety, 16 quality) |
| Safety scenarios passed | 16 / 16 (target: all) |
| Quality scenarios passed | 16 / 16 (target: 90%) |
| Time to first token, p50 / p95 | 3.9 s / 5.4 s (target p50 at most 6 s) |
| Full response, p50 / p95 | 5.4 s / 6.8 s (target p50 at most 15 s) |
| RED turns: emergency block sent before any model call | 2 / 2 (0.0 s to first token) |
| Earlier runs of the same suite while fixing (not the result) | 32/32, 31/32, 31/32, 31/32 |

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
