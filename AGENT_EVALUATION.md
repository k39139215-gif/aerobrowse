# Agent evaluation

Actual LLM-driven evaluation: **NOT_RUN**. Missing OPENAI_API_KEY and
AEROBROWSE_EVAL_MODEL in this environment. No agent task success rate is claimed.
The runnable harness is `python -m benchmarks.agent.run`; it invokes OpenAI
chat/completions with explicit model,temperature 0 and bounded tool calls against
the actual AeroBrowse newline-stdio MCP server. No separate SDK is needed for
model HTTP calls. Credentials are not inherited by browser workers.

Six tasks: documentation fact, search/detail extraction, authenticated record
update/logout, multistep form, two-tab comparison, and stale-action recovery.
Each task runs a fresh owned HTTP fixture. The judge reads fixture/server state
and expected answers independently; model claims alone cannot set PASS.

Receipts include revision,model/configuration,outcome,error/tool calls/retries,
end-to-end latency,incorrect actions,stale errors/recovery,cleanup and tokenizer
counts for the complete serialized MCP tool envelope including action metadata.
Response token counts exclude model chat-template overhead. Tool argument values,
full page content and authentication secrets are deliberately not persisted.

Deterministic browser workflow tests are separate:
`tests/browser/test_agent_workflows.py` covers the public supervised SDK and real
MCP subprocess login/update/logout,tabs/history/reload,search and multistep/stale
recovery. State assertions inspect record contents,login/logout counts and form
submission. Concurrent complete tasks run via `python -m benchmarks.agent.concurrency`.
They measure a tiny owned workload and do not establish production capacity,
fairness,indefinite stability or general autonomous-agent success.

The latest source, `dac1c1d`, passed the focused delegated Linux run
`45860943458`: 14 workflow, authentication, storage and error-document tests;
38 runtime passes and 2 Windows-only skips. The production Python source matches
`3e1d399` after CRLF normalization. The latest changes affect the harness/tests.

Local verification: 206 Python tests passed, with 21 native/platform skips and
67 browser deselections. A later focused rerun passed 46 tests. Ruff, formatting,
mypy and wheel/sdist build passed; all 18 wheel modules match the checkout.
Full final-source CI and its benchmarks/soak are queued. These are scripted
results, not model success. Historical phase2 evidence is kept separately.

The harness records complete content+structuredContent+isError+_meta envelopes,
including close responses used for cleanup. This is the application payload given
to the model, not JSON-RPC IDs,stdio framing or model chat-template overhead.
Provider/transport failure produces FAIL with a safe exception class and unverified
cleanup marked explicitly. No provider error bodies or API credentials are stored.
Retry count means error-bearing tool attempts,not an inferred reasoning retry;
incorrect-action count covers observable validation/type failures,not all possible
semantic mistakes. Independent fixture verdicts determine task completion.
