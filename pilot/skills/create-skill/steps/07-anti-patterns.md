## Step 7: Anti-Patterns & Troubleshooting

| Anti-Pattern | Fix |
|--------------|-----|
| **Kitchen sink** — skill does too many things | One skill = one purpose. Split it. |
| **Vague instructions** — "properly format the code" | Name the specific tool and command |
| **Explaining AI knowledge** — "React is a JavaScript library..." | Only add what AI doesn't know: YOUR conventions |
| **Too many options** — "use pdfplumber, PyMuPDF, or camelot..." | Give one default, mention alternatives only if needed |
| **No verification** — "deploy to staging" (how do you know it worked?) | Always include a verification command |
| **Hardcoded paths** — `/Users/john/projects/my-app/...` | Relative paths or environment variables |
| **Ambiguous language** — "Make sure to validate things properly" | `Before calling create_project, verify: project name non-empty, at least one team member assigned` |
| **Premature completion** — agent declares a step done early and rushes on | Sharpen the completion criterion first (see *Writing useful instructions* in Step 1) |
| **Negation steering** — walls of "never do X" prohibitions | State the positive target (see *Writing useful instructions*) |
| **Sediment & sprawl** — stale layers accumulate; SKILL.md grows past legibility | Prune on every revision (adding feels safe, removing feels risky — remove anyway); move conditional detail into linked references |
| **Duplication** — the same meaning stated in two places | Single source of truth: one authoritative place, so a behavior change is a one-place edit. Repeat a contract only when independently loaded artifacts require it; keep the copies synchronized |

### Iteration Signals

| Signal | Symptom | Fix |
|--------|---------|-----|
| **Undertriggering** | Skill doesn't load when it should, users manually enabling it | Add more detail and trigger keywords to description |
| **Overtriggering** | Skill loads for irrelevant queries, users disabling it | Add negative triggers ("Do NOT use for..."), be more specific |
| **Instructions not followed** | Agent loads skill but ignores steps | Instructions too verbose (condense), buried (move critical to top), or ambiguous (use exact commands) |
| **Large context issues** | Skill seems slow or responses degraded | Move conditional detail to `references/` and remove instructions that add no value |

### Correcting a demonstrated workflow failure

Use an observed failure to identify the missing decision rule or fragile contract. Add a specific condition, required field, or deterministic check that addresses it. Do not accumulate motivational slogans, imagined excuses, or prohibition tables merely because a workflow involves testing or verification.

Keep the correction proportional and validate it against a different realistic case. A rule that only fixes the original example is overfit.
