## Step 8: Hand Off to /spec or /build

Step 7 already settled and approved the PRD content. Show the hand-off command without another confirmation.

**⛔ Never auto-invoke `/spec`, `/build`, `Skill('spec')`, or `Skill('build')`.** The user MUST type the command themselves (global rule in `task-and-workflow.md`). This skill's terminal action is to PRINT the command, then stop and wait.

**Pick which command to print** from what the PRD says the work is measured against:

| The PRD's own centre of gravity | Print |
|---|---|
| An ordered set of requirements to implement and verify | `/spec` |
| A named reference to match or beat, or a quality standard as the acceptance bar | `/build` |
| Genuinely both, or unclear | print `/spec` and mention `/build` in one line |

Size is not the discriminator — a large PRD is not automatically `/spec`.

Print the appropriate hand-off command for the user to run; do not invoke it yourself. If the user explicitly said they are done for now, just confirm the saved PRD path.



```
PRD saved to docs/prd/YYYY-MM-DD-slug.md

To start implementation planning, run:
  /spec "Implement <one-line-summary> — PRD: docs/prd/YYYY-MM-DD-slug.md — see PRD for full requirements"
```

or, when the PRD's acceptance bar is a standard rather than a task list:

```
PRD saved to docs/prd/YYYY-MM-DD-slug.md

To start the build-judge loop, run:
  /build "<one-line-summary> — PRD: docs/prd/YYYY-MM-DD-slug.md"
```

**The command's argument must NOT end in `.md`** — the trailing text after the path prevents the `/spec` dispatcher from treating it as an existing plan file (dispatcher plan-file mode triggers only when the argument ends with `.md` AND the file exists).

ARGUMENTS: $ARGUMENTS
