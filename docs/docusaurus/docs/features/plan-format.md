---
sidebar_position: 9
title: Plan File Format
description: The plan file contract any tool can target — header fields, sections, task cards and numbering — plus the `pilot spec` CLI that scaffolds and validates it.
---

# Plan File Format

Pilot's plan files are plain Markdown. Nothing about them is private: any skill,
script, or editor can write one, and the Console, the statusline, the stop guard
and the shared review pages will all pick it up.

This page is the contract. The machine-readable form ships with Pilot at
`~/.pilot/spec/plan-format.json`, and `pilot spec validate` is the authoritative
check — if this page and the validator ever disagree, the validator is right.

:::tip Don't hand-check any of this
`pilot spec init` writes a skeleton that already conforms, and
`pilot spec validate --json` tells you exactly what is wrong and where. See
[the CLI reference](cli#spec-authoring).
:::

## Anatomy

```markdown
# My Feature Implementation Plan

Created: 2026-08-24
Status: PENDING
Approved: No
Iterations: 0
Worktree: No
Type: Feature

## Summary

**Goal:** What the user can do once this lands.

## Progress Tracking

- [ ] Task 1: First thing
- [ ] Task 2: Second thing

## Implementation Tasks

### Task 1: First thing

**Objective:** What this task does and why.

**Files:**

- Modify: `src/thing.py`

**Key Decisions / Notes:**

- Follow the pattern at `src/other.py:42`.

**Definition of Done:**

- [ ] The observable outcome.
- [ ] Verify: `pytest tests/test_thing.py -q`
```

## Header fields

The header is a run of `Key: value` lines below the title. Values are closed sets
— an unrecognised value is an error, not a free-text note.

| Field | Required | Allowed values |
|---|---|---|
| `Created` | yes | A date |
| `Author` | no | Usually an email |
| `Agent` | no | `Claude Code` or `Codex` |
| `Status` | yes | `PENDING`, `COMPLETE`, `VERIFIED` — bare keyword, no trailing prose |
| `Approved` | yes | `Yes`, `No` |
| `Worktree` | yes | `Yes`, `No` |
| `Type` | yes | `Feature`, `Bugfix`, `Build` |
| `Iterations` | yes (Feature, Bugfix) | A number |
| `Rounds` | yes (Build) | A number |

`Type` decides which task-card fields are required and which progress counter is
read. `Status` is what the statusline and the Console file the plan under, and it
is the field most often got wrong: `RESOLVED`, `DONE` and `CLOSED` are not in the
set and are treated as terminal-unknown.

## Line endings

**Plan files must use LF (`\n`).** The renderers are newline-anchored, so a plan
saved with CRLF loses every task card — the carriage return ends up inside each
task title. `pilot spec validate` reports CRLF as an error rather than letting a
file pass here and render wrong in the Console.

## Sections

Any `## Heading` is a section. Recognised headings render in this fixed order,
regardless of where they appear in the file, so the Console and the public
`pilot-shell.com/s/<id>` pages always agree:

`Summary` · `Acceptance Criteria` · `Criteria` · `Out of Scope` · `Investigation` ·
`Behavior Contract` · `Approach` · `Fix Approach` · `Scope` ·
`Autonomous Decisions` · `Global Constraints` · `Context for Implementer` ·
`Runtime Environment` · `Feature Inventory` · `Assumptions` · `Deviations` ·
`Risks and Mitigations` · `Goal Verification` · `E2E Test Scenarios` ·
`E2E Results` · `Verification Scenario` · `Verification Scenarios` ·
`File Structure` · `Open Questions` · `Deferred Ideas` · `Round Log` ·
`Changed Files`

**Your own sections render too.** A heading that is not on that list is not
dropped — it appears after the recognised sections, in the order you wrote it. So
a plan built by your own tooling can carry whatever sections it needs.

Two exceptions:

- **Hidden:** `Progress Tracking` and the legacy `Progress` never render as
  sections. Each surface already shows that checklist as a task count in the
  header card, so rendering it again would duplicate it.
- **Rendered specially:** `Implementation Tasks` (feature and build) and `Tasks`
  (bugfix) are turned into clickable task cards rather than an ordinary section.

### `## Deviations` — what implementation learned

The implement phase appends this section when reality diverges from the approved
plan (the `/spec` discovery protocol): one entry per deviation, in the shape
`- Task N (tactical|user-agreed): <discovery> → <what changed>`. Tactical entries
record detail-level adaptations the agent made on its own; `user-agreed` entries
record amendments settled with you during a discussion pause. A deviation that
changes which files are touched must name the exact repository paths and update
the affected task's `Files:` block in the same edit. Verification scopes its
review lineage to the plan's `Files:` blocks **plus files recorded here**, so an
agreed amendment is reviewed as in-scope rather than flagged as drift.

## Tasks

Task headings are `### Task N: Title`, numbered **1..n, contiguous, in order**.
Gaps, duplicates and a list starting at 2 are all errors — several surfaces index
by position, so a gap silently misaligns them.

For `Type: Feature` and `Type: Build`, every task heading under
`## Implementation Tasks` must also appear in `## Progress Tracking` as
`- [ ] Task N: Title` (or `- [x] …` when done), and vice versa.

For `Type: Bugfix`, `## Tasks` owns both shapes: its checklist comes first, then
the matching `### Task N:` bodies. Bugfix plans intentionally have no duplicate
`## Progress Tracking` section. In both shapes, the checklist drives the progress
counter.

### Task-card fields

For `Type: Feature` and `Type: Bugfix`, each task body must contain these four
labels **verbatim**, including the bold markers:

```markdown
**Objective:**
**Files:**
**Key Decisions / Notes:**
**Definition of Done:**
```

This is the single most common thing to get wrong. `Files:` without the asterisks,
`DoD:` instead of `Definition of Done:`, or `Verification:` as a separate block
will not render as task-card fields — the text still appears, but the collapsible
per-field layout does not.

`Type: Build` tasks require only `**Objective:**`. A Buildout also carries
`## Acceptance Criteria` with `- [ ] Criterion N: …` lines, which are a separate
list from its tasks.

### User-owned tasks

Feature and Bugfix plans may place a non-automatable step in the normal task order:

```markdown
**Owner:** User
**User Action:** Sign in to the device locally; do not paste credentials into chat.
```

Both labels are omitted for ordinary agent work. `Owner` defaults to `Agent`, and
`User Action` is invalid without `Owner: User`. A user-owned task contains only
the manual action; surrounding agent preparation and verification belong in
adjacent tasks. `/spec` pauses durably at the task and proceeds only after exact
`done` plus any observable verification. Autonomous Buildouts cannot contain
user-owned tasks.

## Registering a plan

Writing the file is not enough for Pilot's hooks to treat it as *yours*:

```bash
~/.pilot/bin/pilot register-plan "docs/plans/2026-08-24-my-feature.md" "PENDING"
```

Registration is what scopes Pilot's behaviour to your session. Pilot reads the
active plan from `~/.pilot/sessions/<session-id>/active_plan.json`, so several
sessions can run in one repository directory without seeing each other's work.

:::warning Register, or share the fallback
Without a registration the planning stop guard cannot attribute a plan file to a
session and falls back to scanning the directory for today's plans. In that
fallback a sibling session's file can satisfy your session's check. If you are
building a workflow that runs alongside other sessions in the same working copy,
call `register-plan` as soon as you create the file.
:::

Update the status as the work moves:

```bash
~/.pilot/bin/pilot register-plan "docs/plans/2026-08-24-my-feature.md" "COMPLETE"
```

## Where plans live

| Type | Directory |
|---|---|
| `Feature`, `Bugfix` | `docs/plans/` |
| `Build` | `docs/builds/` |

Filenames are `YYYY-MM-DD-<slug>.md`. The `Type:` header, not the directory, is
what identifies a file — a Buildout left in `docs/plans/` still works.

## Machine-readable contract

Everything above comes from one file, which ships with Pilot:

```bash
cat ~/.pilot/spec/plan-format.json
```

It carries the section order, the hidden sections, the header field rules, the
task-card labels per type and the heading/progress-line patterns. Read it instead
of hard-coding these rules, and run `pilot spec validate` instead of
re-implementing the checks.
