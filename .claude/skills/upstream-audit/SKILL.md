---
name: upstream-audit
description: |
  Audit and update Pilot Shell upstream dependencies in installer/upstreams.yaml.
  Checks npm, PyPI, brew, and curl-pipe entries for newer stable versions,
  known security advisories, and sha256 drift. Verifies each update installs
  successfully before committing. Use when: "check upstreams", "update dependencies",
  "audit upstreams.yaml", "are our dependencies up to date", "supply chain check".
---

# Upstream Audit

Checks every entry in `installer/upstreams.yaml` for newer stable versions, security
advisories, and hash drift. Updates the manifest and verifies each change installs
correctly.

## Important

- **Never update to pre-release, alpha, beta, rc, or canary versions.** Only stable releases.
- **Never update a curl entry's sha256 without downloading and verifying the script content first.**
- **Every version bump must be install-tested before writing to upstreams.yaml.**
- **Preserve all existing fields** (comments, `last_audited`, `soft_pin`, `scripts_policy`, etc.) — only change `version`, `sha256`, and `last_audited`.

## Instructions

### Step 1: Load the Manifest

```bash
cat installer/upstreams.yaml
```

Parse the entries. Group them by `source_type`: `npm`, `brew`, `curl`, `pypi`.

### Step 2: Check for Newer Versions

For each entry, check the latest stable version using the appropriate method:

**npm packages** (`source_type: npm`):
```bash
npm view <source_url> version 2>/dev/null
# Example: npm view @colbymchenry/codegraph version
```

**PyPI packages** (`source_type: pypi`):
```bash
pip index versions <name> 2>/dev/null | head -1
# Or: curl -s https://pypi.org/pypi/<name>/json | python3 -c "import sys,json; print(json.load(sys.stdin)['info']['version'])"
```

**Homebrew formulas** (`source_type: brew`):
```bash
brew info --json=v2 <brew_formula> 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['formulae'][0]['versions']['stable'])"
```

**curl-pipe installers** (`source_type: curl`):

Commit-pinned entries (have `commit` field — extract repo URL from `source_url`):
```bash
# Extract repo URL from source_url (everything before /raw/ or before the commit hash path)
# Example: https://raw.githubusercontent.com/rtk-ai/rtk/COMMIT/install.sh → https://github.com/rtk-ai/rtk.git
git ls-remote <repo_url> HEAD | cut -c1-40
```
If HEAD differs from the current `commit`, download the new script, hash it, and update `source_url` (embed new commit), `version` (`commit-<short>`), `commit`, `sha256`.

Tag-pinned entries (version starts with `v`, e.g., nvm):
```bash
git ls-remote --tags <repo_url> | grep -oP 'v\d+\.\d+\.\d+$' | sort -V | tail -1
```
If newer tag exists, update `source_url` (embed new tag), `version`, `sha256`, and `name` if it includes the version.

Soft-pinned entries (`soft_pin: true` — vendor-managed live endpoints):
```bash
curl -fsSL "<source_url>" -o /tmp/upstream-audit-script.sh
shasum -a 256 /tmp/upstream-audit-script.sh
rm -f /tmp/upstream-audit-script.sh
```
Compare sha256 to manifest. If different → sha256 drifted, update `sha256` and `version` label (e.g., `live-YYYY-MM-DD` or `vendor-managed-YYYY-MM-DD`). If same → no drift, just update `last_audited`.

For every proposed update, also inspect its published runtime requirements and
release notes. A package being installable is insufficient when its executable
requires a newer Node, Python, Go, libc, or OS baseline than Pilot provisions.
Trace that requirement to Pilot's prerequisite/bootstrap entry and include any
required runtime migration in the same audit. Treat major-version changes and
new migration/status flags as capability changes that need an explicit test.

**Update ALL entries' `last_audited` to today's date** — even entries where the version didn't change. The audit date records when we last verified the version is current, not when it was last bumped.

### Step 3: Check Security Advisories

For each entry with a newer version available:

**npm packages:**
```bash
npm audit --json --package <source_url>@<current_version> 2>/dev/null || true
```

Also check: `WebSearch` for `"<package_name> CVE"` or `"<package_name> security vulnerability"`.

**PyPI packages:**
```bash
pip audit --requirement=<(echo "<name>==<version>") 2>/dev/null || true
```

Or search: `WebSearch` for `"<package_name> CVE"` or `"<package_name> security advisory"`.

**Homebrew formulas:** Check the formula's source repo for security advisories.

Report any findings. If the CURRENT version has known vulnerabilities, flag as urgent.

### Step 4: Install-Test Each Update

**This step is mandatory. Do not skip it.**

An install test proves package resolution only. After it passes, exercise the
installed artifact through Pilot's real integration path:

- CLI tools: run `--version` plus the primary command Pilot depends on.
- MCP servers: perform an MCP initialize handshake and list or invoke the tool
  surface Pilot uses; a process that merely stays alive is not enough.
- Browser tools: launch a real page and perform one representative action such
  as a screenshot.
- Language servers/compilers: complete a handshake or compile/typecheck a small
  project using Pilot's actual runtime and configuration.
- Migration-aware tools: inspect their status/capability output and exercise
  the migration path against an existing artifact, not only a fresh install.

