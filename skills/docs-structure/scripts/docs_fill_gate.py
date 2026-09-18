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
# An ordered-list marker ends in a full stop and is not a sentence end. Every numbered step in
# a draft was reported as a sentence without evidence - on the shape the DEPLOYMENT template
# asks for by name ("Numbered, from a clean checkout to a live URL").
# A list marker or a version number ending a sentence: "pins express 4.18." is not a
# sentence boundary the draft left unsourced.
LIST_MARKER = re.compile(r"(?:^|\s)\d{1,3}(?:\.\d+)*\.$")
ABBREV = re.compile(r"\b(?:[A-Z]|e\.g|i\.e|etc|vs|cf|approx|Inc|Ltd|Dr|St|No|Fig|Ref)\.$", re.I)
BAD_BREAK = re.compile(r"[^\]`.]\.\s+(?=[A-Z`(])")
# Hyphen-aware: fast-glob, simple-git and secure-compare are names. A hyphen is a word
# character for this purpose even though \b says otherwise.
BANNED = re.compile(r"(?<![\w-])(robust|secure|simple|clean|fast|modern|scalable|easy|powerful|"
                    r"seamless|best|properly|elegant|efficient|reliable)(?![\w-])", re.I)
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
# Five ways to say a thing is absent, not one. The rule was written against the single
# example sentence in SKILL.md and caught that phrasing only: "contains no X", "lacks X",
# "X is absent", "zero X" and "without any X" all read as audited fact and all passed.
NEGATION = re.compile(
    r"\bthere (?:is|are) no\s+\w+"
    r"|\b(?:contains?|has|have|had|includes?|defines?|ships?|provides?|applies|applied|enforces?|enforced|performs?|requires?|required|uses?|implements?|implemented|sets?) no\s+\w+"
    r"|\b(?:lacks?|lacking)\s+\w+"
    r"|\b(?:is|are|was|were)\s+(?:entirely |completely |wholly )?absent\b"
    r"|\bzero\s+\w+"
    r"|\bwithout any\s+\w+"
    r"|\bno\s+\w+(?:\s+\w+){0,2}\s+(?:is|are|was|were)\s+(?:present|configured|defined|set|applied|used|implemented|enabled)\b"
    r"|\bno (?:\w+ ){0,3}(?:exists?|existed|is|are|was|were|found|applies|applied)\s+\w+"
    r"|\b(?:is|are|was|were|does|do|did|has|have|had) not\s+(?!a\b|an\b|the\b)(?!recorded|documented|stated|named|written|commented|described|mentioned)[a-z`\"']\w*"
    r"|\b(?:is|are|was|were)\s+(?:\w+\s+){0,2}(?:missing|nonexistent|non-existent|unauthenticated|unprotected|unvalidated|unchecked|unenforced)\b"
    r"|\bnowhere to be (?:found|seen)\b"
    r"|(?:^|\|\s*)(?:none found|not found|none|n/?a)\s*(?:\||$)"
    r"|\b(?:omits?|omitted|skips?|bypasses)\s+(?:any|all|every)?\s*\w+"
    r"|\bnever\s+\w+|\bnothing\s+\w+|\bnone of\s+\w+|\bno such\s+\w+", re.I)
# A scope is evidence that a search happened: a command, or a named place with a path in it.
# A bare path is not a scope - citing a file says it was read, never that anything was looked
# for - and "under any circumstances" is not a place.
# A scope names a place or a command. The bare word "scan" was enough on its own, so adding
# ", per a scan" to any claim cleared the rule without anyone looking at anything.
# The command needs an argument that is not the evidence bracket. Every drafted sentence ends
# with one, so "[" was always the non-space that followed - and ", per grep" cleared the rule
# exactly as ", per a scan" used to.
SCOPE = re.compile(r"\b(?:grep|rg|ripgrep|git grep)\s+[\"'`]?[\w/*-][\w./*-]*"
                   r"|\b(?:searched|scanned|scan(?:ned)?)\s+(?:every |all |the )?`?[\w.-]*[/.][\w/*-][\w./*-]*"
                   r"|\b(?:under|across|throughout|within)\s+`?[\w.-]*[/.][\w/*-][\w./*-]*", re.I)
