## Step 0: Runtime and Model Settings

<!-- CC-ONLY -->
Read the current model-switching setting; a Console change should affect this invocation:

```bash
MODE=$(python3 -c "import sys,os;sys.path.insert(0,os.path.expanduser('~/.pilot/hooks'));from _lib.util import read_model_switch_mode;print(read_model_switch_mode())" 2>/dev/null || echo "manual")
echo "MODE=$MODE"
```

Manual and Off preserve the current `/model` choice through the workflow. Automated uses Claude Code's `opusplan` mode when available: the planning skill prepares its registered draft before entering native plan mode, follows the runtime's read-only limits, and uses native approval for the handoff. See `$HOME/.pilot/agents/spec-native-plan.md` at that point.

Respect the current permission mode. Relay a concrete model-selection or capability mismatch once when it affects this run; do not add a routine permission warning, recommend bypass mode, or pause for a model switch. Continue with Step 1.
<!-- /CC-ONLY -->
<!-- CODEX-START
Pilot's Claude permission/model-switching tools do not apply here. Preserve the active Codex model and native mode, use its current tool schemas, and continue with Step 1.
CODEX-END -->
