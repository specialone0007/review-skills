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
  G9  a count of repository artefacts agrees with the inventory's own number for that noun,
      or the draft names the scan behind it, or cites the inventory key it counted
  G10 a negative claim names a search: a grep, a scanned path, or an inventory key. Citing a
      file is not a search - it says the file was read, never that anything was looked for

G1 to G8 check the shape of a sentence. G9 and G10 are the two shapes that were actually
wrong when drafts were read by hand: a number a second scanner disagrees with, and an
absence nobody looked for. Neither can tell whether a sentence is true - no script can -
but both refuse the sentence that cannot be checked at all.
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
# A sentence that ended mid-paragraph without a bracket before the next one began. An
# abbreviation is not a sentence end: U.S., i.e., etc., vs. and a single initial all carry a
# full stop in the middle of a clause.
ABBREV = re.compile(r"\b(?:[A-Z]|e\.g|i\.e|etc|vs|cf|approx|Inc|Ltd|Dr|St|No|Fig|Ref)\.$", re.I)
BAD_BREAK = re.compile(r"[^\]`.]\.\s+(?=[A-Z`(])")
BANNED = re.compile(r"\b(robust|secure|simple|clean|fast|modern|scalable|easy|powerful|"
                    r"seamless|best|properly|elegant|efficient|reliable)\b", re.I)
INTENT = re.compile(r"\b(so that|because|designed to|ensures|aims to)\b", re.I)
# Case-insensitive like BANNED and INTENT: sentence-start is where a modal actually appears.
MODAL = re.compile(r"\b(should|must|will|guarantees|handles)\b", re.I)
# A count is the weakest sentence a draft can carry: two scanners give two answers and the
# reader cannot tell which one wrote the doc. A number has to be one the inventory reports.
# Things a repository scan counts. A number in front of one of these is an aggregate someone
# has to be able to re-derive; a number in front of anything else is prose (an HTTP 200, a
# 30 s timer, 2 vCPU) and not this rule's business.
COUNT_NOUNS = ("files", "routes", "endpoints", "tables", "columns", "models", "migrations",
               "services", "packages", "tests", "names", "variables", "entries", "folders",
               "directories", "docs", "documents", "commits", "dependencies", "scripts",
               "workflows", "jobs", "queues", "components", "modules", "schemas", "enums",
               "handlers", "workers", "containers", "images", "environments", "rows", "keys")
NUMBER = re.compile(r"(?<![\w.$/-])(\d[\d,]*)(?![\w.%/-])\s+(?:[a-z][a-z-]*\s+){0,2}(" +
                    "|".join(COUNT_NOUNS) + r")\b", re.I)
YEARISH = re.compile(r"^(19|20)\d{2}$")
# A negative claim is the other one. "No guard is applied" reads as an audited fact and the
# gate cannot open the file, so the draft has to say what was looked at instead.
# "continues when it is not." is a clause ending, not a claim of absence, so a negation has to
# be followed by something it denies.
NEGATION = re.compile(
    r"\bthere (?:is|are) no\s+\w+"
    r"|\bno (?:\w+ ){0,3}(?:exists?|existed|is|are|was|were|found|applies|applied)\s+\w+"
    r"|\b(?:is|are|was|were|does|do|did|has|have|had) not\s+(?!a\b|an\b|the\b)(?!recorded|documented|stated|named|written|commented|described|mentioned)[a-z`\"']\w*"
    r"|\bnever\s+\w+|\bnothing\s+\w+|\bnone of\s+\w+|\bno such\s+\w+", re.I)
# A scope is evidence that a search happened: a command, or a named place with a path in it.
# A bare path is not a scope - citing a file says it was read, never that anything was looked
# for - and "under any circumstances" is not a place.
SCOPE = re.compile(r"\b(?:grep|rg|ripgrep|git grep)\b|\bsearched\b|\bscan(?:ned|s|ning)?\b"
                   r"|\b(?:under|across|throughout|within)\s+`?[\w.-]*[/.][\w./*-]*", re.I)
INV_BRACKET = re.compile(r"\[inventory:[ 	]*([^\]]+)\]")
KEY_BRACKET = re.compile(r"\[[^\]]+\.[A-Za-z0-9]+:\s*[^\]]+\]")
PATH_SPAN = re.compile(r"`[\w.-]*[\w-]/[\w./*-]+`")
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


