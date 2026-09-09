"""Tests for scripts/check_manifest_drift.py."""

from __future__ import annotations

from pathlib import Path

import pytest


# Import the script as a module by adding its directory to sys.path.
@pytest.fixture
def drift_module():
    import importlib.util
    import sys

    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "check_manifest_drift.py"
    spec = importlib.util.spec_from_file_location("check_manifest_drift", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_manifest_drift"] = module
    spec.loader.exec_module(module)
    return module


class TestDriftDetection:
    """Forbidden patterns are detected on the right files."""

    def test_at_latest_in_dependencies_fails(self, drift_module, tmp_path: Path) -> None:
        py = tmp_path / "dependencies.py"
        py.write_text('def install_x():\n    return _run_bash_with_retry("npm install -g something@latest")\n')
        findings = drift_module.scan_file(py)
        assert any("@latest" in f.message for f in findings)

    def test_master_install_sh_fails(self, drift_module, tmp_path: Path) -> None:
        py = tmp_path / "dependencies.py"
        py.write_text('cmd = "curl -fsSL https://example.com/master/install.sh | bash"\n')
        findings = drift_module.scan_file(py)
        assert any("install.sh" in f.message for f in findings)

    def test_head_install_sh_fails(self, drift_module, tmp_path: Path) -> None:
        py = tmp_path / "prerequisites.py"
        py.write_text("curl https://x/HEAD/install.sh | bash\n")
        findings = drift_module.scan_file(py)
        assert any("install.sh" in f.message for f in findings)

    def test_unversioned_uv_run_with_in_install_sh_fails(self, drift_module, tmp_path: Path) -> None:
        sh = tmp_path / "install.sh"
        sh.write_text('#!/bin/bash\nuv run --python 3.12 --no-project --with rich --with certifi python -c "..."\n')
        findings = drift_module.scan_file(sh)
        # Two unversioned --with calls.
        assert any("--with" in f.message for f in findings)

    def test_versioned_uv_run_with_passes(self, drift_module, tmp_path: Path) -> None:
        sh = tmp_path / "install.sh"
        sh.write_text(
            "#!/bin/bash\n"
            'uv run --python 3.12 --no-project --with rich==14.0.0 --with certifi==2026.4.22 python -c "..."\n'
        )
        findings = drift_module.scan_file(sh)
        assert not any("--with" in f.message for f in findings)

    def test_unversioned_npx_in_mcp_json_fails(self, drift_module, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "npx", "args": ["-y", "open-websearch"]}}}')
        findings = drift_module.scan_file(mcp)
        assert any("npx" in f.message.lower() or "unpinned" in f.message.lower() for f in findings)

    def test_versioned_npx_in_mcp_json_passes_when_in_manifest(self, drift_module, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "npx", "args": ["-y", "fetcher-mcp@0.3.9"]}}}')
        findings = drift_module.scan_file(mcp)
        assert not any("npx" in f.message.lower() or "unpinned" in f.message.lower() for f in findings)

    def test_npx_pinned_but_unmonitored_fails(self, drift_module, tmp_path: Path) -> None:
        """Pinned npx package missing from manifest is rejected by the cross-ref check."""
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "npx", "args": ["-y", "totally-not-monitored@1.2.3"]}}}')
        findings = drift_module.cross_reference_mcp(mcp)
        assert any("not in manifest" in f.message.lower() or "unmonitored" in f.message.lower() for f in findings)

    def test_unpinned_uvx_from_in_mcp_json_fails(self, drift_module, tmp_path: Path) -> None:
        """`uvx --from <pkg>` with no `==<version>` floats to whatever PyPI serves."""
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "uvx", "args": ["--from", "semble[mcp]", "semble"]}}}')
        findings = drift_module.scan_file(mcp)
        assert any("unpinned" in f.message.lower() for f in findings)

    def test_pinned_uvx_from_in_mcp_json_passes_when_in_manifest(self, drift_module, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "uvx", "args": ["--from", "semble[mcp]==0.5.6", "semble"]}}}')
        assert not drift_module.scan_file(mcp)
        assert not drift_module.cross_reference_mcp(mcp)

    def test_uvx_pinned_but_unmonitored_fails(self, drift_module, tmp_path: Path) -> None:
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "uvx", "args": ["--from", "not-monitored==1.2.3", "x"]}}}')
        findings = drift_module.cross_reference_mcp(mcp)
        assert any("not in manifest" in f.message.lower() or "unmonitored" in f.message.lower() for f in findings)

    def test_uvx_version_disagreeing_with_manifest_fails(self, drift_module, tmp_path: Path) -> None:
        """The whole point of the pin: config and manifest must name the SAME release."""
        mcp = tmp_path / ".mcp.json"
        mcp.write_text('{"mcpServers": {"x": {"command": "uvx", "args": ["--from", "semble[mcp]==0.4.0", "semble"]}}}')
        findings = drift_module.cross_reference_mcp(mcp)
        assert any("0.5.6" in f.message for f in findings), [f.message for f in findings]

    def test_npx_with_http_url_does_not_trigger(self, drift_module, tmp_path: Path) -> None:
        """HTTP URLs in args (e.g. typefully MCP endpoint) shouldn't trigger drift."""
        mcp = tmp_path / ".mcp.json"
        mcp.write_text(
            '{"mcpServers": {"x": {"command": "npx", "args": ["-y", "mcp-remote@0.1.38", '
            '"https://mcp.typefully.com/mcp?KEY=abc"]}}}'
        )
        findings = drift_module.scan_file(mcp)
        assert not findings

    def test_noqa_with_justification_skips(self, drift_module, tmp_path: Path) -> None:
        py = tmp_path / "dependencies.py"
        py.write_text(
            "# Some legacy curl that survives this scan only because:\n"
            'cmd = "curl https://x/master/install.sh | bash"  # noqa: drift-check  # legacy fallback documented in PRD\n'
        )
        findings = drift_module.scan_file(py)
        assert not findings

    def test_noqa_without_justification_rejected(self, drift_module, tmp_path: Path) -> None:
        py = tmp_path / "dependencies.py"
        py.write_text('cmd = "curl https://x/master/install.sh | bash"  # noqa: drift-check\n')
        findings = drift_module.scan_file(py)
        # Bare noqa is treated as a finding (justification required).
        assert findings

    def test_npm_install_pkg_at_latest_unpinned(self, drift_module) -> None:
        # `pkg@latest` MUST NOT pass as pinned even though it has an `@`.
        assert drift_module._is_npm_install_pkg_pinned("pkg@latest") is False

    def test_npm_install_pkg_at_beta_unpinned(self, drift_module) -> None:
        assert drift_module._is_npm_install_pkg_pinned("pkg@beta") is False
        assert drift_module._is_npm_install_pkg_pinned("pkg@next") is False

    def test_npm_install_pkg_with_range_unpinned(self, drift_module) -> None:
        for spec in ("pkg@^1.2.3", "pkg@~1.2.3", "pkg@>=1.0.0"):
            assert drift_module._is_npm_install_pkg_pinned(spec) is False, spec

    def test_npm_install_pkg_exact_pinned(self, drift_module) -> None:
        assert drift_module._is_npm_install_pkg_pinned("pkg@1.2.3") is True
        assert drift_module._is_npm_install_pkg_pinned("@scope/pkg@1.2.3") is True
        assert drift_module._is_npm_install_pkg_pinned("pkg@1.2.3-rc.1") is True

    def test_bare_scope_unpinned(self, drift_module) -> None:
        assert drift_module._is_npm_install_pkg_pinned("@scope/pkg") is False

    def test_invalid_utf8_emits_finding_not_crash(self, drift_module, tmp_path: Path) -> None:
        # Regression: a non-UTF-8 file used to abort the entire run with
        # UnicodeDecodeError; now it's a deterministic Finding so the gate
        # stays robust.
        bad = tmp_path / "broken.py"
        bad.write_bytes(b"# valid header\nx = '\xd1\xff bad utf-8'\n")
        findings = drift_module.scan_file(bad)
        assert len(findings) == 1
        assert "utf-8" in findings[0].message.lower()

    def test_bare_noqa_with_forbidden_pattern_yields_one_finding(self, drift_module, tmp_path: Path) -> None:
        """Bare-noqa lines must NOT also report the matched forbidden pattern.

        Regression guard for changes-review must_fix #2 (false-positive double-report
        when bare-noqa scan was reported to fall through to pattern matching).
        Confirms `_scan_python_or_shell` short-circuits via `continue` after the
        bare-noqa finding.
        """
        py = tmp_path / "dependencies.py"
        py.write_text('cmd = "curl https://x/master/install.sh | bash"  # noqa: drift-check\n')
        findings = drift_module.scan_file(py)
        assert len(findings) == 1
        assert "bare" in findings[0].message.lower()