SCAN_CMD = re.compile(r"\b(?:grep|rg|ripgrep|git grep|find|wc|ls)\b\s*[-\w`\"']", re.I)
INV_BRACKET = re.compile(r"\[inventory:[ 	]*([^\]]+)\]")
# The keys docs_evidence actually emits.
INVENTORY_KEYS = {"packages", "services", "env", "schema", "routes", "cli", "exports", "frontend",
                  "tests", "ci", "ops", "decisions", "readme", "tree", "release", "kinds",
                  "ecosystems", "warnings"}
KEY_BRACKET = re.compile(r"\[[^\]]+\.[A-Za-z0-9]+:\s*[^\]]+\]")
PATH_SPAN = re.compile(r"`[\w.-]*[\w-]/[\w./*-]+`")
URL_TOKEN = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+")
LINE_CITE = re.compile(r"\.[A-Za-z]{1,5}:\d+")
SHA_REF = re.compile(r"^[0-9a-f]{7,40} \d{4}-\d{2}-\d{2}$")
FENCE = re.compile(r"^ {0,3}(```|~~~)")
# The template's own owner line. It states what the document covers; there is nothing to cite
# for that, so asking it for an evidence bracket makes the lead unwritable.
OWNER_LINE = re.compile(r"^>?\s*\*\*(?:This document owns|Part of)")
# What a doc legitimately writes in a value column: a type, a default marker, a description.
# Shapes that are a credential wherever they appear. Kept in step with docs_evidence.redact().
REDACTABLE = re.compile(r"\b(?:sk|pk|rk)[-_][A-Za-z0-9_-]{16,}|\bAIza[A-Za-z0-9_-]{20,}"
                        r"|\bglpat-[A-Za-z0-9_-]{16,}|\b(?:hf|npm)_[A-Za-z0-9]{20,}"
                        r"|\bghp_[A-Za-z0-9]{20,}|\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"
                        r"|\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")
# A URL, an assignment, a bare number, or a long opaque run. Prose after a colon is not a value.
LOOKS_LIKE_VALUE = re.compile(r"://|=|^\d[\d._-]*$|^[A-Za-z0-9+/_-]{16,}$")
PLACEHOLDER_VALUE = re.compile(r"^(?:-+|—|n/?a|none|unset|empty|required|optional|string|number|bool(?:ean)?|url|path|int|float|secret|token|\.\.\.|<[^>]*>|\{[^}]*\}|\[[^\]]*\])$", re.I)
BULLET = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")
CODESPAN = re.compile(r"`[^`]*`")
TABLE_RULE = re.compile(r"^\|[\s:|-]+\|?$")
HEADING = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
DOC_EXTS = {".md", ".mdx"}
# Pruned before descending, never after: rglob over a repo with node_modules costs half a minute.
# Where [sha date] brackets are resolved. The tree being gated may be a copy without .git,
# so the operator can point this at the original with --git-repo.
SHA_REPO: Path | None = None

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", "__pycache__", ".next",
             "vendor", "target", "coverage", ".tox", ".mypy_cache", ".pytest_cache", "tmp"}
MAX_WALK_DEPTH = 12

warnings: list[str] = []


def safe(text: str) -> str:
    """Never echo a line back raw: a drafted line can quote a value the inventory flagged."""
    return docs_evidence.redact(text) if docs_evidence is not None else text


def read(path: Path) -> str:
    """Text, with a byte-order mark stripped.

    utf-8 rather than utf-8-sig left the BOM on the first line, so the H1 did not match, the
    lead section was never found, and four real violations in it vanished behind an OK. BOMs
    are routine on Windows - PowerShell, VS Code, .NET tooling - and this was written there.
    """
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")
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


def is_git_repo(repo: Path) -> bool:
    """Whether commits can be looked up here at all.

    SKILL.md tells the agent to gate a scratch copy of the tracked files, which has no .git,
    and every [sha date] bracket then failed - so the documented apply path could never finish
    for a doc citing a commit, which ARCHITECTURE, DEPLOYMENT and PRODUCT all do.
    """
    key = str(repo)
    if key in _IS_REPO:
        return _IS_REPO[key]
    if shutil.which("git") is None:
        _IS_REPO[key] = False
        return False
    try:
        p = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        _IS_REPO[key] = False
        return False
    _IS_REPO[key] = p.returncode == 0
    return _IS_REPO[key]


