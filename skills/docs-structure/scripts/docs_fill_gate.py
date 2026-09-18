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
BAD_BREAK = re.compile(r"[^\]`.][.?!]\s+(?=[A-Z`(])")
# Hyphen-aware: fast-glob, simple-git and secure-compare are names. A hyphen is a word
# character for this purpose even though \b says otherwise.
# The adverb too: "validates input efficiently and securely" is the same claim as the adjective,
# and the trailing lookahead used to let every -ly form through.
BANNED = re.compile(r"(?<![\w-])(robust|secure|simple|simply|clean|fast|modern|scalable|easy|easily|powerful|"
                    r"seamless|best|properly|elegant|efficient|reliable|reliably)(?:ly)?(?![\w-])", re.I)
INTENT = re.compile(r"\b(so that|because|designed to|ensures|aims to|intended to|meant to|in order to)\b", re.I)
# Case-insensitive like BANNED and INTENT: sentence-start is where a modal actually appears.
# "handles" left: "the worker keeps 3 file handles open" is a count of file descriptors, not a
# promise, and it is the ordinary way to write that sentence.
# Contracted and periphrastic too: shouldn't, won't, has to, needs to are how a promise is
# actually written, and the four bare words caught none of them.
MODAL = re.compile(r"\b(should|shouldn't|must|mustn't|will|won't|can't|cannot|shall|may|might|could|would|guarantees|has to|have to|needs? to|ought to)\b", re.I)
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
    # "reach every handler unauthenticated", "no middleware checks", "guarded by nothing", "left
    # out of every route": the sentences a security paragraph is actually made of, and each
    # walked past the shapes above. Still a phrase test, and the report still says so.
    r"|\b(?:unauthenticated|unprotected|unvalidated|unchecked|unenforced|unguarded)\b"
    r"|\bno\s+\w+\s+(?:checks?|verif(?:y|ies)|validates?|guards?|protects?|enforces?|requires?|inspects?)\b"
    r"|\b(?:guarded|protected|checked|validated|covered|backed)\s+by\s+(?:nothing|no one|nobody|none)\b"
    r"|\bleft out\b|\bopted out\b|\bturned off\b|\bdisabled\b(?!\s+by)"
    # The broad shape, after four rounds of narrow ones: a sentence that opens with "No" or
    # "Without" is a claim of absence until proven otherwise. A false hit costs one rewrite;
    # a miss puts an audited-sounding security claim in a document nobody audited.
    r"|(?:^|[.!?]\s+)(?:no|without)\s+(?!one\b|longer\b|doubt\b|matter\b|more\b)\w+"
    # "run with no guard", "ships without a check": the mid-sentence forms of the same claim.
    r"|\bwith no\s+\w+|\bwithout\s+(?!--)(?:(?:a|an|any|the)\s+)?\w+"
    # "is skipped on every route", "is off for", "only the login route checks": three more
    # sentences a security paragraph is made of. The report still says this is a phrase test.
    r"|\b(?:is|are|was|were|remains?|stays?)\s+(?:skipped|disabled|off|absent|omitted|bypassed|unset)\b(?!\s+by)"
    r"|\bonly\s+(?:the\s+)?\w+(?:\s+\w+){0,2}\s+(?:checks?|requires?|guards?|verif(?:y|ies)|validates?|enforces?|protects?)\b"
    r"|\bnowhere to be (?:found|seen)\b"
    # "none found" in a table cell is the wording structure.md and the API template hand fill for
# the guard column. It is a finding in prose, where it is a claim; in a cell it is the column's
# own vocabulary, and blocking it made the prescribed table unwritable row by row.
                                  r"|(?<!\| )(?<!\|)\b(?:nothing found|none found|not found anywhere)\b"
    r"|\b(?:omits?|omitted|skips?|bypass(?:es|ed)?)\s+(?:any|all|every)?\s*\w+"
    r"|\bnever\s+\w+|\bnothing\s+\w+|\bnone of\s+\w+|\bno such\s+\w+", re.I)