# Which inventory number answers a count of each noun. A count the skill itself cannot produce
# (files, folders, lines) has no entry: the draft has to name its own scan for those.
COUNT_FIELDS: dict[str, tuple] = {
    "routes": ("routes", "count"), "endpoints": ("routes", "count"), "handlers": ("routes", "count"),
    "tables": ("schema", "table_count"),
    # "models" is deliberately absent: an ORM's model count and the SQL table count are two
    # different numbers, and a rule that conflates them flags a correct draft.
    "migrations": ("schema", "migrations", "count"),
    "services": ("#len", "services"), "packages": ("#len", "packages"), "modules": ("#len", "packages"),
    "tests": ("#len", "tests"), "workflows": ("#len", "ci"), "jobs": ("#len", "ci"),
    "dependencies": ("#deps",), "names": ("#env",), "variables": ("#env",), "keys": ("#env",),
}


def inventory_counts(inv: dict) -> dict[str, set[str]]:
    """The number the inventory reports for each countable noun, and nothing else.

    Harvesting every digit in the inventory was not a check: it accepted anything, and because
    the inventory carries the repository's own path, the set changed with the directory a clone
    happened to sit in. One noun, one authority.
    """
    out: dict[str, set[str]] = {}

    def get(path: tuple) -> set[str]:
        if path[0] == "#len":
            v = inv.get(path[1])
            return {str(len(v))} if isinstance(v, list) else set()
        if path[0] == "#env":
            vals = set()
            total = set()
            for entry in inv.get("env") or []:
                names = entry.get("names") or []
                vals.add(str(len(names)))
                total.update(names)
            vals.add(str(len(total)))
            return vals
        if path[0] == "#deps":
            vals = set()
            allx = set()
            for p in inv.get("packages") or []:
                d = p.get("dependencies") or []
                vals.add(str(len(d)))
                allx.update(d)
            vals.add(str(len(allx)))
            return vals
        node: object = inv
        for key in path:
            if not isinstance(node, dict):
                return set()
            node = node.get(key)
        return {str(node)} if isinstance(node, int) else set()

    for noun, path in COUNT_FIELDS.items():
        v = get(path)
        if v:
            out[noun] = v
    routes = inv.get("routes")
    if isinstance(routes, dict) and isinstance(routes.get("items"), list):
        for noun in ("routes", "endpoints", "handlers"):
            out.setdefault(noun, set()).add(str(len(routes["items"])))
    # One schema read by two tools is one set of tables counted twice: a Prisma schema and the
    # SQL baseline generated from it describe the same database. Every per-tool count is a valid
    # answer, so "22 models" and "50 tables" are both true of the same repository.
    tables = (inv.get("schema") or {}).get("tables")
    if isinstance(tables, list):
        per_tool: dict[str, int] = {}
        for t in tables:
            if isinstance(t, dict) and t.get("tool"):
                per_tool[t["tool"]] = per_tool.get(t["tool"], 0) + 1
        for noun in ("tables", "models"):
            out.setdefault(noun, set()).update(str(v) for v in per_tool.values())
            out[noun].add(str(len(tables)))
    # A detector that found nothing has not counted zero of anything: it did not look where this
    # repository keeps them. Buildkite, CircleCI, Zig, Bazel and everything else outside the
    # detector list would otherwise make every count of that noun unwritable.
    return {k: v for k, v in out.items() if v - {"0"}}


def gate_inventory(repo: Path) -> tuple[set[str], dict[str, set[str]] | None]:
    """Variable names for G7 and per-noun counts for G9, from one pass over the repository.

    Counts come back None when the inventory could not be built, which turns G9 off rather
    than failing every draft on a host where the inventory is unavailable.
    """
    if docs_evidence is None:
        warnings.append("docs_evidence.py not found beside this script; G7 and G9 not checked")
        return set(), None
    try:
        inv = docs_evidence.inventory(repo, 400, use_git=False)
    except Exception as exc:  # the gate must never fail because the inventory did
        warnings.append(f"evidence inventory unavailable, G7 and G9 not checked: {type(exc).__name__}")
        return set(), None
    names: set[str] = set()
    for entry in inv.get("env") or []:
        names.update(n for n in entry.get("names", []) if isinstance(n, str))
    return names, inventory_counts(inv)




