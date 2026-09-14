#!/usr/bin/env python3
"""Check the shape of a repository's Markdown documentation.

Read-only. Standard library only. Writes nothing.

    python docs_structure.py                        # text report, repo = git root of cwd
    python docs_structure.py --repo ../other
    python docs_structure.py --format json
    python docs_structure.py --propose-manifest     # print a manifest to start from
    python docs_structure.py --check-paths          # also check backticked repo paths (noisy)
    python docs_structure.py --fail-on-findings     # exit 1 when any rule fails (CI gate)

Eleven mechanical rules, each with a fixed severity. None of them judges prose.

  R1  every doc is reachable in one hop: linked from the central index, or from the
      index that sits beside its folder. No central index at all is ONE finding.
  R2  a doc says what it owns: a marked line near the top, or a frontmatter description
  R3  a doc over `splitAt` lines is a candidate for an index plus parts. The script
      only analyses whether and where it could be cut; it never cuts.
  R4  an index and its folder agree: every doc in the folder is linked from the index
  R5  links resolve: relative links, heading anchors (GitHub slug rules), images,
      reference-style definitions
  R6  backticked repo paths exist (opt-in, --check-paths; noisy on real repos)
  R7  no `file.ext:123` citations for source files; they rot within one change
  R8  the same distinctive number in three or more docs (warning only)
  R9  a checklist index's todo / doing / done counts equal the boxes in the file (opt-in)
  R10 every doc under a folder appears in a registry table (opt-in)
  R11 the front door points at the index: the root README links the central index, and
      does not keep a parallel list of docs that would drift from it

Configuration is a small JSON manifest, by default `docs/structure.json` under the repo.
Without one the script discovers a docs root and proposes a manifest; it never writes it.
When there is no docs folder at all, the JSON carries an `init` block: the skeleton files
(index, manifest, one README line) and a starter routing section, as text for the agent to
write in the apply workflow. The script itself still writes nothing.

Exit codes: 0 when the run completed (findings are data, not failure), 1 only with
--fail-on-findings and at least one failure, 2 for a bad flag or manifest.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_READ = 2_000_000
GIT_TIMEOUT = 30

ALWAYS_SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git"}
TOP_LEVEL_SKIP = {"dist", "build"}
DOC_EXTS = {".md", ".mdx"}
ROOT_FILES = ("README.md", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md")
DOCS_FOLDER_NAMES = ("docs", "doc", "documentation")
RECORD_NAMES = {"plans", "specs", "archive", "log", "logs"}
GENERATOR_MARKERS = ("mkdocs.yml", "SUMMARY.md", "_sidebar.md", ".vitepress")
GENERATOR_GLOBS = ("docusaurus.config.*", "sidebars.*")

SEVERITY = {"R1": "P1", "R2": "P2", "R3": "P2", "R4": "P1", "R5": "P1",
            "R6": "P3", "R7": "P2", "R8": "P3", "R9": "P2", "R10": "P2", "R11": "P1"}
FRONT_DOOR_PARALLEL = 8  # a README linking this many docs under the roots is a second index
RULE_TITLE = {
    "R1": "reachable from an index", "R2": "owner line", "R3": "oversize doc",
    "R4": "index and folder agree", "R5": "links and anchors resolve",
    "R6": "backticked paths exist", "R7": "line-number citations",
    "R8": "duplicated measurement", "R9": "checklist counts", "R10": "registry",
    "R11": "front door links the index",
}

DEFAULT_MANIFEST = {
    "roots": [],
    "centralIndex": None,
    "indexConvention": "sibling",
    "ownerLine": {"markers": ["This document owns:", "Part of"], "enforce": False},
    "splitAt": 500,
    "maxParts": 30,
    "pathPrefixes": [],
    "citationExtensions": ["ts", "tsx", "js", "jsx", "mjs", "cjs", "py", "sql", "go", "rs", "java", "rb"],
    "recordFolders": [],
    "duplicateExempt": [],
    "exempt": {},
    "counts": [],
    "registries": [],
    "existingChecker": None,
    "frontDoor": "README.md",
    "ignore": [],
}

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
LINK_RE = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+\S")
REF_USE_RE = re.compile(r"\[[^\]]+\]\[([^\]]+)\]")
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
MEASURE_RE = re.compile(r"\$\d+\.\d+|(?<![\d.])\d{1,3}\.\d+%|(?<![\d.])0\.\d{3,}\b")
TRIVIAL_MEASURES = {"$0.00", "0.0%", "100.0%"}
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)\s*$")
CODESPAN_RE = re.compile(r"`[^`\n]*`")
BOX_RE = re.compile(r"^\s*[-*] \[( |~|x|X)\]")
DATE_RE = re.compile(r"\b20\d{2}-\d{2}(-\d{2})?\b")
PREFIX_RE = re.compile(r"^([A-Z]{2,}-\d+|20\d{2}-\d{2}(-\d{2})?)[-_ .]")
PLACEHOLDER_MARKERS = ("(auto, review me)", "| unreviewed |")
# Link targets that are examples, not promises: `[text](url)`, `[x](javascript:...)`, `[y](path/to/file)`.
PLACEHOLDER_TARGET = re.compile(r"^(url|link|path|file|href)$|^javascript:|^\.{3}|[<>{}$*]|(^|/)(path/to|your[-_]|my[-_]|example|foo|bar|placeholder)(?=[./-]|$)", re.I)
MAX_JSON_FINDINGS = 1000

warnings: list[str] = []


# ---------------------------------------------------------------- helpers

def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


_listing: dict[Path, set[str]] = {}


def exists_exact(path: Path) -> bool:
    """Case-exact existence check, so a Windows run agrees with Linux and GitHub."""
    if not path.exists():
        return False
    parent = path.parent
    if parent not in _listing:
        try:
            _listing[parent] = set(os.listdir(parent))
        except OSError:
            _listing[parent] = set()
    return path.name in _listing[parent]


def posix(p: Path, repo: Path) -> str:
    try:
        return p.relative_to(repo).as_posix()
    except ValueError:
        return p.as_posix()


def git_root(start: Path) -> Path | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        p = subprocess.run([git, "rev-parse", "--show-toplevel"], cwd=str(start), text=True,
                           timeout=GIT_TIMEOUT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    return Path(p.stdout.strip()) if p.returncode == 0 and p.stdout.strip() else None


def strip_fences(lines: list[str]) -> list[str]:
    """Blank out fenced blocks, keeping line numbers stable."""
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
            out.append("")
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append("")
            continue
        out.append(line)
    return out


def fences_balanced(lines: list[str]) -> bool:
    fence: str | None = None
    for line in lines:
        m = FENCE_RE.match(line)
        if not m:
            continue
        if fence is None:
            fence = m.group(1)
        elif m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
            fence = None
    return fence is None


def slug(text: str) -> str:
    t = re.sub(r"`[^`]*`", lambda m: m.group(0)[1:-1], text)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = t.strip().lower().replace("\r", "")
    t = "".join(ch for ch in t if ch.isalnum() or ch in " _-")
    return t.replace(" ", "-")


def headings(clean: list[str]) -> list[tuple[int, int, str]]:
    """(line_number_1_based, level, text) for every heading outside fences."""
    out = []
    for i, line in enumerate(clean, start=1):
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
            continue
        # setext: a non-blank line followed by === or ---
        if i < len(clean) and clean[i - 1].strip() and SETEXT_RE.match(clean[i]) and not clean[i - 1].lstrip().startswith(("|", "-", "*", "#")):
            out.append((i, 1 if clean[i].strip()[0] == "=" else 2, clean[i - 1].strip()))
    return out


def anchors(clean: list[str]) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for _, _, text in headings(clean):
        base = slug(text)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.add(f"{base}-{n}" if n else base)
    return out


def frontmatter_end(lines: list[str]) -> int:
    """Index of the line after a leading `---` block, or 0."""
    if not lines or lines[0].strip() != "---":
        return 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return i + 1
    return 0


def matches_any(rel: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatchcase(rel, pat) or rel == pat.rstrip("/") or rel.startswith(pat.rstrip("/") + "/"):
            return True
    return False


# ---------------------------------------------------------------- manifest

raw_keys: set[str] = set()


def load_manifest(repo: Path, explicit: str | None) -> tuple[dict, Path | None, str]:
    """Returns (manifest, path or None, source) where source is found | none."""
    if explicit:
        e = Path(explicit)
        candidates = [e] if e.is_absolute() else [Path.cwd() / e, repo / e]
        candidates = [c for c in candidates if c.is_file()] or [candidates[-1]]
    else:
        candidates = [repo / "docs" / "structure.json", repo / "docs-structure.json"]
    for c in candidates:
        if c.is_file():
            try:
                data = json.loads(read(c))
            except ValueError as exc:
                sys.stderr.write(f"error: manifest {c} is not valid JSON: {exc}\n")
                raise SystemExit(2)
            if not isinstance(data, dict):
                sys.stderr.write(f"error: manifest {c} must be a JSON object\n")
                raise SystemExit(2)
            unknown = sorted(set(data) - set(DEFAULT_MANIFEST))
            if unknown:
                sys.stderr.write(f"error: manifest {c} has unknown key(s): {', '.join(unknown)}\n")
                raise SystemExit(2)
            for k, v in data.items():
                d = DEFAULT_MANIFEST[k]
                if v is None or d is None:
                    continue
                want = bool if isinstance(d, bool) else int if isinstance(d, int) else type(d)
                if not isinstance(v, want) or (want is int and isinstance(v, bool)):
                    sys.stderr.write(f"error: manifest {c}: key {k} must be {want.__name__}\n")
                    raise SystemExit(2)
            ol = data.get("ownerLine")
            if isinstance(ol, dict) and not isinstance(ol.get("markers", []), list):
                sys.stderr.write(f"error: manifest {c}: ownerLine.markers must be a list\n")
                raise SystemExit(2)
            merged = json.loads(json.dumps(DEFAULT_MANIFEST))
            raw_keys.update(data.keys())
            for k, v in data.items():
                if k == "ownerLine" and isinstance(v, dict):
                    merged["ownerLine"].update(v)
                else:
                    merged[k] = v
            return merged, c, "found"
        if explicit:
            sys.stderr.write(f"error: manifest {c} does not exist\n")
            raise SystemExit(2)
    return json.loads(json.dumps(DEFAULT_MANIFEST)), None, "none"


# ---------------------------------------------------------------- discovery

def skill_dirs(repo: Path) -> set[Path]:
    out = set()
    for p in repo.rglob("SKILL.md"):
        if p.parent == repo:
            warnings.append("SKILL.md at the repo root is not used for exclusion; a single-skill repo is still audited")
            continue
        if not any(part in ALWAYS_SKIP or part.startswith(".") for part in p.relative_to(repo).parts[:-1]):
            out.add(p.parent)
    return out


def excluded(path: Path, repo: Path, skills: set[Path], ignore: list[str]) -> bool:
    rel_parts = path.relative_to(repo).parts
    for i, part in enumerate(rel_parts[:-1] if path.is_file() else rel_parts):
        if part in ALWAYS_SKIP or (part.startswith(".") and part not in (".",)):
            return True
        if i == 0 and part in TOP_LEVEL_SKIP:
            return True
    for s in skills:
        try:
            path.relative_to(s)
            return True
        except ValueError:
            pass
    return matches_any(path.relative_to(repo).as_posix(), ignore)


def docs_under(folder: Path, repo: Path, skills: set[Path], ignore: list[str]) -> list[Path]:
    out = []
    if folder.is_file():
        return [folder] if folder.suffix.lower() in DOC_EXTS else []
    for p in sorted(folder.rglob("*")):
        if p.is_file() and p.suffix.lower() in DOC_EXTS and not excluded(p, repo, skills, ignore):
            out.append(p)
    return out


def linked_folders(repo: Path, skills: set[Path], ignore: list[str]) -> dict[str, int]:
    """Folders linked from the root files, with their doc counts."""
    found: dict[str, int] = {}
    for name in ROOT_FILES:
        f = repo / name
        if not f.is_file():
            continue
        for _, target in LINK_RE.findall("\n".join(strip_fences(read(f).splitlines()))):
            t = target.split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "<")):
                continue
            p = (repo / t).resolve() if not t.startswith("/") else None
            if p is None:
                continue
            if p.is_file():
                p = p.parent
            if p == repo or not p.is_dir():
                continue
            try:
                rel = p.relative_to(repo).as_posix()
            except ValueError:
                continue
            if rel in found or excluded(p, repo, skills, ignore):
                continue
            n = len(docs_under(p, repo, skills, ignore))
            if n >= 2:
                found[rel] = n
    return found


def discover(repo: Path, skills: set[Path], ignore: list[str]) -> dict:
    for name in DOCS_FOLDER_NAMES:
        d = repo / name
        if d.is_dir() and docs_under(d, repo, skills, ignore):
            return {"rule": "a", "status": "resolved", "roots": [name], "candidates": {}}
    linked = linked_folders(repo, skills, ignore)
    for child in list(linked):
        if any(child != other and child.startswith(other + "/") for other in linked):
            del linked[child]
    if len(linked) == 1:
        return {"rule": "b", "status": "resolved", "roots": list(linked), "candidates": linked}
    if len(linked) > 1:
        return {"rule": "b", "status": "ambiguous", "roots": [], "candidates": linked}
    return {"rule": "c", "status": "root-files-only", "roots": [], "candidates": {}}


def detect_generator(repo: Path) -> str | None:
    for m in GENERATOR_MARKERS:
        if (repo / m).exists() or (repo / "docs" / m).exists():
            return m
    for g in GENERATOR_GLOBS:
        if list(repo.glob(g)):
            return g
    return None


def is_record_folder(folder: Path, repo: Path, docs: list[Path]) -> bool:
    name = folder.name
    if name in RECORD_NAMES or fnmatch.fnmatchcase(name, "audit-*") or DATE_RE.search(name):
        return True
    here = [d for d in docs if d.parent == folder]
    if len(here) >= 2:
        prefixed = sum(1 for d in here if PREFIX_RE.match(d.name))
        if prefixed * 2 > len(here):
            return True
    return False


def top_level_dirs(repo: Path) -> list[str]:
    out = []
    for p in sorted(repo.iterdir()):
        if p.is_dir() and not p.name.startswith(".") and p.name not in ALWAYS_SKIP | TOP_LEVEL_SKIP:
            out.append(p.name)
    return out


# ---------------------------------------------------------------- init skeleton

INDEX_TEMPLATE = """# Docs index

