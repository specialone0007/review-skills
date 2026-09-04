#!/usr/bin/env python3
"""Survey a repository's structure so an audit can start from facts instead of guesses.

Read-only. Standard library only. Writes nothing.

    python repo_inventory.py                  # text summary of the current repo
    python repo_inventory.py --repo ../other  # a different repo
    python repo_inventory.py --format json    # machine-readable

Reports detected stacks, available commands, per-directory size, extension mix,
largest files, where tests/CI/docs/lockfiles live, and structural smells such as
flat directories and catch-all folders.

Output is capped. When a section is trimmed it says so, so its list is never
mistaken for the whole picture.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

# A single non-ASCII byte crashes a default Windows console, so never let it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GIT_TIMEOUT = 30

# Directories to skip when git is unavailable and we have to walk the tree ourselves.
IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "vendor", "venv", ".venv", "env",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox",
    "dist", "build", "target", "out", ".next", ".nuxt", ".svelte-kit",
    ".idea", ".vscode", ".gradle", "Pods", ".terraform", "coverage",
}

# Manifest filename -> the stack it implies.
MANIFESTS = {
    "package.json": "JavaScript/TypeScript", "deno.json": "Deno", "bun.lockb": "Bun",
    "pyproject.toml": "Python", "setup.py": "Python", "requirements.txt": "Python",
    "Pipfile": "Python", "Cargo.toml": "Rust", "go.mod": "Go",
    "pom.xml": "Java/Maven", "build.gradle": "Java/Gradle", "build.gradle.kts": "Kotlin/Gradle",
    "Gemfile": "Ruby", "composer.json": "PHP", "mix.exs": "Elixir",
    "pubspec.yaml": "Dart/Flutter", "Package.swift": "Swift", "CMakeLists.txt": "C/C++/CMake",
    "Makefile": "Make", "Dockerfile": "Docker", "docker-compose.yml": "Docker Compose",
    "*.csproj": ".NET", "*.sln": ".NET",
}

LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb", "deno.lock",
    "poetry.lock", "Pipfile.lock", "uv.lock", "Cargo.lock", "go.sum",
    "Gemfile.lock", "composer.lock", "mix.lock", "pubspec.lock",
}

TEST_HINTS = re.compile(r"(^|/)(tests?|spec|specs|__tests__|e2e|integration)(/|$)|"
                        r"(^|/)[^/]*[._-](test|spec)s?\.[A-Za-z0-9]+$|"
                        r"(^|/)test_[^/]*\.py$", re.IGNORECASE)
DOC_HINTS = re.compile(r"(^|/)(docs?|documentation|guides?|adr|rfcs?)(/|$)|"
                       r"(^|/)(readme|changelog|contributing|architecture)[^/]*$", re.IGNORECASE)
CI_HINTS = re.compile(r"(^\.github/workflows/|^\.gitlab-ci|^\.circleci/|^azure-pipelines|"
                      r"^Jenkinsfile|^\.travis|^\.drone|^buildkite)", re.IGNORECASE)
CATCH_ALL = {"utils", "util", "helpers", "helper", "common", "misc", "shared", "lib", "core", "stuff"}

# Extensions we count lines for. Binary and generated formats are sized but not counted.
TEXT_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".go", ".rs", ".rb", ".php", ".java", ".kt", ".kts", ".swift", ".scala",
    ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".m", ".mm", ".ex", ".exs",
    ".dart", ".sh", ".bash", ".zsh", ".ps1", ".sql", ".graphql", ".proto",
    ".css", ".scss", ".sass", ".less", ".html", ".md", ".mdx", ".rst", ".txt",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".xml",
}

warnings: list[str] = []


def run_git(args: list[str], repo: Path) -> str | None:
    """Run a git command. Returns None on any failure rather than raising."""
    git = shutil.which("git")
    if git is None:
        return None
    try:
        result = subprocess.run(
            [git, *args], cwd=str(repo), text=True, timeout=GIT_TIMEOUT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
        )
    except (OSError, subprocess.SubprocessError) as exc:
        warnings.append(f"git {' '.join(args)} failed: {exc}")
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def list_files(repo: Path) -> list[str]:
    """Prefer git's index: deterministic, and it already honours .gitignore."""
    out = run_git(["ls-files", "--cached", "--other", "--exclude-standard"], repo)
    if out is not None:
        files = [line.strip() for line in out.splitlines() if line.strip()]
        if files:
            return sorted(files)
        warnings.append("git reported no files; falling back to a filesystem walk")
    else:
        warnings.append("git unavailable or not a repository; using a filesystem walk (ignore rules approximated)")

    files = []
    for root, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS and not d.startswith(".")]
        for fn in filenames:
            rel = Path(root, fn).relative_to(repo).as_posix()
            files.append(rel)
    return sorted(files)