# A scope is evidence that a search happened: a command, or a named place with a path in it.
# A bare path is not a scope - citing a file says it was read, never that anything was looked
# for - and "under any circumstances" is not a place.
# A scope names a place or a command. The bare word "scan" was enough on its own, so adding
# ", per a scan" to any claim cleared the rule without anyone looking at anything.
# The command needs an argument that is not the evidence bracket. Every drafted sentence ends
# with one, so "[" was always the non-space that followed - and ", per grep" cleared the rule
# exactly as ", per a scan" used to.
# A quoted pattern or a path-shaped argument: "per grep everywhere" is a word, not a search,
# and it cleared this the same way ", per a scan" once did.
SCOPE = re.compile(r"\b(?:grep|rg|ripgrep|git grep)\s+(?:-\S+\s+)*(?:[\"'`][^\"'`]+[\"'`]|[\w.*-]*[/.][\w./*-]+)"
                   r"|\b(?:searched|scanned|scan(?:ned)?)\s+(?:every |all |the )?`?[\w.-]*[/.][\w/*-][\w./*-]*"
                   # The trailing segment is optional: `src/` names a folder, and refusing it asked the author to
# write a less precise scope than the one they had.
                   r"|\b(?:under|across|throughout|within)\s+`?[\w.-]*[/.][\w./*-]*", re.I)
# The same argument test SCOPE already makes. "[-\w`\"']" after the verb meant the English
# word find cleared the count rule: "Developers find 400 routes in this service" named no scan
# and ran nothing, and G9 stopped looking at the number.
SCAN_CMD = re.compile(r"\b(?:grep|rg|ripgrep|git grep|find|wc|ls)\b\s+(?:-\S+\s+)*"
                      r"(?:[\"'`][^\"'`]+[\"'`]|[\w.*-]*[/.][\w./*-]+)", re.I)
SCAN_PATTERN_BEFORE = re.compile(r"\b(?:grep|rg|ripgrep|git grep|find|ag|ack)\s+(?:-\S+\s+)*$", re.I)
INV_BRACKET = re.compile(r"\[inventory:[ 	]*([^\]]+)\]")
# The keys docs_evidence actually emits.
INVENTORY_KEYS = {"packages", "services", "env", "schema", "routes", "cli", "exports", "frontend",
                  "tests", "ci", "ops", "decisions", "readme", "tree", "release", "kinds",
                  "ecosystems", "warnings"}
KEY_BRACKET = re.compile(r"\[[^\]]+\.[A-Za-z0-9]+:\s*[^\]]+\]")
URL_TOKEN = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+")
# Source extensions only: ".com:5432" and "redis.io:6379" are a host and a port, and a
# DEPLOYMENT draft is told to state them. The checker's R7 makes the same distinction.
LINE_CITE = re.compile(r"\.(?:ts|tsx|js|jsx|mjs|cjs|py|sql|go|rs|java|kt|kts|rb|php|cs|ex|exs|swift|c|h|cpp|hpp|vue|svelte|sh|ps1|yaml|yml|toml|json|md|mdx):\d+\b"
                       r"|\b(?:Makefile|Dockerfile|Procfile|Justfile|\.env(?:\.[\w-]+)?):\d+\b")
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
# Names that say the value beside them is a credential. Kept in step with
# docs_evidence.SECRET_NAME, which is what the inventory flags as secret_like.
SECRET_NAME = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|API_KEY|APIKEY|CREDENTIAL|AUTH)", re.I)
# What a secret_like column holds instead of a value: structure.md asks for that flag, and it
# is a yes or a no, not a password.
FLAG_VALUE = re.compile(r"^(?:yes|no|y|n|true|false|server|client|build|runtime|redacted|hidden|masked|server-only|client-only|build-time|build-only|internal|public|private)$", re.I)
# How a description of a variable starts. "One word or it is prose" let a value through the
# moment anything followed it - "hunter2 (dev only)", "hunter2 in development" - which is how
# a password is actually written down. The first token is the value unless the field opens
# like a sentence about the variable rather than the variable's contents.
# What a value looks like when it is not a URL or a long run: a digit, an underscore, or a case
# change inside the word. Ordinary English has none of these.
VALUE_SHAPED = re.compile(r"\d|_|[a-z][A-Z]")
# The header of the table being read, so a cell is judged by its column: under "where" or
# "service" a single word is a place, under "value" or "default" it is a value.
_TABLE_HEADER: dict[str, list[str]] = {}
DESCRIPTIVE_COLUMN = re.compile(r"where|service|scope|env|owner|source|secret|sensitive|note|description|purpose|read by|used by|type|kind|required|meaning|read in")
VALUE_COLUMN = re.compile(r"value|default|example|sample")
PROSE_LEAD = frozenset("""a an the this that these those its it their your our any each every some no not
one two only same both either neither used use uses set sets setting generated provided supplied issued
created chosen picked derived read reads holds hold points identifies controls enables disables selects
defaults default must may can should will when where whether if for from in on at by with without
name names value values how what which see whatever per as of to and or but so then also""".split())
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
             "vendor", "target", "coverage", ".tox", ".mypy_cache", ".pytest_cache"}
