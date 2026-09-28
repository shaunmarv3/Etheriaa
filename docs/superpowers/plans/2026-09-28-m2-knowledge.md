# M2 Knowledge Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `uv run etheria seed` downloads and verifies the public datasets, loads Postgres (`medicine_brands`, `drug_synonyms`) and Neo4j (DDInter drugs and interactions, the critical safety net, curated India-common conditions and symptoms), enriches codes from NLM / BioPortal / RxNav, passes the five canaries and writes the real counts to `docs/NUMBERS.md`.

**Architecture:** `medical_apis` holds cached, throttled httpx clients (ported from v1, aiohttp -> httpx). `cache.json_cache` is the one cache-aside helper for public data. `seed` owns the manifest, downloader, parsers, loaders, code enrichment, verification and the phase runner. `knowledge` owns the Neo4j driver, schema and the three read services later used as M4 tool backends: `MedicineResolver`, `InteractionService`, `ConditionExplorer`. The seeder writes as the Postgres owner role; the app role stays read-only on reference tables.

**Tech Stack:** httpx 0.28, redis-py 8.1, neo4j driver 6.3, psycopg 3 (COPY), PyYAML, pydantic 2, typer.

**Spec:** `docs/superpowers/specs/2026-09-28-etheria-v2-design.md` sections 3.3, 3.4, 6, 8.3, 16, 17. M0 facts: `docs/spikes/m0-results.md`.

## Measured facts (2026-09-28, before writing this plan)

- DDInter: 8 CSVs `https://ddinter.scbdd.com/static/media/download/ddinter_downloads_code_{A,B,D,H,L,P,R,V}.csv`, header `DDInterID_A,Drug_A,DDInterID_B,Drug_B,Level`. 222,383 rows -> **1,939 drugs, 160,235 unordered pairs**, no severity conflict between files. Levels: Moderate 130,367 / Unknown 47,182 / Major 33,896 / Minor 10,938 (row counts). Drug names are unique case-insensitively. The server is slow (one file took 16 minutes) and supports HTTP Range, so the downloader resumes.
- Warfarin + Acetaminophen is in DDInter (Moderate). **Sertraline + Tramadol is not**: the safety net must add it.
- Indian Medicine Dataset: `https://raw.githubusercontent.com/junioralive/Indian-Medicine-Dataset/main/DATA/indian_medicine_data.csv`, 253,973 rows, header `id,name,price(₹),Is_discontinued,manufacturer_name,type,pack_size_label,short_composition1,short_composition2`. Compositions look like `Amoxycillin  (500mg) ` (irregular whitespace, dose in parentheses); `short_composition2` is empty in 141,802 rows. "Dolo 650" appears only as `Dolo 650 Tablet`, so exact match is not enough.

## Global Constraints

- Never modify anything under `D:\Etheria\`. DDInter data is never committed (`backend/data/` is gitignored); curated YAML under `src/etheria/seed/data/` is committed.
- Run from `backend/` with `uv run`. Windows: async entry points use the selector loop (`cli._loop_factory`). Console output ASCII only.
- Cache TTLs (spec 8.3): PubMed 24 h, MedlinePlus 7 d, ICD-10 / BioPortal / RxNav 30 d. Cache public data only.
- Seeder: idempotent (`MERGE` / truncate-and-COPY in one transaction), per-phase report, **no silent `except`**, non-zero exit on any canary failure.
- Interaction semantics: a pair with no edge is `not_found`, never safe; unresolved names are reported.
- Resolution never guesses: ambiguous or low-similarity names are `unresolved`.
- Neo4j community has a single database: integration tests create uniquely named nodes (`zz-test-<run id>`) and delete them afterwards, so they never clobber the seeded graph.
- Docker total at most 3 GB after seeding.

## Review Focus

1. **Brand-name noise**: `"DOLO 650"`, `"dolo-650"`, `"Dolo 650 tab"` resolve to acetaminophen; a query whose close candidates carry *different* ingredient sets is `ambiguous`, not guessed. (Task 8 `test_resolver_*`.)
2. **Direction and duplicates**: a DDInter pair listed as (B, A) or in several ATC files is one undirected edge, found from either side. (Task 7 `test_interaction_found_in_both_directions`, Task 5 `test_pairs_are_deduplicated_across_files`.)
3. **Interrupted or tampered download**: a partial file resumes via Range; a checksum mismatch fails the phase and nothing is loaded. (Task 4.)
4. **Re-running the seeder**: counts are identical after a second run. (Task 10 manual check, recorded.)
5. **Upstream failure**: an HTTP error or timeout raises `MedicalApiError` and is not cached; Redis being down does not break fetches (fail open). (Task 2.)

---

## File structure

```text
infra/docker-compose.yml                     # Neo4j tx-log trim
backend/pyproject.toml                       # + pyyaml; --live option lives in conftest
backend/src/etheria/
  core/settings.py                           # + seed_dir
  cache/json_cache.py                        # JsonCache.get_or_fetch (fail-open cache-aside)
  medical_apis/base.py                       # ApiClient: shared httpx, JsonCache, throttle, MedicalApiError
  medical_apis/{pubmed,medlineplus,icd10,bioportal,rxnav}.py
  knowledge/neo4j.py                         # create_driver(settings)
  knowledge/schema.py                        # constraints + indexes (idempotent)
  knowledge/text.py                          # normalise_name, normalise_term (shared by seed + services)
  knowledge/resolver.py                      # MedicineResolver
  knowledge/interactions.py                  # InteractionService
  knowledge/conditions.py                    # ConditionExplorer, SymptomMatcher
  safety/red_flags.yaml  safety/red_flags.py # rule table + schema (matcher is M4)
  seed/manifest.yaml  seed/download.py
  seed/sources.py                            # DDInter + medicine CSV parsing, composition parsing
  seed/curated.py                            # pydantic models + cross-reference validation for data/*.yaml
  seed/data/{conditions,symptoms,drug_classes,critical_interactions,drug_synonyms}.yaml
  seed/load_postgres.py  seed/load_neo4j.py  seed/codes.py  seed/verify.py  seed/runner.py
  cli.py                                     # + seed command
