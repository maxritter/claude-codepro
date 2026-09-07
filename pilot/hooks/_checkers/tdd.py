"""TDD enforcer - reminds to use TDD when modifying implementation code.

Provides reusable TDD check functions used by file_checker.py hook.
"""

from __future__ import annotations

import functools
import json
import re
import sys
from pathlib import Path

from _lib.util import post_tool_use_context

EXCLUDED_EXTENSIONS = [
    ".md",
    ".rst",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".lock",
    ".sum",
    ".env",
    ".env.example",
    ".sql",
    ".dll",
    ".exe",
    ".pdb",
    ".csproj",
    ".sln",
    ".props",
    ".targets",
]

EXCLUDED_DIRS = [
    "/cdk/",
    "/infra/",
    "/infrastructure/",
    "/terraform/",
    "/pulumi/",
    "/stacks/",
    "/cloudformation/",
    "/aws/",
    "/deploy/",
    "/migrations/",
    "/alembic/",
    "/generated/",
    "/proto/",
    "/__generated__/",
    "/dist/",
    "/build/",
    "/node_modules/",
    "/.venv/",
    "/venv/",
    "/__pycache__/",
]

# .NET build output — skipped only for .NET source, since other ecosystems
# legitimately keep hand-written source under bin/ (entry-point scripts, etc.).
DOTNET_BUILD_DIRS = ["/bin/", "/obj/"]


def should_skip(file_path: str) -> bool:
    """Check if file should be skipped based on extension or directory."""
    path = Path(file_path)

    if path.suffix in EXCLUDED_EXTENSIONS:
        return True

    if path.name in EXCLUDED_EXTENSIONS:
        return True

    for excluded_dir in EXCLUDED_DIRS:
        if excluded_dir in file_path:
            return True

    if path.suffix in (".cs", ".razor") and any(d in file_path for d in DOTNET_BUILD_DIRS):
        return True

    return False


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path = Path(file_path)
    name = path.name

    if name.endswith(".py"):
        stem = path.stem
        if stem.startswith("test_") or stem.endswith("_test"):
            return True

    if name.endswith((".test.ts", ".spec.ts", ".test.tsx", ".spec.tsx")):
        return True

    if name.endswith("_test.go"):
        return True

    if name.endswith(".cs"):
        stem = path.stem
        if stem.endswith("Tests") or stem.endswith("Test"):
            return True

    return False


def has_related_failing_test(project_dir: str, impl_file: str) -> bool:
    """Check if there's a failing test specifically for this module.

    Looks for test files matching the implementation file name in the
    pytest lastfailed cache. Only returns True if there's a failing test
    that appears to be for the module being edited.
    """
    cache_file = Path(project_dir) / ".pytest_cache" / "v" / "cache" / "lastfailed"

    if not cache_file.exists():
        return False

    impl_path = Path(impl_file)
    module_name = impl_path.stem

    try:
        with cache_file.open() as f:
            lastfailed = json.load(f)

        if not lastfailed:
            return False

        for test_path in lastfailed:
            test_file = test_path.split("::")[0]
            test_name = Path(test_file).stem

            if test_name == f"test_{module_name}" or test_name == f"{module_name}_test":
                return True

        return False
    except (json.JSONDecodeError, OSError):
        return False


def _find_test_dirs(start: Path) -> list[Path]:
    """Walk up from start to find common test directories."""
    dirs: list[Path] = []
    current = start
    for _ in range(15):
        for name in ("tests", "test", "__tests__"):
            candidate = current / name
            if candidate.is_dir():
                dirs.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    return dirs


def is_dotnet_test_project_name(name: str) -> bool:
    """True if a directory name follows a .NET test-project convention.

    Matches the dotted convention (``MyApp.Tests``) or a PascalCase boundary
    (``IntegrationTests``, ``FooTest``). Requiring the dot or a capital 'T'
    avoids matching words that merely end in "test" (latest, contest, greatest).
    Shared by the format checker's skip and test-dir discovery so the two agree.
    """
    return name.lower().endswith((".tests", ".test")) or name.endswith(("Tests", "Test"))


def is_inside_dotnet_test_project(file_path: "str | Path") -> bool:
    """True if *file_path* is nested inside an actual .NET test-project directory.

    Combines the name heuristic with a ``.csproj`` presence check to avoid
    suppressing enforcement for production directories that coincidentally end
    with 'Test' in PascalCase (e.g. ``ContextTest``, ``LoadTest``).  Every
    modern .NET project directory contains its own ``*.csproj``; a production
    folder with a test-sounding name typically does not.
    """
    p = Path(file_path)
    for i in range(1, len(p.parts)):
        candidate = Path(*p.parts[:i])
        if is_dotnet_test_project_name(candidate.name) and any(candidate.glob("*.csproj")):
            return True
    return False


