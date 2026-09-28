# M0 spikes

Throwaway scripts that prove the spec's riskiest assumptions on this machine
(spec section 17, M0). Results and the go / no-go live in `docs/spikes/m0-results.md`.

Prerequisites: `docker compose -f infra/docker-compose.yml up -d`, and `backend/.env`
with `DEEPSEEK_API_KEY` (the owner uses DeepSeek only; there is no Anthropic key).

| Script | Proves | Run |
|---|---|---|
| `s1_deepseek.py` | Structured output, extraction grounding, bounded tool agent on DeepSeek | `uv run python spikes/s1_deepseek.py` |
| `s2_checkpointer.py` | `durability="exit"`, fork-for-regenerate, delete + rebuild fallback (aprune is not implemented) | `uv run python spikes/s2_checkpointer.py` |
| `s3_temporal.py` | Temporal workflow survives a worker restart | see the script docstring |

These scripts cost a few cents of API credit per run.
