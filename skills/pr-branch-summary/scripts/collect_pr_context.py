#!/usr/bin/env python3
"""Collect git evidence for drafting PR communication."""

from __future__ import annotations

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

# Everything this script prints is user content: commit subjects, git status and a
# full diff. On a default Windows console one emoji or CJK character anywhere in the
# branch would raise UnicodeEncodeError and kill the run, so never let it.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_out(args: list[str], cwd: Path, check: bool = True) -> str:
    result = run_git(args, cwd, check=check)
    return result.stdout.strip()


def git_block(args: list[str], cwd: Path, check: bool = True) -> str:
    result = run_git(args, cwd, check=check)
    text = result.stdout.strip()
    if not text and result.stderr.strip():
        text = result.stderr.strip()
    return text


def resolve_repo(path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise SystemExit(f"Not inside a git repository: {path}")
    return Path(result.stdout.strip())


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def ref_exists(ref: str, cwd: Path) -> bool:
    result = run_git(["rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"], cwd, check=False)
    return result.returncode == 0


def resolve_base_ref(base: str, cwd: Path) -> str:
    candidates = [base]
    if "/" not in base and not base.startswith("refs/"):
        candidates.extend([f"origin/{base}", f"upstream/{base}", f"remotes/origin/{base}"])
    else:
        short = base.split("/", 1)[1] if base.startswith("origin/") else base
        candidates.extend([short, f"refs/remotes/{base}"])

    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if ref_exists(candidate, cwd):
            return candidate

    raise SystemExit(
        f"Could not resolve base ref '{base}'. Try fetching or pass an explicit ref like origin/{base}."
    )


def fenced(command: str, body: str) -> str:
    if not body:
        body = "(no output)"
    return f"$ {command}\n\n```text\n{body}\n```"


def capped_diff(cwd: Path, merge_base: str, max_diff_lines: int) -> tuple[str, bool]:
    diff = git_block(["diff", "--find-renames", f"{merge_base}..HEAD"], cwd)
    lines = diff.splitlines()
    if len(lines) <= max_diff_lines:
        return diff, False
    return "\n".join(lines[:max_diff_lines]), True


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect git context for PR summary drafting.")
    parser.add_argument("--base", required=True, help="Base branch/ref, for example staging or production.")
    parser.add_argument("--repo", default=".", help="Path inside the git repository.")
    parser.add_argument(
        "--fetch",
        action="store_true",
        help=(
            "Fetch only the base ref before resolving refs (git fetch <remote> <base>). "
            "Updates one remote-tracking ref; never touches the working tree, index, or local branches."
        ),
    )
    parser.add_argument(
        "--fetch-remote",
        default="origin",
        help="Remote to fetch the base ref from when --fetch is used. Defaults to origin.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Add --prune to the fetch, deleting stale remote-tracking refs. Off by default.",
    )
    parser.add_argument("--output", help="Write markdown report to this path. Defaults to stdout.")
    parser.add_argument(
        "--allow-repo-output",
        action="store_true",
        help="Allow --output to write inside the target repository. Use only when the user explicitly asks for a file.",
    )
    parser.add_argument("--max-diff-lines", type=int, default=1500, help="Maximum full diff lines to include.")
    args = parser.parse_args()

    repo = resolve_repo(Path(args.repo).resolve())
    fetch_note = ""
    if args.fetch:
        remote = args.fetch_remote
        # Accept either "staging" or "origin/staging" as --base; git fetch wants the bare ref name.
        base_name = args.base
        if base_name.startswith(f"{remote}/"):
            base_name = base_name[len(remote) + 1 :]
        fetch_args = ["fetch", remote, base_name]
        if args.prune:
            fetch_args.insert(1, "--prune")
        printable = "git " + " ".join(fetch_args)
        fetch = run_git(fetch_args, repo, check=False)
        if fetch.returncode == 0:
            fetch_note = f"Fetch: completed with `{printable}`. Remote-tracking ref only; working tree untouched."
        else:
            fetch_note = (
                f"Fetch: `{printable}` failed; report uses local refs.\n\n```text\n"
                + fetch.stderr.strip()
                + "\n```"
            )

    base_ref = resolve_base_ref(args.base, repo)
    merge_base = git_out(["merge-base", "HEAD", base_ref], repo)
    branch = git_out(["branch", "--show-current"], repo, check=False) or "(detached HEAD)"
    head_sha = git_out(["rev-parse", "--short", "HEAD"], repo)
    base_sha = git_out(["rev-parse", "--short", base_ref], repo)
    merge_base_short = git_out(["rev-parse", "--short", merge_base], repo)
    upstream = git_out(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], repo, check=False)
    status = git_block(["status", "--short", "--branch"], repo, check=False)
    commits = git_block(
        ["log", "--reverse", "--date=short", "--pretty=format:%h %ad %s", f"{merge_base}..HEAD"],
        repo,
        check=False,
    )
    diff_stat = git_block(["diff", "--stat", f"{merge_base}..HEAD"], repo, check=False)
    name_status = git_block(["diff", "--name-status", f"{merge_base}..HEAD"], repo, check=False)
    numstat = git_block(["diff", "--numstat", f"{merge_base}..HEAD"], repo, check=False)
    staged_stat = git_block(["diff", "--cached", "--stat"], repo, check=False)
    worktree_stat = git_block(["diff", "--stat"], repo, check=False)
    diff, truncated = capped_diff(repo, merge_base, args.max_diff_lines)

    generated_at = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    rel_repo = os.fspath(repo)
    report = [
        "# PR Branch Comparison Context",
        "",
        f"Generated: {generated_at}",
        f"Repository: `{rel_repo}`",
        f"Current branch: `{branch}`",
        f"Upstream: `{upstream or '(none)'}`",
        f"Requested base: `{args.base}`",
        f"Resolved base: `{base_ref}` ({base_sha})",
        f"HEAD: `{head_sha}`",
        f"Merge base: `{merge_base_short}`",
        "",
        fetch_note or "Fetch: not requested.",
        "",
        "## Working Tree",
        "",
        fenced("git status --short --branch", status),
        "",
        "## Commits In Branch",
        "",
        fenced(f"git log --reverse --date=short --pretty=format:'%h %ad %s' {merge_base_short}..HEAD", commits),
        "",
        "## Diff Stat",
        "",
        fenced(f"git diff --stat {merge_base_short}..HEAD", diff_stat),
        "",
        "## Changed Files",
        "",
        fenced(f"git diff --name-status {merge_base_short}..HEAD", name_status),
        "",
        "## Numstat",
        "",
        fenced(f"git diff --numstat {merge_base_short}..HEAD", numstat),
        "",
        "## Uncommitted Changes",
        "",
        "These are not part of the branch PR unless committed.",
        "",
        fenced("git diff --cached --stat", staged_stat),
        "",
        fenced("git diff --stat", worktree_stat),
        "",
        "## Full Diff",
        "",
        f"Diff is {'truncated' if truncated else 'complete'} at {args.max_diff_lines} line limit.",
        "",
        fenced(f"git diff --find-renames {merge_base_short}..HEAD", diff),
        "",
    ]

    output = "\n".join(report)
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = repo / output_path
        output_path = output_path.resolve()
        if is_relative_to(output_path, repo) and not args.allow_repo_output:
            raise SystemExit(
                "Refusing to write a PR summary report inside the repository. "
                "Omit --output to print to stdout, or write to a path outside the repo."
            )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(output_path)
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
