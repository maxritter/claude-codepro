## Step 3: All Tasks Complete → Verification

1. Confirm the required broad suite and diagnostics passed against the integrated current code. Reuse a current successful Quality Gate result; rerun checks whose inputs changed or whose evidence is missing. Task-level focused checks do not replace the required integrated suite.
2. **For migrations:** Feature parity check against old code. If features missing: add tasks, do NOT mark complete. See sub-section 3.1 below.
3. Set `Status: COMPLETE` in plan
4. Register: `~/.pilot/bin/pilot register-plan "<plan_path>" "COMPLETE" $LANE_FLAG 2>/dev/null || true`

> **`$LANE_FLAG`** is `--lane <id>` when this run was dispatched as an orchestration lane, and **nothing at all** otherwise — the value the planning phase parsed from its arguments. It keeps the registration in `sessions/<id>/lanes/<lane>/` rather than the coordinator's single slot, which is what stops a lane's plan blocking the coordinator's stop guard (issue #174). Skills build into separate SKILL.md files, so this is restated wherever the placeholder is used.

5. Read `Type:` field.
   <!-- CC-ONLY -->
   Bugfix: `Skill(skill='spec-bugfix-verify', args='<plan-path> $LANE_FLAG')` | Otherwise: `Skill(skill='spec-verify', args='<plan-path> $LANE_FLAG')`
   <!-- /CC-ONLY -->
   <!-- CODEX-START
   Codex has no callable phase-dispatch tool. Bugfix: continue immediately with the `$spec-bugfix-verify` skill instructions using arguments: `<plan-path> $LANE_FLAG` | Otherwise: continue immediately with the `$spec-verify` skill instructions using arguments: `<plan-path> $LANE_FLAG`.
   CODEX-END -->

### 3.1 Migration/Refactoring Additions (only when `## Feature Inventory` is present in the plan)

**Before starting any migration task:** Locate Feature Inventory in plan. If missing: STOP. Verify all features mapped.

**During each migration task:** Read old files, create checklist of functions/behaviors, verify each exists in new code, test with same inputs.

**Red flags (STOP):** Feature Inventory missing, old functions not in any task, "Out of Scope" items that should be migrated, tests pass but functionality missing vs old code.

ARGUMENTS: $ARGUMENTS
