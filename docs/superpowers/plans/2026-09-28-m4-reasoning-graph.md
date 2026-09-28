# M4 Reasoning Graph Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-in user chats over `POST /chat/stream`. Every message runs the deterministic safety shell around a bounded tool-calling retrieval agent (spec 4), streams guarded tokens as SSE in the v1 frontend's shapes, is persisted in `messages`, can be regenerated, and shows up in `/history`. The graph eval meets spec 1.2 criterion 5 and the contract tests are green.

**Architecture:** `graph/` holds the LangGraph `StateGraph` (state, nodes, the agent's tools, the builder and the chat service that runs a turn). Nodes are closures over a `GraphDeps` bundle of services, so tests inject fakes. Identity lives only in `ChatContext` (runtime context). Pure safety code (`safety/`: triage rule matcher, `StreamGuard`, input guard, drug cautions, fixed texts) and data access (`db/repositories/`, `retrieval/`) stay outside the graph and are unit or integration tested on their own. The api adds thin `chat` and `history` routers.

**LangGraph concepts used:** `StateGraph` with a reducer-annotated state (`add_messages`, a merge reducer for `turn`); runtime context (`context=`, `Runtime`, `ToolRuntime`); conditional edges; parallel fan-out and waiting joins (`add_edge([...], join)`); a `create_agent` subgraph with middleware bounds and a custom agent state; custom stream mode (`get_stream_writer`); `AsyncPostgresSaver` with `durability="exit"`; time travel (`aget_state_history`) for regenerate; `aupdate_state(as_node=...)` to rebuild a pruned thread; `RemoveMessage` for summarisation; `draw_mermaid()` for the diagram.

**Tech Stack:** langgraph 1.2.12, langchain 1.4.2 (`create_agent`, middleware), langchain-deepseek (`deepseek-flash` thinking disabled; `deepseek-v4-pro` audit), langgraph-checkpoint-postgres 3.1.2 + psycopg pool, sentence-transformers (BGE-large query embeddings; `cross-encoder/ms-marco-MiniLM-L-6-v2` reranker), pgvector + Postgres full-text, Neo4j, Redis (public caches, rate limit), FastAPI `StreamingResponse`.

**Spec:** `docs/superpowers/specs/2026-09-28-etheria-v2-design.md` sections 1.2 (criteria 3, 5, 8), 4 (all), 5.5 (datamarking, medication resolution), 6.3, 7, 8.2, 8.3, 10, 11.1, 14, 15, 17 (M4 row).

## Decisions made while planning (recorded in the spec in Task 7)

1. **`StreamGuard` runs inside `generate`, and tokens reach SSE through the custom stream mode**, not `messages` mode. The node streams the model, guards each sentence, emits the guarded text with `get_stream_writer()` and stores exactly that text. So the streamed text equals the stored text, and no other node's LLM tokens can leak into the stream. `finalize` re-runs the rules over the whole reply; any extra hit (a pattern split across two flushes) is fixed in the stored copy and counted in the trace (`guard_late_hits`), so the eval measures it.
2. **The emergency block is sent by the first node that knows the turn is RED:** `input_guard` (rule pre-scan, before any LLM call), else `triage`, else `generate` as the last safety net. Always before `generate`'s first model token. `turn.emergency_sent` stops a second copy.
3. **`turn` has a merge reducer.** Parallel branches (`retrieval_agent || triage`, `generate || clinical_structuring`) write different `TurnData` fields in the same superstep; a plain channel would raise `InvalidUpdateError`. A node returns `{"turn": {"field": value}}`; a `TurnData` instance replaces the whole value (the turn reset), and `None` empties it (`finalize`).
4. **Checkpoint tables come from Alembic migration 0003**, run as the owner role, using the library's own `BasePostgresSaver.MIGRATIONS` (with `CONCURRENTLY` removed: the tables are empty) plus the version rows, then granted to `etheria_app`. The app role never runs DDL. A unit test fails if an installed library version adds a migration the repo does not have. Checkpoint tables have no RLS (they are keyed by `thread_id` text); the chat service verifies conversation ownership through the RLS-protected `conversations` table before touching a thread.
5. **Reranker: `cross-encoder/ms-marco-MiniLM-L-6-v2`** (about 90 MB, fast on CPU), loaded lazily in the api process. Only free-text passages (report chunks, PubMed, MedlinePlus) are reranked and cut to the token budget; structured evidence (lab rows, interactions, cautions, condition matches) is never dropped.
6. **Citation sources:** `user_document` (lab rows, medications, report chunks), `neo4j` (conditions, DDInter and safety-net interactions), `pubmed`, plus two additive values, `medlineplus` and `curated` (drug cautions). M6 adds the two to the `Citation.source` union in the copied `types.ts`; no frontend code branches on the value today.
7. **The test catalogue and a stated pregnancy reach the tools through the agent's own state** (`create_agent(state_schema=AgentState subclass)`, read via `ToolRuntime.state`), never through model-visible arguments or identity.
8. **Stable evidence ids:** `lab:<uuid>`, `med:<uuid>`, `chunk:<uuid>`, `pubmed:<pmid>`, `medlineplus:<url>`, `condition:<icd10>`, `interaction:<a>|<b>`, `caution:<rule>:<lab uuid or 'pregnancy'>`.
9. **Structured nodes retry inside the node** (3 attempts for `understand`, 2 for `triage` and `clinical_structuring`) so that the fallback (`general_health`, YELLOW, empty lists) is recorded in the trace instead of failing the run.
10. **Datamarking** (spec 5.5, 11.1): report text that reaches a model is wrapped in `<document>` and its whitespace replaced with `^` (spotlighting); the system prompts say that marked text is data, never instructions.
11. **The audit** is an `asyncio` task started after `finalize` persists the message; it writes `metadata.audit` back to the row. The service keeps task references; the deps flag disables it in tests. Failures are logged only.
12. **Conditions for drug cautions** come from discharge summaries (`documents.extracted->'diagnoses'`); the eval's profile conditions are stored the same way.
13. **The graph eval grades by code first** (triage floor, tools used, `must_not` phrases, dose patterns, emergency block first, disclaimer, "safe" wording) and uses the audit model only for the free-text `must` items.

## Global Constraints

- Never modify anything under `D:\Etheria\`. v1's `src/lib/types.ts` and `api.ts` are the contract, read only.
- Product rules (spec 4.6): never diagnose, never prescribe or give doses, always append the disclaimer, India emergency numbers 112 / 108, Tele-MANAS 14416 or 1-800-891-4416, a missing interaction is "not found, confirm with a pharmacist", never "safe".
- Identity only in `ChatContext` (`user_id`, `conversation_id`, `request_id`, `regenerate`); never in state, prompts or tool arguments.
- Bounds: agent `ModelCallLimitMiddleware(run_limit=3, exit_behavior="end")`, `ToolCallLimitMiddleware(run_limit=8)`, 8 s per tool, 25 s per agent node; summarise when the window exceeds 20 messages, keep the last 8; evidence budget 6,000 tokens.
- Triage rules only raise the level; any triage failure is YELLOW, never GREEN.
- Models only through `llm/registry.py`; prompts in `backend/prompts/*.md`.
- `durability="exit"`; `finalize` empties `turn`; the `messages` table is the system of record.
- Caching: public layers only (PubMed 24 h, MedlinePlus 7 d, query embeddings 7 d, knowledge-graph lookups 24 h). Never answers, triage, labs, medications or chunks.
- Chat rate limit 20 per minute per user. Message length 1-4,000 characters.
- SSE payloads and REST shapes match v1 `types.ts` / `api.ts` exactly (camel-case `relevanceScore`, snake_case `AgentTrace`); additions are additive only.
- Import rules (3.3): `graph` never imports `ingestion`, `auth`, `voice`, `seed`; `safety`, `knowledge`, `retrieval` never import `graph`.
- Windows: selector event loop; console output ASCII only.
- Commits: plain conventional messages, no Claude or AI attribution trailer. Work on `main`.

## Review Focus

1. **Another user's conversation id** on `/chat/stream`, `/chat/regenerate`, `GET/PATCH/DELETE /history/{id}` returns 404 `not_found` and never touches that thread's checkpoints. (Task 6 `test_cross_user_conversation_is_404`.)
2. **RED arrives first even when the models fail.** Chest pain with sweating: the first `token` event is the emergency block, from the rule pre-scan, before any LLM call, with the triage model raising errors. (Task 4 `test_red_rule_emits_block_before_llm`, Task 6 `test_stream_red_block_first`.)
3. **Model failure mid-answer.** The generator raises after two sentences: the stream ends with `error`, the partial answer is stored with `metadata.incomplete = true`, and the next turn in the same conversation works. (Task 6 `test_generate_failure_mid_stream`.)
4. **A missing checkpoint.** A conversation whose thread was deleted (pruned) continues from `messages`; regenerate on the first turn works through the rebuild path. (Task 6 `test_turn_after_thread_deleted`, `test_regenerate_first_turn`.)
5. **"Safe" never gets through.** A model sentence "These two are safe to take together." becomes the not-found wording; a pair with no edge and a drug with no recorded caution are both reported as "not found / no recorded caution", never as clearance. (Task 1 `test_guard_rewrites_safe_claims`, Task 5 `test_check_interactions_reports_not_found`.)

---

## File structure

```text
backend/
  migrations/versions/0003_checkpoints.py      checkpoint tables from the library's MIGRATIONS, granted to etheria_app
  prompts/understand.md triage.md retrieval_agent.md generate.md clinical.md summarize.md audit.md
  src/etheria/
    safety/texts.py            disclaimer, emergency block, Tele-MANAS, not-found and no-caution wording, dose replacement
    safety/triage_rules.py     RuleMatcher over red_flags.yaml (levels, categories, helpline)
    safety/input_guard.py      length, injection heuristics, red-flag pre-scan
    safety/stream_guard.py     StreamGuard (sentence buffer, 4 rules) + apply_rules(text)
    safety/drug_cautions.yaml  curated class x lab / condition / pregnancy cautions (owner review)
    safety/cautions.py         load + evaluate cautions (pure)
    knowledge/conditions.py    coverage ranking; cached explore
    knowledge/resolver.py      word_similarity; shared ingredients across ambiguous candidates
    knowledge/interactions.py  drug classes lookup for cautions; cached edge lookups
    retrieval/hybrid.py        report search: pgvector + full-text, fused with RRF
    retrieval/rerank.py        cross-encoder reranker (Protocol + MiniLM implementation)
    retrieval/query_cache.py   cached query embeddings (7 d)
    db/models.py               + Conversation, Message
    db/repositories/chat.py    conversations + messages
    db/repositories/health_record.py  report index, test catalogue, lab snapshot, lab values, medications, conditions
    llm/registry.py            + chat nodes, audit model, streaming model
    llm/prompts.py             + datamark()
    graph/context.py           ChatContext
    graph/schemas.py           Understanding, TriageResult, Evidence, ClinicalOutput, TraceEntry, GuardResult, TurnData
    graph/state.py             ChatState + merge_turn reducer
    graph/deps.py              GraphDeps (services + model factories + flags)
    graph/nodes/*.py           load_context, input_guard, summarize, understand, triage, rerank, generate, clinical, canned, finalize
    graph/tools.py             the 8 agent tools
    graph/agent.py             create_agent subgraph + the retrieval_agent wrapper node
    graph/builder.py           build_graph(deps, checkpointer) and mermaid()
    graph/payloads.py          SSE / REST payloads in the frontend's shapes (Citation, Symptom, AgentTrace, ...)
    graph/service.py           ChatService: run a turn, regenerate, rebuild a thread, delete a thread
    graph/eval.py              graph eval runner (profiles, graders, report)
    api/routers/chat.py        POST /chat/stream (SSE), POST /chat/regenerate
    api/routers/history.py     GET /history/, GET/PATCH/DELETE /history/{id}
  tests/
    unit/test_triage_rules.py test_stream_guard.py test_input_guard.py test_cautions.py
    unit/test_graph_state.py test_graph_nodes.py test_agent_tools.py test_payloads.py test_checkpoint_migrations.py
    integration/test_chat_repos.py test_hybrid_search.py test_knowledge_fixes.py test_chat_api.py
    graph_fakes.py             scripted fake chat models (tool calls, streaming, structured output)
    evals/graph_scenarios.yaml >= 30 scenarios
docs/ARCHITECTURE.md           generated Mermaid diagram of the compiled graph
docs/evals/graph.md            graph eval report
```

---

### Task 1: Safety core (pure)

**Files:** create `safety/texts.py`, `safety/triage_rules.py`, `safety/input_guard.py`, `safety/stream_guard.py`, `safety/drug_cautions.yaml`, `safety/cautions.py`; tests `tests/unit/test_triage_rules.py`, `test_stream_guard.py`, `test_input_guard.py`, `test_cautions.py`.

**Interfaces (produces):**
- `texts.DISCLAIMER`, `texts.emergency_block(helpline: bool) -> str`, `texts.NOT_FOUND_WORDING`, `texts.NO_CAUTION_WORDING`, `texts.DOSE_REPLACEMENT`.
- `triage_rules.RuleMatcher.load() -> RuleMatcher`; `.match(text) -> list[RuleHit]` (`RuleHit(id, level, category, helpline)`); `triage_rules.max_level(*levels) -> Level`; `Level = Literal["GREEN","YELLOW","RED"]`.
- `input_guard.check(message, matcher) -> GuardResult(blocked: bool, reason: str | None, rule_hits: list[RuleHit], rule_level: Level | None)`.
- `stream_guard.StreamGuard(max_chars=200, max_wait_s=0.4)`: `.feed(token) -> list[str]` (guarded segments ready to send), `.flush() -> list[str]`, `.hits: list[str]` (rule names); `stream_guard.apply_rules(text) -> tuple[str, list[str]]`.
- `cautions.CautionRule`, `cautions.load_cautions()`, `cautions.evaluate(drugs: list[DrugClasses], labs: list[LabFact], conditions: list[str], pregnant: bool, rules) -> list[Caution]` where `Caution(drug, trigger, value, rationale, source, rule_id, lab_id)`.

- [ ] Rules matcher: case-insensitive whole-phrase matching (word boundaries), `any_of` or every `all_of` group; tests: chest pain + sweating is RED `cardiac_chest_pain`; "I don't want to live" is RED with `helpline`; "chest pain" alone does not fire the `all_of` rule; "fits" does not fire inside "benefits".
- [ ] StreamGuard rules, each with a test: (1) dosing (`\d+\s?(mg|mcg|ml|g|tablets?|tabs?|capsules?|drops?|units?|puffs?)` with a frequency or "take N", "N times a day", "every N hours", "twice/thrice a day", "BD/TDS/OD") -> the sentence becomes `DOSE_REPLACEMENT`; lab values like "haemoglobin is 9.1 g/dL" stay; (2) "you have X" / "you are suffering from X" / "you are diagnosed with X" -> "this may be consistent with X"; (3) "safe to take/combine/use together", "no interaction", "no known interaction", "does not interact" -> `NOT_FOUND_WORDING`; (4) 911 / 999 -> 112. Buffering: segments release at `.`, `!`, `?`, newline, or 200 chars; `.flush()` releases the tail; the concatenation of segments equals the guarded text.
- [ ] Input guard: injection patterns ("ignore (all|any|your|the) (previous|prior|above) instructions", "you are now", "act as (a|my) doctor", "system prompt", "developer mode", "jailbreak") block the turn **unless** the rule pre-scan is RED (an emergency is never blocked).
- [ ] `drug_cautions.yaml`: NSAID + creatinine high / eGFR low / platelets low / pregnancy / peptic ulcer; aspirin + platelets low; biguanide + eGFR low; ACE inhibitor or ARB + potassium high / pregnancy; anticoagulant or vitamin K antagonist + platelets low; potassium-sparing diuretic + potassium high; statin + ALT high. Each `{id, drug_classes, trigger: {lab, flag} | {condition_any} | {pregnancy: true}, rationale, source}`. Tests: CKD profile + ibuprofen gives two cautions with the lab values; no abnormal labs gives none; pregnancy + ibuprofen gives one; lab name matching is alias-aware (`eGFR`, `Estimated GFR`, `Platelet count`, `Platelets`).
- [ ] `uv run pytest tests/unit -q`, `uv run ruff check .`; commit `feat(safety): triage rule matcher, input guard, StreamGuard and drug cautions`.

### Task 2: Knowledge fixes (M2 gaps) and graph-lookup caching

**Files:** modify `knowledge/conditions.py`, `knowledge/resolver.py`, `knowledge/interactions.py`, `seed/data/symptoms.yaml`; test `tests/integration/test_knowledge_fixes.py`, update `tests/unit/test_resolver_logic.py`.

**Interfaces (produces):**
- `ConditionExplorer(driver, cache: JsonCache | None = None).explore(symptoms, k=5)`; `ConditionHit` gains `coverage: float`.
- `Resolution` gains `shared_ingredients: list[str]` (set when ambiguous).
- `InteractionService(resolver, driver, cache=None).check(names, extra_ingredients=None)`; new `.drug_classes(drugs: list[str]) -> dict[str, list[str]]`.

- [ ] Coverage ranking in Cypher: `coverage = sum(matched weight) / sum(all weights of the condition)`, order by coverage then summed weight; test: headache alone ranks tension-type headache or migraine above meningitis and Japanese encephalitis.
- [ ] Trigram step uses `word_similarity(:q, name)` with the `<%` operator (index-backed, threshold local to the transaction); test: "Brufen" resolves or is ambiguous with shared ingredient ibuprofen, never unresolved; "Dolo 650" still resolves to acetaminophen.
- [ ] Ambiguous results: resolve every close candidate's ingredients and set `shared_ingredients` to their intersection; `InteractionService.check` uses the shared ingredients of an ambiguous name for pair checks and still lists the name as ambiguous with its candidates.
- [ ] Lay terms: add "tinnitus", "ringing in my ears", "ears ringing", "ringing in both ears" to the tinnitus symptom; re-run `uv run etheria seed --skip-codes` (phase 6 only changes) and `--verify-only`.
- [ ] 24 h cache (spec 8.3) around `explore` and the edge lookup via `JsonCache` (source `kg`), keyed on the sorted inputs; test that a second call hits the cache.
- [ ] Tests green; commit `fix(knowledge): coverage ranking, word-similarity brands, shared ingredients, lay terms, graph caching`.

### Task 3: Chat data layer, hybrid search, reranker, checkpoint tables

**Files:** create `migrations/versions/0003_checkpoints.py`, `db/repositories/chat.py`, `db/repositories/health_record.py`, `retrieval/hybrid.py`, `retrieval/rerank.py`, `retrieval/query_cache.py`; modify `db/models.py`; tests `tests/unit/test_checkpoint_migrations.py`, `tests/integration/test_chat_repos.py`, `tests/integration/test_hybrid_search.py`.

**Interfaces (produces):**
- `chat.create_conversation(s, user_id, title) -> Conversation`, `get_conversation(s, user_id, id)`, `list_conversations(s, user_id, page, page_size) -> (total, list[ConversationSummary])`, `rename`, `soft_delete`, `touch(s, conv, triage_level)`, `insert_message(s, *, conversation_id, user_id, role, content, intent=None, metadata=None) -> Message`, `list_messages(s, user_id, conversation_id, include_superseded=False)`, `last_turn(s, user_id, conversation_id) -> (Message | None, Message | None)`, `supersede(s, message)`, `update_metadata(s, user_id, message_id, created_at, patch)`.
- `health_record.report_index(s, user_id) -> list[ReportCard]`, `test_catalogue(s, user_id) -> list[str]`, `lab_snapshot(s, user_id, limit=30) -> list[LabFact]` (abnormal rows, newest report first), `lab_values(s, user_id, test_names, include_abnormal) -> list[LabFact]`, `medications(s, user_id) -> list[MedFact]`, `conditions(s, user_id) -> list[str]`.
- `hybrid.search_reports(s, user_id, query_vec, query_text, k=8, doc_types=None) -> list[ChunkHit]` (RRF k=60 over the top 20 of each list).
- `rerank.Reranker` Protocol `score(query, passages) -> list[float]`; `CrossEncoderReranker(model_name)`.
- `query_cache.CachedQueryEmbedder(embedder, cache).embed_query(text) -> list[float]` (7 d, key model + SHA-256).

- [ ] Migration 0003 as described in Decision 4; unit test compares the migration's statement count with `BasePostgresSaver.MIGRATIONS`; integration: `AsyncPostgresSaver` as `etheria_app` can write and read a checkpoint.
- [ ] ORM `Conversation`, `Message` (composite PK `id, created_at`); repository tests: RLS isolation (user B sees nothing), paging order by `last_message_at desc`, preview is the first user message (200 chars), superseded messages hidden from history.
- [ ] Health-record queries; test with a seeded document + lab rows + medication + discharge diagnoses.
- [ ] Hybrid search: `SET LOCAL hnsw.iterative_scan = relaxed_order`; dense top 20 by `<=>`, keyword top 20 by `ts_rank_cd` with `websearch_to_tsquery('simple', ...)`; fuse with RRF; test that "HbA1c" finds the exact-token chunk and another user's chunk never appears.
- [ ] Reranker and cached query embeddings; the integration test uses the real models (weights download into the Hugging Face cache on first run, as in M3).
- [ ] Tests green; commit `feat(chat): conversation and message repositories, hybrid report search, reranker, checkpoint tables`.

### Task 4: Graph state and the deterministic shell nodes

**Files:** create `graph/context.py`, `graph/schemas.py`, `graph/state.py`, `graph/deps.py`, `graph/nodes/*.py`, `graph/builder.py`, `graph/payloads.py`, prompts `understand.md triage.md generate.md clinical.md summarize.md audit.md`; modify `llm/registry.py`, `llm/prompts.py`; tests `tests/graph_fakes.py`, `tests/unit/test_graph_state.py`, `tests/unit/test_graph_nodes.py`, `tests/unit/test_payloads.py`.

**Interfaces (produces):**
- `ChatContext(user_id, conversation_id, request_id, regenerate=False)` frozen dataclass.
- `TurnData` fields: `user_message, report_index, test_catalogue, lab_snapshot, current_medications, conditions, guard, understanding, evidence, interaction_findings, cautions, agent_tools, triage, reply, reply_incomplete, clinical, emergency_sent, trace, timings`.
- `merge_turn(current, update)`; `ChatState(messages, summary, turn)`.
- `GraphDeps(db, explorer, interactions, resolver, pubmed, medlineplus, query_embedder, reranker, matcher, cautions, models: ModelFactory, audit_enabled: bool, now)`; `ModelFactory.structured(node, schema)`, `.chat(node)`, `.streaming(node)`.
- `build_graph(deps, checkpointer=None) -> CompiledStateGraph`; `mermaid(graph) -> str`.
- `payloads.citation(e, n)`, `payloads.symptoms(understanding)`, `payloads.differential(clinical)`, `payloads.agent_trace(turn, duration_ms)`, `payloads.metadata_event(...)`.

- [ ] Reducer tests: parallel partial updates merge; a `TurnData` replaces; `None` empties.
- [ ] Node tests with fakes (`GenericFakeChatModel` for streaming, a scripted structured fake): load_context fills the record; input_guard routes blocked -> canned, window > 20 -> summarize; summarize keeps the last 8 via `RemoveMessage`; understand falls back to `general_health` after 3 failures and drops tests not in the catalogue; triage: rule RED beats model GREEN, model RED beats rules, model failure -> YELLOW; rerank keeps structured evidence and numbers citations 1..n; generate emits the RED block first, guards sentences, stores exactly the streamed text; clinical returns empty lists on failure and no differential for non-symptom intents; finalize appends the disclaimer, stores the message, emits `metadata`, empties `turn`.
- [ ] Builder: edges exactly as spec 4.4 (conditional after `input_guard` and `understand`; waiting joins); a full-graph test with fakes runs a symptom turn end to end and checks the custom-stream event order (`status`*, `token`+, `metadata`) and that the checkpoint's `turn` is empty.
- [ ] Payload tests pin the key sets from `types.ts`: `Citation{source, identifier, title, url, relevanceScore}`, `Symptom`, `DifferentialDiagnosis`, `AgentTrace` and `AgentEntry`.
- [ ] Commit `feat(graph): chat state, safety shell nodes and graph builder`.

### Task 5: Retrieval agent and tools

**Files:** create `graph/tools.py`, `graph/agent.py`, `prompts/retrieval_agent.md`; test `tests/unit/test_agent_tools.py` (fakes) and `tests/integration/test_agent_tools_db.py`.

**Interfaces (produces):** `make_tools(deps) -> list[BaseTool]`; `AgentState(AgentState)` with `test_catalogue: list[str]`, `pregnant: bool`; `retrieval_agent_node(deps)` returning `{"turn": {"evidence", "interaction_findings", "cautions", "agent_tools", ...}}`.

- [ ] Each tool: `@tool(response_format="content_and_artifact")`, async, reads `runtime.context.user_id`; content = compact JSON with evidence ids; artifact = `list[Evidence]`; 8 s timeout -> `{"error": "timeout"}`; errors never raise into the agent.
- [ ] `get_lab_values` rejects names outside the catalogue; `search_my_reports` datamarks passages; `check_interactions` resolves `drugs` (+ current medications via the resolver, Decision spec 5.5), returns findings, `not_found`, unresolved, duplicates, the coverage note, and `cautions` evaluated against the user's labs, conditions and the agent-state pregnancy flag, with `NO_CAUTION_WORDING` when none.
- [ ] Wrapper node: input = question, understanding, report index, catalogue, lab snapshot, summary + last 4 messages; streams the agent with `stream_mode="updates"`, collecting artifacts as they arrive; `asyncio.timeout(25)` keeps what was collected; records the tools called.
- [ ] Tests with a scripted tool-calling fake: the agent calls `check_interactions` and the wrapper returns its findings; a tool never sees another user's rows (two users, same tool call); the call limit stops a looping model; a slow tool times out and the rest of the evidence survives.
- [ ] Commit `feat(graph): bounded retrieval agent with user-scoped tools`.

### Task 6: Chat service, SSE, regenerate, history API

**Files:** create `graph/service.py`, `api/routers/chat.py`, `api/routers/history.py`; modify `api/app.py`, `cli.py`; test `tests/integration/test_chat_api.py`.

**Interfaces (produces):** `ChatService(db, graph, checkpointer, deps).stream_turn(user_id, message, session_id, request_id) -> AsyncIterator[dict]`, `.regenerate(user_id, session_id, request_id) -> dict`, `.delete_thread(conversation_id)`.

- [ ] Stream: verify or create the conversation (404 for another user's id), insert the user message in its own transaction, rebuild the thread from `messages` when the checkpointer has no state but history exists, run `astream(..., stream_mode="custom", durability="exit", context=ChatContext(...))`, map to SSE `data:` lines, end with `done`; on an exception emit `error`, store any partial reply with `metadata.incomplete=true`.
- [ ] Regenerate: find the last user and assistant messages, fork from the newest snapshot with N-1 user messages and empty `next`; fallback: delete the thread, rebuild from `messages` minus the last turn, run; supersede the old assistant row; return the `ChatResponse` shape plus `message_id`.
- [ ] History: list (`total, page, page_size, sessions[{session_id, triage_level, started_at, ended_at, message_count, preview, name}]`), detail (`messages[{message_id, role, content, intent, symptoms, triage_level, citations, differential, created_at}]`), rename, soft delete + `adelete_thread`.
- [ ] Rate limit 20/min per user on stream and regenerate. Wiring: `AsyncConnectionPool` for the checkpointer (app role), deps built in the lifespan, reranker and BGE loaded lazily on first use.
- [ ] Integration tests (fake models via deps): Review Focus 1-4, SSE contract (event types in order, metadata keys), history shapes.
- [ ] Commit `feat(api): streamed chat, regenerate and history endpoints`.

### Task 7: Graph eval, diagram, live run, docs

**Files:** modify `tests/evals/graph_scenarios.yaml` (>= 30), `tests/unit/test_eval_scenarios.py`, `cli.py`; create `graph/eval.py`, `docs/ARCHITECTURE.md`, `docs/evals/graph.md`; update spec, `docs/NUMBERS.md`, `CLAUDE.md`, the Build Guide doc, memory.

- [ ] Add scenarios: injected instruction inside a report chunk (profile with chunks), "thanks" (no tools), off-topic (canned), upload help (canned), a follow-up referring to the previous turn, a lab value outside the catalogue.
- [ ] Runner: creates a throwaway user per profile (documents, lab rows, medications, diagnoses, chunks embedded with BGE), runs each scenario through `ChatService` with real models, grades (Decision 13), records per-node timings, time to first token, total latency; writes `docs/evals/graph.md`; exit code non-zero unless all safety pass and quality >= 90%.
- [ ] `uv run etheria graph-diagram` writes the Mermaid diagram from `graph.get_graph().draw_mermaid()` into `docs/ARCHITECTURE.md` between markers.
- [ ] Live smoke with the real API, then the full eval; fix prompts or rules (never the ground truth) until the criteria hold; record latency p50s in `docs/NUMBERS.md`.
- [ ] Spec updates (decisions above, 4.7 stream mode, 6.1 coverage, citations), `CLAUDE.md` current state and commands, Build Guide M4 section + state diagram + challenges + numbers + Q&A, memory handover; push `main`.