def sections(lines: list[str]) -> list[tuple[str, int, int]]:
    """(heading text, first body line index, end index) for the lead and every H2.

    The lead - what sits between the H1 and the first H2 - is the most-read paragraph in the
    document and was not gated at all, so an unscoped negative and two modals in it passed
    while the same sentences inside a section were caught.
    """
    marks = [(i, HEADING.match(l)) for i, l in enumerate(lines)]
    h1 = next((i for i, m in marks if m and len(m.group(1)) == 1), None)
    h2 = [(i, m.group(2).strip()) for i, m in marks if m and len(m.group(1)) == 2]
    out = []
    if h1 is not None:
        lead_end = h2[0][0] if h2 else len(lines)
        if lead_end > h1 + 1:
            out.append(("(lead)", h1 + 1, lead_end))
    for n, (i, text) in enumerate(h2):
        end = h2[n + 1][0] if n + 1 < len(h2) else len(lines)
        out.append((text, i + 1, end))
    return out


def check_doc(repo: Path, rel: str, names: set[str], max_lines: int,
              numbers: set[str] | None = None) -> list[dict]:
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
                breaks = [m for m in BAD_BREAK.finditer(bare)
                          if not ABBREV.search(bare[:m.end(0)].rstrip()[:m.end(0)])]
                if breaks:
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
                # G9: a number the inventory does not report. Brackets carry paths and keys, and
                # code spans carry commands and identifiers, so both are removed first.
                # A draft that names its own scan, or cites the inventory key it counted, has
                # already answered this rule; the message says so and now it is true.
                historical = any(SHA_REF.match(r.strip()) for r in BRACKET_ANY.findall(joined))
                if numbers and not historical and not SCOPE.search(joined) and not INV_BRACKET.search(joined):
                    prose = BRACKET_ANY.sub(" ", bare)
                    for m in NUMBER.finditer(prose):
                        raw = m.group(1).replace(",", "")
                        noun = m.group(2).lower()
                        known = numbers.get(noun)
                        if not known or YEARISH.match(raw) or raw in known:
                            continue
                        add("G9", first,
                            f'the count "{m.group(1)} {noun}" disagrees with the inventory, which reports '
                            f'{" or ".join(sorted(known, key=int))}; name the scan behind it, cite an '
                            f"[inventory: key], or use the inventory's number")
                        break
                # G10: a negative claim without a scope is an audit nobody ran.
                # Scope means a search was run, or a named key was read. A path in backticks is
                # neither: backticking the file in the sentence used to clear this rule without
                # changing a thing about the evidence behind it.
                neg = NEGATION.search(BRACKET_ANY.sub(" ", unquoted))
                scoped = (SCOPE.search(joined) or INV_BRACKET.search(joined)
                          or KEY_BRACKET.search(joined))
                if neg and not scoped:
                    add("G10", first, f"negative claim (\"{neg.group(0)}\") names no scope; say what was searched, or cite an [inventory: key]")
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
                # A drafted endpoint table puts the handler and its guard in middle cells;
                # resolving only the last one let a row cite a file that does not exist.
                for cell in cells[:-1]:
                    for ref in BRACKET_ANY.findall(cell):
                        why = resolve_bracket(repo, ref)
                        if why:
                            add("G2", n, why)
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
    if data["docs"]:
        lines.append("")
        lines.append("**Not checked.** Every rule here reads the shape of a sentence. None opens the file in")
        lines.append("the bracket to see whether the sentence about it is true, so a clean run means the draft")
        lines.append("is checkable, not that it is correct. What still needs a person: that each sentence")
        lines.append("matches the code it cites, that a table is complete and not just well formed, and that")
        lines.append("an absence is real. The `*(draft, review me)*` markers say where to start.")
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

    names, numbers = gate_inventory(repo) if targets else (set(), {})
    findings: list[dict] = []
    for rel in targets:
        findings.extend(check_doc(repo, rel, names, args.max_lines, numbers))

    data = {"repo": str(repo), "docs": targets, "findings": findings,
            "total": len(findings), "warnings": warnings}
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render(data, args.cap))
    return 1 if (args.fail_on_findings and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