@functools.lru_cache(maxsize=128)
def _find_dotnet_test_dirs(start: Path) -> list[Path]:
    """Walk up from start to find common .NET test directories/projects.

    Memoized: both callers per edit (``has_dotnet_test_file`` and
    ``has_test_importing_module_dotnet``) pass the same start dir, so the second
    lookup is a cache hit instead of a second full iterdir walk. The hook runs as
    a short-lived process, so the cache only dedupes within a single run (no
    cross-edit staleness). Callers must not mutate the returned list.
    """
    dirs: list[Path] = []
    current = start
    seen: set[Path] = set()

    for _ in range(15):
        for name in ("tests", "test", "Tests"):
            candidate = current / name
            if candidate.is_dir() and candidate not in seen:
                dirs.append(candidate)
                seen.add(candidate)

        try:
            for child in current.iterdir():
                if not child.is_dir() or child in seen:
                    continue
                if is_dotnet_test_project_name(child.name):
                    dirs.append(child)
                    seen.add(child)
        except OSError:
            pass

        if current.parent == current:
            break
        current = current.parent

    return dirs


def _search_test_dirs(test_dirs: list[Path], base_name: str, extensions: list[str]) -> bool:
    """Search test directories for files matching base_name with any of the given extensions."""
    patterns = [f"**/{base_name}{ext}" for ext in extensions]
    for test_dir in test_dirs:
        for pattern in patterns:
            if list(test_dir.glob(pattern)):
                return True
    return False


def _search_test_dirs_prefix(test_dirs: list[Path], prefix: str, extensions: list[str]) -> bool:
    """Search test directories for files whose name starts with prefix (e.g. 'vault' matches 'vault-view.test.ts')."""
    for test_dir in test_dirs:
        for ext in extensions:
            if list(test_dir.glob(f"**/{prefix}{ext}")) or list(test_dir.glob(f"**/{prefix}-*{ext}")):
                return True
    return False


def has_python_test_file(impl_path: str) -> bool:
    """Check if corresponding Python test file exists (sibling or in test dirs)."""
    path = Path(impl_path)
    module_name = path.stem

    sibling_names = [f"test_{module_name}.py", f"{module_name}_test.py"]
    for name in sibling_names:
        if (path.parent / name).exists():
            return True

    test_dirs = _find_test_dirs(path.parent)
    return _search_test_dirs(test_dirs, "", [f"test_{module_name}.py", f"{module_name}_test.py"])