backend/tests/
  unit/test_json_cache.py test_medical_apis.py test_download.py test_sources.py
  unit/test_curated.py test_resolver_logic.py test_numbers_doc.py
  integration/test_seed_postgres.py test_knowledge_graph.py test_resolver.py
  live/test_medical_apis_live.py             # opt-in: --live
  fixtures/medical_apis/*                     # small real responses captured once
docs/NUMBERS.md
```

---

### Task 1: Infra and settings

**Files:** `infra/docker-compose.yml`, `backend/src/etheria/core/settings.py`, `backend/pyproject.toml`, `backend/tests/conftest.py`

- [ ] Neo4j env: `NEO4J_db_tx__log_preallocate=false`, `NEO4J_db_tx__log_rotation_size=32M`, `NEO4J_db_tx__log_rotation_retention__policy=keep_none`, `NEO4J_server_logs_debug_level`, keep heap/pagecache caps. Confirm the graph is empty (`MATCH (n) RETURN count(n)` = 0), then recreate the neo4j container and volume and measure the volume (`docker system df -v`). Record before/after in the commit message.
- [ ] `Settings.seed_dir: Path = BACKEND_DIR / "data" / "seed"`.
- [ ] Add `pyyaml>=6,<7` to dependencies; `uv lock`.
- [ ] conftest: `--live` option; tests under `tests/live/` are skipped without it.
- [ ] Commit `chore(infra): trim neo4j tx logs; seed_dir setting; live test opt-in`.

### Task 2: Cache-aside and the API client base

**Files:** `cache/json_cache.py`, `medical_apis/base.py`, `tests/unit/test_json_cache.py`, `tests/unit/test_medical_apis.py` (base part)

**Interfaces (produces):**
```python
class JsonCache:                       # cache/json_cache.py
    def __init__(self, redis: Redis | None, namespace: str = "cache") -> None
    @staticmethod
    def key(source: str, *parts: object) -> str   # "cache:<source>:<sha256 of json(parts)>[:32]"
    async def get_or_fetch(self, key: str, ttl_s: int, fetch: Callable[[], Awaitable[T]]) -> T
    hits: int; misses: int                         # for the seed report / agent_trace later

class MedicalApiError(Exception): source: str      # medical_apis/base.py
class ApiClient:
    def __init__(self, http: httpx.AsyncClient, cache: JsonCache, *, source: str,
                 per_second: float, ttl_s: int) -> None
    async def get_json(self, url, params=None, headers=None) -> Any   # throttled, raises MedicalApiError
    async def get_text(self, url, params=None, headers=None) -> str
    async def cached(self, key_parts: tuple, fetch) -> Any            # JsonCache with this client's TTL
def create_http_client() -> httpx.AsyncClient      # timeout 15 s (connect 5), UA "etheria-v2 (portfolio)"
```
- Throttle: in-process `asyncio` token spacing per client (1/per_second between request starts). Seeding and the API process each hold one client, so in-process spacing is enough; v1's Redis counter skipped requests instead of waiting.
- Tests: miss then hit (fetch called once); Redis raising -> fetch still returns, warning logged; fetch raising -> nothing cached and error propagates; `get_json` on 500 / timeout raises `MedicalApiError` (httpx `MockTransport`); throttle spaces two calls by at least `1/per_second`.
- [ ] Tests fail -> implement -> pass -> commit `feat(medical_apis): cache-aside helper and throttled httpx base client`.

### Task 3: Medical API clients (ported from v1)

**Files:** `medical_apis/{pubmed,medlineplus,icd10,bioportal,rxnav}.py`, `tests/fixtures/medical_apis/*`, `tests/unit/test_medical_apis.py`, `tests/live/test_medical_apis_live.py`

**Interfaces (produces), pydantic models returned, cached as JSON:**
```python
PubMed(api: ApiClient, api_key: str | None)            # 10/s with key, 3/s without; TTL 24 h
  async search(query: str, k: int = 5) -> list[str]
  async fetch(pmids: list[str]) -> list[Article]       # Article{pmid,title,abstract,year,mesh_terms}
  async search_articles(query: str, k: int = 5) -> list[Article]
MedlinePlus(api)                                       # TTL 7 d
  async search(term: str, k: int = 3) -> list[HealthTopic]   # HealthTopic{title,url,summary}
Icd10(api)                                             # NLM Clinical Tables; TTL 30 d
  async lookup(code: str) -> Icd10Code | None          # exact code only, else None
  async search(term: str, k: int = 10) -> list[Icd10Code]
BioPortal(api, api_key: str)                           # TTL 30 d
  async find_concept(term: str) -> Concept | None      # Concept{pref_label, snomed: str|None, cui: str|None}
RxNav(api)                                             # normalisation only; TTL 30 d
  async rxcui(name: str) -> str | None
```
- Capture one small real response per endpoint into `tests/fixtures/medical_apis/` (curl, trimmed), and parse those in unit tests. No `get_interactions` (retired 2024-01-02).
- Live tests (`--live`): one real call per client.
- [ ] Commit `feat(medical_apis): pubmed, medlineplus, icd10, bioportal, rxnav clients`.

### Task 4: Manifest and resumable, verified download

**Files:** `seed/manifest.yaml`, `seed/download.py`, `tests/unit/test_download.py`

**Interfaces:**
```python
@dataclass(frozen=True) class SourceFile: name: str; url: str; sha256: str; size: int
def load_manifest(path: Path | None = None) -> list[SourceFile]
async def ensure_file(http: httpx.AsyncClient, f: SourceFile, dest_dir: Path, *, attempts: int = 6) -> Path
    # present + checksum ok -> skip; partial -> Range resume; 416/complete -> verify;
    # mismatch after completion -> delete, raise ChecksumMismatch (never loaded)
```
- Manifest values are the checksums measured above (9 files).
- Tests (MockTransport): fresh download verifies; partial file is resumed with `Range: bytes=<n>-`; server ignoring Range (200) restarts cleanly; wrong checksum raises and deletes; already-complete file makes no request.
- [ ] Commit `feat(seed): manifest and resumable checksum-verified downloader`.

### Task 5: Source parsing and the Postgres load

**Files:** `knowledge/text.py`, `seed/sources.py`, `seed/load_postgres.py`, `seed/data/drug_synonyms.yaml`, `tests/unit/test_sources.py`, `tests/integration/test_seed_postgres.py`

**Interfaces:**
```python
def normalise_name(s: str) -> str        # knowledge/text.py: lowercase, NFKC, collapse spaces, strip punctuation at ends
def parse_ingredient(s: str) -> str | None   # "Amoxycillin  (500mg) " -> "amoxycillin"; "" -> None
def read_ddinter(paths: list[Path]) -> DDInterData   # drugs: dict[id,name]; pairs: dict[(id_lo,id_hi), level]
def read_medicines(path: Path) -> Iterator[BrandRow] # BrandRow matches medicine_brands columns
async/sync load_medicine_brands(owner_url, rows) -> int   # one tx: TRUNCATE + COPY; returns count
load_drug_synonyms(owner_url, synonyms: dict[str,str]) -> int  # upsert
```
- `drug_synonyms.yaml`: about 30 Indian/British -> DDInter names (paracetamol -> acetaminophen, amoxycillin -> amoxicillin, frusemide -> furosemide, salbutamol -> albuterol, adrenaline -> epinephrine, glibenclamide -> glyburide, ...). Every canonical must be a DDInter drug name (checked in Task 6's validation using the DDInter file when present).
- Tests: ingredient parsing edge cases (double spaces, `%` doses, `w/v`, empty); ddinter dedupe across files and reversed pairs; COPY of a 5-row fixture into `etheria_test`; re-run gives the same count; the app role still cannot write.
- [ ] Commit `feat(seed): parse DDInter and brand data; load medicine_brands and drug_synonyms`.

### Task 6: Curated data (owner review required)

**Files:** `seed/data/{conditions,symptoms,drug_classes,critical_interactions}.yaml`, `safety/red_flags.yaml`, `safety/red_flags.py`, `seed/curated.py`, `tests/unit/test_curated.py`

**Schemas (pydantic, `extra="forbid"`):**
```yaml
# symptoms.yaml
- code: diarrhoea            # slug, unique
  name: Diarrhoea
  lay_terms: [loose motions, loose stools, running stomach]
  source: https://medlineplus.gov/diarrhea.html
# conditions.yaml
- icd10: A90                 # unique
  name: Dengue fever
  synonyms: [dengue, break-bone fever]
  body_systems: [Infectious]
  india_common: true
  symptoms: {fever: 1.0, headache: 0.6, retro_orbital_pain: 0.8, ...}   # symptom code -> weight (0, 1]
  first_line: [paracetamol_antipyretic]        # drug class names
  self_care: [...]
  red_flags: [...]
  source: https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue
# drug_classes.yaml
- name: ssri
  label: Selective serotonin reuptake inhibitors
  members: [Sertraline, Fluoxetine, ...]       # DDInter drug names
# critical_interactions.yaml
- a: {class: ssri}            # or {drug: Tramadol}
  b: {drug: Tramadol}
  severity: Major
  rationale: Serotonin syndrome risk.
  source: <public URL>
# safety/red_flags.yaml (matcher in M4)
- id: cardiac_chest_pain
  level: RED
  category: cardiac
  all_of: [[chest pain, chest tightness], [sweating, left arm, jaw, breathless]]   # every group needs a hit
  any_of: []
  helpline: null              # tele_manas for self-harm rules
```
- Scope: about 100 conditions, about 120 symptoms, about 30 critical pairs, the red-flag categories in spec 4.6 (cardiac, stroke FAST, breathing, anaphylaxis, seizure / unconscious, heavy bleeding, self-harm, meningitis signs, dengue warning signs), seeded from v1's `llm/triage.py` clusters and re-curated for India.
- `validate_curated(ddinter_names: set[str] | None) -> list[str]` returns every problem: unknown symptom codes, unknown classes, duplicate keys, weights outside (0, 1], conditions with no symptoms, class members / critical drugs / synonym canonicals missing from DDInter (when the names are given).
- Tests: the committed files validate with no problems; each rule above has a failing example; the DDInter cross-check runs when `data/seed/` is present (skip otherwise).
- [ ] Commit `feat(seed): curated India-common conditions, symptoms, drug classes, critical interactions, red flags (draft for owner review)`.

### Task 7: Neo4j schema and loaders

**Files:** `knowledge/neo4j.py`, `knowledge/schema.py`, `seed/load_neo4j.py`, `api/app.py` (use `create_driver`), `tests/integration/test_knowledge_graph.py`

**Interfaces:**
```python
def create_driver(settings: Settings) -> neo4j.AsyncDriver
async def apply_schema(driver) -> None
    # unique: Condition.icd10, Symptom.code, Drug.ddinter_id, DrugClass.name, BodySystem.name
    # index: Drug.key (lowercase name); fulltext drug_name ON Drug.name; symptom_text ON Symptom.search_text
async def load_drugs(driver, drugs: dict[str, str], batch: int = 5000) -> int
async def load_interactions(driver, pairs, batch: int = 5000) -> int      # source "ddinter", stored id_lo -> id_hi
async def load_curated(driver, curated: Curated) -> CuratedCounts         # body systems, classes + MEMBER_OF,
    # symptoms (terms = normalised name + lay terms; search_text), conditions + edges, critical edges
    # (class sides expanded to member drugs; source "critical", rationale, reference)
```
- `Symptom.search_text` = name + lay terms joined (a fulltext index over one string property avoids relying on list-property fulltext support).
- Tests (namespaced test nodes, cleaned up): schema is idempotent; two drugs + one pair load and re-load without duplicates; an edge stored A -> B is found from B; a class-level critical pair expands to member edges with `source: "critical"`.
- [ ] Commit `feat(knowledge): neo4j driver, schema and batched loaders`.

### Task 8: Knowledge services

**Files:** `knowledge/resolver.py`, `knowledge/interactions.py`, `knowledge/conditions.py`, `tests/unit/test_resolver_logic.py`, `tests/integration/test_resolver.py`

**Interfaces:**
```python
class Resolution(BaseModel):
    query: str; status: Literal["resolved", "ambiguous", "unresolved"]
    matched_brand: str | None; ingredients: list[str]            # canonical DDInter names
    unresolved_ingredients: list[str]; candidates: list[str]
class MedicineResolver:
    def __init__(self, db: Database, driver: neo4j.AsyncDriver) -> None
    async def resolve(self, name: str) -> Resolution
    # 1 the name is itself an ingredient / synonym / DDInter drug -> resolved
    # 2 exact brand (lower(name)) -> ingredients
    # 3 trigram: candidates with similarity >= 0.45; group by ingredient set; the top group must lead
    #   the best *different* group by 0.1, else ambiguous
    # 4 ingredients -> drug_synonyms -> DDInter Drug.key; unmatched ingredients reported
def pick_candidate(cands: list[tuple[str, float, tuple[str, ...]]]) -> tuple[str, tuple[str, ...]] | Literal["ambiguous", "none"]
class InteractionFinding(BaseModel): a: str; b: str; severity: str; sources: list[str]
class InteractionReport(BaseModel):
    findings: list[InteractionFinding]; not_found: list[tuple[str, str]]
    unresolved: list[str]; coverage_note: str
class InteractionService:
    async def check(self, names: list[str]) -> InteractionReport     # resolves names first
class ConditionExplorer:
    async def match_symptoms(self, terms: list[str]) -> dict[str, str | None]  # term -> symptom code
    async def explore(self, symptoms: list[str], k: int = 5) -> list[ConditionHit]
```
- Spec change recorded in Task 11: the 0.1 lead rule compares different ingredient sets (two pack sizes of one product are not ambiguity).
- Tests: `pick_candidate` unit cases; integration with a namespaced fixture brand set + drugs: noise variants resolve, two different ingredient sets within 0.1 -> ambiguous, unknown -> unresolved, a pair with no edge -> `not_found` (never "safe"), severity max over ddinter + critical, `loose motions` -> diarrhoea via lay term, a non-exact phrase via fulltext fallback.
- [ ] Commit `feat(knowledge): medicine resolver, interaction service, condition explorer`.

### Task 9: Code enrichment (phase 7)

**Files:** `seed/codes.py`, `tests/unit/test_medical_apis.py` (enrichment part)

- `enrich_codes(driver, icd: Icd10, bioportal: BioPortal | None, rxnav: RxNav, concurrency: int = 8) -> CodeReport`:
  conditions -> `icd10_name` (official NLM name; a code NLM does not know is a reported failure), `snomed`, `cui`; symptoms -> `snomed`, `cui`; drugs -> `rxcui`. `asyncio.Semaphore(8)`; every failure is counted and listed, never swallowed.
- Tests: with fake clients, counts of filled / missing / failed are exact and a raising client lands in `failed`.
- [ ] Commit `feat(seed): ICD-10, SNOMED, CUI and RxCUI enrichment`.

### Task 10: Runner, verification, CLI, real run

**Files:** `seed/verify.py`, `seed/runner.py`, `cli.py`, `docs/NUMBERS.md`, `tests/unit/test_numbers_doc.py`

- `etheria seed [--skip-download] [--skip-codes] [--verify-only]`; phases 1-8 of spec 6.4 with a per-phase line `phase N <name>: ok|FAILED (<counts>, <seconds>s)`.
- `verify`: counts per label and relationship type (and per `source` for `INTERACTS_WITH`), Postgres row counts; the five canaries; `write_numbers(path, section)` replaces the block between `<!-- seed:begin -->` and `<!-- seed:end -->`, keeping the rest of the file.
- Real run: full seed, then a second run (counts identical), then `docker system df -v` recorded in `docs/NUMBERS.md` (spec 16).
- [ ] Commit `feat(seed): phase runner, canaries and docs/NUMBERS.md`.

### Task 11: Docs and close-out

- [ ] Spec: 6.3 ingredient-set lead rule; 6.4 measured facts (sources, resume); 6.5 file names (`drug_classes.yaml`, `drug_synonyms.yaml`, `safety/red_flags.yaml`); 16 measured Docker footprint.
- [ ] CLAUDE.md: M2 state, `etheria seed` flags, `--live`.
- [ ] `ruff check`, `lint-imports`, full `pytest`; push `main`.
- [ ] Build guide doc: M2 section, numbers, Q&A, changelog. Memory: open items.
- [ ] Ask the owner to review the curated YAML (M2 closes on their review).
