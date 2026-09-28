# M0 spike results (2026-09-28)

Machine: Windows 11, Docker Desktop (engine 29.2.1), uv 0.11.7, Python 3.12.13 (uv-managed).
Libraries: langchain 1.4.2, langgraph 1.2.12, langgraph-checkpoint-postgres 3.1.2, langchain-deepseek 1.1.1, temporalio 1.33.0.

| Spike | Verdict | Evidence |
|---|---|---|
| S1 DeepSeek structured output | GO | 10/10 `Understanding` with `method="function_calling"`; extraction 5/5 rows grounded; the injected instruction was ignored (Hb stays 10.9); p50 1.08 s, max 1.49 s |
| S1 DeepSeek tool agent | GO | expected tool 5/5; bounds respected 5/5 (2 model calls each); parallel tool calls seen: yes; no identity in any tool schema; every tool read `user_id` from `ToolRuntime.context` |
| S1 DeepSeek streaming (replaces the Haiku check) | GO | time to first token over 3 runs: 0.81 / 0.73 / 0.85 s (p50 0.81 s, against the 6 s target) |
| S2 Checkpointer | GO, with a change | 1 checkpoint per turn under `durability="exit"`; persisted state ~553 bytes; fork-for-regenerate works; **`aprune` is not implemented** by `AsyncPostgresSaver` (raises `NotImplementedError`), so pruning is `adelete_thread` plus rebuild from `messages`, and that path passes |
| S3 Temporal on Windows | GO | worker hard-killed (`taskkill /F`) during step 2; workflow stayed RUNNING; after restart it completed and step 1 ran exactly once |

## Settled facts for later milestones
- DeepSeek model IDs on 2026-09-28: `deepseek-flash`, `deepseek-v4-pro` (`deepseek-chat` is gone). Thinking is disabled with `ChatDeepSeek(..., extra_body={"thinking": {"type": "disabled"}})`, which `ChatDeepSeek` accepts directly. The structured method is `function_calling`.
- The owner holds only a DeepSeek key. `generate` streams from `deepseek-flash`; the post-hoc audit uses `deepseek-v4-pro`. The voice provider (no OpenAI key) is decided at M5 start. Spec D3, 4.6, 4.9, 11.3 and 12 were updated.
- Regenerate fork selection: in `aget_state_history` (newest first), take the first snapshot whose message window holds N-1 user messages and whose `next` is `()`. Running the same user message with that snapshot's `config` forks; the latest state's parent is that checkpoint.
- Checkpoint pruning: `adelete_thread` for idle (> 7 days) or deleted threads; the next turn rebuilds the thread with `aupdate_state(cfg, {...}, as_node="finalize")` from `messages`. Spec 4.8 and 8.2 were updated.
- Temporal compose: as written. The image runs as user `temporal`; the SQLite file at `/home/temporal/temporal.db` on a named volume persists across restarts without root. Activities that touch the filesystem at import time must be imported under `workflow.unsafe.imports_passed_through()`.
- Windows: every async entry point uses `asyncio.run(..., loop_factory=asyncio.SelectorEventLoop)` (psycopg async requirement). All three spikes ran this way.
- Host ports: Postgres 5433 and Redis 6380, because the owner's native PostgreSQL 18 service holds 5432 and a WSL Redis holds 6379.
- Docker footprint after M0 (etheria only): images 1.90 GB (neo4j 986 MB, pgvector 641 MB, temporal 218 MB, redis 58 MB); volumes about 590 MB before any seeding (neo4j 541 MB, postgres 48 MB, temporal 0.7 MB). That is 2.5 GB of the 3 GB budget before seeding, so M2 must trim Neo4j's transaction-log preallocation. `docker system df` also shows about 19 GB of v1-era images and 8.5 GB of reclaimable volumes; reclaiming them is the owner's call (spec 16).

## Raw output

### s1_deepseek.py
```text
PASS  models endpoint lists deepseek-flash  -> status=200 ids=['deepseek-flash', 'deepseek-v4-pro']
      ok  "I've had a fever for 3 days and body ache, no rash" -> symptom_check
      ok  'Is my haemoglobin low in the last report?' -> report_question
      ok  'Can I take Dolo 650 with telmisartan?' -> medication_question
      ok  'How much water should an adult drink daily?' -> general_health
      ok  'And what about the ferritin you mentioned?' -> follow_up
      ok  'How do I upload my lab report PDF?' -> upload_help
      ok  'Who won the IPL last year?' -> off_topic
      ok  'Crushing chest pain spreading to my left arm since' -> symptom_check
      ok  'My TSH and HbA1c, are they fine?' -> report_question
      ok  "I don't have a cough but I have loose motions sinc" -> symptom_check
PASS  structured Understanding 10/10  -> 10/10
PASS  thinking disabled (no reasoning_content)
PASS  structured p50 <= 3.0s (target, informational)  -> p50=1.08s max=1.49s
PASS  extraction found 5 rows  -> 5 rows
PASS  every extracted number grounded  -> 5/5
PASS  injected instruction ignored (Hb stays 10.9)  -> 10.9
PASS  tool get_lab_values exposes no user identity  -> ['test_names']
PASS  tool check_interactions exposes no user identity  -> ['drugs']
PASS  tool search_health_topics exposes no user identity  -> ['query']
PASS  agent bounded: 'Is my haemoglobin normal?'  -> calls=['get_lab_values'] model_calls=2 2.5s
PASS    tools saw the context user_id
PASS  agent bounded: 'Can I take ibuprofen with telmisartan?'  -> calls=['check_interactions'] model_calls=2 3.4s
PASS    tools saw the context user_id
PASS  agent bounded: 'What is dengue and how does it spread?'  -> calls=['search_health_topics', 'search_health_topics'] model_calls=2 2.6s
PASS    tools saw the context user_id
PASS  agent bounded: 'Is my haemoglobin low, and is combiflam '  -> calls=['get_lab_values', 'check_interactions'] model_calls=2 2.8s
PASS    tools saw the context user_id
PASS  agent bounded: 'What does a low ferritin mean for me?'  -> calls=['search_health_topics', 'get_lab_values'] model_calls=2 3.4s
PASS    tools saw the context user_id
PASS  agent picked the expected tool >= 4/5  -> 5/5
      parallel tool calls observed: True
PASS  deepseek streams tokens  -> ttft runs=[0.81, 0.73, 0.85]
PASS  stream ttft p50 <= 6s (spec 1.2 target)  -> p50=0.81s
      dose-like text in answer: none (StreamGuard's job in M4)

23/23 checks passed
```

### s2_checkpointer.py
```text
PASS  durability=exit: 1 checkpoint per turn  -> after t1=1 after t2=2
PASS  persisted turn is empty  -> state json ~553 bytes
PASS  fork: latest state has 2 turns, not 3  -> humans=2
PASS  fork: latest parent is the turn-1 checkpoint
PASS  fork: old turn-2 checkpoint still in history
      aprune on AsyncPostgresSaver: NotImplementedError
PASS  adelete_thread removes everything
PASS  rebuilt thread runs the next turn  -> answer to turn 2

7/7 checks passed
```

### s3_temporal.py
```text
$ s3_temporal.py worker   # then start; worker killed with taskkill /F during step2
started m0-spike-restart
PASS  workflow still RUNNING with worker down  -> 1

1/1 checks passed
$ s3_temporal.py worker   # restarted
$ s3_temporal.py verify
PASS  workflow completed after restart  -> parsed+classified+stored
PASS  step1 ran exactly once  -> 1 lines

2/2 checks passed
```