def sha_known(repo: Path, sha: str) -> bool:
    """True when this repository has that commit. Unknown (no git) counts as known: the gate
    reports what it can prove, and never fails a draft because git is missing."""
    git = shutil.which("git")
    if git is None or not is_git_repo(repo):
        return True
    try:
        p = subprocess.run([git, "cat-file", "-e", sha], cwd=str(repo), text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=GIT_TIMEOUT,
                           encoding="utf-8", errors="replace")
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


_GATE_LISTING: dict[str, set[str]] = {}
# Asked once per tree: sha_known calls this for every [sha date] bracket, so a decisions
# section citing twenty commits was spawning forty git processes.
_IS_REPO: dict[str, bool] = {}


def exists_exact(repo: Path, rel: str) -> bool:
    """Case-exact existence, so a draft that works on Windows still works on Linux."""
    target = repo / rel
    if not target.exists():
        return False
    try:
        parts = Path(rel).parts
        here = repo
        for part in parts:
            # One listing per directory, cached, as the checker already does. Without it a
            # 400-row endpoint table in a large folder took eleven seconds.
            key = str(here)
            if key in _GATE_LISTING:
                names = _GATE_LISTING[key]
            else:
                names = {p.name for p in here.iterdir()}
                _GATE_LISTING[key] = names
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
            # The key has to exist. Any [inventory: anything] used to satisfy G10 and switch
            # G9 off, so an invented key was a licence to write an unscoped claim.
            key = part.split(":", 1)[1].strip().split("[")[0].split(".")[0].strip()
            if key and INVENTORY_KEYS and key not in INVENTORY_KEYS:
                return f"no such inventory key: {key}"
            continue
        if SHA_REF.match(part):
            if not sha_known(SHA_REPO or repo, part.split()[0]):
                return f"commit not in this repository: {part}"
            continue
        # A [path: key] bracket asserts the key is in that file. Accepting it unread let
        # "[src/api/admin.js: guard]" clear G10 on the very sentence SKILL.md names as the
        # reason G10 exists, with no guard anywhere in the file.
        if ": " in part and " § " not in part:
            p_, k_ = part.split(": ", 1)
            p_, k_ = p_.strip(), k_.strip()
            if p_ and not p_.startswith(("http://", "https://")) and exists_exact(repo, p_):
                body = read(repo / p_)
                leaf = k_.split(".")[-1].split("[")[0].strip()
                if body and leaf and leaf not in body:
                    return f"{p_} does not contain '{k_}'"
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
    # "services" is absent on purpose: one service described by a Dockerfile and a compose
    # entry is counted twice, so the inventory's number answers a different question from the
    # one a sentence about compose is asking.
    "packages": ("#len", "packages"),
    # "tests", "jobs", "workflows" and "modules" are gone: the inventory holds one row per
    # runner config and one per workflow *file*, so it answers a different question from the
    # one a sentence counting jobs or test files is asking, and blocked true counts.
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
        # "models" gets no authority at all, for the same reason it is absent from
        # COUNT_FIELDS: an ORM model count, a SQL table count and a per-group subtotal are
        # three different numbers, and only the writer knows which one a sentence means.
        out.setdefault("tables", set()).update(str(v) for v in per_tool.values())
        out["tables"].add(str(len(tables)))
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
    # The inventory's own warnings - a depth cap, a capped scan, a detector that failed - change
    # what G9 can know, so a count judged against a truncated scan has to say so.
    for w in inv.get("warnings") or []:
        warnings.append(f"inventory: {w}")
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
    # Fence-aware: a shell comment starting ## used to split the section here, and the rest of
    # the document then ran with in_fence flipped the wrong way - every semantic rule skipped,
    # and the report said nothing blocks a write. The templates ask fill for exact commands,
    # and # comments are ordinary in shell.
    marks = []
    fenced = False
    for i, l in enumerate(lines):
        if FENCE.match(l):
            fenced = not fenced
            continue
        marks.append((i, None if fenced else HEADING.match(l)))
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
              numbers: dict[str, set[str]] | None = None) -> list[dict]:
    """Findings for one doc. Only sections carrying the draft marker are judged."""
    path = repo / rel
    text = read(path)
    if not text:
        return [{"doc": rel, "line": 1, "rule": "G0", "message": "unreadable or empty"}]
    if DRAFT_MARK not in text:
        # Not judged. Returning nothing made the report print OK for a document whose draft
        # marker was mistyped, and silent approval is the one failure a gate must not have.
        return [{"doc": rel, "line": 1, "rule": "G0", "level": "skipped",
                 "message": f"no {DRAFT_MARK} marker; this document was not judged"}]
    lines = text.splitlines()
    found: list[dict] = []
    # An unclosed fence makes everything after it look fenced, and every shape rule is then
    # skipped while the report still says OK. That is not covered by the "Not checked" block:
    # it disclaims truth, not the rules the gate does enforce.
    if not any(HEADING.match(l) and len(HEADING.match(l).group(1)) == 1 for l in lines):
        found.append({"doc": rel, "line": 1, "rule": "G0", "level": "fail",
                      "message": "no H1, so the lead section could not be found and was not judged; a drafted document starts with its title"})
        return found
    if sum(1 for l in lines if FENCE.match(l)) % 2:
        found.append({"doc": rel, "line": 1, "rule": "G0", "level": "fail",
                      "message": "a code fence is never closed, so the rules below it were not "
                                 "applied; balance the fences and run this again"})
        return found

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
        # The lead carries its marker inline on the owner line - the shape every template
        # produces and SKILL.md prescribes - so its last line is prose, the section was skipped,
        # and the report printed OK. A drafted document's lead is drafted.
        # Only when the lead's own owner line carries the marker. Judging it because some other
        # section is still a draft graded prose a person had already reviewed - the one thing the
        # skill promises never to do - and blocked refill on any part-reviewed document.
        if heading == "(lead)" and any(DRAFT_MARK in l for l in lines[start:end]):
            pass
        elif body[-1].strip() != DRAFT_MARK:
            # Not a drafted section, so a person's prose is left alone - but a section inside a
            # drafted document that carries no marker of its own was silently unjudged, and the
            # report then read OK for the whole file.
            if heading != "(lead)" and any(DRAFT_MARK in l for l in lines):
                found.append({"doc": rel, "line": start, "rule": "G0", "level": "skipped",
                              "message": f"section '{safe(heading)}' carries no {DRAFT_MARK} marker, "
                                         f"so it was not judged"})
            continue
        # A paragraph is the unit, not a line: a draft may be hard-wrapped, and the evidence
        # bracket belongs at the end of the paragraph's last line.
        para: list[tuple[int, str]] = []

        def semantics(joined: str, first: int) -> None:
            """G4 to G10, over any drafted text: a paragraph, a bullet, or a table row.

            These used to live inside the paragraph handler, so the format fill is told to write
            for endpoints, services and env names - a table - was judged on G1 to G3 alone. An
            evaluative word, a modal, an invented count and an unscoped negative all reached a
            clean report inside table cells.
            """
            # The evidence bracket is a citation, not the draft's words: a path containing
            # clean/fast/simple made every sentence citing it unwritable.
            bare = CODESPAN.sub("", BRACKET_ANY.sub(" ", joined))
            # Code spans out, then quotations out. A file named fast.js or a dependency called
            # simple-git is a name, not a claim about quality; and a quoted README sentence is the
            # repository's words, which G5 and G6 have always respected. G4 did not, so an
            # attributed quotation - the evidence the fill rules require for PRODUCT.md's first
            # section - was blocked, and the only way past it was to drop the quote.
            unquoted = QUOTED.sub(" ", bare)
            if True:  # noqa: SIM103 - kept to preserve the block's indentation
                # A capitalised word followed by another capitalised word is a name - Modern
                # Treasury, Simple Storage Service, Fast Refresh - and a repo that integrates
                # one could not write a true sentence about it.
                for m_ in BANNED.finditer(unquoted):
                    after = unquoted[m_.end():m_.end() + 40].lstrip()
                    if m_.group(0)[0].isupper() and after[:1].isupper():
                        continue
                    add("G4", first, f"evaluative word: {m_.group(0)}")
                    break
                if MODAL.search(unquoted):
                    add("G5", first, f"modal verb: {MODAL.search(unquoted).group(0)}")
                # A paragraph citing a commit is quoting its subject, which structure.md asks for
                # verbatim - so "drop redis because the latency was unacceptable" is the repo's
                # words, not the draft's reasoning.
                intent_hit = INTENT.search(QUOTED.sub(" ", joined))
                cites_commit = any(SHA_REF.match(r.strip()) for r in BRACKET_ANY.findall(joined))
                if intent_hit and not cites_commit and not joined.lower().startswith("inferred:"):
                    add("G6", first, f"intent word outside a quotation or `inferred:`: {intent_hit.group(0)}")
                # A table cell and a YAML-style colon are both "beside". Matching only NAME=value
                # let a live secret through in the column layout DEPLOYMENT.md asks for.
                for name in names:
                    # `` `? `` after the name: every Markdown table writes identifiers in code
                    # spans, and the closing backtick sat between the name and the separator, so
                    # the one rule that keeps values out of drafts was defeated by ordinary
                    # formatting - in the very table the DEPLOYMENT template asks for.
                    hit = re.search(rf"\b{re.escape(name)}\b`?\s*(?:[=:]|\|)\s*`?([^\s|`]+)", joined)
                    # A value has the shape of one. "Not a placeholder word" made the env table
                    # the DEPLOYMENT template asks for unwritable: a 200-row table produced 112
                    # findings, none of them a value, and whether a row passed depended on
                    # whether the name happened to be in backticks.
                    if hit and not PLACEHOLDER_VALUE.match(hit.group(1)) and LOOKS_LIKE_VALUE.search(hit.group(1)):
                        add("G7", first, f"a value is written beside {name}; drafts carry names, never values")
                # A credential-shaped string is a credential whatever it sits beside: the name
                # in front of it does not have to be one the inventory found.
                tok = REDACTABLE.search(joined)
                if tok:
                    add("G7", first, f"a token-shaped string is written here ({tok.group(0)[:8]}...); drafts carry names, never values")
                # G9: a number the inventory does not report. Brackets carry paths and keys, and
                # code spans carry commands and identifiers, so both are removed first.
                # A draft that names its own scan, or cites the inventory key it counted, has
                # already answered this rule; the message says so and now it is true.
                historical = any(SHA_REF.match(r.strip()) for r in BRACKET_ANY.findall(joined))
                # G9 takes a narrower exemption than G10: naming a folder is a scope for a
                # claim of absence, but it is not a reason to contradict the inventory about a
                # count. Only a scan command or the inventory key itself will do.
                # A sentence that names a subset - "3 endpoints under /admin" - is not claiming
                # the repo-wide total, and the API template asks for exactly that shape, one H3
                # per path prefix.
                # "in" alone accepted "in this repository", which is the whole thing rather
                # than a subset. A subset names a path or a route prefix.
                scoped_count = re.search(
                    r"\b(?:under|within|beneath|across)\s+[`/\w.*-]+"
                    r"|\bin\s+`?[\w.-]*[/.][\w./*-]+", joined)
                # Citing the inventory key means "the inventory says so", so the number has to
                # be the inventory's. It used to switch the rule off without comparing anything,
                # which made [inventory: routes] a licence to write 400.
                inv_cite = INV_BRACKET.search(joined)
                if numbers and not historical and not SCAN_CMD.search(joined):
                    prose = BRACKET_ANY.sub(" ", bare)
                    for m in NUMBER.finditer(prose):
                        raw = m.group(1).replace(",", "")
                        noun = m.group(2).lower()
                        known = numbers.get(noun)
                        # More than three candidate values means the inventory counts this noun
                        # several ways - per file, per tool, and in total - so it cannot say the
                        # draft is wrong. "36 names" against "1 or 2 or 4 or 8 or 34 or 97" is a
                        # rule talking past the sentence.
                        if not known or len(known) > 3 or YEARISH.match(raw) or raw in known:
                            continue
                        # A sentence naming a subset is claiming a subtotal, and a subtotal is
                        # smaller than the total. Larger than the total, it is not a subtotal at
                        # all - naming a folder does not make an impossible number possible.
                        ceiling = max(int(k) for k in known)
                        # A sentence naming a subset, or citing the inventory key it counted, is
                        # claiming a subtotal - and a subtotal is smaller than the total. Above the
                        # total it is not a subtotal at all, which is how [inventory: routes] used
                        # to wave 400 through in a four-route repository.
                        # A path alone is not a scan: "2 routes in `src/api/guard.js`" passed
                        # on a file with none, because the number was under the repo-wide
                        # total. A scoped subtotal needs the scan that produced it; citing the
                        # inventory key is the other way to answer.
                        if ((scoped_count and SCAN_CMD.search(joined)) or inv_cite) and int(raw) <= ceiling:
                            continue
                        add("G9", first,
                            f'the count "{m.group(1)} {noun}" disagrees with the inventory, which reports '
                            f'{" or ".join(sorted(known, key=int))}. One of the two is wrong: name '
                            f'the scan behind your number, cite an [inventory: key], or check the '
                            f"inventory's before using it")
                        break
                # G10: a negative claim without a scope is an audit nobody ran.
                # Scope means a search was run, or a named key was read. A path in backticks is
                # neither: backticking the file in the sentence used to clear this rule without
                # changing a thing about the evidence behind it.
                # Read with code spans still in: stripping them let one pair of backticks around
                # "absent" clear the rule on an otherwise identical sentence. That is the same
                # phrasing plus punctuation, not another phrasing.
                # The backticks come out, the words inside stay. Stripping the whole code span
                # let one pair around "absent" clear the rule on an otherwise identical
                # sentence - the same phrasing plus punctuation, not another phrasing.
                neg = NEGATION.search(BRACKET_ANY.sub(" ", QUOTED.sub(" ", joined)).replace("`", " "))
                # The brackets are evidence, not scope: searching the text with them still in
                # let a command name immediately before one count as a search that ran.
                bracketless = BRACKET_ANY.sub(" ", joined)
                scoped = (SCOPE.search(bracketless) or INV_BRACKET.search(joined)
                          or KEY_BRACKET.search(joined))
                if neg and not scoped:
                    add("G10", first, f"negative claim (\"{neg.group(0)}\") names no scope; say what was searched, or cite an [inventory: key]")

        def flush() -> None:
            if not para:
                return
            first = para[0][0]
            joined = " ".join(t for _, t in para)
            last = para[-1][1]
            bare = CODESPAN.sub("", joined)
            if OWNER_LINE.match(joined.strip()):
                para.clear()
                return
            if not joined.lower().startswith("open question:"):
                if not BRACKET_END.search(last):
                    add("G1", first, f"paragraph does not end with an evidence bracket: {safe(joined[:60])}")
                breaks = [m for m in BAD_BREAK.finditer(bare)
                          if not ABBREV.search(bare[:m.end(0)].rstrip())
                          and not LIST_MARKER.search(bare[:m.end(0)].rstrip())]
                if breaks:
                    add("G1", first, "a sentence inside this paragraph ends without an evidence bracket")
                for ref in BRACKET_ANY.findall(joined):
                    why = resolve_bracket(repo, ref)
                    if why:
                        add("G2", first, why)
                # URLs out first, then look. Skipping any paragraph containing one meant a real
                # citation beside a dashboard link was never reported.
                no_urls = URL_TOKEN.sub(" ", joined)
                if LINE_CITE.search(no_urls):
                    add("G3", first, f"line-number citation: {LINE_CITE.search(no_urls).group(0)}")
                semantics(joined, first)
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
                # A fenced block is not prose, so the style rules stay out of it - but it is
                # exactly where an env example lands, and the templates ask fill for "the exact
                # commands". A secret does not stop being a secret inside three backticks.
                for name in names:
                    # [=:] as outside a fence: NAME: value is compose, k8s and YAML shape, which
                    # is where the DEPLOYMENT template's own evidence comes from.
                    hit = re.search(rf"\b{re.escape(name)}\b`?\s*[=:]\s*`?([^\s`]+)", s_)
                    if hit and not PLACEHOLDER_VALUE.match(hit.group(1)):
                        add("G7", idx + 1, f"a value is written beside {name} inside a fenced block; "
                                           f"drafts carry names, never values")
                if REDACTABLE and REDACTABLE.search(s_):
                    add("G7", idx + 1, "a token-shaped string is written inside a fenced block")
                continue
            n = idx + 1
            # A blockquote is drafted prose - DESIGN_GUIDELINES ships one - and skipping it left
            # every semantic rule blind inside it. Strip the marker and judge the text.
            if s_.startswith(">") and s_.lstrip("> ").strip():
                para.append((n, s_.lstrip("> ").strip()))
                continue
            if not s_ or s_ == DRAFT_MARK or s_.startswith(("#", "<!--", ">")) or TABLE_RULE.match(s_):
                flush()
                continue
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
                # Any cell, not the last: structure.md and the API template both prescribe a
                # guard column after the handler, so the evidence lands mid-row by design.
                m = next((BRACKET_END.search(c) for c in reversed(cells) if BRACKET_END.search(c)), None)
                if not m:
                    add("G1", n, "table row carries no evidence bracket in any cell")
                else:
                    why = resolve_bracket(repo, m.group(1))
                    if why:
                        add("G2", n, why)
                row_no_urls = URL_TOKEN.sub(" ", s_)
                if LINE_CITE.search(row_no_urls):
                    add("G3", n, f"line-number citation: {LINE_CITE.search(row_no_urls).group(0)}")
                # Joined with the pipe intact: G7 reads "name | value" as a value beside a
                # name, and splitting the row on pipes first hid exactly that shape.
                semantics(" | ".join(cells), n)
                continue
            # A bullet is its own claim. Treated as a continuation of the paragraph above, a
            # list of five fabricated statements needed one bracket on the last line to pass
            # G1 - and ARCHITECTURE and DEPLOYMENT both ask fill for exactly that shape.
            if BULLET.match(s_):
                flush()
            para.append((n, s_))
        flush()
    return found