def count_lines(path: Path) -> int:
    try:
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def build(repo: Path, files: list[str]) -> dict:
    stacks: dict[str, list[str]] = defaultdict(list)
    commands: dict[str, list[str]] = {}
    lockfiles, env_files, ci_files = [], [], []
    test_files, doc_files = [], []
    ext_counter: Counter[str] = Counter()
    dir_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"files": 0, "lines": 0})
    direct_children: Counter[str] = Counter()
    sizes: list[tuple[int, int, str]] = []  # (bytes, lines, path)
    total_lines = 0

    for rel in files:
        abs_path = repo / rel
        name = Path(rel).name
        ext = Path(rel).suffix.lower()
        depth_parts = rel.split("/")
        top = depth_parts[0] if len(depth_parts) > 1 else "(root)"

        # stacks
        for pattern, stack in MANIFESTS.items():
            if (pattern.startswith("*") and name.endswith(pattern[1:])) or name == pattern:
                stacks[stack].append(rel)
        if name in LOCKFILES:
            lockfiles.append(rel)
        if name.startswith(".env"):
            env_files.append(rel)  # name only; contents are never read
        if CI_HINTS.search(rel):
            ci_files.append(rel)
        if TEST_HINTS.search(rel):
            test_files.append(rel)
        if DOC_HINTS.search(rel):
            doc_files.append(rel)

        ext_counter[ext or "(none)"] += 1
        direct_children[str(Path(rel).parent).replace("\\", "/")] += 1

        lines = count_lines(abs_path) if ext in TEXT_EXTS else 0
        total_lines += lines
        dir_stats[top]["files"] += 1
        dir_stats[top]["lines"] += lines
        try:
            sizes.append((abs_path.stat().st_size, lines, rel))
        except OSError:
            pass

    # Available commands. Manifests are not always at the root -- in a monorepo the
    # only package.json may be at apps/web/ or packages/ui/ -- so read every one we
    # found, nearest the root first, and label each by its directory.
    def by_name(target: str) -> list[str]:
        found = [f for f in files if Path(f).name == target]
        return sorted(found, key=lambda p: (p.count("/"), p))[:5]

    for rel in by_name("package.json"):
        prefix = str(Path(rel).parent).replace("\\", "/")
        label = "npm run" if prefix in (".", "") else f"npm run (in {prefix})"
        try:
            data = json.loads((repo / rel).read_text(encoding="utf-8", errors="replace"))
        except (ValueError, OSError) as exc:
            warnings.append(f"could not parse {rel}: {exc}")
            continue
        if isinstance(data.get("scripts"), dict) and data["scripts"]:
            commands[label] = sorted(data["scripts"].keys())
        if data.get("workspaces"):
            stacks["JavaScript/TypeScript monorepo"].append(f"{rel}:workspaces")

    for rel in by_name("Makefile"):
        prefix = str(Path(rel).parent).replace("\\", "/")
        label = "make" if prefix in (".", "") else f"make (in {prefix})"
        try:
            targets = re.findall(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?!=)",
                                 (repo / rel).read_text(encoding="utf-8", errors="replace"), re.MULTILINE)
        except OSError as exc:
            warnings.append(f"could not read {rel}: {exc}")
            continue
        if targets:
            commands[label] = sorted(set(targets))

    for rel in by_name("pyproject.toml"):
        prefix = str(Path(rel).parent).replace("\\", "/")
        label = "python entry points" if prefix in (".", "") else f"python entry points (in {prefix})"
        try:
            text = (repo / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "[project.scripts]" not in text:
            continue
        section = text.split("[project.scripts]", 1)[1].split("\n[", 1)[0]
        scripts = re.findall(r"^\s*([A-Za-z0-9_.-]+)\s*=", section, re.MULTILINE)
        if scripts:
            commands[label] = sorted(set(scripts))

    sizes.sort(reverse=True)
    flat = [(d, n) for d, n in direct_children.most_common() if n >= 25]
    catch_all = sorted({d for d in direct_children if Path(d).name.lower() in CATCH_ALL})
    deepest = sorted(files, key=lambda p: p.count("/"), reverse=True)

    return {
        "repo": str(repo),
        "totals": {
            "files": len(files),
            "lines": total_lines,
            "test_files": len(test_files),
            "doc_files": len(doc_files),
        },
        "stacks": {k: sorted(v) for k, v in sorted(stacks.items())},
        "commands": commands,
        "directories": sorted(
            ({"dir": d, **s} for d, s in dir_stats.items()),
            key=lambda x: x["lines"], reverse=True,
        ),
        "extensions": [{"ext": e, "files": n} for e, n in ext_counter.most_common()],
        "largest_files": [{"path": p, "bytes": b, "lines": ln} for b, ln, p in sizes],
        "lockfiles": lockfiles,
        "env_files": env_files,
        "ci_files": ci_files,
        "flat_directories": [{"dir": d, "direct_children": n} for d, n in flat],
        "catch_all_directories": catch_all,
        "deepest_paths": deepest,
        "warnings": warnings,
    }


def truncate(items: list, limit: int, label: str, out: list[str]) -> list:
    if len(items) > limit:
        out.append(f"  TRUNCATED: showing top {limit} of {len(items)} {label}")
        return items[:limit]
    return items


def render(data: dict, top: int) -> str:
    L: list[str] = []
    t = data["totals"]
    L.append("# Repository Inventory")
    L.append("")
    L.append(f"Repo: {data['repo']}")
    L.append(f"Files: {t['files']}   Lines (text files): {t['lines']}   "
             f"Test files: {t['test_files']}   Doc files: {t['doc_files']}")
    L.append("")

    L.append("## Detected stacks")
    if data["stacks"]:
        for stack, paths in data["stacks"].items():
            shown = paths[:3]
            more = f" (+{len(paths) - 3} more)" if len(paths) > 3 else ""
            L.append(f"- {stack}: {', '.join(shown)}{more}")
    else:
        L.append("- none detected (no recognised manifest)")
    L.append("")

    L.append("## Available commands")
    if data["commands"]:
        for runner, names in data["commands"].items():
            shown = names[:15]
            more = f" (+{len(names) - 15} more)" if len(names) > 15 else ""
            L.append(f"- {runner}: {', '.join(shown)}{more}")
    else:
        L.append("- none found in manifests")
    L.append("")

    L.append("## Top-level directories by size")
    for d in truncate(data["directories"], top, "directories", L):
        L.append(f"- {d['dir']}: {d['files']} files, {d['lines']} lines")
    L.append("")

    L.append("## Extension mix")
    exts = truncate(data["extensions"], top, "extensions", L)
    L.append("- " + ", ".join(f"{e['ext']} ({e['files']})" for e in exts))
    L.append("")

    L.append("## Largest files")
    for f in truncate(data["largest_files"], top, "files", L):
        L.append(f"- {f['path']}: {f['bytes']} bytes, {f['lines']} lines")
    L.append("")

    L.append("## Configuration and infrastructure")
    L.append(f"- Lockfiles: {', '.join(data['lockfiles']) or 'none'}")
    L.append(f"- CI config: {', '.join(data['ci_files']) or 'none'}")
    # Names only. This script never reads the contents of an env file.
    L.append(f"- Env files (names only, contents never read): {', '.join(data['env_files']) or 'none'}")
    L.append("")

    L.append("## Structural smells")
    if data["flat_directories"]:
        for d in truncate(data["flat_directories"], top, "flat directories", L):
            L.append(f"- Flat directory: {d['dir']} has {d['direct_children']} direct children")
    else:
        L.append("- No directory has 25 or more direct children")
    if data["catch_all_directories"]:
        L.append(f"- Catch-all names: {', '.join(data['catch_all_directories'])}")
    else:
        L.append("- No catch-all directory names found")
    deepest = data["deepest_paths"][:5]
    if deepest:
        L.append(f"- Deepest path: {deepest[0]} ({deepest[0].count('/')} levels)")
    L.append("")

    if data["warnings"]:
        L.append("## Warnings")
        for w in data["warnings"]:
            L.append(f"- {w}")
        L.append("")

    L.append("Heuristic survey only. Confirm anything you intend to report as a finding.")
    return "\n".join(L)


def main() -> int:
    parser = argparse.ArgumentParser(description="Survey a repository's structure. Read-only.")
    parser.add_argument("--repo", default=".", help="Path inside the repository to survey.")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    parser.add_argument("--top", type=int, default=20, help="Rows per ranked section. Default 20.")
    parser.add_argument(
        "--no-git-root",
        action="store_true",
        help=(
            "Treat --repo literally instead of expanding to the enclosing git repository root. "
            "Use this to scope the survey to one package or subdirectory of a monorepo."
        ),
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2

    if not args.no_git_root:
        root = run_git(["rev-parse", "--show-toplevel"], repo)
        if root and root.strip():
            repo = Path(root.strip()).resolve()

    files = list_files(repo)
    if not files:
        print(f"error: no files found under {repo}", file=sys.stderr)
        return 2

    data = build(repo, files)
    if args.format == "json":
        print(json.dumps(data, indent=2))
    else:
        print(render(data, args.top))
    # Partial failures are reported in `warnings` rather than failing the run.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
