# Security

Etheria v2 is a portfolio project that holds synthetic data only and has no real users. This page describes the controls the code implements, how they are tested, and what they do not cover. It is not a compliance certification. Design reference: spec section 11.

## Threat model and controls

| Threat | Control in the code | Tested by |
|---|---|---|
| Credential stuffing | argon2id password hashes; login limited to 5 per minute per IP + email; registration to 5 per minute per IP; the same error for an unknown email and a wrong password | `test_auth_api.py` (rate limits, uniform errors) |
| Stolen refresh token | Opaque 256-bit token, stored as a SHA-256 hash, httpOnly `SameSite=Lax` cookie scoped to `/auth`; rotated on every refresh; presenting a rotated token revokes the whole family and is audit-logged | `test_auth_api.py::test_refresh_rotates_and_detects_reuse` |
| Forged access token | HS256 only, with `exp`, `iat`, `sub` and `jti` required; the user must still exist | `tests/security/test_forged_tokens.py` (alg `none`, wrong secret, HS512, no `exp`, expired, non-UUID subject, unknown user, tampered payload) |
| Token outliving account erasure | Each request looks up the user by primary key; an erased user's token gets 401 on every endpoint | `test_user_api.py::test_an_erased_users_token_is_refused_everywhere` |
| CSRF on cookie endpoints | `/auth/refresh` and `/auth/logout` require an allowed `Origin` and `X-Requested-With`; CORS allows the frontend origin only | `test_auth_api.py` |
| Cross-user data access | Three layers: service checks (another user's resource is 404, never 403); graph tools take the user from the trusted runtime context, never from model arguments; Postgres row-level security as the app role, which owns no tables | `tests/security/test_rls.py`, `test_chat_api.py` and `test_upload_api.py` cross-user tests, `test_graph_run.py::test_tools_only_see_the_context_user` |
| Indirect prompt injection (in an uploaded report) | Report text reaches chat models datamarked inside one `<document>` block; prompts say document content is data; the agent's tools are read-only and user-scoped; every extracted number must appear verbatim in the source (grounding check) | Extraction eval (`lab_injected.pdf`: the injected value is not stored); graph eval scenario `injected_report` |
| Direct prompt injection | `input_guard` heuristics answer with a fixed reply; behind it, the same read-only tools and the deterministic output rules (`StreamGuard`) | `tests/security/test_injection_corpus.py`; 15 held-out attacks in the graph eval (`graph_scenarios_injection.yaml`) |
| Malicious upload | Type from magic bytes, 10 MB and 30-page limits, encrypted-PDF rejection, pixel-bomb guard, random storage names, AES-256-GCM at rest, content never executed | `test_validation.py`; `tests/security/test_upload_fuzz.py` (450 seeded mutations of real fixtures: accepted or rejected with a known code, never a crash; the endpoint never answers 500) |
| Duplicate-upload race | The unique `(user_id, sha256)` index decides; the losing request answers like a duplicate | `test_upload_api.py::test_concurrent_same_file_upload_returns_the_winner` |
| Unsafe medical output | No diagnosis, no doses, never "safe to combine", India emergency numbers (112, 108, Tele-MANAS 14416); triage rules can only raise the level; `StreamGuard` filters sentences before they stream; a post-hoc audit model measures | Graph eval (safety scenarios), `test_stream_guard.py`, `test_triage_rules.py` |
| Data sent to third-party LLMs | Aadhaar numbers and Indian phone numbers are masked before any model call or indexing; synthetic data only; tracing off unless `LANGSMITH_TRACING=true` | `test_pii_mask.py`, extraction eval (all fixture PII masked) |
| Cost blow-up | Rate limits (chat 20 per minute per user, uploads 10 per hour); bounded agent loops (model and tool call limits); per-node timeouts | `test_chat_api.py::test_chat_rate_limit`, `test_upload_api.py::test_upload_rate_limited_after_10` |
| Secret leakage | Secrets come from the environment only; `.env` is gitignored; startup fails when a required secret is missing | `test_settings.py` |

### Measured: how far `input_guard` generalises

The injection heuristics were widened in M7 until a 20-attack development corpus was fully blocked, with none of 15 benign messages that use the same trigger words blocked. A held-out set of 15 attacks, written after the patterns were frozen, was then measured: `input_guard` blocked **2 of 15**. Regex heuristics do not generalise, so the guard is treated as a cheap first filter. The controls that must hold are the ones behind it. The held-out attacks run end to end through the real graph in every graph eval, and their result is in `docs/evals/graph.md`.

## Data protection (DPDP Rules 2025, Rule 6)

| Rule 6 safeguard | Implementation |
|---|---|
| Encryption, obfuscation, masking | AES-256-GCM for uploaded files; PII masking before LLM calls and indexing. Disk encryption for database volumes is the stated deployment requirement (not provided by this dev setup) |
| Access control | Authentication, per-user service checks, row-level security, a least-privilege database role that owns no tables and cannot delete audit rows |
| Visibility of access | `audit_log` actions: `register`, `login`, `login_failed`, `logout`, `refresh_reused`, `upload`, `download`, `document_delete`, `erasure`. Health content is never logged |
| Log retention for one year | `audit_log` is partitioned by month. The daily maintenance workflow drops months past 12 months through `drop_expired_partitions`, which refuses any retention below 12 months and any other table |
| Erasure | `DELETE /user` removes every user row, checkpoint thread and encrypted file; audit rows are kept, with the user reference replaced by a keyed pseudonym |
| Breach detection and response | See the runbook below |

The substantive obligations apply from 13 May 2027. v2 is designed to them, but it is not a compliance certification.

## Scheduled maintenance

A daily Temporal Schedule (`maintenance-daily`, created by the worker) runs `MaintenanceWorkflow`. `uv run etheria maintain` runs the same jobs once.

1. It keeps monthly partitions of `messages` and `audit_log` three months ahead. The readiness check fails if a row ever lands in a default partition.
2. It drops `audit_log` months older than 12 months.
3. It deletes LangGraph checkpoint threads idle for 7 days, or whose conversation was deleted or no longer exists. A pruned thread is rebuilt from `messages` on its next turn.

The app role can do each job only through a `SECURITY DEFINER` function that does one bounded thing (migration 0004).

## Breach response runbook

1. **Detect.** Sources:
   - `audit_log` rows with action `refresh_reused` (a stolen refresh token was replayed) or bursts of `login_failed`.
   - Bursts of `rate_limited` errors in the JSON request logs.
   - Readiness failures.
   - Unexpected `audit_log` access patterns (downloads by one user in bulk).
2. **Contain.**
   - Rotate `JWT_SECRET`, which invalidates every access token, and revoke refresh-token families.
   - Rotate any exposed third-party key (DeepSeek, NCBI, BioPortal).
   - If files may be exposed, rotate `DATA_ENCRYPTION_KEY` and re-encrypt.
3. **Assess.** Use `audit_log` and the request logs, which are keyed by `request_id` and a hashed user reference, to establish which users and records were affected.
4. **Notify.**
   - With real users, inform each affected Data Principal without delay.
   - Send the detailed report to the Data Protection Board within 72 hours (Rule 7).
   - In this project there are no real users, so this step is documented, not exercised.
5. **Review.** Record the cause and the fix, and add a regression test to `tests/security/`.

## Third-party processors

- **DeepSeek**: its API servers are outside India. It receives masked report text and chat messages.
- **LangSmith**: receives data only when tracing is switched on, and it is off by default.

With real users, each processor would need a processor agreement and a cross-border transfer review. Only synthetic data reaches them here. The model registry (`llm/registry.py`) routes per node, so any node can move to a self-hosted open-weight model without changing the graph.

## Known limitations

- **Logout does not revoke the access token.** After logout, the access token stays valid until it expires (at most 15 minutes). Erasure is covered, because the user lookup fails.
- **Login limiting is per IP + email.** One IP trying many emails is limited only by registration and per-email limits.
- **Uploads over 10 MB are read before they are rejected.** Starlette reads the whole multipart body before the handler checks the size, so a large body costs memory first.
- **One long streamed segment can escape the dose filter.** `StreamGuard` releases text at a sentence end, after 200 characters without one (cut at a space), or after a 0.4 s pause. A dose phrase split across a forced cut is checked as two halves and may pass. The post-hoc audit measures this; it does not block it.
- **Public evidence is not datamarked.** PubMed and MedlinePlus text reaches the model inside delimiters, but only report text is datamarked.
- **Checkpoint tables have no row-level security.** Checkpoints are keyed by `thread_id` (text). The chat service checks conversation ownership through the RLS-protected `conversations` table before it touches a thread.
- **Scanned uploads fail until Tesseract is installed.** They fail with `ocr_unavailable`. Numeric lab values are never taken from images in any case.
- **Frontend: two tabs refreshing at once can sign one out.** The second refresh presents an already-rotated cookie and counts as reuse.