def _pascal_to_kebab(name: str) -> str:
    """Convert PascalCase/camelCase to kebab-case."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    s = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1-\2", s)
    return s.lower()


def has_typescript_test_file(impl_path: str) -> bool:
    """Check if corresponding TypeScript test file exists (sibling or in test dirs)."""
    path = Path(impl_path)

    if path.name.endswith(".tsx"):
        base_name = path.name[:-4]
        extensions = [".test.tsx", ".spec.tsx", ".test.ts", ".spec.ts"]
    elif path.name.endswith(".ts"):
        base_name = path.name[:-3]
        extensions = [".test.ts", ".spec.ts"]
    else:
        return False

    kebab_name = _pascal_to_kebab(base_name)
    names = [base_name] if kebab_name == base_name else [base_name, kebab_name]

    for name in names:
        for ext in extensions:
            if (path.parent / f"{name}{ext}").exists():
                return True

    test_dirs = _find_test_dirs(path.parent)
    for name in names:
        if _search_test_dirs(test_dirs, name, extensions):
            return True

    parent_kebab = _pascal_to_kebab(path.parent.name)
    if parent_kebab and parent_kebab not in (n.lower() for n in names):
        if _search_test_dirs_prefix(test_dirs, parent_kebab, extensions):
            return True

    return False


def has_test_importing_module(impl_path: str) -> bool:
    """Return True if any test file under nearby test dirs imports the module's name.

    Broader than has_*_test_file: catches functional/integration tests that already
    import the module without sitting next to it under a sibling-named file. Honours
    the parsimony rule (pilot/rules/testing.md § Test Parsimony) — an existing
    behavioural test surface counts; we don't insist on test_<module>.py.
    """
    path = Path(impl_path)
    module_name = path.stem
    if not module_name or module_name == "__init__":
        return False

    test_dirs = _find_test_dirs(path.parent)
    if not test_dirs:
        return False

    py_from = re.compile(rf"^\s*from\s+\S*\b{re.escape(module_name)}\b\s+import\b", re.MULTILINE)
    py_from_package_import = re.compile(
        rf"^\s*from\s+\S+\s+import\s+(?:\([^)]*\b{re.escape(module_name)}\b|[^\n#]*\b{re.escape(module_name)}\b)",
        re.MULTILINE,
    )
    py_import = re.compile(rf"^\s*import\s+\S*\b{re.escape(module_name)}\b", re.MULTILINE)

    for test_dir in test_dirs:
        for pattern_glob in ("**/test_*.py", "**/*_test.py"):
            for test_file in test_dir.glob(pattern_glob):
                try:
                    src = test_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if py_from.search(src) or py_from_package_import.search(src) or py_import.search(src):
                    return True
    return False


def has_test_importing_module_ts(impl_path: str) -> bool:
    """TypeScript variant of has_test_importing_module.

    Looks for `from "..*<base_name>..*"` or `import "..*<base_name>..*"` patterns
    in any .test.ts(x) / .spec.ts(x) file under nearby test dirs.
    """
    path = Path(impl_path)
    if path.name.endswith(".tsx"):
        base_name = path.name[:-4]
    elif path.name.endswith(".ts"):
        base_name = path.name[:-3]
    else:
        return False
    if not base_name:
        return False

    test_dirs = _find_test_dirs(path.parent)
    if not test_dirs:
        return False

    kebab = _pascal_to_kebab(base_name)
    names = [base_name] if kebab == base_name else [base_name, kebab]
    patterns = [re.compile(rf"""(?:from|import)\s+['"][^'"]*\b{re.escape(n)}\b[^'"]*['"]""") for n in names]

    for test_dir in test_dirs:
        for ext_glob in ("**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/*.spec.tsx"):
            for test_file in test_dir.glob(ext_glob):
                try:
                    src = test_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if any(p.search(src) for p in patterns):
                    return True
    return False


def has_go_test_file(impl_path: str) -> bool:
    """Check if corresponding Go test file exists (sibling or in test dirs)."""
    path = Path(impl_path)

    if not path.name.endswith(".go"):
        return False

    base_name = path.stem

    if (path.parent / f"{base_name}_test.go").exists():
        return True

    test_dirs = _find_test_dirs(path.parent)
    return _search_test_dirs(test_dirs, base_name, ["_test.go"])


def has_dotnet_test_file(impl_path: str) -> bool:
    """Check if corresponding .NET test file exists (sibling or in test dirs)."""
    path = Path(impl_path)

    if not path.name.endswith((".cs", ".razor")):
        return False

    base_name = path.stem
    if not base_name:
        return False

    sibling_names = [f"{base_name}Tests.cs", f"{base_name}Test.cs"]
    for name in sibling_names:
        if (path.parent / name).exists():
            return True

    test_dirs = _find_dotnet_test_dirs(path.parent)
    return _search_test_dirs(test_dirs, "", sibling_names)


def has_test_importing_module_dotnet(impl_path: str) -> bool:
    """Return True if any nearby .NET test references the edited module/component."""
    path = Path(impl_path)
    if not path.name.endswith((".cs", ".razor")):
        return False

    module_name = path.stem
    if not module_name:
        return False

    test_dirs = _find_dotnet_test_dirs(path.parent)
    if not test_dirs:
        return False

    symbol_re = re.compile(rf"\b{re.escape(module_name)}\b")
    test_attr_re = re.compile(r"\[(Fact|Theory|Test|TestMethod|TestCase|TestCaseSource)\b")

    for test_dir in test_dirs:
        for test_file in test_dir.glob("**/*.cs"):
            try:
                src = test_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if not test_attr_re.search(src):
                continue
            # Strip comments/strings so a mention of the symbol in a `// TODO`
            # comment or a string literal does not count as a real reference.
            if symbol_re.search(_strip_cs_comments_and_strings(src)):
                return True

    return False


def _strip_cs_comments_and_strings(src: str) -> str:
    """Remove C# comments and string/char literals.

    Braces, '=>', and keywords inside comments or string/char literals must not
    drive logic detection. Verbatim (@"..."), interpolated ($"..."), and regular
    strings are all reduced to empty content.
    """
    out: list[str] = []
    i, n = 0, len(src)
    while i < n:
        c = src[i]
        # Line comment // ... (also covers /// XML doc)
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            if j == -1:
                break
            i = j
            continue
        # Block comment /* ... */
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # Verbatim string @"..." or verbatim-interpolated @$"..." with doubled "" escapes.
        # ($@"..." is handled by the regular-string branch below after the leading $.)
        if c == "@" and i + 1 < n and (src[i + 1] == '"' or (src[i + 1] == "$" and i + 2 < n and src[i + 2] == '"')):
            i += 2 if src[i + 1] == '"' else 3
            while i < n:
                if src[i] == '"':
                    if i + 1 < n and src[i + 1] == '"':
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        # Regular / interpolated string "..." (the $ before it falls through to here)
        if c == '"':
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        # Char literal '.'
        if c == "'":
            i += 1
            while i < n:
                if src[i] == "\\":
                    i += 2
                    continue
                if src[i] == "'":
                    i += 1
                    break
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


# Reserved statement keywords whose presence implies executable logic. All are
# reserved (or contextual) C# keywords, so they cannot appear as PascalCase type
# or member names — matching lowercase \b…\b is safe against identifiers.
_CS_LOGIC_KEYWORDS = re.compile(r"\b(return|if|for|foreach|while|switch|try|throw|await|yield|goto|do)\b")
_CS_TYPE_KEYWORDS = re.compile(r"\b(interface|enum|record|class|struct)\b")
# A type header's own primary-constructor parameter list, so `record Foo(...) { props }`
# and `class Foo(...)` are not misread as a method/constructor body.
_CS_PRIMARY_CTOR = re.compile(r"\b(?:record|class|struct|interface)\s+\w+(?:\s*<[^>]*>)?\s*\([^)]*\)")
# An initializer's constructor/factory call (`= new(...)`, `= new T<U>(...)`, `= Make(...)`),
# so an object/collection initializer brace (`= new() { ... }`) is not misread as a
# method/ctor body by the ')' '{' check below.
_CS_INITIALIZER_CALL = re.compile(r"=\s*(?:new\b\s*)?[\w.]*(?:\s*<[^>]*>)?\s*\([^)]*\)")


def is_dotnet_logic_free(impl_path: str) -> bool:
    """Conservatively report whether a C# file is provably free of testable logic.

    True ⇒ the file is only interfaces (signatures), enums, positional records, or
    POCO/DTO classes whose members are auto-properties/fields/constants — safe to
    skip the TDD reminder. Any sign of executable logic, or any inability to read
    the file, returns False (keep enforcing). `.razor` is never treated as logic-free.
    """
    # Only plain .cs. .razor (and components in general) carry logic in markup/@code.
    if not impl_path.endswith(".cs"):
        return False

    try:
        raw = Path(impl_path).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False

    code = _strip_cs_comments_and_strings(raw)

    # Must contain at least one type declaration; otherwise (e.g. assembly-info,
    # top-level statements) treat as ambiguous and enforce.
    if not _CS_TYPE_KEYWORDS.search(code):
        return False

    # Expression-bodied member / lambda.
    if "=>" in code:
        return False

    # Statement keyword anywhere ⇒ executable logic.
    if _CS_LOGIC_KEYWORDS.search(code):
        return False

    # Manual accessor body (get/set/init/add/remove { … }) — also catches default
    # interface methods written as accessors and explicit event accessors, which
    # carry executable logic. Auto-properties use `get;` and never match.
    if re.search(r"\b(?:get|set|init|add|remove)\b\s*\{", code):
        return False

    # Method / constructor / control body: a ')' followed by '{', after stripping the
    # type header's primary-constructor list AND any initializer call. An optional
    # generic constraint (`where T : class`) may sit between ')' and '{' on a
    # constrained generic method — it must not let a real body slip through.
    # Field/property initializers (`= new() { ... }`, `= Factory()`) are deliberately
    # NOT treated as own-logic — only method/accessor/ctor bodies are. Without the
    # initializer strip, an idiomatic DTO with a braced collection/object initializer
    # (`= new() { 1, 2 }`) would false-match ')' '{' and be wrongly enforced.
    body_code = _CS_INITIALIZER_CALL.sub(" ", _CS_PRIMARY_CTOR.sub(" ", code))
    # A `where T : new()` generic constraint introduces a bare `()` whose `)` would
    # otherwise false-match the ')''{' body check below (`class C<T> where T : new() {`).
    # Initializer `new()` (`= new()`) is already stripped above, so a remaining bare
    # `new()` is only a constraint - safe to drop.
    body_code = re.sub(r"\bnew\s*\(\s*\)", " ", body_code)
    if re.search(r"\)\s*(?:where\b[^{}]*)?\{", body_code):
        return False

    return True


def _is_import_line(line: str) -> bool:
    """Check if a line is part of an import statement."""
    if line.startswith(("import ", "from ")):
        return True
    if line in (")", "("):
        return True
    if re.match(r"^[A-Za-z_][A-Za-z_0-9]*,?$", line):
        return True
    return False


def _is_subsequence(shorter: list[str], longer: list[str]) -> bool:
    """Check if shorter is an ordered subsequence of longer."""
    it = iter(longer)
    return all(line in it for line in shorter)


def is_trivial_edit(tool_name: str, tool_input: dict) -> bool:
    """Check if an Edit is trivial (imports, constants, removals) and doesn't need a failing test."""
    if tool_name != "Edit":
        return False

    old_string = tool_input.get("old_string", "")
    new_string = tool_input.get("new_string", "")

    if not old_string or not new_string:
        return False

    old_lines = [line.strip() for line in old_string.strip().splitlines() if line.strip()]
    new_lines = [line.strip() for line in new_string.strip().splitlines() if line.strip()]

    if not old_lines and not new_lines:
        return False

    all_lines = old_lines + new_lines
    if all_lines and all(_is_import_line(line) for line in all_lines):
        return True

    if new_lines and len(new_lines) < len(old_lines) and _is_subsequence(new_lines, old_lines):
        return True

    added = [line for line in new_lines if line not in old_lines]
    removed = [line for line in old_lines if line not in new_lines]
    if added and not removed and all(re.match(r"^[A-Z][A-Z_0-9]*\s*=\s*", line) for line in added):
        return True

    return False


def warn(message: str, suggestion: str) -> int:
    """Send a suppressed TDD reminder to the agent and return 0."""
    reason = f"TDD Reminder: {message}\n    {suggestion}"
    print(post_tool_use_context(reason))
    return 0


def run_tdd_enforcer() -> int:
    """Run TDD enforcement and return exit code."""
    try:
        hook_data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0

    tool_name = hook_data.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return 0

    tool_input = hook_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    if should_skip(file_path):
        return 0

    if is_test_file(file_path):
        return 0

    if is_trivial_edit(tool_name, tool_input):
        return 0

    if file_path.endswith(".py"):
        path = Path(file_path).parent
        found_failing = False

        for _ in range(10):
            if has_related_failing_test(str(path), file_path):
                found_failing = True
                break
            if path.parent == path:
                break
            path = path.parent

        if found_failing:
            return 0

        if has_python_test_file(file_path):
            return 0

        if has_test_importing_module(file_path):
            return 0

        module_name = Path(file_path).stem
        return warn(
            f"No nearby test identified for '{module_name}' module",
            "Consider whether existing tests cover this behaviour. "
            "If not, add a test for the new behaviour — not necessarily a new file. "
            "See pilot/rules/testing.md § Test Parsimony.",
        )

    if file_path.endswith((".ts", ".tsx")):
        if has_typescript_test_file(file_path):
            return 0

        if has_test_importing_module_ts(file_path):
            return 0

        return warn(
            "No nearby test identified for this module",
            "Consider whether existing tests cover this behaviour. "
            "If not, add a test for the new behaviour — not necessarily a new file. "
            "See pilot/rules/testing.md § Test Parsimony.",
        )

    if file_path.endswith(".go"):
        if has_go_test_file(file_path):
            return 0

        return warn(
            "No nearby test identified for this module",
            "Consider whether existing tests cover this behaviour. "
            "If not, add a test for the new behaviour — not necessarily a new file. "
            "See pilot/rules/testing.md § Test Parsimony.",
        )

    if file_path.endswith((".cs", ".razor")):
        # A file inside a .NET test project (MyApp.Tests, IntegrationTests, ...) is
        # itself test code - skip, matching check_dotnet's format-path behaviour.
        if is_inside_dotnet_test_project(file_path):
            return 0

        if has_dotnet_test_file(file_path):
            return 0

        if has_test_importing_module_dotnet(file_path):
            return 0

        if is_dotnet_logic_free(file_path):
            return 0

        return warn(
            "No nearby test identified for this module",
            "Consider whether existing tests cover this behaviour. "
            "If not, add a test for the new behaviour — not necessarily a new file. "
            "See pilot/rules/testing.md § Test Parsimony.",
        )

    return 0
