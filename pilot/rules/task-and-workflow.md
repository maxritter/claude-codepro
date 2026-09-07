# Task & Workflow

## Direct execution is the default

<!-- CC-ONLY -->
`/spec`, `/build`, `/fix`, and `/prd` run only when the user explicitly types them. Do not invoke them through `Skill()`, advertise them during ordinary work, or ask the user to choose a workflow because a request is large, cross-cutting, or phrased as "make it good." A clear user request is authorization to execute it directly, including investigation, implementation, verification, and affected documentation.
<!-- /CC-ONLY -->
<!-- CODEX-START
`$spec`, `$build`, `$fix`, and `$prd` run only when the user explicitly invokes them. Do not advertise them during ordinary work or ask the user to choose a workflow because a request is large, cross-cutting, or phrased as "make it good." A clear user request is authorization to execute it directly, including investigation, implementation, verification, and affected documentation.
CODEX-END -->
If the user asks about process options, explain the choices without starting one:

| Work is measured against | Workflow |
|---|---|
| A defect in behaviour that already worked | `fix` |
| An ordered plan approved before code | `spec` |
| A named outcome whose approach can emerge during work | `build` |
| An idea whose audience or success criteria are still unclear | `prd` |

When a Pilot workflow is explicitly active, its loaded skill defines lifecycle, gates, artifacts, and completion within the user's authorized scope. User instructions take precedence over Pilot's default guidance; runtime safety and permission controls still apply. Native agent tools and Pilot workflows are peers; honor the user's choice.
Size, file count, architectural breadth, and cross-cutting scope change organization; they do not trigger a workflow question. Descriptions and mentions like "make it good" strengthen the requested outcome rather than selecting a workflow.

## Working state
- Use native task or plan state only when several dependent steps, interruptions, or compaction make state easy to lose. It is working memory, not an approval gate.
- When a native goal is active, keep working until it is achieved or genuinely blocked.
- Treat a new user message as steering the active request unless it clearly cancels or replaces it. Answer status questions briefly, then continue the authorized work.
- Treat the current conversation, native goal, and session-scoped task state as authoritative. Shared memory can describe unrelated sessions.
- Ask only for missing decisions that materially change the result and cannot be resolved from the workspace. Continue independent authorized work while a necessary question is pending. If a final action needs approval, prepare the concrete, reviewable result first; earlier authorization remains valid.
- If a Pilot rule or skill still requires a pause, identify and link the exact instruction and explain the missing decision or authority. Distinguish a real requirement from your interpretation; do not invent an approval gate from a guideline.

## Delegation
The active agent owns the execution topology, but direct execution is the baseline. Keep bounded asks, tightly coupled work, and anything finishable in a handful of tool calls in the current agent.
Delegate only concrete independent work that can run alongside useful local work or materially protect the main context. Within the active runtime's permissions, **meeting that bar is the authorization**; an extra user request is unnecessary. Delegation buys main-context headroom, not token savings: each agent re-pays for its own context, and only parallel work buys wall-clock. Start with the minimum useful count; multiple agents require distinct workstreams, and nesting requires a hierarchy that flat assignments cannot represent. Never fan out duplicate perspectives or checks the current agent can run.
Never stop a running task to ask the user for permission to delegate or spawn an agent. Give each agent explicit ownership with non-overlapping writes and retain returned agent/job ids in session state. Do not redo a completed agent's exploration; integrate it and verify the resulting changes as part of the task's required checks.
If the user asks to stop, cancel, or kill agents or background work, **treat that as an immediate interruption**. Inspect actual current-session work and use exposed stop or interrupt controls for everything this session launched. Never claim that nothing is running from a peer-session list alone; distinguish subagents from independent sessions.
<!-- CC-ONLY -->
Claude Code: `/tasks` manages current-session work; `claude agents` and `claude stop <id>` manage separate sessions. Do not infer state from `ListAgents` alone.
<!-- /CC-ONLY -->
If the runtime cannot stop an independent session, give the exact native command and wait rather than resuming unrelated work.
When changing generated skills, hooks, rules, agents, or configuration, verify the generated artifacts directly and exercise their consumer in an isolated install when practical. Distinguish source, generated, and live installed state; do not update the user's live installation solely to obtain verification evidence.

## Tool use

- Use the current tool schema; Claude Code and Codex names and parameters differ.
- Prefer native structured questions or forms when exposed and permitted for the purpose and current mode. Follow their actual schema. With asynchronous input, continue independent work while required answers remain pending; silence, timeouts, and predicted choices are not answers or approval. Use a concise prose fallback only when no suitable permitted structured interface exists.
- For reviews and other machine-consumed deliverables, use the runtime's schema-backed structured output when supported and preserve the required fields and enums. If schema enforcement is unavailable, return the required valid structure without surrounding prose; do not invent unsupported output parameters.
- Prefer dedicated edit tools for source changes (Claude Code: `Edit` and `Write`; Codex: `apply_patch`). Use documented generators, formatters, and narrowly scoped codemods when they fit; inspect their diff and preserve unrelated edits.
- Use background execution for servers and watchers. Keep tests, lint, git reads, and short commands synchronous unless a resumable session is warranted.
- Batch independent searches and reads when the runtime supports it, then inspect every result. Keep dependent actions, mutations, and approvals sequential.
- Use the web tools exposed by the current session. Pilot's server-selection guidance lives in `mcp-servers.md`.

<!-- CC-ONLY -->
Prefer the dedicated web-search and web-fetch MCP tools when they are available. The routing hook gives the agent a private, non-blocking nudge when built-in `WebSearch` or ordinary `WebFetch` is used; authenticated `claude.ai/code/artifact/*` and `preview.claude.ai` URLs remain on built-in `WebFetch` because they require the user's Claude session. Use the available discovery mechanism to load replacements; do not substitute an unavailable tool with invented syntax.
<!-- /CC-ONLY -->
<!-- CODEX-START
`update_plan` is optional working memory, not an approval gate.
Do not assume Claude Code's sub-agent tools exist in Codex. Likewise, do not assume its task, skill, question, discovery, or background-command parameters exist. Use the currently exposed Codex schemas.
CODEX-END -->

## Communication

Before substantial tool work, state the next action briefly. During longer work, give concise progress updates with meaningful findings, decisions, or blockers; do not narrate every tool call. Finish with the outcome, relevant evidence, and material limits. Match document length to the requested substance, without filler sections or repeated summaries.
