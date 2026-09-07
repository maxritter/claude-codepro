## Step 2: Status-Based Dispatch (existing plans)

**`$LANE_FLAG`** is `--lane <id>` when the invocation carried one (Step 1.2a) and **nothing at all** otherwise — a re-entry into an existing lane's plan must register back into that lane's directory, not the coordinator's slot.

Read plan, register association: `~/.pilot/bin/pilot register-plan "<plan_path>" "<status>" $LANE_FLAG 2>/dev/null || true`


| Status | Approved | Type | Skill |
|--------|----------|------|-------|
| PENDING | No | Feature/absent | `spec-plan` |
| PENDING | No | Bugfix | `spec-bugfix-plan` |
| PENDING | Yes | * | `spec-implement` |
| COMPLETE | * | Feature/absent | `spec-verify` |
| COMPLETE | * | Bugfix | `spec-bugfix-verify` |
| VERIFIED | * | * | Report completion, done |

Dispatch the selected skill with the parsed plan path plus `$LANE_FLAG`; preserve both on every transition and loopback.

ARGUMENTS: $ARGUMENTS