> **This document owns:** the list of every doc in this repository, what each one owns, and its state.

Pick the one file you need here; do not read the folder. One doc owns each fact; the others link to it.

| doc | owns | state |
| --- | --- | --- |
"""

ROUTING_STARTER = """## Docs routing - where a change gets written down

One doc owns each fact; the others link. Every doc's header says what it owns. When you change
one of these, update the owner in the same change.

| you changed... | update |
|---|---|
| <a kind of change> | `docs/<OWNER>.md` |

Rules that keep this true:

- Cite symbols and log tags, never line numbers - `file.ts:123` rots within one change.
- Strike superseded figures (`~~old~~ -> new`), do not delete them.
- Every doc has a row in `docs/INDEX.md` and a `> **This document owns:**` line under its H1.
- `python <skill-dir>/scripts/docs_structure.py --repo . --fail-on-findings` is the check.
"""


def init_block(repo: Path, front_rel: str) -> dict:
    """Skeleton for a repo with no docs folder. Text only; the agent writes it in apply."""
    manifest = {
        "roots": ["docs"] + [f for f in ROOT_FILES if (repo / f).is_file()],
        "centralIndex": "docs/INDEX.md",
        "indexConvention": "sibling",
        "ownerLine": {"markers": DEFAULT_MANIFEST["ownerLine"]["markers"], "enforce": False},
        "splitAt": 500,
        "pathPrefixes": top_level_dirs(repo),
        "recordFolders": [],
        "frontDoor": front_rel,
        "ignore": [],
    }
    files = {
        "docs/INDEX.md": INDEX_TEMPLATE,
        "docs/structure.json": json.dumps(manifest, indent=2) + "\n",
    }
    readme_line = "Every doc is listed in [docs/INDEX.md](docs/INDEX.md) - what each one owns and its state. Start there."
    return {
        "files": files,
        "readme_line": {"path": front_rel, "append": readme_line,
                        "why": "so the front door links the index (R11) from day one"},
        "print_only": {"CLAUDE.md or AGENTS.md": ROUTING_STARTER},
        "then": "run the checker again; it should report 0 failures and the empty index",
    }


# ---------------------------------------------------------------- analysis

class Doc:
    def __init__(self, path: Path, repo: Path):
        self.path = path
        self.rel = posix(path, repo)
        try:
            self.skipped = path.stat().st_size > MAX_READ
        except OSError:
            self.skipped = True
        self.raw = read(path)
        self.lines = self.raw.splitlines()
        self.clean = strip_fences(self.lines)
        # links and citations are scanned with inline code removed as well
        self.nocode = [CODESPAN_RE.sub("", l) for l in self.clean]
        self.balanced = fences_balanced(self.lines)
        self.headings = headings(self.clean)
        self.anchors = anchors(self.clean)
        self.fm_end = frontmatter_end(self.lines)

    def links(self):
        """(line_no, is_image, target) for every link outside fences."""
        for i, line in enumerate(self.nocode, start=1):
            for img, target in LINK_RE.findall(line):
                yield i, bool(img), target


def resolve_target(doc_path: Path, repo: Path, file_part: str) -> Path:
    """Resolve a link target the way GitHub does: root-relative from the repo, else from the doc."""
    file_part = unquote(file_part)
    if file_part.startswith("/"):
        return repo / file_part.lstrip("/")
    return doc_path.parent / file_part


def sibling_index(folder: Path, repo: Path, convention: str) -> Path | None:
    if convention == "inside":
        for name in ("README.md", "INDEX.md", "index.md"):
            if (folder / name).is_file():
                return folder / name
        return None
    parent = folder.parent
    try:
        parent.relative_to(repo)
    except ValueError:
        return None
    want = f"{folder.name}.md".lower()
    for p in parent.iterdir():
        if p.is_file() and p.name.lower() == want:
            return p
    return None


def index_for(doc: Doc, repo: Path, roots: list[Path], convention: str) -> Path | None:
    """Walk up from the doc's folder to a root looking for a sibling index."""
    folder = doc.path.parent
    while True:
        if folder in roots or folder == repo:
            return None
        idx = sibling_index(folder, repo, convention)
        if idx is not None and idx != doc.path:
            return idx
        folder = folder.parent