class TestUvBootstrapCrossRef:
    """install.sh's uv bootstrap URL must match the manifest's uv-installer entry.

    Hard-pinned entry: the sha256 literal must match too. Soft-pinned entry
    (vendor-managed floating endpoint): a hard sha literal is forbidden.
    """

    @pytest.fixture
    def manifest_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "upstreams.yaml"
        p.write_text(
            "version: 1\n"
            "entries:\n"
            "  - id: uv-installer\n"
            "    name: astral.sh/uv/install.sh (1.2.3)\n"
            "    source_type: curl\n"
            "    source_url: https://astral.sh/uv/1.2.3/install.sh\n"
            '    version: "1.2.3"\n'
            f'    sha256: "{"a" * 64}"\n'
            '    last_audited: "2026-06-09"\n'
        )
        return p

    @pytest.fixture
    def soft_pin_manifest_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "upstreams.yaml"
        p.write_text(
            "version: 1\n"
            "entries:\n"
            "  - id: uv-installer\n"
            "    name: astral.sh/uv/install.sh\n"
            "    source_type: curl\n"
            "    source_url: https://astral.sh/uv/install.sh\n"
            '    version: "live-2026-06-12"\n'
            f'    sha256: "{"a" * 64}"\n'
            "    soft_pin: true\n"
            '    soft_pin_reason: "vendor-managed endpoint; tracks latest uv"\n'
            '    last_audited: "2026-06-12"\n'
        )
        return p

    @staticmethod
    def _write_install_sh(tmp_path: Path, url: str, sha: str | None = None) -> Path:
        sh = tmp_path / "install.sh"
        body = f'#!/bin/sh\ninstall_uv() {{\n\tlocal UV_INSTALL_URL="{url}"\n'
        if sha is not None:
            body += f'\tlocal UV_INSTALL_SHA256="{sha}"\n'
        body += "}\n"
        sh.write_text(body)
        return sh

    def test_drifted_url_and_sha_fail(self, drift_module, tmp_path: Path, manifest_path: Path) -> None:
        """Floating URL + stale hash (the GH install-failure shape) must both be flagged."""
        sh = self._write_install_sh(tmp_path, "https://astral.sh/uv/install.sh", "b" * 64)
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=manifest_path)
        assert any("source_url" in f.message for f in findings)
        assert any("sha256" in f.message for f in findings)

    def test_matching_pin_passes(self, drift_module, tmp_path: Path, manifest_path: Path) -> None:
        sh = self._write_install_sh(tmp_path, "https://astral.sh/uv/1.2.3/install.sh", "a" * 64)
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=manifest_path)
        assert not findings, [f.message for f in findings]

    def test_missing_literals_fail(self, drift_module, tmp_path: Path, manifest_path: Path) -> None:
        """A refactor that renames the literals must not silently disable the check."""
        sh = tmp_path / "install.sh"
        sh.write_text("#!/bin/sh\necho no uv pin here\n")
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=manifest_path)
        assert any("not found" in f.message for f in findings)

    def test_soft_pin_floating_url_without_sha_passes(
        self, drift_module, tmp_path: Path, soft_pin_manifest_path: Path
    ) -> None:
        sh = self._write_install_sh(tmp_path, "https://astral.sh/uv/install.sh")
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=soft_pin_manifest_path)
        assert not findings, [f.message for f in findings]

    def test_soft_pin_with_hard_sha_literal_fails(
        self, drift_module, tmp_path: Path, soft_pin_manifest_path: Path
    ) -> None:
        """Re-introducing a hard sha pin against the floating endpoint is the GH #147 failure shape."""
        sh = self._write_install_sh(tmp_path, "https://astral.sh/uv/install.sh", "b" * 64)
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=soft_pin_manifest_path)
        assert any("soft-pinned" in f.message for f in findings)

    def test_soft_pin_url_mismatch_fails(self, drift_module, tmp_path: Path, soft_pin_manifest_path: Path) -> None:
        """Re-pinning install.sh to a versioned URL while the manifest stays floating must be flagged."""
        sh = self._write_install_sh(tmp_path, "https://astral.sh/uv/1.2.3/install.sh")
        findings = drift_module.cross_reference_uv_bootstrap(sh, manifest_path=soft_pin_manifest_path)
        assert any("source_url" in f.message for f in findings)


