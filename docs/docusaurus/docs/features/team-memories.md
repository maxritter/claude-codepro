---
sidebar_position: 2
title: Team Memories
description: Turn on Team sharing once and let project knowledge follow the code through Git automatically.
---

# Team Memories

Pilot memory works automatically on your machine. **Team sharing** extends it to coworkers through the project repository.

The only choice is whether sharing is **on or off** for that project. Team sharing requires a Team plan; local memory continues to work without it.

## Turn sharing on

Open **Memories** in the Console and enable **Team sharing** for the project. Pilot handles the rest:

- Existing project learnings are prepared for sharing automatically.
- New useful findings are written to the project's shared memory as work progresses.
- Existing daily JSONL records continue to work; unchanged generated Markdown copies are recovered into that layout without losing their records.
- Coworkers working in the enabled project automatically receive knowledge that arrives through Git.

The agents handle recall and keep the shared knowledge current as they work.

## Knowledge follows the code

Pilot writes automatic findings to `.pilot/memories/<author>/<YYYY-MM-DD>.jsonl`, one file per contributor per day. Explicitly maintained knowledge lives under `.pilot/knowledge/`; local synchronization state stays outside the repository. Your normal Git workflow carries shared files between contributors: commit and push changes as usual, and pull your coworkers' updates as usual. Pilot refreshes its local view automatically, including updates received during an existing session.

Memory files follow the same review, commit, push, and pull workflow as the code. Agents can include them in the Git work you authorize.

Shared memories become available for relevant agent queries. Raw prompts, session transcripts, and private session summaries stay local.

## Turn sharing off

Switch **Team sharing** off to stop exchanging further updates for that project. Local memory continues working, and previously received knowledge remains available locally. Committed files and existing memories are preserved.

If Team access becomes unavailable, Pilot continues locally.

## Background operation

Capture, provider selection, synchronization, format compatibility, validation, and retrieval are handled in the background. Agents use the accumulated knowledge directly during work; the Console provides a view of remembered findings and their sources.

See [Automatic Memory](./knowledge.md) for how Pilot works alongside the native memory in Claude Code and Codex.