MAX_WALK_DEPTH = 12

warnings: list[str] = []


def safe(text: str) -> str:
    """Never echo a line back raw: a drafted line can quote a value the inventory flagged."""
    return docs_evidence.redact(text) if docs_evidence is not None else text


# Every heading each gated document has, filled by check_doc, read when --wrote is compared.
_HEADINGS_SEEN: dict[str, list[str]] = {}
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "references" / "templates"
_TEMPLATE_LINES: set[str] | None = None


def is_template_text(candidate: list[str]) -> bool:
    """Lines the bundled templates ship, verbatim.

    TASKLIST and DESIGN_GUIDELINES carry unbracketed prose in their leads by design, so the
    moment fill flipped the owner line the template's own words failed G1, G2 and G10 - the
    plan and design concerns could not be filled at all, and "never rewrite template prose"
    and "the gate must be clean" contradicted each other with no way out.
    """
    global _TEMPLATE_LINES
    if _TEMPLATE_LINES is None:
        _TEMPLATE_LINES = set()
        try:
            for p in sorted(TEMPLATES_DIR.glob("*.md")):
                for l in read(p).splitlines():
                    t = l.strip()
                    if not t:
                        continue
                    # A blockquote reaches the rules with its "> " taken off - the gate judges
                    # the text, not the marker - so the quoted form has to be here as well, or
                    # DESIGN_GUIDELINES' own golden rule failed G1 and G10.
                    _TEMPLATE_LINES.add(t)
                    if t.startswith(">"):
                        _TEMPLATE_LINES.add(t.lstrip("> ").strip())
        except OSError:
            pass
    text = [l.strip() for l in candidate if l.strip()]
    return bool(text) and bool(_TEMPLATE_LINES) and all(t in _TEMPLATE_LINES for t in text)


def read(path: Path) -> str:
    """Text, with a byte-order mark stripped.

    utf-8 rather than utf-8-sig left the BOM on the first line, so the H1 did not match, the
    lead section was never found, and four real violations in it vanished behind an OK. BOMs
    are routine on Windows - PowerShell, VS Code, .NET tooling - and this was written there.
    """
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        # PowerShell 5.1's ">" writes UTF-16LE. Read as UTF-8 with errors replaced, such a
        # file became NUL-laden text with no heading, no owner line and no anchors - and every
        # rule then failed it, in silence. The BOM says what it is; decode it as that.
        raw = path.read_bytes()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return raw.decode("utf-16", errors="replace")
        return raw.decode("utf-8-sig", errors="replace")
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


def _norm(text: str) -> str:
    return " ".join(text.split()).casefold()


_QUOTE_SRC: dict[str, str] = {}