class TestManifestSchemaGate:
    """Drift checker validates the manifest schema before running pattern checks."""

    def test_invalid_manifest_emits_finding(self, drift_module, tmp_path: Path) -> None:
        bad_manifest = tmp_path / "upstreams.yaml"
        bad_manifest.write_text(
            "version: 1\n"
            "entries:\n"
            "  - id: bad\n"
            "    name: bad\n"
            "    source_type: curl\n"
            "    source_url: https://example.com/x.sh\n"
            "    version: v1\n"
            "    last_audited: 2026-05-07\n"  # missing sha256
        )
        finding = drift_module.validate_manifest(bad_manifest)
        assert finding is not None
        assert "sha256" in finding.message.lower()


class TestWorkflowRuntimeCrossRef:
    """CI runtime pins must follow the installer runtime manifest."""

    @pytest.fixture
    def runtime_manifest(self, tmp_path: Path) -> Path:
        manifest = tmp_path / "upstreams.yaml"
        manifest.write_text(
            "version: 1\n"
            "entries:\n"
            "  - id: node-24-brew\n"
            "    name: Node.js 24\n"
            "    source_type: brew\n"
            "    source_url: https://github.com/nodejs/node\n"
            '    version: "24.20.0"\n'
            "    pin_kind: monitor\n"
            '    brew_formula: "node@24"\n'
            "    brew_tap: homebrew/core\n"
            '    last_audited: "2026-09-09"\n'
            "  - id: bun-brew\n"
            "    name: bun\n"
            "    source_type: brew\n"
            "    source_url: https://github.com/oven-sh/bun\n"
            '    version: "1.4.2"\n'
            "    pin_kind: monitor\n"
            "    brew_formula: bun\n"
            "    brew_tap: oven-sh/bun\n"
            '    last_audited: "2026-09-09"\n'
        )
        return manifest

    def test_stale_node_and_bun_workflow_pins_fail(self, drift_module, tmp_path: Path, runtime_manifest: Path) -> None:
        workflow = tmp_path / "release.yml"
        workflow.write_text('node-version: "22"\nbun-version: "1.3.11"\n')

        findings = drift_module.cross_reference_workflow_runtimes([workflow], manifest_path=runtime_manifest)

        assert any("Node" in finding.message and "24" in finding.message for finding in findings)
        assert any("Bun" in finding.message and "1.4.2" in finding.message for finding in findings)

    def test_matching_workflow_runtime_pins_pass(self, drift_module, tmp_path: Path, runtime_manifest: Path) -> None:
        workflow = tmp_path / "release.yml"
        workflow.write_text('node-version: "24.20.0"\nbun-version: "1.4.2"\n')

        assert not drift_module.cross_reference_workflow_runtimes([workflow], manifest_path=runtime_manifest)