def split_analysis(doc: Doc, split_at: int, max_parts: int) -> dict:
    """Where a doc could be cut. Reports, never cuts."""
    n = len(doc.lines)
    out: dict = {"path": doc.rel, "lines": n, "level": None, "parts": None,
                 "largest": None, "refuse": None}
    if not doc.balanced:
        out["refuse"] = "unbalanced code fence"
        return out
    if sum(1 for _, lvl, _ in doc.headings if lvl == 1) > 1:
        out["refuse"] = "more than one H1"
        return out
    if any(REF_DEF_RE.match(l) for l in doc.clean) or any(FOOTNOTE_RE.search(l) for l in doc.clean):
        out["refuse"] = "reference-style definitions or footnotes"
        return out
    reasons = []
    for level in (2, 3):
        cuts = [(ln, lvl) for ln, lvl, _ in doc.headings if 2 <= lvl <= level]
        if not cuts:
            reasons.append(f"H{level}: no headings")
            continue
        intro = cuts[0][0] - 1
        if intro > split_at:
            reasons.append(f"H{level}: intro is {intro} lines")
            continue
        # merge a heading with no body into the part that follows it
        bounds = [c[0] for c in cuts] + [n + 1]
        parts = []
        i = 0
        while i < len(bounds) - 1:
            start, end = bounds[i], bounds[i + 1]
            body = [l for l in doc.lines[start:end - 1] if l.strip()]
            if not body and i + 1 < len(bounds) - 1:
                i += 1
                end = bounds[i + 1]
                while i + 1 < len(bounds) - 1 and not [l for l in doc.lines[bounds[i]:bounds[i + 1] - 1] if l.strip()]:
                    i += 1
                    end = bounds[i + 1]
            parts.append(end - start)
            i += 1
        largest = max(parts)
        if len(parts) < 3:
            reasons.append(f"H{level}: only {len(parts)} part(s)")
        elif len(parts) > max_parts:
            reasons.append(f"H{level}: {len(parts)} parts, over maxParts {max_parts}")
        elif largest > split_at:
            reasons.append(f"H{level}: one section is {largest} lines")
        else:
            out.update({"level": f"H{level}", "parts": len(parts), "largest": largest})
            return out
    out["refuse"] = "; ".join(reasons) or "no usable heading level"
    return out


