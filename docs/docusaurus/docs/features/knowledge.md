---
sidebar_position: 1
title: Automatic Memory
description: Background memory for Claude Code and Codex, with automatic capture, retrieval, and optional team sharing.
---

# Automatic Memory

Pilot remembers useful decisions, discoveries, fixes, and project context as you work. It runs in the background, capturing useful findings and making them available to your agents when they help the current task.

**The only memory setting is Team sharing: on or off.** With sharing off, memory stays local. With sharing on for a Team project, project learnings also travel with the repository and become available to coworkers automatically.

## How it helps your agents

Pilot captures useful findings from session evidence and retains the broader history across Claude Code and Codex. Agents use that history when it adds information needed for the current task, and refine durable memories as they work. They handle searching, reading sources, and updating knowledge themselves.

Native agent memory continues to provide compact context directly to the live session. Pilot complements it with a fuller, on-demand view across agents and past work. Useful facts may overlap. Agents use context they already have, then ask Pilot for additional history or detail when useful.

Background observation focuses on new project evidence and filters routine memory maintenance, keeping the retained history useful.

## Provider selection is automatic

Pilot uses available Claude Code or Codex resources with low-cost background models. It works with either provider alone or both. If the current provider cannot run because of authentication, quota, or a temporary failure, Pilot can use the other available provider and retry automatically.

Local search and saved memories remain available independently of background synthesis. When no provider can synthesize new observations, Pilot retains pending evidence within bounded limits and retries later. Your existing memory remains usable. Capture resumes automatically as provider resources become available.

## One memory view

The Console's **Memories** page is an optional view into what Pilot remembers. It shows remembered findings and their sources, while agents handle recall directly during work. Local and shared project knowledge are combined automatically, with sources shown where available.

To collaborate, use the single **Team sharing** switch. See [Team Memories](./team-memories.md).

## Existing memories and backups

Existing observations and their identifiers remain available. Automatic shared memories stay in daily JSONL files grouped by author. Generated Markdown copies from the earlier automatic conversion are recovered into that layout before their unchanged copies are removed; edited knowledge files are preserved.

Pilot's existing backups include local history, personal knowledge files, checkout mappings, and pending capture evidence. Shared project files remain part of the repository and its Git history. Restores preserve existing concepts when there is a conflict instead of silently overwriting them.

## Under the hood

Private history is stored locally in SQLite. Automatic shared memories use `.pilot/memories/<author>/<YYYY-MM-DD>.jsonl`, so each contributor adds to one readable file per day. Explicitly maintained knowledge uses portable Markdown based on the Open Knowledge Format under `.pilot/knowledge/`. Local indexes make both searchable without depending on a vector service; synchronization state stays outside the repository.

For isolated development and verification, `PILOT_MEMORY_DATA_DIR` can point to an absolute temporary directory. This relocates Pilot's memory data, logs, backups, and indexes without changing either provider's authentication home.