NEAR_MARK = re.compile(r"draft\s*,\s*review\s+me", re.I)


def drafted_docs(repo: Path, near: list[str] | None = None) -> list[str]:
    """Every doc carrying the draft marker. Prunes on the way down: a repository with a
    node_modules tree costs half a minute to walk and holds nothing this gate judges.

    Docs whose marker is close but not exact are appended to `near` rather than ignored.
    """
    out: list[str] = []
    near = near if near is not None else []
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
            text = read(path)
            if DRAFT_MARK in text:
                out.append(path.relative_to(repo).as_posix())
            elif NEAR_MARK.search(text):
                # Meant to be a draft and spelled the marker wrong. Left out of the run it
                # was silently approved: the report printed nothing and the operator read
                # zero findings as permission to write.
                near.append(path.relative_to(repo).as_posix())
    return out


def render(data: dict, cap: int, strict: bool = False, blocked: bool | None = None) -> str:
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
    orphan = [f for f in data["findings"] if f["doc"] not in data["docs"]]
    if orphan:
        # A doc whose marker is misspelled is never in targets, so its finding was counted and
        # never shown - and the reader was told there was nothing to gate.
        lines.append("")
        for f in orphan[:cap]:
            lines.append(f"  {f['doc']}: [{f['rule']}] {f['message']}")
    for w in data["warnings"]:
        lines.append(f"note: {w}")
    blocking = ([f for f in data["findings"] if strict or f.get("level") != "skipped"]
                if blocked is None else ([1] if blocked else []))
    if blocking:
        lines.append("")
        lines.append("Nothing should be written while any finding stands: fix the draft, then run this again.")
    elif data["total"]:
        lines.append("")
        lines.append("The notes above say what was not judged. Nothing here blocks a write.")
    if data["docs"]:
        lines.append("")
        unjudged = sorted(set(COUNT_NOUNS) - set(data.get("count_authorities") or []))
        if unjudged:
            shown = ", ".join(unjudged[:14])
            more = "" if len(unjudged) <= 14 else " and %d more" % (len(unjudged) - 14)
            lines.append("**Counts not judged.** The inventory has no number of its own for these nouns")
            lines.append("in this repository, so a count in front of one of them was not checked: "
                         + shown + more + ".")
            lines.append("")
        lines.append("**Not checked.** G10 is a phrase test: it catches the common ways of writing that")
        lines.append("something is absent, and it will never catch all of them. A clean run is not evidence")
        lines.append("that no unscoped claim of absence got through - read every negative sentence yourself.")
        lines.append("")
        lines.append("Every rule here reads the shape of a sentence. None opens the file in")
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
    ap.add_argument("--git-repo", help="repository to resolve [sha date] brackets against, when the\n                         tree being gated is a copy without .git")
    ap.add_argument("--no-git-root", action="store_true", help="do not expand --repo to its git root")
    ap.add_argument("--max-lines", type=int, default=0, help="draft line cap (default: half the manifest's splitAt, else 250)")
    ap.add_argument("--cap", type=int, default=40, help="findings printed per doc in text mode (default 40)")
    ap.add_argument("--wrote", action="append", default=[], metavar="DOC#SECTION",
                    help="a section this run drafted, as path#Heading. With --strict, only\n                         sections named here are required to carry the marker, so a part-reviewed\n                         document can still be refilled")
    ap.add_argument("--strict", action="store_true",
                    help="treat an unjudged section as a failure; use it after a fill run, "
                         "where a dropped marker is the likeliest slip and unjudged is not clean")
    ap.add_argument("--fail-on-findings", action="store_true", help="exit 1 when any finding stands")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"error: {repo} is not a directory\n")
        return 2
    if not args.no_git_root:
        repo = git_root(repo) or repo

    # SKILL.md says a draft stays under splitAt/2 so it never becomes a split candidate. The
    # gate hardcoded 250 and never read the manifest, so a repo with splitAt 800 got 250.
    if not args.max_lines:
        args.max_lines = DEFAULT_MAX_LINES
        for name in ("docs/structure.json", "docs-structure.json"):
            f = repo / name
            if f.is_file():
                try:
                    split_at = int(json.loads(read(f)).get("splitAt") or 0)
                except Exception:  # a malformed manifest is the checker's finding, not the gate's
                    split_at = 0
                if split_at:
                    args.max_lines = max(50, split_at // 2)
                break
    near_misses: list[str] = []
    if args.all or not args.docs:
        targets = drafted_docs(repo, near_misses)
    else:
        targets = []
        for d in args.docs:
            rel = Path(d).as_posix()
            if not (repo / rel).is_file():
                sys.stderr.write(f"error: {rel} not found under {repo}\n")
                return 2
            targets.append(rel)

    names, numbers = gate_inventory(repo) if targets else (set(), {})
    # The documented apply path gates a scratch copy built from `git ls-files`, which has no
    # .git - so every [sha date] bracket passed unchecked and silently. Say it out loud, and
    # let --git-repo point at the original when the operator has one.
    global SHA_REPO
    SHA_REPO = Path(args.git_repo).expanduser().resolve() if args.git_repo else repo
    if targets and not is_git_repo(SHA_REPO):
        warnings.append("commits were not verified: no git repository here. Pass --git-repo <the real repo> to check [sha date] brackets.")
    findings: list[dict] = []
    # A finding per document citing a commit nobody can check, so --strict refuses rather
    # than passing an invented sha in silence. A note printed under an OK reads as permission.
    if targets and not is_git_repo(SHA_REPO or repo):
        for rel in targets:
            if any(SHA_REF.match(r.strip()) for r in BRACKET_ANY.findall(read(repo / rel))):
                findings.append({"doc": rel, "line": 1, "rule": "G0", "level": "skipped",
                                 "message": "cites a commit, and no git repository is reachable "
                                            "here, so the sha was not checked; pass --git-repo"})
    for rel in near_misses:
        findings.append({"doc": rel, "line": 1, "rule": "G0", "level": "skipped",
                         "message": f"the draft marker is misspelled here, so this document was "
                                    f"not judged; write it exactly as {DRAFT_MARK}"})
    for rel in targets:
        findings.extend(check_doc(repo, rel, names, args.max_lines, numbers))

    # --strict blocks on unjudged sections, but only the ones this run drafted when --wrote
    # names them. Without that, a document with one reviewed section could never be refilled -
    # the messy-middle workflow the design exists for.
    wrote = {w.strip() for w in args.wrote}
    def blocks(f: dict) -> bool:
        if f.get("level") != "skipped":
            return True
        if not args.strict:
            return False
        if not wrote:
            return True
        head = f["message"].split("'")[1] if "'" in f["message"] else ""
        # --wrote names what this run drafted. A skipped section the run did not write is a
        # person's prose and must not block; one it did write and left unmarked must.
        return f"{f['doc']}#{head}" in wrote
    blocking = [f for f in findings if blocks(f)]

    data = {"repo": str(repo), "docs": targets, "findings": findings,
            "count_authorities": sorted(numbers or {}),
            "total": len(findings), "warnings": warnings}
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render(data, args.cap, args.strict, bool(blocking)))
    # G0 rows say what the gate did not judge. They are information, not a defect: failing on
    # them meant a doc with one reviewed section could never be refilled, which is the whole
    # messy-middle workflow.
    # --strict: after a fill run, a section the gate did not judge is not a section that passed.
    # Without it, one dropped marker turned the gate green over prose breaking six of ten rules.
    return 1 if (args.fail_on_findings and blocking) else 0


if __name__ == "__main__":
    raise SystemExit(main())