def build(repo: Path, manifest: dict, manifest_path: Path | None, source: str,
          check_paths: bool) -> dict:
    findings: list[dict] = []
    ignore = list(manifest.get("ignore") or [])
    skills = skill_dirs(repo)

    def add(rule: str, path: str, line: int | None, message: str, level: str = "fail") -> None:
        findings.append({"rule": rule, "severity": SEVERITY[rule], "level": level,
                         "path": path, "line": line, "message": message})

    # ---- roots
    discovery = None
    roots_rel = list(manifest.get("roots") or [])
    if not roots_rel:
        discovery = discover(repo, skills, ignore)
        roots_rel = list(discovery["roots"])
        if discovery["status"] != "resolved":
            roots_rel = [f for f in ROOT_FILES if (repo / f).is_file()]
        else:
            roots_rel += [f for f in ROOT_FILES if (repo / f).is_file()]
    roots = [repo / r for r in roots_rel if (repo / r).exists()]
    for r in roots_rel:
        if not (repo / r).exists():
            warnings.append(f"root {r} does not exist")

    root_files_only = discovery is not None and discovery["status"] != "resolved"
    generator = detect_generator(repo)

    # ---- doc set
    paths: list[Path] = []
    non_doc = 0
    for r in roots:
        if r.is_file():
            paths.append(r)
            continue
        for p in sorted(r.rglob("*")):
            if not p.is_file() or excluded(p, repo, skills, ignore):
                continue
            if p.suffix.lower() in DOC_EXTS:
                paths.append(p)
            elif p.name != "structure.json":
                non_doc += 1
    paths = sorted(set(paths))
    docs = [Doc(p, repo) for p in paths]
    by_rel = {d.rel: d for d in docs}

    folders = sorted({d.path.parent for d in docs if d.path.parent not in roots and d.path.parent != repo})
    detected_records = sorted(posix(f, repo) for f in folders if is_record_folder(f, repo, paths))
    # A manifest that names recordFolders is authoritative; the heuristic only runs when it is
    # silent, so committing the proposed manifest freezes the result instead of re-guessing.
    explicit_records = manifest.get("recordFolders")
    record_folders = sorted(explicit_records) if explicit_records is not None and source == "found" and "recordFolders" in raw_keys else detected_records

    def in_record(rel: str) -> bool:
        return matches_any(rel, record_folders)

    def exempt(rule: str, rel: str) -> bool:
        return matches_any(rel, list((manifest.get("exempt") or {}).get(rule, [])))

    convention = manifest.get("indexConvention") or "sibling"
    central_rel = manifest.get("centralIndex")
    if not central_rel and not root_files_only:
        for r in roots:
            if r.is_dir():
                for name in ("INDEX.md", "index.md", "README.md"):
                    if (r / name).is_file():
                        central_rel = posix(r / name, repo)
                        break
            if central_rel:
                break
    central = repo / central_rel if central_rel else None
    central_exists = bool(central and central.is_file())

    # links out of a file, resolved to repo-relative paths (outside fences)
    def links_out(doc: Doc) -> set[str]:
        out = set()
        for _, _, target in doc.links():
            t = target.split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "<")):
                continue
            try:
                out.add(posix(resolve_target(doc.path, repo, t).resolve(), repo))
            except (ValueError, OSError):
                continue
        return out

    central_links = links_out(by_rel[central_rel]) if central_exists and central_rel in by_rel else (
        links_out(Doc(central, repo)) if central_exists else set())
    index_links: dict[str, set[str]] = {}

    r1_off = root_files_only or generator is not None
    unreachable: list[str] = []

    prefixes = list(manifest.get("pathPrefixes") or []) or top_level_dirs(repo)
    path_pat = re.compile(r"`((?:%s)/[^`\s]+?\.[a-z]{1,5})`" % "|".join(re.escape(p) for p in prefixes)) if prefixes else None
    exts = "|".join(manifest.get("citationExtensions") or DEFAULT_MANIFEST["citationExtensions"])
    cite = re.compile(r"[\w./\[\]-]+\.(?:%s):\d+(?:-\d+)?" % exts)

    for d in docs:
        rec = in_record(d.rel)
        if d.skipped:
            warnings.append(f"{d.rel} is over {MAX_READ} bytes and was not analysed")

        # ---- R1 / R4
        if not r1_off and d.path not in roots and central_rel != d.rel:
            idx = index_for(d, repo, roots, convention)
            if idx is not None:
                irel = posix(idx, repo)
                if irel not in index_links:
                    index_links[irel] = links_out(by_rel[irel]) if irel in by_rel else links_out(Doc(idx, repo))
                if d.rel not in index_links[irel]:
                    add("R4", irel, 1, f"index does not link {d.rel}, which sits in its folder")
            elif central_exists:
                if d.rel not in central_links:
                    add("R1", d.rel, 1, f"not linked from the central index {central_rel}")
            else:
                unreachable.append(d.rel)

        # ---- R2
        markers = list((manifest.get("ownerLine") or {}).get("markers") or [])
        enforce = bool((manifest.get("ownerLine") or {}).get("enforce"))
        has_owner = False
        if d.fm_end and any(l.strip().startswith("description:") for l in d.lines[:d.fm_end]):
            has_owner = True
        else:
            seen = 0
            for line in d.lines:
                if not line.strip():
                    continue
                seen += 1
                if any(m in line for m in markers):
                    has_owner = True
                    break
                if seen >= 12:
                    break
        if not has_owner and not exempt("R2", d.rel) and d.path not in roots and not d.skipped:
            add("R2", d.rel, 1, "no owner line near the top and no frontmatter description",
                "fail" if enforce else "warn")

        # ---- R5 links, anchors, images, reference definitions
        defs = {m.group(1).lower() for l in d.clean for m in [REF_DEF_RE.match(l)] if m}
        for i, is_img, target in ([] if d.skipped else d.links()):
            if target.startswith(("http://", "https://", "mailto:", "<", "tel:", "data:")):
                continue
            if PLACEHOLDER_TARGET.search(target):
                continue
            file_part, _, anchor = target.partition("#")
            anchor = unquote(anchor).lower()
            if not file_part:
                if anchor and anchor not in d.anchors:
                    add("R5", d.rel, i, f"dead anchor #{anchor} (no such heading in this file)")
                continue
            tgt = resolve_target(d.path, repo, file_part)
            if not exists_exact(tgt):
                add("R5", d.rel, i, f"{'image' if is_img else 'link'} target does not exist: {file_part}")
                continue
            if anchor and tgt.suffix.lower() in DOC_EXTS:
                try:
                    trel = posix(tgt.resolve(), repo)
                except ValueError:
                    trel = None
                tdoc = by_rel.get(trel) if trel else None
                tanchors = tdoc.anchors if tdoc else anchors(strip_fences(read(tgt).splitlines()))
                if anchor not in tanchors:
                    add("R5", d.rel, i, f"dead anchor {file_part}#{anchor}")
        # `[text][id]` is a reference-style link only in a doc that defines at least one
        # reference; elsewhere adjacent brackets are tags like `[R7][R8]`.
        if defs and not d.skipped:
            for i, line in enumerate(d.nocode, start=1):
                for ref in REF_USE_RE.findall(line):
                    if ref.lower() not in defs:
                        add("R5", d.rel, i, f"reference-style link [{ref}] has no definition")

        # ---- R6 backticked repo paths (opt-in)
        if check_paths and path_pat is not None and not exempt("R6", d.rel) and not d.skipped:
            for i, line in enumerate(d.clean, start=1):
                for m in path_pat.findall(line):
                    if "*" in m or "<" in m or re.search(r"(^|/)\.env(\.|$)", m):
                        continue
                    if not exists_exact(repo / m):
                        add("R6", d.rel, i, f"path does not exist: {m}", "warn" if rec else "fail")

        # ---- R7 line-number citations
        if not exempt("R7", d.rel) and not d.skipped:
            for i, line in enumerate(d.clean, start=1):
                for tok in line.split():
                    if "://" in tok:
                        continue
                    for m in cite.findall(tok):
                        add("R7", d.rel, i, f'line-number citation "{m}" - cite a symbol or a log tag',
                            "warn" if rec else "fail")

    # ---- R1 aggregate when no central index
    if not r1_off and not central_exists and unreachable:
        if manifest_path is not None:
            anchor_path, anchor_line = posix(manifest_path, repo), 1
            for i, line in enumerate(read(manifest_path).splitlines(), start=1):
                if "centralIndex" in line:
                    anchor_line = i
                    break
        else:
            anchor_path, anchor_line = unreachable[0], 1
        add("R1", anchor_path, anchor_line,
            f"no central index - {len(unreachable)} doc(s) unreachable in one hop")

    # ---- R3 candidates
    split_at = int(manifest.get("splitAt") or 500)
    max_parts = int(manifest.get("maxParts") or 30)
    candidates = []
    for d in docs:
        if d.skipped:
            add("R3", d.rel, 1, f"over {MAX_READ} bytes, not analysed - oversize by any measure", "warn")
            continue
        if len(d.lines) > split_at and not exempt("R3", d.rel):
            a = split_analysis(d, split_at, max_parts)
            candidates.append(a)
            if a["refuse"]:
                add("R3", d.rel, 1, f"{a['lines']} lines, oversize and unsplittable ({a['refuse']}) - needs a human restructure", "warn")
            else:
                add("R3", d.rel, 1, f"{a['lines']} lines - could become an index plus {a['parts']} parts at {a['level']} (largest {a['largest']})", "warn")

    # ---- R8 duplicated measurements
    owners: dict[str, list[str]] = {}
    dup_exempt = list(manifest.get("duplicateExempt") or [])
    for d in docs:
        if in_record(d.rel) or matches_any(d.rel, dup_exempt) or exempt("R8", d.rel):
            continue
        if d.skipped:
            continue
        seen = set()
        for line in d.clean:
            for m in MEASURE_RE.findall(line):
                if m not in TRIVIAL_MEASURES:
                    seen.add(m)
        for m in seen:
            owners.setdefault(m, []).append(d.rel)
    for m, where in sorted(owners.items()):
        if len(where) >= 3:
            add("R8", where[0], None, f'"{m}" appears in {len(where)} docs - one should own it, the rest link: {", ".join(where)}', "warn")

    # ---- R9 checklist counts
    for spec in manifest.get("counts") or []:
        idx = repo / spec.get("index", "")
        folder = repo / spec.get("folder", "")
        if not idx.is_file() or not folder.is_dir():
            warnings.append(f"R9: {spec} - index or folder missing")
            continue
        idx_doc = by_rel.get(posix(idx, repo)) or Doc(idx, repo)
        shown: dict[str, list[int]] = {}
        row = re.compile(r"^\|\s*\[[^\]]+\]\(([^)\s]+\.md)\)\s*\|.*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*$")
        for i, line in enumerate(idx_doc.clean, start=1):
            m = row.match(line)
            if m:
                try:
                    shown[posix((idx.parent / m.group(1)).resolve(), repo)] = [int(m.group(2)), int(m.group(3)), int(m.group(4)), i]
                except ValueError:
                    pass
        for f in sorted(folder.rglob("*.md")):
            frel = posix(f, repo)
            want = shown.get(frel)
            if not want:
                add("R9", posix(idx, repo), 1, f"phase file not in the index: {frel}")
                continue
            c = [0, 0, 0]
            for line in strip_fences(read(f).splitlines()):
                m = BOX_RE.match(line)
                if m:
                    c[0 if m.group(1) == " " else 1 if m.group(1) == "~" else 2] += 1
            if c != want[:3]:
                add("R9", posix(idx, repo), want[3],
                    f"{frel}: index says {'/'.join(map(str, want[:3]))} (todo/doing/done), the file has {'/'.join(map(str, c))}")

    # ---- R10 registries
    for spec in manifest.get("registries") or []:
        folder = repo / spec.get("folder", "")
        table = repo / spec.get("table", "")
        if not folder.is_dir() or not table.is_file():
            warnings.append(f"R10: {spec} - folder or table missing")
            continue
        tdoc = by_rel.get(posix(table, repo)) or Doc(table, repo)
        linked = links_out(tdoc)
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in DOC_EXTS and f.name not in (spec.get("except") or []):
                if posix(f, repo) not in linked:
                    add("R10", posix(table, repo), 1, f"registry does not list {posix(f, repo)}")

    # ---- R11 the front door. A repo's README is where a reader starts; if a central index
    #      exists the README must hand off to it, and should not keep its own list of docs.
    front_rel = manifest.get("frontDoor") or "README.md"
    front = repo / front_rel
    if front_rel != "README.md" and not front.is_file():
        warnings.append(f"frontDoor {front_rel} does not exist")
    if (central_exists and front.is_file() and not r1_off and not exempt("R11", front_rel)
            and front.resolve() != central.resolve()):
        fdoc = by_rel.get(front_rel) or Doc(front, repo)
        outgoing = links_out(fdoc)
        # `[docs](docs/)` renders as docs/README.md on GitHub, so a folder link reaches an
        # index of that name.
        folder_hit = central.name.lower() == "readme.md" and posix(central.parent, repo) in outgoing
        if central_rel not in outgoing and not folder_hit:
            add("R11", front_rel, 1, f"front door does not link the central index {central_rel}")
        root_dirs = [posix(r, repo) for r in roots if r.is_dir()]
        parallel = sorted(t for t in outgoing if t != central_rel and any(t.startswith(rd + "/") for rd in root_dirs) and t in by_rel)
        if len(parallel) >= FRONT_DOOR_PARALLEL:
            add("R11", front_rel, 1,
                f"front door links {len(parallel)} docs directly - a second index that will drift from {central_rel}; keep a handful and point at the index", "warn")

    # ---- init: nothing to index yet, so hand the agent the skeleton
    init = None
    if discovery is not None and discovery["status"] == "root-files-only" and not (repo / "docs").exists():
        init = init_block(repo, front_rel)

    # ---- placeholders
    placeholders = 0
    for d in docs:
        for marker in PLACEHOLDER_MARKERS:
            placeholders += d.raw.count(marker)

    # ---- proposed manifest
    proposed = None
    if source == "none" and not root_files_only:
        conv = "sibling"
        saw_inside = False
        for f in folders:
            if sibling_index(f, repo, "sibling"):
                saw_inside = False
                break
            if sibling_index(f, repo, "inside"):
                saw_inside = True
        if saw_inside:
            conv = "inside"
        proposed = {
            "roots": roots_rel,
            "centralIndex": central_rel or (f"{roots_rel[0]}/INDEX.md" if roots_rel and not root_files_only else None),
            "indexConvention": conv,
            "ownerLine": {"markers": DEFAULT_MANIFEST["ownerLine"]["markers"], "enforce": False},
            "splitAt": split_at,
            "pathPrefixes": top_level_dirs(repo),
            "recordFolders": detected_records,
            "duplicateExempt": [],
            "exempt": {},
            "counts": [],
            "registries": [],
            "existingChecker": None,
            "frontDoor": "README.md",
            "ignore": ["**/*.csv", "**/*.xlsx"] if non_doc else [],
        }

    order = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}
    findings.sort(key=lambda f: (0 if f["level"] == "fail" else 1, order[f["severity"]], f["rule"], f["path"], f["line"] or 0))
    per_rule = {}
    for r in SEVERITY:
        fs = [f for f in findings if f["rule"] == r]
        per_rule[r] = {"severity": SEVERITY[r], "title": RULE_TITLE[r],
                       "failures": sum(1 for f in fs if f["level"] == "fail"),
                       "warnings": sum(1 for f in fs if f["level"] == "warn"),
                       "first": [f"{f['path']}:{f['line']}" if f["line"] else f["path"] for f in fs[:3]]}
    return {
        "repo": str(repo),
        "manifest": {"source": source, "path": posix(manifest_path, repo) if manifest_path else None},
        "discovery": discovery,
        "roots": roots_rel,
        "central_index": central_rel if central_exists else None,
        "generator": generator,
        "record_folders": record_folders,
        "totals": {"docs_checked": len(docs), "non_doc_files": non_doc,
                   "failures": sum(1 for f in findings if f["level"] == "fail"),
                   "warnings": sum(1 for f in findings if f["level"] == "warn"),
                   "placeholders": placeholders, "split_candidates": len(candidates)},
        "rules": per_rule,
        "findings": findings,
        "split_candidates": candidates,
        "unreachable": unreachable,
        "proposed_manifest": proposed,
        "init": init,
        "warnings": warnings,
    }


