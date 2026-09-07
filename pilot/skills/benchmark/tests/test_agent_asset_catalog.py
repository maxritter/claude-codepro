import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT_PATH = Path(__file__).resolve().parents[4] / "scripts" / "validate_agent_assets.py"
SPEC = importlib.util.spec_from_file_location("validate_agent_assets", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
validator = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = validator
SPEC.loader.exec_module(validator)


def test_shipped_catalog_rules_and_generated_descriptions_pass() -> None:
    result = validator.validate(validator.REPO_ROOT, validator.DEFAULT_CATALOG, validator.DEFAULT_RATCHET)

    assert result["findings"] == []
    assert result["metrics"]["positive_top_three_rate"] == 1.0
    assert result["metrics"]["positive_rank_one_rate"] >= 0.8
    assert result["metrics"]["unscoped_lines"] <= 500
    assert result["metrics"]["unscoped_words"] <= 7500


def test_manifest_routing_metadata_overrides_catalog_fallback() -> None:
    entry = {"visibility": "public", "invocation": "explicit"}
    manifest = {"version": 2, "visibility": "internal", "invocation": "implicit", "parent": "spec"}

    assert validator._resolve_metadata(entry, manifest) == ("internal", "implicit", "spec")
    assert validator._resolve_metadata(entry, {"version": 1}) == ("public", "explicit", None)


def test_explicit_and_internal_skills_do_not_hijack_direct_requests() -> None:
    catalog = validator._read_json(validator.DEFAULT_CATALOG)
    records = validator._load_records(validator.REPO_ROOT, catalog)

    direct_ranked = [name for name, _ in validator._route("Fix the login redirect bug.", {}, records)]
    internal_ranked = [name for name, _ in validator._route("$spec-implement this plan", {}, records)]
    handoff_ranked = [
        name for name, _ in validator._route("Continue with $spec-implement.", {"parent": "spec"}, records)
    ]

    assert "fix" not in direct_ranked
    assert "spec-implement" not in internal_ranked
    assert internal_ranked[0] == "spec"
    assert handoff_ranked[0] == "spec-implement"


def test_description_validator_rejects_leading_routing_policy() -> None:
    record = validator.SkillRecord(
        name="fix",
        source=Path("pilot/skills/fix"),
        visibility="public",
        invocation="explicit",
        parent=None,
        description="Use only when explicitly invoked. Diagnose a defect.",
        positives=(),
        negatives=(),
    )

    findings, _ = validator._validate_descriptions(
        [record],
        {"descriptions": {"error_jaccard": 0.8, "max_pairwise_jaccard": 0.75}},
    )

    assert "description.leading-routing" in {finding.code for finding in findings}


def test_zero_signal_implicit_skills_do_not_route() -> None:
    catalog = validator._read_json(validator.DEFAULT_CATALOG)
    records = validator._load_records(validator.REPO_ROOT, catalog)

    ranked = [
        name
        for name, _ in validator._route(
            "Rotate the TLS certificate for the production load balancer.",
            {},
            records,
        )
    ]

    assert "ui-design" not in ranked
    assert "design-system" not in ranked
    assert "ui-design-review" not in ranked
    assert "benchmark" not in ranked
    assert "create-skill" not in ranked


@pytest.mark.parametrize("agent_name", ["spec-review", "changes-review", "build-review"])
def test_native_review_contract_is_read_only_with_a_json_result(agent_name: str) -> None:
    source = validator.REPO_ROOT / "pilot" / "agents" / f"{agent_name}.md"
    _, raw_metadata, prompt = source.read_text(encoding="utf-8").split("---", 2)
    metadata = yaml.safe_load(raw_metadata)
    allowed_tools = {tool.strip() for tool in metadata["tools"].split(",")}

    assert metadata["permissionMode"] == "plan"
    assert allowed_tools <= {"Read", "Grep", "Glob", "Bash(git diff:*)", "Bash(git log:*)"}
    assert {"Read", "Grep", "Glob"} <= allowed_tools
    assert "output_path" not in prompt
    assert "jsonSchema" not in metadata

    json_block = re.search(r"```json\s*\n(.*?)\n```", prompt, re.DOTALL)
    assert json_block is not None
    result = json.loads(json_block.group(1))
    assert isinstance(result["plan_file"], str)
    assert isinstance(result["issues"], list)
    assert {"severity", "category", "title", "description", "suggested_fix"} <= result["issues"][0].keys()


def _generated_codex_runtime(skill_name: str) -> str:
    from installer.steps.codex_files import _adapt_invocation_syntax, build_codex_skill_md

    skill_dir = validator.REPO_ROOT / "pilot" / "skills" / skill_name
    parts = [build_codex_skill_md(skill_dir)]
    manifest = json.loads((skill_dir / "manifest.json").read_text())
    if manifest.get("delivery") == "progressive":
        parts.extend(_adapt_invocation_syntax((skill_dir / step["file"]).read_text()) for step in manifest["steps"])
    return "\n\n".join(parts)


@pytest.mark.parametrize(
    "skill_name", ["spec-plan", "spec-bugfix-plan", "spec-implement", "spec-verify", "spec-bugfix-verify"]
)
def test_emitted_spec_phase_preserves_lane_on_every_handoff(skill_name: str) -> None:
    emitted = _generated_codex_runtime(skill_name)

    assert "Parse the plan path or description separately" in emitted
    assert "Resolve `LANE_ID` and `$LANE_FLAG`" in emitted
    handoffs = re.findall(r"using arguments:? `([^`]+)`", emitted)
    assert handoffs
    assert all("$LANE_FLAG" in arguments for arguments in handoffs)


@pytest.mark.parametrize("skill_name", ["spec-plan", "spec-verify", "build", "fix"])
def test_emitted_review_launch_requires_durable_record(skill_name: str) -> None:
    emitted = _generated_codex_runtime(skill_name)

    assert "review-state-protocol.md" in emitted
    assert "Persist each returned native or companion handle atomically" in emitted
    assert "reload that record after compaction and before collection" in emitted


@pytest.mark.parametrize("runtime", ["claude", "codex"])
@pytest.mark.parametrize("skill_name", ["spec-plan", "spec-verify", "build", "fix"])
def test_emitted_native_review_lifecycle_is_ordered(skill_name: str, runtime: str) -> None:
    if runtime == "codex":
        emitted = _generated_codex_runtime(skill_name)
        launch_step = "Use the spawn-agent tool exposed in the current Codex tool schema"
    else:
        from installer.skill_builder import build_skill_md

        skill_dir = validator.REPO_ROOT / "pilot" / "skills" / skill_name
        parts = [build_skill_md(skill_dir)]
        manifest = json.loads((skill_dir / "manifest.json").read_text())
        if manifest.get("delivery") == "progressive":
            parts.extend((skill_dir / step["file"]).read_text() for step in manifest["steps"])
        emitted = re.sub(r"<!-- CODEX-START.*?CODEX-END -->", "", "\n\n".join(parts), flags=re.DOTALL)
        launch_step = "Launch with the actual `Agent` schema" if skill_name == "build" else "Agent(\n"
    ordered_steps = [
        "Read and reconcile the existing native review record",
        "Atomically write `state: launching`",
        launch_step,
        "Immediately persist the returned `native_agent_id`",
        "At native collection, confirm terminal completion",
        "write `state: completed`",
        "write `state: collected`",
    ]
    offsets = [emitted.index(step) for step in ordered_steps]
    assert offsets == sorted(offsets)
    assert "`state: incomplete`" in emitted


@pytest.mark.parametrize(
    "step_path",
    [
        "spec-plan/steps/12-approval.md",
        "spec-bugfix-plan/steps/06-approval.md",
        "spec-verify/steps/10-review-gate.md",
        "spec-bugfix-verify/steps/06-code-review-gate.md",
    ],
)
def test_persisted_gate_validates_identity_without_blocking_synchronous_question(step_path: str) -> None:
    step = (validator.REPO_ROOT / "pilot" / "skills" / step_path).read_text()
    assert ":-default" not in step
    assert "A synchronous permitted question needs no disk sentinel" in step
    for snippet in re.findall(r"```bash\n(.*?)\n```", step, re.DOTALL):
        if "touch " in snippet or "rm -f " in snippet:
            assert snippet.index("SESSION_ID=") < snippet.index("case ") < snippet.index("SESS_DIR=")


@pytest.mark.parametrize(
    "step_path",
    [
        "spec-plan/steps/10-plan-verification.md",
        "spec-verify/steps/01-launch-review.md",
        "fix/steps/06-finalise.md",
    ],
)
def test_companion_once_precheck_validates_session_before_reading_flag(step_path: str) -> None:
    step = (validator.REPO_ROOT / "pilot" / "skills" / step_path).read_text()
    assert ":-default" not in step
    assert step.index('case "$SESS') < step.index("CODEX_FLAG=")


def test_emitted_dispatcher_parses_lane_before_plan_path_detection() -> None:
    emitted = _generated_codex_runtime("spec")

    assert emitted.index("First parse optional `--lane <id>`") < emitted.index('ELIF arguments end with ".md"')
    assert "Dispatch the selected skill with the parsed plan path plus `$LANE_FLAG`" in emitted


def test_emitted_codex_catalog_has_no_unavailable_claude_native_instructions() -> None:
    from installer.steps.codex_files import CodexFilesStep

    for skill_name in CodexFilesStep._CODEX_SUPPORTED_SKILLS:
        emitted = _generated_codex_runtime(skill_name)
        for forbidden in (
            "mcp__claude-in-chrome__",
            "mcp__plugin_chrome-devtools-mcp_",
            "Automated Claude planning uses the native-plan bridge",
        ):
            assert forbidden not in emitted, (skill_name, forbidden)
    # This is a cross-agent skill, so the generated Codex UI review must retain it.
    assert "open-claude-ui-review" in _generated_codex_runtime("spec-verify")


def test_review_and_gate_runbooks_preserve_recovery_and_reader_compatibility() -> None:
    agents = validator.REPO_ROOT / "pilot" / "agents"
    state = (agents / "review-state-protocol.md").read_text()
    companion = (agents / "codex-companion-protocol.md").read_text()
    gate = (agents / "agent-gate-protocol.md").read_text()
    native = (agents / "spec-native-plan.md").read_text()

    assert "os.replace(temporary, target)" in state
    for field in ("native_agent_id", "job_id", "prompt_path", "lane_id", "reviewed_sha256", "retry_count"):
        assert field in state
    assert "timeout: 15000" in companion
    assert "There is no arbitrary total review deadline" in companion
    assert "Current stop-guard readers consume only main-session sentinels" in gate
    assert "Never create, consume, or clear a coordinator's sentinel from a lane" in gate
    assert 'pilot spec validate "<registered-plan-path>" --json' in native
    assert "user dialog edits invalidate stale review evidence" in native


def test_rule_budget_counts_only_unscoped_rules(tmp_path: Path) -> None:
    rules = tmp_path / "pilot" / "rules"
    rules.mkdir(parents=True)
    (rules / "global.md").write_text("first line\nsecond line\n", encoding="utf-8")
    (rules / "scoped.md").write_text("---\npaths: ['**/*.py']\n---\nDated 2099 claim\n", encoding="utf-8")
    config = {"max_unscoped_lines": 2, "max_unscoped_words": 4, "max_unscoped_file_lines": 2}

    findings, metrics = validator._validate_rules(tmp_path, config)

    assert findings == []
    assert metrics == {"unscoped_files": 1, "unscoped_lines": 2, "unscoped_words": 4}


def test_rule_budget_reports_overflow_and_dated_claims(tmp_path: Path) -> None:
    rules = tmp_path / "pilot" / "rules"
    rules.mkdir(parents=True)
    (rules / "global.md").write_text("A dated 2026 claim.\nToo many lines.\n", encoding="utf-8")
    config = {"max_unscoped_lines": 1, "max_unscoped_words": 3, "max_unscoped_file_lines": 1}

    findings, _ = validator._validate_rules(tmp_path, config)

    assert {finding.code for finding in findings} == {
        "rules.dated-claim",
        "rules.file-lines",
        "rules.lines",
        "rules.words",
    }
