#!/usr/bin/env python3
"""Manifest drift checker — fails CI when installer code references unpinned upstreams.

Forbidden patterns (per source-type):

- `*.py`:        `@latest`, `master/install.sh`, `HEAD/install.sh`,
                 unversioned `npm install -g <pkg>`,
                 hardcoded `\\d+\\.\\d+\\.\\d+` literals not in manifest.
- `install.sh`:  same Python set + unversioned `uv run --with <pkg>`, plus
                 cross-reference: the bootstrap `UV_INSTALL_URL` literal MUST
                 match the manifest's `uv-installer` entry. Hard-pinned entry:
                 `UV_INSTALL_SHA256` must match too. Soft-pinned entry
                 (vendor-managed floating endpoint): a hard sha literal is
                 forbidden - it breaks on every uv release (GH #147).
- `*.mcp.json`:  unversioned `npx <pkg>` args, plus cross-reference: every
                 pinned `npx <pkg>@<version>` MUST resolve to a manifest
                 entry by id (derived from the package name without the
                 `@scope/` prefix). The same holds for `uvx --from
                 <pkg>[extras]==<version>` launches, which additionally MUST
                 name the same version as the manifest entry - the config and
                 the installed tool are pinned precisely so they agree.

Per-line override: `# noqa: drift-check  # <justification>` is honored if
non-empty justification follows on the same line.

Usage:
    python scripts/check_manifest_drift.py            # human output, exit non-zero on findings
    python scripts/check_manifest_drift.py --json     # machine-readable JSON, same exit code
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT_DEFAULT = Path(__file__).resolve().parents[1]

SCAN_FILES: list[str] = [
    "installer/steps/dependencies.py",
    "installer/steps/prerequisites.py",
    "install.sh",
    "launcher/build.py",
    ".mcp.json",
    "pilot/.mcp.json",
]

WORKFLOW_RUNTIME_FILES: list[str] = [
    ".github/workflows/release.yml",
    ".github/workflows/release-dev.yml",
    ".github/workflows/deploy-website.yml",
]

# Patterns that flag any python/shell file:
PY_SH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("@latest tag", re.compile(r"@latest\b")),
    ("master/install.sh", re.compile(r"master/install\.sh|HEAD/install\.sh")),
    (
        "unversioned npm install -g",
        re.compile(r'npm install -g\s+(?:--[a-z-]+\s+)*([a-zA-Z@][^\s"]*)'),
    ),
]

# install.sh / launcher/build.py — uv run --with <pkg> must be ==<version>:
UV_RUN_WITH_PATTERN = re.compile(r"--with\s+([a-zA-Z][\w-]*)(?!\S*==)")

# Strict semver — exactly `\d+.\d+.\d+` with optional pre-release/build, no
# range operators or dist-tags (`@beta`, `@^1.2.3`, `@~1.2`, `@latest`).
_EXACT_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+(?:[-+][\w.+-]+)?$")

# install.sh bootstrap pin for the uv installer (runs before the manifest is
# readable, so the literals live in the script - same class as the PyPI set):
UV_BOOTSTRAP_URL_RE = re.compile(r'^\s*local UV_INSTALL_URL="([^"]+)"')
UV_BOOTSTRAP_SHA_RE = re.compile(r'^\s*local UV_INSTALL_SHA256="([0-9a-f]{64})"')
NODE_WORKFLOW_PIN_RE = re.compile(r'^\s*node-version:\s*["\']?([^"\'\s#]+)')
BUN_WORKFLOW_PIN_RE = re.compile(r'^\s*bun-version:\s*["\']?([^"\'\s#]+)')

NOQA_PATTERN = re.compile(r"#\s*noqa:\s*drift-check\b\s*(?:#\s*(.*))?")

# `uvx --from "<pkg>[extra,extra]==<version>" <entrypoint>` - the launch form
# upstream projects document for PyPI-distributed MCP servers (e.g. semble).
# Extras are part of the requirement, not the package name, so they are
# stripped before the manifest lookup.
UVX_FROM_SPEC_RE = re.compile(r"^(?P<pkg>[A-Za-z0-9._-]+)(?:\[[A-Za-z0-9,._-]+\])?(?:==(?P<version>[\w.+-]+))?$")


def _uvx_from_spec(cfg: dict[str, Any]) -> str | None:
    """Return the `--from` requirement of a uvx-launched server, if any."""
    if cfg.get("command") != "uvx":
        return None
    args = cfg.get("args") or []
    for i, a in enumerate(args):
        if a == "--from" and i + 1 < len(args) and isinstance(args[i + 1], str):
            return args[i + 1]
    return None


@dataclass
class Finding:
    file: Path
    line: int
    message: str


@dataclass
class _LineCtx:
    text: str
    line_no: int
    has_noqa: bool = False
    noqa_justified: bool = False


def _parse_noqa(line: str) -> tuple[bool, bool]:
    """Return (has_noqa, justified). Bare `# noqa: drift-check` (no comment) is unjustified."""
    m = NOQA_PATTERN.search(line)
    if not m:
        return False, False
    justification = (m.group(1) or "").strip()
    return True, bool(justification)


def _iter_lines(path: Path) -> tuple[list[_LineCtx], Finding | None]:
    """Read and parse `path`. Returns lines plus an error-Finding if any.

    A non-UTF-8 file used to abort the entire run (`UnicodeDecodeError`); now
    the read failure is reported as a deterministic Finding so the gate stays
    robust even if a tracked file is mojibake or accidentally binary.
    """
    out: list[_LineCtx] = []
    try:
        # Explicit UTF-8: pathlib.Path.read_text() uses the locale default, which
        # is not always UTF-8 on CI runners (depends on $LANG / $LC_ALL).
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return out, Finding(file=path, line=0, message=f"could not read: {exc}")
    except UnicodeDecodeError as exc:
        return out, Finding(
            file=path,
            line=0,
            message=f"not valid UTF-8: {exc.reason} at byte {exc.start}",
        )
    for i, line in enumerate(text.splitlines(), start=1):
        has_noqa, justified = _parse_noqa(line)
        out.append(_LineCtx(text=line, line_no=i, has_noqa=has_noqa, noqa_justified=justified))
    return out, None


def _add_finding(findings: list[Finding], path: Path, ctx: _LineCtx, msg: str) -> None:
    if ctx.has_noqa and ctx.noqa_justified:
        return
    findings.append(Finding(file=path, line=ctx.line_no, message=msg))


def _is_npm_install_pkg_pinned(pkg_arg: str) -> bool:
    """Pinned == package name + `@` + strict numeric semver.

    `pkg@1.2.3`, `@scope/pkg@1.2.3-rc.1` are pinned. All of `pkg`, `@scope/pkg`,
    `pkg@latest`, `pkg@beta`, `pkg@^1.2.3`, `pkg@~1.2` are unpinned — the policy
    is exact version pinning, so dist-tags and range operators must drop out.
    """
    if pkg_arg in {"-g", "--force", "--ignore-scripts", "--no-audit", "--no-fund"}:
        return True  # flag, not a package
    if pkg_arg.startswith("--"):
        return True
    # Split on the LAST `@` so `@scope/pkg@1.2.3` keeps the scope and only the
    # version trails. Bare `@scope/pkg` (no trailing version) has the only `@`
    # in position 0 → split returns "" before, full string after → unpinned.
    if "@" not in pkg_arg.lstrip("@"):
        return False
    version_part = pkg_arg.rsplit("@", 1)[1]
    return bool(_EXACT_SEMVER_RE.match(version_part))


def _scan_python_or_shell(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    is_shell = path.name.endswith(".sh")
    lines, read_finding = _iter_lines(path)
    if read_finding is not None:
        findings.append(read_finding)
    for ctx in lines:
        # A bare drift-check suppression (no justification) is itself a finding.
        # Spelled without the literal directive token so ruff does not parse this
        # prose as a real noqa and warn about an invalid code list.
        # `continue` keeps the line from also matching downstream patterns —
        # one line, one bare-noqa finding (no double-reporting).
        if ctx.has_noqa and not ctx.noqa_justified:
            findings.append(
                Finding(
                    file=path,
                    line=ctx.line_no,
                    message="bare `# noqa: drift-check` requires a justification comment",
                )
            )
            continue

        for label, pat in PY_SH_PATTERNS:
            for m in pat.finditer(ctx.text):
                if label == "unversioned npm install -g":
                    pkg = m.group(1)
                    if _is_npm_install_pkg_pinned(pkg):
                        continue
                    _add_finding(
                        findings,
                        path,
                        ctx,
                        f"unversioned npm install -g target {pkg!r} (pin to @<version>)",
                    )
                else:
                    _add_finding(findings, path, ctx, f"{label} match: {m.group(0)!r}")

        if is_shell or path.name == "build.py":
            for m in UV_RUN_WITH_PATTERN.finditer(ctx.text):
                _add_finding(
                    findings,
                    path,
                    ctx,
                    f"unversioned `--with {m.group(1)}` (use `--with {m.group(1)}==<version>`)",
                )
    return findings


def _scan_mcp_json(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return [Finding(file=path, line=0, message=f"could not parse JSON: {exc}")]
    servers = doc.get("mcpServers") or {}
    for name, cfg in servers.items():
        spec = _uvx_from_spec(cfg)
        if spec is not None:
            m = UVX_FROM_SPEC_RE.match(spec)
            if m is None or not m.group("version"):
                findings.append(
                    Finding(
                        file=path,
                        line=0,
                        message=f"{name}: unpinned uvx package {spec!r} (use `<pkg>[extras]==<version>`)",
                    )
                )
            continue
        if cfg.get("command") != "npx":
            continue
        args = cfg.get("args") or []
        for a in args:
            if not isinstance(a, str):
                continue
            if a.startswith("-"):
                continue
            if a.startswith("http://") or a.startswith("https://"):
                continue
            # First non-flag, non-URL argument is the package spec.
            if not _is_npm_install_pkg_pinned(a):
                findings.append(
                    Finding(
                        file=path,
                        line=0,
                        message=f"{name}: unpinned npx package {a!r} (use `<pkg>@<version>`)",
                    )
                )
                break
            break
    return findings


def cross_reference_mcp(path: Path) -> list[Finding]:
    """Every pinned `npx <pkg>@<v>` in an MCP file MUST have a manifest entry."""
    from installer.manifest import load

    findings: list[Finding] = []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return findings
    manifest = load()
    monitored_urls = {e.source_url for e in manifest.entries if e.source_type == "npm"}
    by_id = {e.id: e for e in manifest.entries}
    servers = doc.get("mcpServers") or {}
    for name, cfg in servers.items():
        spec = _uvx_from_spec(cfg)
        if spec is not None:
            m = UVX_FROM_SPEC_RE.match(spec)
            if m is None:
                continue
            pkg, version = m.group("pkg"), m.group("version")
            entry = by_id.get(pkg)
            if entry is None:
                findings.append(
                    Finding(
                        file=path,
                        line=0,
                        message=f"{name}: pinned package {pkg!r} is not in manifest (unmonitored)",
                    )
                )
            elif version and version != entry.version:
                findings.append(
                    Finding(
                        file=path,
                        line=0,
                        message=(
                            f"{name}: uvx pin {pkg}=={version} disagrees with manifest entry {pkg!r} at {entry.version}"
                        ),
                    )
                )
            continue
        if cfg.get("command") != "npx":
            continue
        for a in cfg.get("args") or []:
            if not isinstance(a, str):
                continue
            if a.startswith("-") or a.startswith("http"):
                continue
            # Strip the @<version>; keep @scope/ prefix.
            if a.startswith("@"):
                rest = a[1:]
                pkg = "@" + rest.split("@", 1)[0]
            else:
                pkg = a.split("@", 1)[0]
            if pkg and pkg not in monitored_urls:
                findings.append(
                    Finding(
                        file=path,
                        line=0,
                        message=f"{name}: pinned package {pkg!r} is not in manifest (unmonitored)",
                    )
                )
            break
    return findings


def cross_reference_uv_bootstrap(path: Path, manifest_path: Path | None = None) -> list[Finding]:
    """install.sh's uv bootstrap URL MUST match the manifest's uv-installer entry.

    Hard-pinned entry: the UV_INSTALL_SHA256 literal must match the manifest.
    Soft-pinned entry (vendor-managed floating endpoint): a hard sha literal is
    forbidden - it would break on every uv release (GH #147).
    """
    from installer.manifest import load

    lines, read_finding = _iter_lines(path)
    if read_finding is not None:
        return [read_finding]
    entry = next((e for e in load(path=manifest_path).entries if e.id == "uv-installer"), None)
    if entry is None:
        return [Finding(file=path, line=0, message="manifest has no uv-installer entry to cross-reference")]

    findings: list[Finding] = []
    url_match: tuple[_LineCtx, str] | None = None
    sha_match: tuple[_LineCtx, str] | None = None
    for ctx in lines:
        if url_match is None and (m := UV_BOOTSTRAP_URL_RE.match(ctx.text)):
            url_match = (ctx, m.group(1))
        if sha_match is None and (m := UV_BOOTSTRAP_SHA_RE.match(ctx.text)):
            sha_match = (ctx, m.group(1))
    if url_match is None:
        return [
            Finding(
                file=path,
                line=0,
                message="UV_INSTALL_URL literal not found (uv bootstrap check would be disabled)",
            )
        ]
    ctx, url = url_match
    if url != entry.source_url:
        _add_finding(
            findings, path, ctx, f"uv bootstrap URL {url!r} != manifest uv-installer source_url {entry.source_url!r}"
        )
    if entry.soft_pin:
        if sha_match is not None:
            ctx, sha = sha_match
            _add_finding(
                findings,
                path,
                ctx,
                "hard UV_INSTALL_SHA256 pin against soft-pinned vendor-managed endpoint "
                "(drifts on every uv release - GH #147); remove the sha literal",
            )
    elif sha_match is None:
        findings.append(
            Finding(
                file=path,
                line=0,
                message="UV_INSTALL_SHA256 literal not found (uv bootstrap pin check would be disabled)",
            )
        )
    else:
        ctx, sha = sha_match
        if sha != entry.sha256:
            _add_finding(
                findings, path, ctx, f"uv bootstrap sha256 {sha!r} != manifest uv-installer sha256 {entry.sha256!r}"
            )
    return findings


def cross_reference_workflow_runtimes(paths: list[Path], manifest_path: Path | None = None) -> list[Finding]:
    """Require CI's Node/Bun setup pins to match Pilot's runtime manifest."""
    from installer.manifest import load

    manifest = load(path=manifest_path)
    node_entry = next(
        (entry for entry in manifest.entries if entry.brew_formula and entry.brew_formula.startswith("node@")),
        None,
    )
    bun_entry = next((entry for entry in manifest.entries if entry.id == "bun-brew"), None)
    if node_entry is None or bun_entry is None:
        return [
            Finding(
                file=manifest_path or REPO_ROOT_DEFAULT / "installer/upstreams.yaml",
                line=0,
                message="manifest must define node@<major> and bun-brew runtime entries",
            )
        ]

    expected_node = node_entry.version
    expected_bun = bun_entry.version
    findings: list[Finding] = []
    node_pins = 0
    bun_pins = 0
    for path in paths:
        lines, read_finding = _iter_lines(path)
        if read_finding is not None:
            findings.append(read_finding)
            continue
        for ctx in lines:
            if match := NODE_WORKFLOW_PIN_RE.match(ctx.text):
                node_pins += 1
                if match.group(1) != expected_node:
                    findings.append(
                        Finding(
                            file=path,
                            line=ctx.line_no,
                            message=(f"Node workflow pin {match.group(1)!r} != manifest version {expected_node!r}"),
                        )
                    )
            if match := BUN_WORKFLOW_PIN_RE.match(ctx.text):
                bun_pins += 1
                if match.group(1) != expected_bun:
                    findings.append(
                        Finding(
                            file=path,
                            line=ctx.line_no,
                            message=f"Bun workflow pin {match.group(1)!r} != manifest version {expected_bun!r}",
                        )
                    )
    if node_pins == 0:
        findings.append(Finding(file=paths[0], line=0, message="no Node workflow pins found"))
    if bun_pins == 0:
        findings.append(Finding(file=paths[0], line=0, message="no Bun workflow pins found"))
    return findings


def scan_file(path: Path) -> list[Finding]:
    """Run the appropriate pattern set for `path`. Returns all findings."""
    if not path.exists():
        return []
    if path.suffix == ".json":
        return _scan_mcp_json(path)
    return _scan_python_or_shell(path)


def validate_manifest(manifest_path: Path) -> Finding | None:
    """Validate the manifest schema. Returns a single Finding on failure."""
    from installer.manifest import ManifestError, load

    try:
        load(path=manifest_path)
    except ManifestError as exc:
        return Finding(file=manifest_path, line=0, message=f"manifest schema: {exc}")
    return None


def main(repo_root: Path = REPO_ROOT_DEFAULT, json_mode: bool = False) -> int:
    repo_root = repo_root.resolve()
    findings: list[Finding] = []

    manifest_finding = validate_manifest(repo_root / "installer" / "upstreams.yaml")
    if manifest_finding:
        findings.append(manifest_finding)

    for rel in SCAN_FILES:
        path = repo_root / rel
        findings.extend(scan_file(path))
        if path.suffix == ".json":
            findings.extend(cross_reference_mcp(path))
        if path.name == "install.sh" and path.exists():
            findings.extend(cross_reference_uv_bootstrap(path))
    findings.extend(cross_reference_workflow_runtimes([repo_root / rel for rel in WORKFLOW_RUNTIME_FILES]))

    if json_mode:
        print(
            json.dumps(
                [{"file": str(f.file.relative_to(repo_root)), "line": f.line, "message": f.message} for f in findings],
                indent=2,
            )
        )
    else:
        for f in findings:
            try:
                rel = f.file.relative_to(repo_root)
            except ValueError:
                rel = f.file
            print(f"{rel}:{f.line}: {f.message}")
        if not findings:
            print("OK: no manifest drift detected.")

    return 1 if findings else 0


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Pilot Shell manifest drift checker")
    parser.add_argument("--json", action="store_true", help="output JSON")
    parser.add_argument("--repo-root", default=str(REPO_ROOT_DEFAULT))
    args = parser.parse_args()
    return main(repo_root=Path(args.repo_root), json_mode=args.json)


# Re-export Finding so tests can introspect findings collections.
__all__ = [
    "Finding",
    "scan_file",
    "cross_reference_mcp",
    "cross_reference_uv_bootstrap",
    "cross_reference_workflow_runtimes",
    "validate_manifest",
    "main",
]


if __name__ == "__main__":
    sys.exit(_cli())
