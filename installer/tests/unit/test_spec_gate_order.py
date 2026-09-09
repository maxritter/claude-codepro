"""Human-facing spec gates must be armed before their prose fallback is emitted."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "relative",
    (
        "pilot/skills/spec-verify/steps/10-review-gate.md",
        "pilot/skills/spec-bugfix-verify/steps/06-code-review-gate.md",
    ),
)
def test_review_gate_orders_sentinel_before_prose_question(relative: str) -> None:
    content = (ROOT / relative).read_text()

    arm = content.index("### Arm exactly one gate before presenting")
    sentinel = content.index('touch "$SESS_DIR/verify-gate-pending"')
    present = content.index("### Present the reviewable result")

    assert arm < sentinel < present
    assert "sentinel on disk before any user-visible question" in content
    assert "make no later tool call and yield immediately" in content


def test_shared_agent_gate_protocol_has_the_same_hard_order() -> None:
    content = (ROOT / "pilot/agents/agent-gate-protocol.md").read_text()

    assert "arm any required persistence **before emitting the user-visible question**" in content
    assert "Never print a prose question first" in content
    assert "The sentinel write is the final tool call before the question" in content