# ---------------------------------------------------------------- render

def render(d: dict, top: int) -> str:
    t = d["totals"]
    L = ["# Docs Structure Check", "", f"Repo: {d['repo']}"]
    disc = d["discovery"]
    if d["manifest"]["source"] == "found":
        L.append(f"Manifest: {d['manifest']['path']}")
    elif disc and disc["status"] == "ambiguous":
        L.append("Manifest: none. Discovery found more than one candidate docs folder - pick one:")
        for k, v in sorted(disc["candidates"].items(), key=lambda kv: -kv[1]):
            L.append(f"  {k}/  ({v} docs)")
        L.append("  Checked root files only for now; R1 and R4 are off.")
    elif disc and disc["status"] == "root-files-only":
        L.append("Manifest: none. No project docs folder found - root files only; R1 and R4 are off.")
    else:
        L.append(f"Manifest: none, proposed below. Roots: {', '.join(d['roots'])}")
    L.append(f"Docs checked: {t['docs_checked']}   non-doc files in docs folders: {t['non_doc_files']}")
    L.append(f"Central index: {d['central_index'] or 'none'}   Generator: {d['generator'] or 'none'}")
    if d["record_folders"]:
        L.append(f"Record folders (R6/R7 warn, R8 skipped): {', '.join(d['record_folders'])}")
    L.append(f"Failures: {t['failures']}   Warnings: {t['warnings']}   Placeholders awaiting review: {t['placeholders']}")
    L.append("")
    L.append("| rule | severity | failures | warnings | first |")
    L.append("|---|---|---|---|---|")
    for r, info in d["rules"].items():
        if info["failures"] or info["warnings"]:
            L.append(f"| {r} {info['title']} | {info['severity']} | {info['failures']} | {info['warnings']} | {', '.join(info['first'])} |")
    L.append("")
    shown = d["findings"][:top]
    if not d["findings"]:
        L.append("No structural findings. Prose accuracy is still unchecked.")
    for f in shown:
        where = f"{f['path']}:{f['line']}" if f["line"] else f["path"]
        L.append(f"{f['severity']} {f['rule']} [{f['level']}] {where}: {f['message']}")
    if len(d["findings"]) > top:
        L.append(f"... {len(d['findings']) - top} more (raise --top or use --format json)")
    if d["split_candidates"]:
        L.append("")
        L.append("Split candidates (R3, report only):")
        for c in d["split_candidates"][:top]:
            if c["refuse"]:
                L.append(f"  {c['path']}  {c['lines']} lines  refuse: {c['refuse']}")
            else:
                L.append(f"  {c['path']}  {c['lines']} lines  {c['level']} -> {c['parts']} parts, largest {c['largest']}")
    if d["proposed_manifest"]:
        L.append("")
        L.append("Proposed manifest (docs/structure.json) - review before committing:")
        L.append(json.dumps(d["proposed_manifest"], indent=2))
    if d.get("init"):
        L.append("")
        L.append("No docs folder. Apply would create this skeleton (nothing is written now):")
        for path, body in d["init"]["files"].items():
            L.append(f"  {path}  ({len(body.splitlines())} lines)")
        rl = d["init"]["readme_line"]
        L.append(f"  {rl['path']}  + one line: {rl['append']}")
        L.append("  and print a starter 'Docs routing' section for CLAUDE.md or AGENTS.md (not written).")
    if d["warnings"]:
        L.append("")
        L.extend(f"note: {w}" for w in d["warnings"])
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check the shape of a repository's Markdown docs. Read-only.")
    ap.add_argument("--repo", default=".", help="repository path (default: current directory)")
    ap.add_argument("--no-git-root", action="store_true", help="do not expand --repo to its git root")
    ap.add_argument("--manifest", help="manifest path, relative to the current directory (default: <repo>/docs/structure.json)")
    ap.add_argument("--propose-manifest", action="store_true", help="print only a proposed manifest as JSON")
    ap.add_argument("--check-paths", action="store_true", help="also check backticked repo paths (R6, noisy)")
    ap.add_argument("--fail-on-findings", action="store_true", help="exit 1 when any rule fails")
    ap.add_argument("--top", type=int, default=40, help="findings to print in text mode (default 40)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"error: {repo} is not a directory\n")
        return 2
    if not args.no_git_root:
        root = git_root(repo)
        if root is not None:
            repo = root.resolve()

    manifest, mpath, source = load_manifest(repo, args.manifest)
    data = build(repo, manifest, mpath, source, args.check_paths)

    if args.propose_manifest:
        print(json.dumps(data["proposed_manifest"] or manifest, indent=2))
        return 0
    if args.format == "json":
        if len(data["findings"]) > MAX_JSON_FINDINGS:
            data["warnings"].append(f"findings truncated to {MAX_JSON_FINDINGS} of {len(data['findings'])}")
            data["findings"] = data["findings"][:MAX_JSON_FINDINGS]
        print(json.dumps(data, indent=2, sort_keys=True))
    else:
        print(render(data, args.top))
    if args.fail_on_findings and data["totals"]["failures"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
