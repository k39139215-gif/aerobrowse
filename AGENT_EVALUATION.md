# Agent evaluation

Actual LLM-driven evaluation: **NOT_RUN**. Missing OPENAI_API_KEY and
AEROBROWSE_EVAL_MODEL in this environment. No agent task success rate is claimed.
The runnable harness is `python -m benchmarks.agent.run`; it invokes OpenAI
chat/completions with explicit model,temperature0 and bounded tool calls against
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

Current new-source Linux browser/workflow/concurrency verification: PENDING.
Local server-state and SDK process tests passed; final revision receipts will
supersede this line after CI. Historical phase2 evidence is preserved separately.
