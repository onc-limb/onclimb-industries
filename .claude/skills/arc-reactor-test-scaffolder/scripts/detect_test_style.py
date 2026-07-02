#!/usr/bin/env python3
"""Detect test conventions of a project for arc-reactor-test-scaffolder.

Usage:
    detect_test_style.py <project_root> [target_file]

Prints a JSON object to stdout:
    {
      "language": "python" | "javascript-typescript" | ... | null,
      "config_hints": [{"file": "package.json", "framework": "vitest"}, ...],
      "test_files": ["...relative paths, nearest to target first..."],
      "has_existing_tests": true,
      "suggested_reference": "references/python.md" | null
    }

Stdlib only. Deterministic: same inputs -> same output.
"""

import json
import re
import sys
from pathlib import Path

EXT_LANG = {
    ".py": "python",
    ".ts": "javascript-typescript",
    ".tsx": "javascript-typescript",
    ".js": "javascript-typescript",
    ".jsx": "javascript-typescript",
    ".mjs": "javascript-typescript",
    ".cjs": "javascript-typescript",
    ".go": "go",
    ".java": "java",
    ".kt": "java",
    ".rb": "ruby",
    ".rs": "rust",
    ".php": "php",
    ".cs": "csharp",
}

# Filename patterns that identify a test file, per language.
TEST_PATTERNS = {
    "python": [r"^test_[^/]*\.py$", r".*_test\.py$"],
    "javascript-typescript": [r".*\.(test|spec)\.[cm]?[jt]sx?$"],
    "go": [r".*_test\.go$"],
    "java": [r".*Tests?\.(java|kt)$"],
    "ruby": [r".*_(spec|test)\.rb$"],
    "rust": [r".*\.rs$"],  # tests are usually inline; only used under tests/ dirs
    "php": [r".*Test\.php$"],
    "csharp": [r".*Tests?\.cs$"],
}

# (config file, substring to look for ("" = existence is enough), framework label)
CONFIG_HINTS = [
    ("package.json", "vitest", "vitest"),
    ("package.json", '"jest"', "jest"),
    ("package.json", "mocha", "mocha"),
    ("vitest.config.ts", "", "vitest"),
    ("vitest.config.js", "", "vitest"),
    ("vitest.config.mts", "", "vitest"),
    ("jest.config.js", "", "jest"),
    ("jest.config.ts", "", "jest"),
    ("jest.config.json", "", "jest"),
    ("pyproject.toml", "pytest", "pytest"),
    ("pytest.ini", "", "pytest"),
    ("setup.cfg", "pytest", "pytest"),
    ("tox.ini", "pytest", "pytest"),
    ("go.mod", "stretchr/testify", "go testing + testify"),
    ("go.mod", "", "go testing"),
    ("pom.xml", "junit-jupiter", "junit5"),
    ("pom.xml", "junit", "junit"),
    ("build.gradle", "junit", "junit"),
    ("build.gradle.kts", "junit", "junit"),
    ("Gemfile", "rspec", "rspec"),
    ("Cargo.toml", "", "cargo test"),
]

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "out", "target",
    ".venv", "venv", "__pycache__", ".next", ".nuxt", "coverage",
    ".mypy_cache", ".pytest_cache", ".gradle", "bin", "obj",
}

REFERENCE_LANGS = {"python", "javascript-typescript", "go", "java"}
MAX_TEST_FILES = 20


def detect_language(target: Path | None, test_files: list[Path]) -> str | None:
    if target is not None:
        lang = EXT_LANG.get(target.suffix)
        if lang:
            return lang
    # Fall back to the most common language among found test files.
    counts: dict[str, int] = {}
    for f in test_files:
        lang = EXT_LANG.get(f.suffix)
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    if counts:
        return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return None


def collect_config_hints(root: Path) -> list[dict]:
    hints: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for name, needle, framework in CONFIG_HINTS:
        path = root / name
        if not path.is_file():
            continue
        if needle:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if needle not in content:
                continue
        key = (name, framework)
        if key in seen:
            continue
        seen.add(key)
        hints.append({"file": name, "framework": framework})
    return hints


def is_test_file(path: Path, language: str | None) -> bool:
    name = path.name
    patterns: list[str] = []
    if language and language in TEST_PATTERNS:
        patterns = TEST_PATTERNS[language]
    else:
        for pats in TEST_PATTERNS.values():
            patterns.extend(pats)
    for pat in patterns:
        if re.fullmatch(pat, name):
            # Rust: only treat files under a tests/ dir as separate test files.
            if path.suffix == ".rs" and "tests" not in path.parts:
                continue
            return True
    return False


def collect_test_files(root: Path, language: str | None) -> list[Path]:
    found: list[Path] = []
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for entry in entries:
            if entry.is_dir():
                if entry.name in SKIP_DIRS or entry.name.startswith("."):
                    continue
                stack.append(entry)
            elif entry.is_file() and is_test_file(entry, language):
                found.append(entry)
    return found


def proximity_key(test_file: Path, target: Path | None, root: Path):
    """Sort key: nearest to target first (longest shared path prefix), then path."""
    rel = test_file.relative_to(root)
    if target is None:
        return (0, len(rel.parts), str(rel))
    try:
        target_rel = target.relative_to(root)
    except ValueError:
        return (0, len(rel.parts), str(rel))
    shared = 0
    for a, b in zip(rel.parts[:-1], target_rel.parts[:-1]):
        if a != b:
            break
        shared += 1
    return (-shared, len(rel.parts), str(rel))


def main(argv: list[str]) -> int:
    if len(argv) < 2 or len(argv) > 3:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = Path(argv[1]).resolve()
    if not root.is_dir():
        print(f"error: project_root is not a directory: {root}", file=sys.stderr)
        return 2
    target: Path | None = None
    if len(argv) == 3:
        target = Path(argv[2])
        if not target.is_absolute():
            target = root / target
        target = target.resolve()

    # First pass without a language filter is only needed when target is absent.
    provisional_lang = EXT_LANG.get(target.suffix) if target else None
    test_files = collect_test_files(root, provisional_lang)
    language = detect_language(target, test_files)
    if language and language != provisional_lang:
        test_files = collect_test_files(root, language)

    test_files.sort(key=lambda f: proximity_key(f, target, root))
    test_files = test_files[:MAX_TEST_FILES]

    suggested = (
        f"references/{language}.md" if language in REFERENCE_LANGS else None
    )
    result = {
        "language": language,
        "config_hints": collect_config_hints(root),
        "test_files": [str(f.relative_to(root)) for f in test_files],
        "has_existing_tests": bool(test_files),
        "suggested_reference": suggested,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