class TestCleanRepository:
    """Running drift check against the current repo state."""

    def test_installer_steps_clean_after_tasks_2_through_5(self, drift_module) -> None:
        """Per Task 6 DoD: installer/steps/ produces zero findings after Tasks 2-5."""
        repo_root = Path(__file__).resolve().parents[3]
        for rel in ("installer/steps/dependencies.py", "installer/steps/prerequisites.py"):
            findings = drift_module.scan_file(repo_root / rel)
            assert not findings, f"{rel} drift: {[f.message for f in findings]}"

    def test_bootstrap_surface_clean(self, drift_module) -> None:
        """Per Task 7: install.sh + launcher/build.py have no unversioned --with."""
        repo_root = Path(__file__).resolve().parents[3]
        for rel in ("install.sh", "launcher/build.py"):
            findings = drift_module.scan_file(repo_root / rel)
            assert not findings, f"{rel} drift: {[f.message for f in findings]}"

    def test_full_scan_surface_clean(self, drift_module) -> None:
        """Iterate every entry in SCAN_FILES and assert zero findings.

        Catches regressions in any file Task 6 declared to scan, not just the
        installer steps and MCP JSONs we tested individually above.
        """
        repo_root = Path(__file__).resolve().parents[3]
        for rel in drift_module.SCAN_FILES:
            path = repo_root / rel
            findings = drift_module.scan_file(path)
            assert not findings, f"{rel} drift: {[f.message for f in findings]}"

    def test_bootstrap_uv_pin_matches_manifest(self, drift_module) -> None:
        """Reproduces the reported install failure: install.sh's uv pin drifted from
        the manifest's uv-installer entry (floating astral.sh URL + stale sha256)."""
        repo_root = Path(__file__).resolve().parents[3]
        findings = drift_module.cross_reference_uv_bootstrap(repo_root / "install.sh")
        assert not findings, f"install.sh uv bootstrap drift: {[f.message for f in findings]}"

    def test_mcp_json_clean(self, drift_module) -> None:
        """Per Task 5: both MCP files have only pinned, manifest-monitored npx packages."""
        repo_root = Path(__file__).resolve().parents[3]
        for rel in (".mcp.json", "pilot/.mcp.json"):
            path = repo_root / rel
            scan = drift_module.scan_file(path)
            xref = drift_module.cross_reference_mcp(path)
            assert not scan, f"{rel} scan: {[f.message for f in scan]}"
            assert not xref, f"{rel} xref: {[f.message for f in xref]}"

    def test_workflow_runtime_pins_match_manifest(self, drift_module) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        workflows = [
            repo_root / ".github/workflows/release.yml",
            repo_root / ".github/workflows/release-dev.yml",
            repo_root / ".github/workflows/deploy-website.yml",
        ]

        findings = drift_module.cross_reference_workflow_runtimes(workflows)
        assert not findings, [finding.message for finding in findings]
