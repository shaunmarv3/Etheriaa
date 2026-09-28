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
