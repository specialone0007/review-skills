#!/usr/bin/env python3
"""Check drafted documentation before anybody accepts it.

Read-only. Standard library only. Writes nothing.

    python docs_fill_gate.py --repo . docs/TESTING.md docs/RUNBOOK.md
    python docs_fill_gate.py --repo . --all            # every doc carrying the draft marker
    python docs_fill_gate.py --repo . --all --format json
    python docs_fill_gate.py --repo . --all --fail-on-findings   # exit 1 when anything fails

The fill step of the docs-structure skill writes drafts from a repository's own evidence, and
promises several things about them. This script is where those promises are checked. It reads
only documentation and the files a draft cites; it never edits, stages or commits.

What it checks, per section that carries the draft marker:

  G1  every paragraph and every table row ends with an evidence bracket
  G2  every bracket resolves: `[path]` exists case-exactly, `[path § heading]` names a heading
      that is in that file, `[sha date]` is a commit this repository has. `[inventory: key]`
      and `[path: key]` are accepted as written; the checker owns the inventory, not this
  G3  no `file.ext:123` citation into a source file - those rot within one change (R7)
  G4  no evaluative word (robust, clean, fast, ...): a draft restates, it does not judge
  G5  no modal verb (should, must, will, guarantees, handles) outside a quotation
  G6  no intent word (so that, because, designed to, ...) unless quoted or after `inferred:`
  G7  no `NAME=value` line for a variable the evidence inventory found: names, never values
  G8  every drafted section ends with the marker, and the doc stays under `splitAt/2` lines
      so that a draft can never become a split candidate

A section still holding its template line is a skeleton, not a draft, and is skipped. A doc
with no draft marker anywhere is skipped: this script judges drafts, not people's prose.

Exit codes: 0 when the run completed (findings are data, not failure), 1 only with
--fail-on-findings and at least one finding, 2 for a bad flag or an unreadable path.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # importing the sibling module must not write a __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import docs_evidence  # sibling script, same folder, stdlib only
except ImportError:  # pragma: no cover
    docs_evidence = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GIT_TIMEOUT = 30
MAX_READ = 2_000_000
DRAFT_MARK = "*(draft, review me)*"
SKELETON_MARK = "(skeleton, write me)"
DEFAULT_MAX_LINES = 250  # splitAt 500 / 2

# One level of nesting is allowed inside a bracket. Without it the grammar SKILL.md documents
# ([inventory: services[0]]) fails its own gate, and no file-routed framework can be cited at
# all: Next.js, Remix, SvelteKit and Nuxt all put [param] in the path.
BRACKET_END = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\]\.?$")
BRACKET_ANY = re.compile(r"\[((?:[^\[\]]|\[[^\[\]]*\])+)\](?!\()")
# A Markdown link is not an evidence bracket; its text is prose and resolving it as a path was
# reporting G2 on ordinary cross-doc links, which the fill rules require.
QUOTED = re.compile(r"\"[^\"]*\"|\u201c[^\u201d]*\u201d")
# A sentence that ended mid-paragraph without a bracket before the next one began.
BAD_BREAK = re.compile(r"[^\]`.]\.\s+(?=[A-Z`(])")
BANNED = re.compile(r"\b(robust|secure|simple|clean|fast|modern|scalable|easy|powerful|"
                    r"seamless|best|properly|elegant|efficient|reliable)\b", re.I)
INTENT = re.compile(r"\b(so that|because|designed to|ensures|aims to)\b", re.I)
MODAL = re.compile(r"\b(should|must|will|guarantees|handles)\b")
LINE_CITE = re.compile(r"\.[A-Za-z]{1,5}:\d+")
SHA_REF = re.compile(r"^[0-9a-f]{7,40} \d{4}-\d{2}-\d{2}$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
CODESPAN = re.compile(r"`[^`]*`")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|?$")
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
DOC_EXTS = {".md", ".mdx"}
# Pruned before descending, never after: rglob over a repo with node_modules costs half a minute.
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next",
             "vendor", "target", "coverage", ".tox", ".mypy_cache", ".pytest_cache", "tmp"}
MAX_WALK_DEPTH = 12

warnings: list[str] = []


def safe(text: str) -> str:
    """Never echo a line back raw: a drafted line can quote a value the inventory flagged."""
    return docs_evidence.redact(text) if docs_evidence is not None else text


def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def git_root(start: Path) -> Path | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        p = subprocess.run([git, "rev-parse", "--show-toplevel"], cwd=str(start), text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT,
                           encoding="utf-8", errors="replace")
        return Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def sha_known(repo: Path, sha: str) -> bool:
    """True when this repository has that commit. Unknown (no git) counts as known: the gate
    reports what it can prove, and never fails a draft because git is missing."""
    git = shutil.which("git")
    if git is None:
        return True
    try:
        p = subprocess.run([git, "cat-file", "-e", sha], cwd=str(repo), text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


def exists_exact(repo: Path, rel: str) -> bool:
    """Case-exact existence, so a draft that works on Windows still works on Linux."""
    target = repo / rel
    if not target.exists():
        return False
    try:
        parts = Path(rel).parts
        here = repo
        for part in parts:
            names = {p.name for p in here.iterdir()}
            if part not in names:
                return False
            here = here / part
    except OSError:
        return True
    return True


def headings_of(path: Path) -> set[str]:
    out = set()
    in_fence = False
    for line in read(path).splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = HEADING.match(line)
        if m:
            out.add(m.group(2).strip().lower())
    return out


def resolve_bracket(repo: Path, ref: str) -> str | None:
    """None when the reference resolves; otherwise why it does not."""
    for part in [p.strip() for p in ref.split(";") if p.strip()]:
        if part.startswith("inventory:"):
            continue  # the checker owns the inventory; this gate does not re-derive it
        if SHA_REF.match(part):
            if not sha_known(repo, part.split()[0]):
                return f"commit not in this repository: {part}"
            continue
        path = re.split(r" § |: ", part, maxsplit=1)[0].strip()
        if not path or path.startswith(("http://", "https://", "^", "!")):
            continue
        if not exists_exact(repo, path):
            return f"cited path does not exist: {path}"
        if " § " in part:
            heading = part.split(" § ", 1)[1].strip().lower()
            if heading not in headings_of(repo / path):
                return f"{path} has no heading '{part.split(' § ', 1)[1].strip()}'"
    return None


def env_names(repo: Path) -> set[str]:
    """Variable names the evidence inventory found, so G7 can spot a value written beside one."""
    if docs_evidence is None:
        warnings.append("docs_evidence.py not found beside this script; G7 (env values) not checked")
        return set()
    try:
        inv = docs_evidence.inventory(repo, 100, use_git=False)
    except Exception as exc:  # the gate must never fail because the inventory did
        warnings.append(f"evidence inventory unavailable, G7 not checked: {type(exc).__name__}")
        return set()
    names: set[str] = set()
    for entry in inv.get("env") or []:
        names.update(n for n in entry.get("names", []) if isinstance(n, str))
    return names


def sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """(heading text, first body line index, end index) for every H2."""
    marks = [(i, HEADING.match(l)) for i, l in enumerate(lines)]
    h2 = [(i, m.group(2).strip()) for i, m in marks if m and len(m.group(1)) == 2]
    out = []
    for n, (i, text) in enumerate(h2):
        end = h2[n + 1][0] if n + 1 < len(h2) else len(lines)
        out.append((text, i + 1, end))
    return out


def check_doc(repo: Path, rel: str, names: set[str], max_lines: int) -> list[dict]:
    """Findings for one doc. Only sections carrying the draft marker are judged."""
    path = repo / rel
    text = read(path)
    if not text:
        return [{"doc": rel, "line": 1, "rule": "G0", "message": "unreadable or empty"}]
    if DRAFT_MARK not in text:
        return []
    lines = text.splitlines()
    found: list[dict] = []

    def add(rule: str, line: int, message: str) -> None:
        found.append({"doc": rel, "line": line, "rule": rule, "message": message})

    if len(lines) > max_lines:
        add("G8", 1, f"{len(lines)} lines, over the {max_lines}-line draft cap; a draft must not become a split candidate")

    for heading, start, end in sections(lines):
        body = [l for l in lines[start:end] if l.strip()]
        if not body:
            continue
        # a section still holding only its template italic line is a skeleton, not a draft
        if len(body) == 1 and body[0].strip().startswith("*") and body[0].strip().endswith("*") and body[0].strip() != DRAFT_MARK:
            continue
        if body[-1].strip() != DRAFT_MARK:
            continue  # not a drafted section: leave a person's prose alone
        # A paragraph is the unit, not a line: a draft may be hard-wrapped, and the evidence
        # bracket belongs at the end of the paragraph's last line.
        para: list[tuple[int, str]] = []

        def flush() -> None:
            if not para:
                return
            first = para[0][0]
            joined = " ".join(t for _, t in para)
            last = para[-1][1]
            bare = CODESPAN.sub("", joined)
            if not joined.lower().startswith("open question:"):
                if not BRACKET_END.search(last):
                    add("G1", first, f"paragraph does not end with an evidence bracket: {safe(joined[:60])}")
                if BAD_BREAK.search(bare):
                    add("G1", first, "a sentence inside this paragraph ends without an evidence bracket")
                for ref in BRACKET_ANY.findall(joined):
                    why = resolve_bracket(repo, ref)
                    if why:
                        add("G2", first, why)
                if LINE_CITE.search(joined) and "://" not in joined:
                    add("G3", first, f"line-number citation: {LINE_CITE.search(joined).group(0)}")
                # `bare` has code spans removed: a file named fast.js or a dependency called
                # simple-git is a name, not a claim about quality.
                if BANNED.search(bare):
                    add("G4", first, f"evaluative word: {BANNED.search(bare).group(0)}")
                # Quoted spans are the repo's words, not the draft's, so they are removed before
                # G5 and G6 rather than switching both off for the paragraph that contains them.
                # The fill rules encourage quoting the README, so that hole sat on the happy path.
                unquoted = QUOTED.sub(" ", bare)
                if MODAL.search(unquoted):
                    add("G5", first, f"modal verb: {MODAL.search(unquoted).group(0)}")
                intent_hit = INTENT.search(QUOTED.sub(" ", joined))
                if intent_hit and not joined.lower().startswith("inferred:"):
                    add("G6", first, f"intent word outside a quotation or `inferred:`: {intent_hit.group(0)}")
                for name in names:
                    if re.search(rf"\b{re.escape(name)}\s*=\s*\S", joined):
                        add("G7", first, f"a value is written beside {name}; drafts carry names, never values")
            para.clear()

        in_fence = False
        for idx in range(start, end):
            raw = lines[idx]
            s_ = raw.strip()
            if FENCE.match(raw):
                flush()
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if not s_ or s_ == DRAFT_MARK or s_.startswith(("#", "<!--", ">")) or TABLE_RULE.match(s_):
                flush()
                continue
            n = idx + 1
            if s_.startswith("|"):
                flush()
                nxt = lines[idx + 1].strip() if idx + 1 < len(lines) else ""
                if TABLE_RULE.match(nxt):
                    continue  # header row
                cells = [c.strip() for c in s_.strip("|").split("|")]
                m = BRACKET_END.search(cells[-1]) if cells else None
                if not m:
                    add("G1", n, "table row has no evidence bracket in its last cell")
                else:
                    why = resolve_bracket(repo, m.group(1))
                    if why:
                        add("G2", n, why)
                if LINE_CITE.search(s_) and "://" not in s_:
                    add("G3", n, f"line-number citation: {LINE_CITE.search(s_).group(0)}")
                continue
            para.append((n, s_))
        flush()
    return found


def drafted_docs(repo: Path) -> list[str]:
    """Every doc carrying the draft marker. Prunes on the way down: a repository with a
    node_modules tree costs half a minute to walk and holds nothing this gate judges."""
    out = []
    base = len(repo.parts)
    for dirpath, dirnames, filenames in os.walk(repo):
        here = Path(dirpath)
        if len(here.parts) - base >= MAX_WALK_DEPTH:
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for name in sorted(filenames):
            path = here / name
            if path.suffix.lower() not in DOC_EXTS:
                continue
            if DRAFT_MARK in read(path):
                out.append(path.relative_to(repo).as_posix())
    return out


def render(data: dict, cap: int) -> str:
    lines = ["# Fill Gate", "", f"Repo: {data['repo']}",
             f"Docs checked: {len(data['docs'])}   Findings: {data['total']}"]
    if not data["docs"]:
        lines.append("")
        lines.append("No doc carries the draft marker; nothing to gate.")
    for doc in data["docs"]:
        hits = [f for f in data["findings"] if f["doc"] == doc]
        lines.append("")
        lines.append(f"{doc}: {'OK' if not hits else str(len(hits)) + ' finding(s)'}")
        for f in hits[:cap]:
            lines.append(f"  {doc}:{f['line']}: [{f['rule']}] {f['message']}")
        if len(hits) > cap:
            lines.append(f"  ... {len(hits) - cap} more, use --format json")
    for w in data["warnings"]:
        lines.append(f"note: {w}")
    if data["total"]:
        lines.append("")
        lines.append("Nothing should be written while any finding stands: fix the draft, then run this again.")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check drafted docs against the fill promises. Read-only.")
    ap.add_argument("docs", nargs="*", help="docs to gate, relative to the repo")
    ap.add_argument("--repo", default=".", help="repository path (default: current directory)")
    ap.add_argument("--all", action="store_true", help="gate every doc carrying the draft marker")
    ap.add_argument("--no-git-root", action="store_true", help="do not expand --repo to its git root")
    ap.add_argument("--max-lines", type=int, default=DEFAULT_MAX_LINES, help=f"draft line cap (default {DEFAULT_MAX_LINES})")
    ap.add_argument("--cap", type=int, default=40, help="findings printed per doc in text mode (default 40)")
    ap.add_argument("--fail-on-findings", action="store_true", help="exit 1 when any finding stands")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"error: {repo} is not a directory\n")
        return 2
    if not args.no_git_root:
        repo = git_root(repo) or repo

    if args.all or not args.docs:
        targets = drafted_docs(repo)
    else:
        targets = []
        for d in args.docs:
            rel = Path(d).as_posix()
            if not (repo / rel).is_file():
                sys.stderr.write(f"error: {rel} not found under {repo}\n")
                return 2
            targets.append(rel)

    names = env_names(repo) if targets else set()
    findings: list[dict] = []
    for rel in targets:
        findings.extend(check_doc(repo, rel, names, args.max_lines))

    data = {"repo": str(repo), "docs": targets, "findings": findings,
            "total": len(findings), "warnings": warnings}
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render(data, args.cap))
    return 1 if (args.fail_on_findings and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