Use isolated temporary prefixes/profiles. Read versions back from the exact
binary or generated artifact Pilot will launch, so a globally shadowing older
binary cannot create a false pass.

For each version bump, verify the new version actually installs and works:

**npm packages:**
```bash
# Test install in a temp prefix (doesn't affect global)
npm install --prefix /tmp/upstream-audit-test <source_url>@<new_version> --ignore-scripts 2>&1
echo "exit: $?"
rm -rf /tmp/upstream-audit-test
```

For packages with `scripts_policy: allow` (like better-sqlite3):
```bash
npm install --prefix /tmp/upstream-audit-test <source_url>@<new_version> 2>&1
echo "exit: $?"
rm -rf /tmp/upstream-audit-test
```

**curl-pipe installers:**
```bash
# Download and verify sha256 — do NOT execute
curl -fsSL "<source_url>" -o /tmp/upstream-audit-script.sh
shasum -a 256 /tmp/upstream-audit-script.sh
rm -f /tmp/upstream-audit-script.sh
```

For commit-pinned curl entries, construct the new URL with the latest commit hash and download.

**PyPI packages:**
```bash
uv pip install --dry-run <name>==<new_version> 2>&1
echo "exit: $?"
```

**Homebrew formulas:** No install-test needed — brew formulas are tested by the Homebrew CI.

If any install-test fails, **do not update that entry**. Report the failure and move on.

### Step 5: Update the Manifest AND Cross-File Pins

For each successfully verified update, edit `installer/upstreams.yaml`:

1. Update the `version` field to the new version
2. Update `sha256` if applicable (curl entries — use the hash from Step 4)
3. Update `last_audited` to today's date (YYYY-MM-DD format)
4. For commit-pinned curl entries: update both `commit` and `version` (`commit-<short_hash>`)
5. For soft_pin curl entries: only update `sha256` and `last_audited` if the script changed

**Cross-file version pins that MUST stay in sync with the manifest:**

These files contain hardcoded version strings that duplicate the manifest. After updating
`upstreams.yaml`, grep for the old version and update every occurrence:

| File | What it pins |
|------|-------------|
| `pilot/.mcp.json` | npx-launched MCP servers: `context7-mcp@X`, `open-websearch@X`, `fetcher-mcp@X` |
| `install.sh` | PyPI bootstrap: `rich==X`, `certifi==X`, `PyYAML==X` |
| `launcher/build.py` | PyPI bootstrap: `cryptography==X` |
| `.github/workflows/supply-chain.yml` | CI PyPI pin: `PyYAML==X` |

For curl entries with version-pinned URLs (e.g., `nvm-curl`), also update `source_url`
to embed the new version in the URL path.

**Verification command** — find any remaining stale pins after updating:
```bash
# Extract all versions from the manifest, then grep for old versions
grep -rn "rich==\|certifi==\|cryptography==\|PyYAML==\|context7-mcp@\|open-websearch@\|fetcher-mcp@" \
  install.sh launcher/build.py pilot/.mcp.json .github/workflows/ installer/upstreams.yaml \
  --include="*.sh" --include="*.py" --include="*.json" --include="*.yaml" --include="*.yml"
```

The table above is a minimum allowlist, not the complete duplicate-pin search.
Search the repository for every old version, package spec, formula name, and
immutable commit that changed. Classify each hit as a runtime consumer, test
fixture, documentation example, historical record, or unrelated value; update
all live consumers. Also verify generated/client-specific copies from their
installed artifacts after regeneration.

For major updates, document any config, cache, index, lockfile, or persisted
state migration. Test both an existing installation and a fresh installation,
and preserve user-owned configuration while migrating Pilot-owned state.

**Do not change:**
- `scripts_policy`, `scripts_justification`
- `soft_pin`, `soft_pin_reason`
- `pin_kind`, `auto_upgrade`
- `brew_tap`
- Comments in the YAML

### Step 6: Validate the Manifest

```bash
uv run python -c "from installer.manifest import load; m = load(); print(f'Manifest valid: {len(m.entries)} entries')"
```

If validation fails, fix the YAML and retry.

### Step 7: Run Installer Tests

```bash
uv run pytest installer/tests/unit/ -q
```

All tests must pass. If a test fails due to a version change, investigate and fix.

Then run the focused capability smokes identified in Step 4 and the repository
gates for every runtime consumer changed by the audit. Do not mark an entry
verified from a package-manager exit code alone.

### Step 8: Report

Present a summary table:

| Entry | Type | Current | Latest | Status | Notes |
|-------|------|---------|--------|--------|-------|
| codegraph | npm | 0.7.3 | 0.9.4 | Updated | Install verified |
| better-sqlite3 | npm | 12.9.0 | 12.9.0 | Current | — |
| vtsls | npm | 0.3.0 | 0.3.1 | Updated | Install verified |
| ... | ... | ... | ... | ... | ... |

Flag any:
- **Security advisories** found (urgent or informational)
- **Install failures** (version skipped, reason noted)
- **sha256 drift** on soft-pinned curl entries (re-pin reminder)
- **Major version bumps** that may have breaking changes (flag for manual review)

## When NOT to Use

- For adding NEW upstream entries (that's a code change, not an audit)
- For changing `source_url` or `source_type` (structural change, needs manual review)
- For removing entries (deprecation decision, not an audit)