def quote_sources(repo: Path, refs: list[str]) -> list[str]:
    """The text a paragraph's brackets point at: cited files, and the messages of cited commits.

    A quotation used to switch G4, G5, G6, G9 and G10 off on the theory that quoted words are
    the repository's own - and nothing ever checked that they were. Wrapped in quotes, the
    exact sentence SKILL.md names as the reason G10 exists passed under the prescribed command,
    beside two invented counts, in a repo with zero routes. A quote is the repository's words
    only when the repository can be shown to contain them.
    """
    out: list[str] = []
    for ref in refs:
        r = ref.strip()
        if r.lower().startswith("inventory:"):
            continue
        if SHA_REF.match(r):
            sha = r.split()[0]
            key = "sha:" + sha
            if key not in _QUOTE_SRC:
                git = shutil.which("git")
                body = ""
                if git is not None and is_git_repo(SHA_REPO or repo):
                    try:
                        p = subprocess.run([git, "show", "-s", "--format=%B", sha], cwd=str(SHA_REPO or repo),
                                           text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                           timeout=GIT_TIMEOUT, encoding="utf-8", errors="replace")
                        body = p.stdout if p.returncode == 0 else ""
                    except (OSError, subprocess.SubprocessError):
                        body = ""
                _QUOTE_SRC[key] = _norm(body)
            out.append(_QUOTE_SRC[key])
            continue
        for sep in (" § ", "§", ": "):
            if sep in r:
                r = r.split(sep, 1)[0].strip()
                break
        for part in r.split(";"):
            path = part.strip().strip("`")
            if not path:
                continue
            key = "file:" + path
            if key not in _QUOTE_SRC:
                try:
                    _QUOTE_SRC[key] = _norm(read(repo / path)) if (repo / path).is_file() else ""
                except OSError:
                    _QUOTE_SRC[key] = ""
            out.append(_QUOTE_SRC[key])
    return [o for o in out if o]


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
                # A whole token, not a substring: scripts.build matched the word "esbuild" in a
                # dependency list, so a key that does not exist passed on a common word.
                leaf = k_.split(".")[-1].split("[")[0].strip()
                if body and leaf and not re.search(rf"\b{re.escape(leaf)}\b", body):
                    return f"{p_} does not contain '{k_}'"
                if body and p_.lower().endswith(".json") and "." in k_:
                    try:
                        node = json.loads(body)
                        for part_ in k_.split("."):
                            node = node[part_.split("[")[0]]
                    except Exception:
                        return f"{p_} has no key '{k_}'"
        path = re.split(r" § |: ", part, maxsplit=1)[0].strip()
        if path.startswith(("http://", "https://")):
            # SKILL.md calls the bracket grammar closed. A link to a dashboard is not evidence
            # from this repository, and accepting it made any claim citable.
            return f"a URL is not repository evidence: {path[:40]}"
        if path.startswith("^"):
            # SKILL.md calls the bracket grammar closed. A footnote reference points at a
            # footnote, not at the repository, and it was satisfying the evidence rule.
            return f"a footnote marker is not evidence: [{path[:20]}]"
        if not path or path.startswith("!"):
            continue
        if not exists_exact(repo, path):
            if ".." in path.replace(chr(92), "/").split("/"):
                return f"a cited path may not leave the repository: {path}"
            return f"cited path does not exist: {path}"
        if " § " in part:
            heading = part.split(" § ", 1)[1].strip().lower()
            if Path(path).suffix.lower() not in DOC_EXTS:
                return f"a § heading can only point into a Markdown file, not {path}"
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
        # One subtotal per path prefix, one and two segments deep: the shape a drafted
        # API_REFERENCE is asked to write, under an "@" key no noun can collide with.
        per: dict[str, int] = {}
        for it in routes["items"]:
            parts = [x for x in str(it.get("path") or "").split("/") if x]
            for depth in (1, 2):
                if len(parts) >= depth:
                    key = "/" + "/".join(parts[:depth])
                    per[key] = per.get(key, 0) + 1
        for pre, n in per.items():
            for noun in ("routes", "endpoints", "handlers"):
                out.setdefault(f"{noun}@{pre}", set()).add(str(n))
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

    _HEADINGS_SEEN[rel] = [h for h, _, _ in sections(lines)]
    for heading, start, end in sections(lines):
        body = [l for l in lines[start:end] if l.strip()]
        if not body:
            continue
        # a section still holding only its template italic line is a skeleton, not a draft
        # The template's guide line, and only that. The shape test - starts and ends with "*" -
        # also matched **No authentication guard is applied to any handler.**, so a section
        # holding one bold sentence was skipped as a skeleton: no marker, no bracket, an
        # unscoped absence, and no G0 for --strict to see. The gate's own docstring calls
        # silent approval the one failure it must not have.
        one = body[0].strip() if len(body) == 1 else ""
        italic_only = (one.startswith("*") and one.endswith("*") and not one.startswith("**")
                       and not one.endswith("**") and one != DRAFT_MARK)
        if one and one != DRAFT_MARK and (is_template_text([one]) or italic_only):
            continue
        # A section holding the marker and nothing else said "drafted" and carried no draft.
        # SKILL.md asks for a sentence or an `open question:` line; silence is neither.
        if len(body) == 1 and body[0].strip() == DRAFT_MARK:
            found.append({"doc": rel, "line": start, "rule": "G1", "section": heading,
                          "message": f"section '{safe(heading)}' carries the {DRAFT_MARK} marker "
                                     "and no content; write a sentence with its evidence, or one "
                                     "`open question:` line"})
            continue
        # The lead carries its marker inline on the owner line - the shape every template
        # produces and SKILL.md prescribes - so its last line is prose, the section was skipped,
        # and the report printed OK. A drafted document's lead is drafted.
        # Only when the lead's own owner line carries the marker. Judging it because some other
        # section is still a draft graded prose a person had already reviewed - the one thing the
        # skill promises never to do - and blocked refill on any part-reviewed document.
        # The lead is judged on its own marker. When it has prose beyond the owner line and no
        # marker, in a document that carries one elsewhere, it is reported as unjudged instead -
        # a fill run that forgot to flip the owner line used to come back clean under --strict.
        if heading == "(lead)" and any(DRAFT_MARK in l for l in lines[start:end]):
            pass
        # An HTML comment is not prose. Every template ships one - <!-- concern: deploy; fill:
        # ... --> - so the moment a person reviewed the owner line and took its marker off, the
        # lead "carried prose", the finding had no section for --wrote to name, and refill on
        # that document exited 1 for ever. That is the messy-middle case the skill is for.
        elif heading == "(lead)" and DRAFT_MARK in text and len(
                [l for l in body if not OWNER_LINE.match(l.strip())
                 and not l.strip().startswith("<!--")]) > 0:
            found.append({"doc": rel, "line": start, "rule": "G0", "level": "skipped",
                          "section": "(lead)",
                          "message": "the lead carries prose and no " + DRAFT_MARK + " marker, "
                                     "so it was not judged; flip the owner line if fill wrote it"})
            continue
        elif body[-1].strip() != DRAFT_MARK:
            # Not a drafted section, so a person's prose is left alone - but a section inside a
            # drafted document that carries no marker of its own was silently unjudged, and the
            # report then read OK for the whole file.
            if heading != "(lead)" and any(DRAFT_MARK in l for l in lines):
                found.append({"doc": rel, "line": start, "rule": "G0", "level": "skipped",
                              # The heading goes in a field of its own. Parsing it back out of
                              # the message broke on any heading with an apostrophe - "Who it's
                              # for" became "Who it" - so --wrote never matched and a dropped
                              # marker passed under --strict.
                              "section": heading,
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
            # Code spans first. `app/[slug]/page.tsx` and `req.params[id]` are a Next.js route
            # and an array index; read as evidence brackets they sent G2 looking for files
            # called slug and id, so every correct sentence about a dynamic route was blocked.
            nospan = CODESPAN.sub(" ", joined)
            bare = BRACKET_ANY.sub(" ", CODESPAN.sub("", joined))
            # Code spans out, then quotations out. A file named fast.js or a dependency called
            # simple-git is a name, not a claim about quality; and a quoted README sentence is the
            # repository's words, which G5 and G6 have always respected. G4 did not, so an
            # attributed quotation - the evidence the fill rules require for PRODUCT.md's first
            # section - was blocked, and the only way past it was to drop the quote.
            # Only a quotation the cited sources contain is stripped. One they do not is reported
            # and then judged as ordinary prose, so the rules below see it.
            # The argument of a scan command - grep "rate" src/ - is a pattern, not a quotation:
            # it names what was searched for and is not expected to appear anywhere.
            quotes = [m.group(0)[1:-1] for m in QUOTED.finditer(nospan)
                      if m.group(0)[1:-1].strip() and not SCAN_PATTERN_BEFORE.search(nospan[:m.start()])]
            sources = quote_sources(repo, BRACKET_ANY.findall(nospan)) if quotes else []
            unsourced = [q for q in quotes if not any(_norm(q) in src for src in sources)]
            for q in unsourced[:2]:
                add("G2", first, f'quoted text is not in any cited source: "{safe(q[:50])}" - a quotation '
                                 "has to appear verbatim in a cited file or commit message")
            qsub = (lambda t: QUOTED.sub(" ", t)) if quotes and not unsourced else (lambda t: t)
            unquoted = qsub(bare)
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
            intent_hit = INTENT.search(qsub(joined))
            cites_commit = any(SHA_REF.match(r.strip()) for r in BRACKET_ANY.findall(nospan))
            if intent_hit and not cites_commit and not joined.lower().startswith("inferred:"):
                add("G6", first, f"intent word outside a quotation or `inferred:`: {intent_hit.group(0)}")
            # A table cell and a YAML-style colon are both "beside". Matching only NAME=value
            # let a live secret through in the column layout DEPLOYMENT.md asks for.
            for name in names:
                # `` `? `` after the name: every Markdown table writes identifiers in code
                # spans, and the closing backtick sat between the name and the separator, so
                # the one rule that keeps values out of drafts was defeated by ordinary
                # formatting - in the very table the DEPLOYMENT template asks for.
                # The whole field after the separator, not its first token: whether a table
                # cell is a value or a description is the difference between one word and a
                # sentence, and the rule has to be able to tell them apart.
                # A table row is read cell by cell. The regex below reads the one field after the
                # name, and structure.md asks for name, service, secret_like, then the rest - so
                # hunter2 in the fourth column, and 3000 beside PORT, were never looked at, in
                # the exact layout the skill prescribes.
                if joined.lstrip().startswith("|"):
                    cells = [c.strip() for c in joined.strip().strip("|").split("|")]
                    at = next((i for i, c in enumerate(cells) if re.search(rf"\b{re.escape(name)}\b", c)), None)
                    if at is None:
                        continue
                    header = _TABLE_HEADER.get("cells") or []
                    for offset, cell in enumerate(cells[at + 1:], start=at + 1):
                        column = header[offset] if offset < len(header) and len(header) == len(cells) else ""
                        words = BRACKET_ANY.sub(" ", cell).replace("`", " ").split()
                        if not words:
                            continue
                        val = words[0].rstrip(".,;")
                        if PLACEHOLDER_VALUE.match(val) or FLAG_VALUE.match(val):
                            continue
                        # A one-word cell, or a first word that looks like a value - a digit, an
                        # underscore, a case change inside it. "signs session tokens" is a
                        # description and the env table is unwritable if it is flagged;
                        # "hunter2 (dev only)" is a value with a remark after it.
                        # "web" under "where" is a place; "changeme" under "value" is a value. Without a
                        # header, or under a column that says value, one word is a value.
                        descriptive = bool(DESCRIPTIVE_COLUMN.search(column)) and not VALUE_COLUMN.search(column)
                        secretish = bool(SECRET_NAME.search(name)) and (
                            bool(VALUE_SHAPED.search(val)) or (len(words) == 1 and not descriptive))
                        valueish = any(LOOKS_LIKE_VALUE.search(w_.rstrip(".,;")) for w_ in words)
                        if secretish or valueish:
                            add("G7", first, f"a value is written beside {name}; drafts carry names, never values")
                            break
                    continue
                # No separator at all: "defaults to hunter2", "is set to hunter2", "ships as" -
                # the shapes a sentence about a variable actually takes. Beside a secret-shaped
                # name the word after the verb is judged like a value after a colon.
                if SECRET_NAME.search(name):
                    said = re.search(rf"\b{re.escape(name)}\b`?(?:\s+\w+){{0,3}}?\s+(?:defaults?\s+to|is\s+set\s+to|set\s+to|ships\s+as|equals|is|becomes|reads\s+as|comes\s+as|starts\s+as)\s+`?([^\s`\[|]+)", joined, re.I)
                    # A parenthetical or an appositive right after the name: "`JWT_SECRET` (changeme in
                    # development)", "`JWT_SECRET`, changeme in development,". Inside those the
                    # first word is the value unless it opens like a sentence.
                    said = said or re.search(rf"\b{re.escape(name)}\b`?\s*(?:\(|,)\s*`?([^\s`\[|),]+)", joined)
                    # The imperative puts the verb first: "Set `ADMIN_TOKEN` to hunter2 before starting".
                    said = said or re.search(rf"\b(?:set|export|put|use|pass|provide)\s+`?{re.escape(name)}`?\s+(?:to|as|=)\s+`?([^\s`\[|]+)", joined, re.I)
                    if said:
                        val = said.group(1).rstrip(".,;")
                        if not (PLACEHOLDER_VALUE.match(val) or FLAG_VALUE.match(val) or val.lower() in PROSE_LEAD):
                            add("G7", first, f"a value is written beside {name}; drafts carry names, never values")
                            continue
                hit = re.search(rf"\b{re.escape(name)}\b`?\s*([=:]|\|)\s*([^|\[\n]*)", joined)
                if not hit:
                    continue
                sep = hit.group(1)
                words = hit.group(2).replace("`", " ").split()
                if not words:
                    continue
                val = words[0].rstrip(".,;")
                if PLACEHOLDER_VALUE.match(val):
                    continue
                # A value has the shape of one. "Not a placeholder word" made the env table
                # the DEPLOYMENT template asks for unwritable: a 200-row table produced 112
                # findings, none of them a value, and whether a row passed depended on
                # whether the name happened to be in backticks.
                # But shape alone only catches a long opaque run, a URL or a second "=", and
                # a dev credential is a short ordinary word: postgres, changeme, admin,
                # hunter2 all passed, in the very table this rule exists for. Beside a name
                # that says secret, token, password or key, anything that is not a
                # placeholder is a value. An "=" assigns whatever follows it; after a colon
                # or in a table cell the field has to be that one word alone, or it is prose
                # about the variable rather than its value.
                secretish = (bool(SECRET_NAME.search(name)) and not FLAG_VALUE.match(val)
                             and (sep == "=" or len(words) == 1
                                  or val.lower() not in PROSE_LEAD))
                if secretish or LOOKS_LIKE_VALUE.search(val):
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
            # A commit citation used to switch this rule off entirely, and ARCHITECTURE and
            # DEPLOYMENT drafts cite commits by design - so every count in them went
            # unchecked, and "400 routes [1b6fea9 2026-09-18]" passed in a five-route repo.
            # What the commit licenses is its own words, so the quotation is what is
            # exempt, not the paragraph around it.
            if numbers and not SCAN_CMD.search(joined):
                prose = qsub(BRACKET_ANY.sub(" ", bare))
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
                    # The API template asks for one H3 per path prefix, so "2 routes under
                    # `/admin`" is the prescribed sentence - and it was blocked against the
                    # repo-wide total on every prefix of every drafted API doc. The inventory
                    # knows each route's path, so it can answer the question actually asked.
                    if scoped_count:
                        pre = re.search(r"(/[\w./*-]+)", scoped_count.group(0))
                        sub = numbers.get(f"{noun}@{pre.group(1).rstrip('/')}") if pre else None
                        if sub and raw in sub:
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
            neg = NEGATION.search(BRACKET_ANY.sub(" ", qsub(joined)).replace("`", " "))
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
            if OWNER_LINE.match(joined.strip()) or is_template_text([t for _, t in para]):
                para.clear()
                return
            if not joined.lower().startswith("open question:"):
                # A code span ending in "]" is not an evidence bracket either, and it used to
                # satisfy this rule: `app/[slug]/page.tsx` at the end of a paragraph passed.
                if not BRACKET_END.search(CODESPAN.sub(" ", last)):
                    add("G1", first, f"paragraph does not end with an evidence bracket: {safe(joined[:60])}")
                breaks = [m for m in BAD_BREAK.finditer(bare)
                          if not ABBREV.search(bare[:m.end(0)].rstrip())
                          and not LIST_MARKER.search(bare[:m.end(0)].rstrip())]
                if breaks:
                    add("G1", first, "a sentence inside this paragraph ends without an evidence bracket")
                for ref in BRACKET_ANY.findall(CODESPAN.sub(" ", joined)):
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
                if REDACTABLE.search(s_):
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
                    _TABLE_HEADER["cells"] = [c.strip().lower() for c in s_.strip().strip("|").split("|")]
                    continue  # header row
                if is_template_text([s_]):
                    continue  # the template's own legend row
                cells = [c.strip() for c in s_.strip("|").split("|")]
                # A drafted endpoint table puts the handler and its guard in middle cells;
                # resolving only the last one let a row cite a file that does not exist.
                for cell in cells[:-1]:
                    for ref in BRACKET_ANY.findall(CODESPAN.sub(" ", cell)):
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
                # With the outer pipes too, so the rules can tell a row from a sentence and read
                # it cell by cell.
                semantics("| " + " | ".join(cells) + " |", n)
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
    # The verdict goes last, because SKILL.md says the last line carries it and because a
    # reader who stops at the first sentence that looks like a conclusion stops at the wrong
    # one. The boilerplate below is context for the verdict, so it comes first.
    verdict = ("Nothing should be written while any finding stands: fix the draft, then run this again."
               if blocking else
               "The notes above say what was not judged. Nothing here blocks a write." if data["total"] else
               "No finding. Nothing here blocks a write.")
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
        lines.append("**Quotations.** Text in quotation marks is exempt from G4, G5, G6, G9 and G10 only")
        lines.append("when it appears verbatim in a file or commit the same paragraph cites; otherwise it is")
        lines.append("reported and then judged as ordinary prose. Whether the quote is fairly chosen is not")
        lines.append("checked.")
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
        lines.append("")
        lines.append("**Values.** G7 reads the field beside a variable name. Where the name says")
        lines.append("secret, token, password or key: a one-word field is a value; a longer one is a value")
        lines.append("when its first word carries a digit or an underscore, or follows a verb such as")
        lines.append("\"defaults to\" or an opening bracket - and a description that happens to start with")
        lines.append("an English word (letmein in development) will not be reported.")
    if verdict:
        lines.append("")
        lines.append(verdict)
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
    # Compared on a slug: lower-case, one space, no punctuation at the ends. The exact-string
    # test made the prescribed command one typo away from the unsafe state - "#setup" for a
    # heading "Setup" matched nothing, the unmarked section read as a person's prose, and the
    # run exited 0 saying nothing blocked a write.
    def slug(s: str) -> str:
        # The message promises that case and punctuation do not matter, so "who its for" has
        # to reach "Who it's for": everything that is not a word character, a slash, a dot,
        # a dash or the "#" comes out, then spacing is collapsed.
        doc, _, head = s.strip().replace("\\", "/").partition("#")
        # An apostrophe joins - "it's" and "its" are the same slug - and every other mark is a
        # space, so "Setup - Run" and "Setup Run" are too.
        head = re.sub(r"['\u2019]", "", head)
        head = re.sub(r"[^\w\s]", " ", head)
        return doc.lower() + "#" + " ".join(head.lower().split())

    wrote = {slug(w) for w in args.wrote}
    # And an entry that names no section this run saw is reported. Two agents can spell a
    # heading two ways; the gate says which one the document actually has.
    seen = {slug(f"{f['doc']}#{f['section']}") for f in findings if f.get("section")}
    seen |= {slug(f"{rel}#{h}") for rel in targets for h in _HEADINGS_SEEN.get(rel, ())}
    for w in sorted(wrote - seen):
        doc = w.split("#", 1)[0]
        findings.append({"doc": doc, "line": 1, "rule": "G0", "level": "fail",
                         "message": f"--wrote {w} names no section in that document; the heading has to "
                                    "match the H2 text (case and punctuation do not matter)"})
    def blocks(f: dict) -> bool:
        if f.get("level") != "skipped":
            return True
        if not args.strict:
            return False
        if not wrote:
            return True
        # A document-level G0 - a misspelled marker, a commit nobody could verify - has no
        # section, and --wrote is about sections. Comparing "doc#" against the list meant the
        # prescribed command switched those protections off: a typo in the marker passed.
        head = f.get("section")
        if not head:
            return True

        # --wrote names what this run drafted. A skipped section the run did not write is a
        # person's prose and must not block; one it did write and left unmarked must.
        return slug(f"{f['doc']}#{head}") in wrote
    blocking = [f for f in findings if blocks(f)]

    data = {"repo": str(repo), "docs": targets, "findings": findings,
            # The per-prefix subtotals are an internal answer to one question, not a noun a
            # draft can write, so they do not belong in the list of what the gate can judge.
            "count_authorities": sorted(k for k in (numbers or {}) if "@" not in k),
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
