#!/usr/bin/env python3
"""Check the shape of a repository's Markdown documentation.

Read-only. Standard library only. Writes nothing.

    python docs_structure.py                        # text report, repo = git root of cwd
    python docs_structure.py --repo ../other
    python docs_structure.py --format json
    python docs_structure.py --propose-manifest     # print a manifest to start from
    python docs_structure.py --check-paths          # also check backticked repo paths (noisy)
    python docs_structure.py --fail-on-findings     # exit 1 when any rule fails (CI gate)

Fifteen mechanical rules, each with a fixed severity. None of them judges prose.

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
  R12 every concern the repo has is covered by the doc at its canonical path. Concerns come
      from the evidence inventory (docs_evidence.py beside this script): setup, develop,
      purpose, architecture and the agent file always; deploy, operate, testing, contribute,
      release, configuration, data, http, commands, exports, integrations, security, design,
      pipelines, decisions, changelog and plan when the repo contains the thing they describe;
      onboarding once seven docs are earned; research on request. The path is fixed by
      references/shape.md: a bucket folder (getting-started, guides, reference, explanation,
      history) once it would hold two docs, flat under seven docs in all. An uncovered concern
      is one P2 and a skeleton the apply workflow creates from references/templates/ - never
      content. A doc elsewhere whose headings match the concern is a move (R15), not a cover
  R15 the layout: a doc that covers a concern sits at that concern's canonical path; the
      central index is the list grammar (one line per doc, its state at the end), not a
      table; a companion folder sits beside its doc. Each finding carries the move
  R13 a fact that lives outside the repo carries a dated check. A doc that says
      "verified against <source> on YYYY-MM-DD" (or "Verified against <source> (YYYY-MM-DD)")
      warns when that date is older than `verifiedStaleDays` (default 90). No script can tell
      whether a platform setting or an on-call rota is still true; this says when nobody looked

Configuration is a small JSON manifest, by default `docs/structure.json` under the repo.
Without one the script discovers a docs root and proposes a manifest; it never writes it.
When docs are missing the JSON carries an `init` block: the skeleton files at their canonical
paths (index, manifest, the agent file, the README block) and the moves for docs that sit at the
wrong path, as text for the agent to write in the apply workflow. The script itself writes nothing.

Exit codes: 0 when the run completed (findings are data, not failure), 1 only with
--fail-on-findings and at least one failure, 2 for a bad flag or manifest.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import datetime
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

sys.dont_write_bytecode = True  # importing the sibling module must not write a __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import docs_evidence  # sibling script, same folder, stdlib only
except ImportError:  # pragma: no cover
    docs_evidence = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

MAX_READ = 2_000_000
GIT_TIMEOUT = 30

ALWAYS_SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git"}
TOP_LEVEL_SKIP = {"dist", "build"}
DOC_EXTS = {".md", ".mdx"}
# Documentation this tool cannot parse. Their presence is worth saying out loud, because the
# concern they cover is covered whether or not the checker can read it.
# .txt is deliberately absent: a log file and an llms.txt are not documentation, and calling
# them "a concern this covers" is worse than saying nothing.
OTHER_DOC_EXTS = {".adoc", ".asciidoc", ".rst", ".org", ".textile"}
ROOT_FILES = ("README.md", "CLAUDE.md", "AGENTS.md", "CONTRIBUTING.md")
DOCS_FOLDER_NAMES = ("docs", "doc", "documentation")
PACKAGE_MANIFESTS = ("package.json", "pyproject.toml", "setup.py", "setup.cfg", "go.mod", "Cargo.toml", "pom.xml",
                     "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "mix.exs", "Move.toml")
# What a line-number citation looks like in each language the inventory can name.
ECO_EXTENSIONS = {"csharp": ["cs"], "dotnet": ["cs"], "kotlin": ["kt", "kts"], "swift": ["swift"],
                  "php": ["php"], "elixir": ["ex", "exs"], "c": ["c", "h"], "cpp": ["cpp", "hpp", "cc"],
                  "java": ["java"], "go": ["go"], "rust": ["rs"], "ruby": ["rb"], "python": ["py"],
                  "node": ["ts", "tsx", "js", "jsx", "mjs", "cjs"], "move": ["move"], "shell": ["sh"]}
R1_COLLAPSE_AT = 10
# The line a split writes into each part, and the only reliable sign that a doc is one.
# Both the marker the split writes (**Part of**) and the older plain "> Part of [..]" line.
SPLIT_PART = re.compile(r"^\s*>\s*(?:\*\*)?Part of(?:\*\*)?\s*\[", re.M)
# `history` is the record bucket of the shape; `decisions` is not here because a decision record
# is edited (its status changes) and its links must hold - R6 and R7 apply in full there.
RECORD_NAMES = {"plans", "specs", "archive", "log", "logs", "builds", "adr", "adrs", "rfcs", "changelogs", "history"}
# Files GitHub surfaces by name. Telling a maintainer their AGPL text needs an owner line, a
# row in an index and a human restructure is how a docs checker gets uninstalled.
COMMUNITY_STEMS = {"license", "licence", "copying", "changelog", "change_log", "code_of_conduct",
                   "security", "contributing", "authors", "notice", "support", "governance",
                   "maintainers", "codeowners", "history", "acknowledgements", "acknowledgments"}


def is_community_file(rel: str) -> bool:
    """A standard community-health file at the repository root."""
    if "/" in rel:
        return False
    return rel.rsplit(".", 1)[0].lower().replace("-", "_") in COMMUNITY_STEMS
# A docs site generator owns navigation and URLs; looked for at the repo root and in each docs root.
# GitHub Pages' one-click setup is _config.yml; Hugo used config.toml before v0.110. Missing
# them meant a correct Jekyll or Hugo docs tree got P1 failures on links that resolve on the
# published site.
GENERATOR_MARKERS = ("mkdocs.yml", "mkdocs.yaml", "SUMMARY.md", "_sidebar.md", ".vitepress",
                     "hugo.toml", "hugo.yaml", "hugo.json", "config.toml", "book.toml",
                     "_config.yml", "antora.yml", ".readthedocs.yml", ".readthedocs.yaml")
GENERATOR_GLOBS = ("docusaurus.config.*", "sidebars.*", "astro.config.*", "conf.py")
# Three of those names are ordinary words. A generator switches four rules off, so an ambiguous
# marker has to corroborate itself before it is believed: conf.py must read like Sphinx, and a
# SUMMARY or sidebar must be nav-shaped, a list of links and little else.
AMBIGUOUS_MARKERS = {"conf.py": ("extensions", "master_doc", "html_theme", "sphinx"),
                     # Two of these, not one: config.toml is an ordinary application config
                     # name, and a [ui] section with theme = "dark" switched four rules off.
                     "config.toml": ("baseurl", "theme", "languagecode", "params", "permalinks",
                                     "taxonomies", "markup", "menu"),
                     "SUMMARY.md": None, "_sidebar.md": None}
# Folders whose contents describe something other than this repo; ignored when deciding what the repo is.
# Folders whose Markdown describes test material. Such a doc is still checked for links and
# citations; it just never becomes the doc that covers one of the repo's own concerns.
FIXTURE_DIRS = {"fixtures", "fixture", "__fixtures__", "testdata", "test-data", "mocks", "__mocks__", "golden", "snapshots"}

SEVERITY = {"R1": "P1", "R2": "P2", "R3": "P2", "R4": "P1", "R5": "P1",
            "R6": "P3", "R7": "P2", "R8": "P3", "R9": "P2", "R10": "P2", "R11": "P1", "R12": "P2", "R13": "P3",
            "R14": "P3", "R15": "P1"}
FRONT_DOOR_PARALLEL = 8  # a README linking this many docs under the roots is a second index
# The front door's hand-off section: a reader's first three files, then the index. Apply inserts it
# between these markers after the README's intro; refill regenerates only what is between them.
START_HERE_WORDS = ("start here", "where to start", "read this first", "getting around", "documentation", "docs")
START_HERE_OPEN = "<!-- docs-structure: start here -->"
START_HERE_CLOSE = "<!-- /docs-structure: start here -->"
RULE_TITLE = {
    "R1": "reachable from an index", "R2": "owner line", "R3": "oversize doc",
    "R4": "index and folder agree", "R5": "links and anchors resolve",
    "R6": "backticked paths exist", "R7": "line-number citations",
    "R8": "duplicated measurement", "R9": "checklist counts", "R10": "registry",
    "R11": "front door links the index", "R12": "concern covered", "R13": "verified-on date fresh",
    "R14": "index state vocabulary", "R15": "layout - canonical paths",
}
# The five buckets of references/shape.md, in index order, with the heading each gets.
BUCKETS = (("getting-started", "Getting started"), ("guides", "Guides"), ("reference", "Reference"),
           ("explanation", "Explanation"), ("history", "History"))
BUCKET_TITLE = dict(BUCKETS)
COLLAPSE_BELOW = 7   # fewer earned docs than this: no bucket folders at all
BUCKET_MIN = 2       # a bucket folder exists once it would hold this many docs
AGENT_FILE = "AGENTS.md"

# Keys whose default is null but whose shape still matters.
NULLABLE_TYPES = {"centralIndex": (str,), "templatesDir": (str,), "existingChecker": (str,),
                  "indexConvention": (str,),
                  "requiredDocs": (dict, list)}

DEFAULT_MANIFEST = {
    "roots": [],
    "centralIndex": None,
    # None, not "sibling": load_manifest merges the defaults in, so a value here made the left
    # side of `manifest.get(...) or detect_convention(...)` always truthy and the detector never
    # ran once. A folder-README tree then got one P1 per leaf doc, and the proposed manifest
    # froze the wrong convention into the repository.
    "indexConvention": None,
    "ownerLine": {"markers": ["This document owns:", "Part of"], "enforce": False},
    # 500 cut 43's 359-line PODCASTS.md into eighteen parts of six to forty lines. A doc is long
    # at a thousand lines; a part is a chapter of at least minPart lines, and a doc becomes at
    # most maxParts of them.
    "splitAt": 1000,
    "maxParts": 12,
    "minPart": 80,
    # An uncovered concern warns by default; a team that wants a missing doc to fail the build
    # sets this. Absent from the defaults it was rejected as an unknown key, so the escape
    # hatch SKILL.md documents stopped the tool from running at all.
    "requireConcerns": False,
    "pathPrefixes": [],
    "citationExtensions": ["ts", "tsx", "js", "jsx", "mjs", "cjs", "py", "sql", "go", "rs", "java", "rb"],
    "recordFolders": [],
    "duplicateExempt": [],
    "exempt": {},
    "counts": [],
    "registries": [],
    "existingChecker": None,
    "frontDoor": "README.md",
    "requiredDocs": None,
    # A README section stops counting as coverage once the evidence behind a concern is this large:
    # routes for http, tables for data, deployable units for deploy and architecture. 0 turns it off.
    "heavyEvidence": {"http": 20, "data": 10, "deploy": 3, "architecture": 3, "configuration": 8, "integrations": 3},
    "templatesDir": None,
    # Accepted so an older manifest still loads; the index is grouped by bucket now and this is ignored.
    "indexGroups": None,
    # The agent file at the root and the line count past which it stops being one (R11).
    "agentFile": "AGENTS.md",
    "agentFileMaxLines": 40,
    "verifiedStaleDays": 90,
    "ignore": [],
}
VERIFIED_RE = re.compile(r"[Vv]erified against ([^\n(]+?)\s*(?:on\s+|\()(\d{4}-\d{2}-\d{2})")

TEMPLATES = Path(__file__).resolve().parent.parent / "references" / "templates"

# R12: the concern model. A concern applies when `applies(inv)` returns a reason (a piece of
# evidence, or "always"). It is covered by any doc whose H1/H2 text matches its keywords, or
# whose file name is the default. The default file name depends on the repo's kinds.
def _svc(inv):
    for s_ in inv.get("services") or []:
        if s_.get("source") in ("Dockerfile", "compose", "railway", "fly", "render", "vercel", "netlify", "Procfile", "app.yaml", "k8s", "helm", "terraform"):
            return f"{s_.get('source')}: {s_.get('evidence')}"
    for c in inv.get("ci") or []:
        if c.get("deploy"):
            return f"deploy workflow: {c.get('evidence')}"
    return None


def _first(items, label):
    return f"{label}: {items[0].get('evidence')}" if items else None


def _plan_evidence(inv: dict) -> str | None:
    """A repository that plans in files, rather than in an issue tracker.

    Every other concern is earned from evidence; plan was "always", so ripgrep, prometheus and
    plausible were each told to create a TASKLIST.md and a phase-00 companion they have no use
    for. A repository that plans in files says so by having one.
    """
    tree = inv.get("tree") or {}
    planish = list(tree.get("plan_like_docs") or [])
    # adr, rfcs and decisions are dated records, which the record-folder rules already handle;
    # a phase checklist is the wrong apparatus for them.
    folders = [f for f in (tree.get("top_level_dirs") or [])
               if str(f).lower() in ("plans", "roadmap", "tasklist", "tasks")]
    if planish:
        return "plan-like docs: " + ", ".join(str(p) for p in planish[:3])
    if folders:
        return "folder: " + ", ".join(folders[:3])
    return None


def _lib_or_cli(inv):
    k = set(inv.get("kinds") or [])
    return bool(k & {"library", "cli"}) and "application" not in k


# What a document covering a concern is called in the languages most often met in public
# repositories. Partial by construction and only ever used to say "this existing file looks like
# the home for this concern - confirm", never to create anything: the cost of a miss is advice
# not given, and the cost of a wrong guess is a skeleton written beside a real document.
CONCERN_ALIASES = {
    "purpose": ("producto", "produto", "produkt", "prodotto", "vision", "visao", "vizyon",
                "resumen", "resumo", "ubersicht", "uebersicht", "panoramica", "proposito",
                "objetivo", "zweck", "scopo", "urun", "genelbakis"),
    "architecture": ("arquitectura", "arquitetura", "architektur", "architettura", "mimari",
                     "struktur", "estructura", "estrutura", "struttura", "yapi"),
    "develop": ("desarrollo", "desenvolvimento", "entwicklung", "sviluppo", "gelistirme",
                "developpement", "instalacion", "instalacao", "installazione", "kurulum",
                "empezar", "comecar", "einstieg", "iniziare"),
    "plan": ("planificacion", "planejamento", "planung", "pianificazione", "tareas", "tarefas",
             "aufgaben", "compiti", "gorevler", "hoja-de-ruta"),
    "deploy": ("despliegue", "implantacao", "implantacion", "bereitstellung", "distribuzione",
               "dagitim", "deploiement", "produccion", "producao", "produktion", "produzione"),
    "release": ("lanzamiento", "lancamento", "veroffentlichung", "veroeffentlichung", "rilascio",
                "surum", "publicacion", "publicacao"),
    "data": ("datos", "dados", "daten", "dati", "veri", "modelo-de-datos", "modelodedatos",
             "esquema", "banco-de-dados", "datenbank", "veritabani"),
    "http": ("endpoints", "puntos-finales", "servicios", "servicos", "schnittstelle",
             "arayuz", "rotas", "rutas"),
    "commands": ("comandos", "befehle", "comandi", "komutlar", "commandes"),
    "exports": ("exportaciones", "exportacoes", "esportazioni"),
    "design": ("diseno", "gestaltung", "tasarim", "progettazione", "estilo", "stil"),
    "testing": ("pruebas", "testes", "prufung", "pruefung", "collaudo", "testler"),
    "operate": ("operaciones", "operacoes", "betrieb", "operazioni", "isletme", "manual",
                "handbuch", "guia-operativa"),
    "contribute": ("contribuir", "contribuicao", "contribucion", "beitragen", "contribuire",
                   "katki", "katkida-bulunma"),
    "research": ("investigacion", "pesquisa", "forschung", "ricerca", "arastirma"),
}


def _n(inv, *path, default=0):
    cur = inv
    for k in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def _integrations(inv):
    it = inv.get("integrations") or {}
    n = int(it.get("count") or 0)
    outward = it.get("outward_env_names") or []
    if n >= 3:
        return f"{n} third-party SDKs: " + ", ".join(x["service"] for x in (it.get("sdks") or [])[:4])
    if len(outward) >= 3:
        return f"{len(outward)} outward env names: " + ", ".join(outward[:3])
    return None


def _security(inv):
    a = inv.get("auth") or {}
    if a.get("libraries"):
        return "auth library: " + ", ".join(x["name"] for x in a["libraries"][:3])
    if a.get("middleware_files"):
        return f"auth middleware: {a['middleware_files'][0]}"
    if a.get("roles_in_schema"):
        return f"roles in schema: {a['roles_in_schema'][0]}"
    return None


def _pipelines(inv):
    j = inv.get("jobs") or {}
    if j.get("libraries"):
        return "job library: " + ", ".join(x["name"] for x in j["libraries"][:3])
    if j.get("cron"):
        return f"cron: {j['cron'][0]}"
    if j.get("scheduled_workflows"):
        return f"scheduled workflow: {j['scheduled_workflows'][0]}"
    return None


def _operate(inv):
    # a health route or an alert file, read without guessing; a cron hint earns pipelines, not this
    ops = [o for o in inv.get("ops") or [] if not o.get("hint")]
    return f"ops: {ops[0].get('evidence')}" if ops else None


def _decisions(inv):
    tree = inv.get("tree") or {}
    if tree.get("adr_folders"):
        return f"folder: {tree['adr_folders'][0]}"
    n = len(_n(inv, "decisions", "decision_like", default=[]) or [])
    return f"{n} decision-like commits" if n >= 3 else None


def _changelog(inv):
    ch = inv.get("changelog") or {}
    if ch.get("file"):
        return f"file: {ch['file']}"
    if int(ch.get("tag_count") or 0) >= 3:
        return f"{ch['tag_count']} tags"
    return None


def _configuration(inv):
    n = int(inv.get("env_count") or 0)
    return f"{n} environment names" if n >= 8 else None


def _contribute(inv):
    tree = inv.get("tree") or {}
    gov = [g for g in tree.get("governance_files", []) if g.upper().startswith(("LICEN", "CONTRIBUTING", "CODE_OF_CONDUCT"))]
    if gov:
        return "governance: " + ", ".join(gov)
    if tree.get("pr_template"):
        return "a pull request template under .github"
    return None


# The concern model of references/shape.md. One row per document the shape can propose:
#   id, bucket (None for a root file), applies(inv) -> reason | None, file(inv) -> name,
#   keywords (for finding a misplaced doc by its headings), companions (relative to the doc's folder)
# The template is <bucket>/<file> under references/templates.
CONCERNS = [
    ("agent", None, lambda inv: "always", lambda inv: AGENT_FILE,
     set(), ["CLAUDE.md"]),
    ("setup", "getting-started", lambda inv: "always", lambda inv: "SETUP.md",
     {"setup", "install", "installation", "getting started", "quickstart", "quick start", "prerequisites", "first run"}, []),
    ("onboarding", "getting-started", lambda inv: "seven or more docs", lambda inv: "ONBOARDING.md",
     {"onboarding", "glossary", "reading order", "new here", "start here"}, []),
    ("develop", "guides", lambda inv: "always", lambda inv: "DEVELOPMENT.md",
     {"development", "developing", "local", "locally", "run locally", "daily commands", "hacking", "contributing code", "workflow"}, []),
    ("deploy", "guides", _svc, lambda inv: "DEPLOYMENT.md",
     {"deploy", "deployment", "deploying", "production", "hosting", "railway", "kubernetes", "helm", "docker", "release to"}, []),
    ("operate", "guides", _operate, lambda inv: "OPERATIONS.md",
     {"runbook", "operations", "operating", "on-call", "oncall", "incidents", "alerts", "monitoring", "health", "observability"}, []),
    ("testing", "guides", lambda inv: _first(inv.get("tests") or [], "tests"), lambda inv: "TESTING.md",
     {"testing", "tests", "test", "qa", "coverage", "e2e"}, []),
    ("contribute", "guides", _contribute, lambda inv: "CONTRIBUTING.md",
     {"contributing", "contribution", "contribute", "code of conduct", "pull request", "pull requests", "review process"}, []),
    ("release", "guides", lambda inv: (_first(inv.get("release") or [], "release") if _lib_or_cli(inv) else None), lambda inv: "RELEASING.md",
     {"releasing", "release", "releases", "publish", "publishing", "versioning"}, []),
    ("architecture", "reference", lambda inv: ("always" if ({"application", "monorepo", "infrastructure"} & set(inv.get("kinds") or []))
                                               or len(inv.get("packages") or []) > 1 or len({s.get("name") for s in inv.get("services") or []}) > 1
                                               else None), lambda inv: "ARCHITECTURE.md",
     {"architecture", "components", "services", "system", "data flow", "how it works", "modules", "structure", "containers"}, []),
    ("configuration", "reference", _configuration, lambda inv: "CONFIGURATION.md",
     {"configuration", "config", "environment variables", "env", "settings", "variables", "flags"}, []),
    ("data", "reference", lambda inv: (f"schema: {inv['schema']['tables'][0]['evidence']}" if inv.get("schema") and inv["schema"].get("tables") else (f"migrations: {inv['schema']['migrations']['first']}" if inv.get("schema") and inv["schema"]["migrations"]["count"] else None)), lambda inv: "DATA_MODEL.md",
     {"data model", "schema", "database", "tables", "migrations", "entities", "storage"}, []),
    ("http", "reference", lambda inv: (f"{inv['routes']['count']} routes ({', '.join(f'{k} {v}' for k, v in sorted(inv['routes'].get('by_framework', {}).items()))})" if inv.get("routes") and inv["routes"].get("count", 0) > 0 and inv["routes"].get("items") else None), lambda inv: "API.md",
     {"api", "endpoints", "endpoint", "routes", "openapi", "rest", "http", "api reference"}, []),
    ("commands", "reference", lambda inv: _first([c for c in inv.get("cli") or [] if not c.get("hint")], "cli"), lambda inv: "CLI.md",
     {"cli", "command", "commands", "command line", "usage", "flags", "options"}, []),
    ("exports", "reference", lambda inv: (_first(inv.get("exports") or [], "exports") if "library" in (inv.get("kinds") or []) else None), lambda inv: "PUBLIC_API.md",
     {"public api", "exports", "api reference", "import", "sdk"}, []),
    ("integrations", "reference", _integrations, lambda inv: "INTEGRATIONS.md",
     {"integrations", "integration", "third party", "third-party", "external services", "providers", "vendors"}, []),
    ("security", "reference", _security, lambda inv: "SECURITY.md",
     {"security", "authentication", "authorization", "authorisation", "auth", "roles", "permissions", "secrets"}, []),
    # One vendored stylesheet is not a design system: spring-petclinic was asked for a tokens-and-
    # components document on the strength of bootstrap's custom properties in one CSS file.
    ("design", "reference", lambda inv: (_first(inv.get("frontend") or [], "frontend")
                                         if any(f.get("detector") != "css-custom-properties" for f in inv.get("frontend") or [])
                                         or len(inv.get("frontend") or []) >= 3 else None), lambda inv: "DESIGN_SYSTEM.md",
     {"design", "design system", "design guidelines", "styling", "style guide", "theme", "tokens", "components", "ui", "brand"}, []),
    ("purpose", "explanation", lambda inv: "always", lambda inv: "OVERVIEW.md" if _lib_or_cli(inv) else "PRODUCT.md",
     {"product", "overview", "vision", "purpose", "goal", "goals", "roadmap", "principles", "about", "introduction", "mission", "why", "motivation", "what is"}, []),
    ("pipelines", "explanation", _pipelines, lambda inv: "PIPELINES.md",
     {"pipelines", "pipeline", "jobs", "background jobs", "workers", "queues", "queue", "scheduler", "cron"}, []),
    ("decisions", "explanation", _decisions, lambda inv: "decisions/README.md",
     {"decisions", "decision records", "adr", "adrs", "architecture decisions", "rfcs"}, ["ADR-0001-first-decision.md"]),
    ("changelog", "history", _changelog, lambda inv: "CHANGELOG.md",
     {"changelog", "change log", "release notes", "history", "what's new"}, []),
    ("research", "history", lambda inv: None, lambda inv: "research/LOG.md",
     {"research", "experiments", "experiment", "findings", "lab notebook"}, ["log/YYYY-MM.md"]),
    # Evidence, not habit: a repo that plans in files says so by having one.
    ("plan", "history", lambda inv: _plan_evidence(inv), lambda inv: "plans/TASKLIST.md",
     {"tasklist", "task list", "tasks", "todo", "backlog", "plan", "milestones", "phases", "checklist", "roadmap"}, ["tasklist/phase-00-foundations.md", "ROADMAP.md"]),
]
UNIVERSAL = {"purpose", "develop", "setup"}
# Template file names that changed with the shape; a doc still carrying the old name is that
# concern's doc, at the wrong path.
OLD_NAMES = {"RUNBOOK.md": "operate", "API_REFERENCE.md": "http", "CLI_REFERENCE.md": "commands",
             "DESIGN_GUIDELINES.md": "design", "TASKLIST.md": "plan"}


def concern_template(cid: str, bucket: str | None, fname: str, variant: str | None = None) -> str:
    """The template path under references/templates for a concern's file."""
    if bucket is None:
        return fname
    if variant:
        fname = fname.replace(".md", f".{variant}.md")
    return f"{bucket}/{fname}"


def canonical_paths(rows: list[dict], docs_root: str, root_docs: bool) -> dict[str, str]:
    """The path each applying concern's doc must have, from references/shape.md: flat under
    COLLAPSE_BELOW docs in all, otherwise a bucket folder once it would hold BUCKET_MIN docs.
    Folder-shaped concerns (decisions, research, plan) keep their own folder either way."""
    bucketed = [r for r in rows if r["bucket"]]
    total = len(bucketed)
    flat = total < COLLAPSE_BELOW or root_docs
    per_bucket: dict[str, int] = {}
    for r in bucketed:
        per_bucket[r["bucket"]] = per_bucket.get(r["bucket"], 0) + 1
    out = {}
    for r in rows:
        if r["bucket"] is None:
            out[r["concern"]] = r["file"]
            continue
        folder = "" if flat or per_bucket.get(r["bucket"], 0) < BUCKET_MIN else r["bucket"] + "/"
        rel = folder + r["file"]
        out[r["concern"]] = rel if root_docs else f"{docs_root}/{rel}"
    return out


FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)[ \t]*#*[ \t]*$")
# The angle-bracket form is how GitHub writes a target with a space in it. Without it the
# link was invisible: the indexed doc read as unreachable (a false P1) and a dead target
# behind the brackets was reported nowhere.
LINK_RE = re.compile(r"(!?)\[[^\]]*\]\((?:<([^>\n]+)>|([^)\s]+))(?:\s+\"[^\"]*\")?\)")
REF_DEF_RE = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+\S")
REF_DEF_TARGET = re.compile(r"^ {0,3}\[([^\]]+)\]:\s+(\S+)")
HTML_HREF = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.I)
REF_USE_RE = re.compile(r"\[[^\]]+\]\[([^\]]+)\]")
FOOTNOTE_RE = re.compile(r"\[\^[^\]]+\]")
# The trailing (?!\.\d) keeps a semver out: fastapi 0.107.0 appears in three docs and is a
# dependency pin, not a measurement anybody has to keep in step.
MEASURE_RE = re.compile(r"\$\d+\.\d+|(?<![\d.])\d{1,3}\.\d+%|(?<![\d.])0\.\d{3,}\b(?!\.\d)")
TRIVIAL_MEASURES = {"$0.00", "0.0%", "100.0%"}
SETEXT_RE = re.compile(r"^ {0,3}(=+|-+)\s*$")
# A list item, a table row or a blockquote opens a block whose indented lines are its
# continuation, not a code block.
LIST_MARKER_RE = re.compile(r"^ {0,3}(?:[-*+]\s|\d+[.)]\s|\||>)")
CODESPAN_RE = re.compile(r"`[^`\n]*`")
BOX_RE = re.compile(r"^\s*[-*] \[( |~|x|X)\]")
DATE_RE = re.compile(r"\b20\d{2}-\d{2}(-\d{2})?\b")
PREFIX_RE = re.compile(r"^([A-Za-z]{2,}-\d+|20\d{2}-\d{2}(-\d{2})?)[-_ .]")
PLACEHOLDER_MARKERS = ("(auto, review me)", "| unreviewed |", "(skeleton, write me)", "| skeleton |", "(draft, review me)", "| draft |")
DRAFT_MARK = "*(draft, review me)*"
# Link targets that are examples, not promises: `[text](url)`, `[x](javascript:...)`, `[y](path/to/file)`.
# The placeholder words match a whole path segment. As a prefix they swallowed bar-chart.md,
# so a genuinely dead link went unreported while its neighbours were found.
# GitHub resolves ../../<thing> from a file at the repository root to the repository itself:
# ../../actions/workflows/x.yml/badge.svg is the standard fork-safe badge link. It is not a
# path into the working tree and cannot be checked as one.
GITHUB_REL = re.compile(r"^\.\./\.\./(actions|issues|pulls|pull|releases|wiki|discussions|blob|tree|commits|compare|labels|milestones|graphs|security|settings)(/|$)")
PLACEHOLDER_TARGET = re.compile(r"^(url|link|path|file|href)$|^javascript:|^\.{3}|[<>{}$*]|(^|/)(path/to|your[-_]\w+|my[-_]\w+|example|foo|bar|placeholder)(?=[./]|$)", re.I)
MAX_JSON_FINDINGS = 1000

warnings: list[str] = []


# ---------------------------------------------------------------- helpers

def read(path: Path) -> str:
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


def walk(root: Path, skip_names: set[str] | None = None, max_depth: int = 12):
    """os.walk with pruning: dot-folders, tooling folders and (optionally) more never get entered.
    Yields (dirpath, dirnames, filenames) with dirnames already pruned."""
    skip = ALWAYS_SKIP | (skip_names or set())
    base_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if len(d.parts) - base_depth >= max_depth:
            if dirnames:
                warnings.append(f"depth cap {max_depth} reached under {d.name}; anything below it was not checked")
            dirnames[:] = []
        dirnames[:] = sorted(n for n in dirnames if n not in skip and not n.startswith("."))
        yield d, dirnames, filenames


# A citation is a path plus a line number; nothing longer than this is one. Long tokens are
# minified code, data URIs and signed URLs, and scanning them costs more than it can find.
MAX_TOKEN = 512

_listing: dict[Path, set[str]] = {}


def exists_exact(path: Path) -> bool:
    """Case-exact existence check, so a Windows run agrees with Linux and GitHub.

    Every component, not only the last: ../Docs/GUIDE.md resolved here and was dead on Linux
    and on github.com, which is the divergence this function exists to prevent.
    """
    if not path.exists():
        return False
    for parent, name in _components(path):
        if parent not in _listing:
            try:
                _listing[parent] = set(os.listdir(parent))
            except OSError:
                return True
        if name not in _listing[parent]:
            return False
    return True


def _components(path: Path):
    """(parent, name) for each component that lies inside a directory we can list.

    The path is collapsed first: `docs/../CLAUDE.md` has a `..` component that no directory
    listing contains, and checking it made every relative link out of a docs folder read as dead.
    normpath, not resolve(), because resolve() also normalises case on Windows - which is the
    difference this whole function exists to catch.
    """
    out = []
    cur = Path(os.path.normpath(str(path)))
    while cur.parent != cur and cur.parent.exists():
        out.append((cur.parent, cur.name))
        cur = cur.parent
    return out[:12]



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


# A line telling the reader not to write a line-number citation necessarily contains one as an
# example. The advice is not the offence.
# Phrases, not the bare word "not": "the handler does not validate its input, see src/a.ts:88"
# is an ordinary sentence carrying a real citation, and it was silently excused.
# "instead of" and "rather than" alone excused any sentence containing them - "use the queue
# rather than polling, see src/poll.ts:40" carried a real citation and was skipped. The
# excuse now needs the sentence to be about line numbers, which is what it was for.
CITE_ADVICE = re.compile(r"\bnever (?:cite|write|use)\b"
                         r"|(?:\binstead of\b|\brather than\b)(?=.*\bline[- ]?numbers?\b)"
                         r"|\bline[- ]?numbers?\b.*(?:\binstead of\b|\brather than\b)"
                         r"|\bdo ?n.t (?:cite|write|use)\b|\bavoid (?:citing|writing|using)\b"
                         r"|\bcite (?:a )?symbols?\b|\bnot line numbers\b", re.I)
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def root_names_lower(repo: Path) -> set[str]:
    try:
        return {p.name.lower() for p in repo.iterdir() if p.is_file()}
    except OSError:
        return set()


def owner_marker_hit(line: str, markers: list[str]) -> bool:
    """An owner line opens with its marker - `**This document owns:**`, `> **Part of** ...`.

    A substring test let "Part of the reason we chose Postgres" in an ordinary first
    paragraph satisfy R2, so a document with no owner line at all passed silently while its
    neighbour warned. Blockquote and emphasis markup come off, then the marker has to be the
    first thing on the line.
    """
    # Emphasis is the signal: the templates write `**This document owns:**` and `> **Part
    # of** ...`, and a sentence that merely begins "Part of the reason" is not bold. A marker
    # that ends in a colon is unambiguous on its own.
    # A blockquote is the other deliberate shape: a split part opens `> Part of [X](x.md)`.
    quoted = line.strip().startswith(">")
    low = line.strip().lstrip(">").strip().lower()
    for m in markers:
        ml = m.lower()
        if low.startswith(("**" + ml, "__" + ml)) or (ml.endswith(":") and low.startswith(ml)):
            return True
        if quoted and low.startswith(ml):
            return True
    return False


def strip_html_comments(text: str) -> str:
    """Commenting a stale link out is how people park one; reporting it as dead is noise."""
    return HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


def strip_fences(lines: list[str]) -> list[str]:
    """Blank out code blocks, fenced and indented, keeping line numbers stable.

    Only fenced blocks were blanked, so a stack trace pasted in a four-space block was read as
    prose: its paths became dead links and its frame lines became line-number citations, and
    both are failures rather than advice. An indented block needs a blank line before it and a
    parent that is not a list item, which is what keeps a list continuation out of this.
    """
    out: list[str] = []
    fence: str | None = None
    indented = False
    prev_blank = True
    prev_top = ""
    for line in lines:
        m = FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1)
            out.append("")
            prev_blank = False
            continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append("")
            prev_blank = False
            continue
        blank = not line.strip()
        deep = line.startswith("    ") or line.startswith("\t")
        if indented and not blank and not deep:
            indented = False
        if not indented and deep and prev_blank and not LIST_MARKER_RE.match(prev_top) and prev_top.strip():
            indented = True
        if indented and not blank:
            out.append("")
        else:
            out.append(line)
        if not blank and not deep:
            prev_top = line
        prev_blank = blank
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
    # GitHub renders an emoji shortcode before slugging, and the emoji then drops out - so
    # "Running tests :rocket:" slugs to running-tests-, not running-tests-rocket.
    t = t.strip().lower().replace("\r", "")
    t = re.sub(r":[a-z0-9_+-]+:", "", t)
    t = "".join(ch for ch in t if ch.isalnum() or ch in " _-")
    return t.replace(" ", "-")


def headings(clean: list[str]) -> list[tuple[int, int, str]]:
    """(line_number_1_based, level, text) for every heading outside fences.

    Frontmatter is skipped. Its closing --- made the last key a setext H2, which added a
    phantom anchor and let a `description:` line cover a concern; meanwhile the real `title:`
    was invisible, so every page of a Hugo or Docusaurus site scored zero.
    """
    out = []
    start = 0
    if clean and clean[0].strip() == "---":
        for j in range(1, min(len(clean), 60)):
            if clean[j].strip() in ("---", "..."):
                start = j + 1
                break
    # A frontmatter title is the document's H1 as far as coverage is concerned. Skipping the
    # block was right for anchors and wrong for scoring: on a generator-navigated tree every
    # page has a title: and no H1, so every page scored zero and the tool reported the docs it
    # was looking at as missing.
    if start:
        for j in range(1, start - 1):
            m = re.match(r"^title[:][ 	]*[\"']?(.+?)[\"']?[ 	]*$", clean[j])
            if m:
                out.append((j + 1, 1, m.group(1).strip()))
                break
    for i, line in enumerate(clean[start:], start=start + 1):
        m = HEADING_RE.match(line)
        if m:
            out.append((i, len(m.group(1)), m.group(2)))
            continue
        # setext: a non-blank line followed by === or ---
        if i > start + 0 and i < len(clean) and clean[i - 1].strip() and SETEXT_RE.match(clean[i]) and not clean[i - 1].lstrip().startswith(("|", "-", "*", "#")):
            out.append((i, 1 if clean[i].strip()[0] == "=" else 2, clean[i - 1].strip()))
    return out


HTML_ANCHOR_RE = re.compile(r"""<(?:a|h[1-6]|div|span|p)\b[^>]*\b(?:name|id)\s*=\s*["']([^"']+)["']""", re.I)


def anchors(clean: list[str]) -> set[str]:
    seen: dict[str, int] = {}
    out: set[str] = set()
    for _, _, text in headings(clean):
        base = slug(text)
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.add(f"{base}-{n}" if n else base)
    for line in clean:
        for m in HTML_ANCHOR_RE.findall(line):
            out.add(m.lower())
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
                if d is None:
                    # A key whose default is null still has a shape. {"centralIndex": 42} used to
                    # reach `repo / central_rel` and raise TypeError halfway through the run.
                    want_n = NULLABLE_TYPES.get(k)
                    if v is not None and want_n and not isinstance(v, want_n):
                        names = " or ".join(t.__name__ for t in want_n)
                        sys.stderr.write(f"error: manifest {c}: key {k} must be {names}\n")
                        raise SystemExit(2)
                    continue
                if v is None:
                    continue
                want = bool if isinstance(d, bool) else int if isinstance(d, int) else type(d)
                if not isinstance(v, want) or (want is int and isinstance(v, bool)):
                    sys.stderr.write(f"error: manifest {c}: key {k} must be {want.__name__}\n")
                    raise SystemExit(2)
            # Nested shapes, checked here rather than found by a traceback halfway through a
            # run. Exit 1 is what --fail-on-findings uses, so a crash was indistinguishable in
            # CI from a check that simply failed.
            for key, of in (("counts", ("index", "folder")), ("registries", ("folder", "table"))):
                for row in data.get(key) or []:
                    if not isinstance(row, dict) or any(not isinstance(row.get(f), str) for f in of):
                        sys.stderr.write(f"error: manifest {c}: every {key} entry needs string "
                                         f"{' and '.join(of)}\n")
                        raise SystemExit(2)
            for key in ("ignore", "duplicateExempt", "pathPrefixes", "roots", "citationExtensions", "recordFolders"):
                v = data.get(key)
                if isinstance(v, list) and any(not isinstance(x, str) for x in v):
                    sys.stderr.write(f"error: manifest {c}: {key} must be a list of strings\n")
                    raise SystemExit(2)
            he = data.get("heavyEvidence")
            if isinstance(he, dict):
                for k2, v2 in he.items():
                    if isinstance(v2, bool) or not isinstance(v2, int):
                        sys.stderr.write(f"error: manifest {c}: heavyEvidence.{k2} must be a number\n")
                        raise SystemExit(2)
            ex = data.get("exempt")
            if isinstance(ex, dict):
                for k2, v2 in ex.items():
                    if not isinstance(v2, list) or any(not isinstance(x, str) for x in v2):
                        sys.stderr.write(f"error: manifest {c}: exempt.{k2} must be a list of strings\n")
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
    for d, _, files in walk(repo):
        if "SKILL.md" in files:
            if d == repo:
                warnings.append("SKILL.md at the repo root is not used for exclusion; a single-skill repo is still audited")
                continue
            out.add(d)
    return out


# The four files GitHub reads from .github/ as well as from the root.
GITHUB_DOCS = {"CONTRIBUTING.md", "SECURITY.md", "SUPPORT.md", "CODE_OF_CONDUCT.md"}


def root_files_here(repo: Path) -> list[str]:
    """The standard files this repository actually has, at the root or under .github/.

    A repository that keeps its contributing guide where GitHub documents it was told no doc
    covered the concern, and apply offered to write a second one in docs/.
    """
    here = [f for f in ROOT_FILES if exists_exact(repo / f)]
    here += [".github/" + n for n in sorted(GITHUB_DOCS)
             if n not in here and exists_exact(repo / ".github" / n)]
    return here


def excluded(path: Path, repo: Path, skills: set[Path], ignore: list[str]) -> bool:
    rel_parts = path.relative_to(repo).parts
    # .github/ is where GitHub itself documents CONTRIBUTING, SECURITY, SUPPORT and the code
    # of conduct. Excluding every dot-folder made a repository that follows that convention
    # look as though it had no contributing guide, and apply offered to write a second one.
    if len(rel_parts) == 2 and rel_parts[0] == ".github" and rel_parts[1] in GITHUB_DOCS:
        return False
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
    for d, _, files in walk(folder):
        for name in sorted(files):
            p = d / name
            if p.suffix.lower() in DOC_EXTS and not excluded(p, repo, skills, ignore):
                out.append(p)
    return sorted(out)


def linked_folders(repo: Path, skills: set[Path], ignore: list[str]) -> dict[str, int]:
    """Folders linked from the root files, with their doc counts."""
    found: dict[str, int] = {}
    for name in ROOT_FILES:
        f = repo / name
        if not f.is_file():
            continue
        for _, angled, plain in LINK_RE.findall("\n".join(strip_fences(read(f).splitlines()))):
            target = (angled or plain).strip()
            t = target.split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "<")):
                continue
            # normpath and exists_exact, not resolve(): resolve() returns the on-disk spelling
            # on Windows, so a README linking Docs/ found docs/ here and nothing on Linux.
            if t.startswith("/"):
                continue
            p = Path(os.path.normpath(str(repo / t)))
            if not exists_exact(p):
                continue
            if p.is_file():
                p = p.parent
            if os.path.normpath(str(p)) == os.path.normpath(str(repo)) or not p.is_dir():
                continue
            try:
                rel = p.relative_to(repo).as_posix()
            except ValueError:
                continue
            if rel in found or excluded(p, repo, skills, ignore) or is_package_dir(p):
                continue
            n = len(docs_under(p, repo, skills, ignore))
            if n >= 2:
                found[rel] = n
    return found


def is_package_dir(p: Path) -> bool:
    """A folder with a build manifest is a unit of code (a workspace package, a service), not a docs folder."""
    return any((p / m).is_file() for m in PACKAGE_MANIFESTS) or any(p.glob("*.csproj"))


def linked_package_docs(repo: Path, skills: set[Path], ignore: list[str]) -> list[str]:
    """Markdown files the root files link to inside package folders - a monorepo's per-package
    READMEs. A reader reaches them in one hop from the front door, so they join the doc set."""
    out: list[str] = []
    for name in ROOT_FILES:
        f = repo / name
        if not f.is_file():
            continue
        for _, angled, plain in LINK_RE.findall("\n".join(strip_fences(read(f).splitlines()))):
            target = (angled or plain).strip()
            t = target.split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "<", "/")):
                continue
            p = Path(os.path.normpath(str(repo / t)))
            if not exists_exact(p):
                continue  # same reason as linked_folders: the spelling in the link is the test
            if p.is_dir():
                p = p / "README.md"
            # A root-level doc the front door links (a DEPLOY.md beside the README) is reachable
            # in one hop and belongs to the doc set. Excluding it made the checker declare the
            # concern uncovered and lay a thinner skeleton down beside the real document.
            if not p.is_file() or p.suffix.lower() not in DOC_EXTS:
                continue
            if p.parent == repo and p.name in ROOT_FILES:
                continue  # the standard root files are roots already

            try:
                rel = p.relative_to(repo).as_posix()
            except ValueError:
                continue
            if excluded(p, repo, skills, ignore) or rel in out:
                continue
            folders = [p.parent] + [a for a in p.parent.parents if a != repo and repo in a.parents]
            if any(is_package_dir(a) for a in folders):
                out.append(rel)
    return out


def root_extras(repo: Path, skills: set[Path], ignore: list[str]) -> list[str]:
    """Markdown at the repository root that is not one of the standard files.

    These are documents wherever the docs folder is. Returning early on a docs/ folder made
    them invisible: their concerns read as uncovered and apply offered to create a second copy
    beside each one.
    """
    try:
        return sorted(p.name for p in repo.iterdir()
                      if p.is_file() and p.suffix.lower() in DOC_EXTS
                      and p.name not in ROOT_FILES and not is_community_file(p.name)
                      and not excluded(p, repo, skills, ignore))
    except OSError:
        return []


def discover(repo: Path, skills: set[Path], ignore: list[str]) -> dict:
    pkg = linked_package_docs(repo, skills, ignore)
    pkg += [n for n in root_extras(repo, skills, ignore) if n not in pkg]
    # is_dir()/is_file() are case-insensitive on Windows, so a repo holding Documentation/ was
    # discovered here and not on Linux - the same repo, two sets of findings, and CI is Linux.
    # Match the folder name case-insensitively but keep the spelling on disk: exists_exact made
    # a capitalised Docs/ or Documentation/ - the Linux-kernel and .NET conventions - read as
    # "no docs folder at all", which is a wrong answer where an honest one was available.
    try:
        on_disk = {p.name.lower(): p.name for p in repo.iterdir() if p.is_dir()}
    except OSError:
        on_disk = {}
    for want in DOCS_FOLDER_NAMES:
        name = on_disk.get(want, want)
        d = repo / name
        if exists_exact(d) and d.is_dir() and is_package_dir(d):
            # A docs site that builds itself is a package that happens to be called docs. Taking
            # it as the repo's docs folder found its generator config and switched R1, R4, R11
            # and R12 off for the whole repository - a published SDK reported a clean bill of
            # health because its marketing site lives here.
            continue
        if exists_exact(d) and d.is_dir() and docs_under(d, repo, skills, ignore):
            return {"rule": "a", "status": "resolved", "roots": [name], "candidates": {}, "package_docs": pkg}
    linked = linked_folders(repo, skills, ignore)
    for child in list(linked):
        if any(child != other and child.startswith(other + "/") for other in linked):
            del linked[child]
    if len(linked) == 1:
        return {"rule": "b", "status": "resolved", "roots": list(linked), "candidates": linked, "package_docs": pkg}
    if len(linked) > 1:
        return {"rule": "b", "status": "ambiguous", "roots": [], "candidates": linked, "package_docs": pkg}
    top_md = sorted(p.name for p in repo.iterdir() if p.is_file() and p.suffix.lower() in DOC_EXTS)
    # Community-health files are not documents: root_extras has always excluded them and this
    # rule did not, so a README beside CHANGELOG.md and SECURITY.md - the commonest shape on
    # a public repository - read as "the docs live at the root". Every skeleton then landed
    # beside the code instead of in docs/, and the index was dropped for the README.
    extra = [n for n in top_md if n not in ROOT_FILES and not is_community_file(n)]
    # exists_exact: the roots and the front door are found case-exactly, so discovery has to
    # agree with them, or a lowercase readme.md is a root-docs index here and not on Linux.
    if len(extra) >= 2 and exists_exact(repo / "README.md"):
        # The repository's docs live at its root (an ops-notes repo, say). The README is the index.
        return {"rule": "c", "status": "root-docs", "roots": top_md, "candidates": {}, "package_docs": pkg}
    return {"rule": "c", "status": "root-files-only", "roots": [], "candidates": {}, "package_docs": pkg}


def corroborated(hit: Path) -> bool:
    """An ambiguous marker is believed only when its contents back it up."""
    want = AMBIGUOUS_MARKERS.get(hit.name)
    if hit.name not in AMBIGUOUS_MARKERS:
        return True
    text = read(hit)
    if want is not None:
        low = text.lower()
        # A filename shared with ordinary application config needs more than one word to be
        # believed, because being believed switches R1, R4, R11 and R12 off silently.
        need = 2 if hit.name == "config.toml" else 1
        return sum(1 for w in want if w in low) >= need
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if len(lines) < 2:
        return False
    links = [ln for ln in lines if LINK_RE.search(ln)]
    return len(links) >= 2 and len(links) * 2 >= len(lines)


# Keys a static-site generator uses to order pages. A docs tree where most pages carry a title
# and one of these is navigated by the generator, not by links between the files.
NAV_KEYS = ("sort_rank", "weight", "nav_order", "sidebar_position", "menu", "layout", "permalink")


def infer_generator(docs: list) -> str | None:
    """"external (inferred)" when the pages are ordered by frontmatter rather than by links.

    Prometheus builds its site from another repository, so no config file is here to find - and
    the checker reported 21 documents unreachable, the front door not linking the index, and
    three site routes as dead links, on a healthy and heavily maintained tree.
    """
    considered = [d for d in docs if not d.skipped]
    if len(considered) < 5:
        return None
    fm = 0
    for d in considered:
        # The frontmatter block, and top-level keys in it. Searching the first 600 characters
        # for the substrings "title:" and "layout" matched ordinary prose - "the layout of the
        # button follows the 8px grid" - so a design-system docs folder with title frontmatter
        # switched R1, R4, R11 and R12 off for the whole repository and reported nothing.
        if not d.raw.startswith("---"):
            continue
        end = d.raw.find("\n---", 3)
        if end == -1:
            continue
        keys = set()
        for ln in d.raw[3:end].lower().splitlines():
            if ":" in ln and ln[:1] not in (" ", "\t", "-", "#"):
                keys.add(ln.split(":", 1)[0].strip())
        if "title" in keys and any(k in keys for k in NAV_KEYS):
            fm += 1
    return "external (inferred from frontmatter)" if fm * 2 > len(considered) else None


def detect_generator(repo: Path, roots: list[Path]) -> str | None:
    # One level down as well: a Docusaurus or Hugo site commonly lives in website/ or site/
    # beside the docs it renders, and looking only at the repo root missed every one of them.
    nested = []
    try:
        nested = [p for p in repo.iterdir()
                  if p.is_dir() and not p.name.startswith(".") and p.name.lower() in
                  ("website", "site", "www", "docs-site", "doc-site", "documentation", "docs", "doc")]
    except OSError:
        pass
    places = [repo] + [r for r in roots if r.is_dir()] + nested
    for base in places:
        for m in GENERATOR_MARKERS:
            if (base / m).exists() and corroborated(base / m):
                return posix(base / m, repo)
        for g in GENERATOR_GLOBS:
            hit = next(iter(base.glob(g)), None)
            if hit is not None and corroborated(hit):
                return posix(hit, repo)
    return None


def is_record_folder(folder: Path, docs: list[Path]) -> bool:
    name = folder.name
    # The plan concern's own companion folder: phase-00-foundations.md carries the prefix the
    # heuristic reads as a record, so the skill tripped over the layout it lays down and the
    # proposed manifest froze that in. A tasklist is the living plan, not a record of one.
    if name.lower() in ("tasklist", "tasks"):
        return False
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

INDEX_INTRO = """Pick the one file you need here; do not read the folder. Every doc says what it owns under its title; a fact has one home and the other docs link to it. State is one of `skeleton`, `draft`, `unreviewed`, `reviewed YYYY-MM-DD`, `stale YYYY-MM-DD`."""

# The index is grouped by the bucket a doc lives in - what a reader came to do - then the
# per-package docs and the stray root files. A group with no lines is left out.
INDEX_ORDER = [title for _, title in BUCKETS] + ["Packages", "Root files"]
# One line per doc, llms.txt-shaped: a link, a colon, the owner text, a dash, the state.
INDEX_LINE = re.compile(r"^\s*-\s*\[([^\]]+)\]\(([^)]+)\)\s*:\s*(.*?)\s*(?:-\s*(\S.*?))?\s*$")


def index_content(groups: dict[str, list[str]], name: str, summary: str = "", extra_order: list[str] | None = None) -> str:
    """The central index from its lines: an H1, one sentence on the project, the intro, then one
    H2 per group that has lines. Groups a hand-made index had that are not buckets come after the
    buckets, before Packages, so a rewrite keeps every row a team grouped by hand."""
    out = f"# {name} docs\n\n"
    out += f"> {summary.strip()}\n\n" if summary.strip() else "> *One sentence on what this project is; the README's first paragraph says it.*\n\n"
    out += INDEX_INTRO + "\n"
    buckets = [t for _, t in BUCKETS]
    order = buckets + [g for g in (extra_order or []) if g not in INDEX_ORDER] + ["Packages", "Root files"]
    for title in order:
        lines = groups.get(title) or []
        if lines:
            out += f"\n## {title}\n\n" + "\n".join(lines) + "\n"
    return out


def index_line(title: str, link: str, owns: str, state: str) -> str:
    return f"- [{title}]({link}): {owns} - {state}"


def index_lines(doc: "Doc") -> list[dict]:
    """Every doc line of an index in the list grammar, with its group heading."""
    out: list[dict] = []
    heading = None
    for i, line in enumerate(doc.clean, start=1):
        s_ = line.strip()
        if s_.startswith("## "):
            heading = s_[3:].strip()
            continue
        m = INDEX_LINE.match(line)
        if m:
            out.append({"heading": heading, "title": m.group(1), "target": m.group(2), "owns": m.group(3), "state": m.group(4) or "", "line": i})
    return out


_TEMPLATES_DIR: Path | None = None  # set from the manifest; the bundled folder is the fallback


def template_for(name: str) -> Path | None:
    if _TEMPLATES_DIR is not None and (_TEMPLATES_DIR / name).is_file():
        return _TEMPLATES_DIR / name
    t = TEMPLATES / name
    return t if t.is_file() else None


def owner_text(template: Path) -> str:
    for line in read(template).splitlines():
        if "This document owns:" in line:
            return re.sub(r"\s*\*\((skeleton|draft|auto)[^)]*\)\*\s*$", "", line.split("This document owns:**", 1)[-1]).strip(" *")
    return ""


def doc_title(path: Path, fallback: str) -> str:
    """The H1 of a template or a doc, else the file stem as words."""
    for line in read(path).splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def doc_state(doc: "Doc") -> str:
    """What the index says about a doc that exists: skeleton, draft, else unreviewed until a
    person dates it - a commit is not a review."""
    head = "\n".join(doc.lines[:12])
    if "(skeleton, write me)" in head:
        return "skeleton"
    if "(draft, review me)" in head:
        return "draft"
    return "unreviewed"


def template_sections(template: Path) -> list[tuple[str, str]]:
    """(H2 text, italic guidance line) for each section of a template."""
    lines = read(template).splitlines()
    out = []
    i = 0
    while i < len(lines):
        m = HEADING_RE.match(lines[i])
        if m and len(m.group(1)) == 2:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            guide = lines[j].strip() if j < len(lines) and lines[j].strip().startswith("*") else ""
            out.append((m.group(2).strip(), guide))
        i += 1
    return out


def tokens(text: str) -> str:
    return " " + re.sub(r"[^a-z0-9 ]+", " ", text.lower()).strip() + " "


def concern_score(doc: "Doc", keywords: set[str], default_file: str, front_door: bool = False) -> tuple[int, str]:
    """How strongly a doc covers a concern: file name, H1, then H2s. A README's H1 is the
    project's or package's name, so only its H2s count there, at double weight (a README section is a real home).
    One generic word in a title is not coverage: a doc needs the file name, or two distinct hits,
    or a title hit backed by a section hit."""
    score = 0
    how = []
    name_hit = doc.path.name.lower() == Path(default_file).name.lower()
    if not name_hit:
        # A file whose own name is one of the concern's words is that concern's document, whatever
        # the template calls it: PURPOSE.md is the purpose doc even though the default is
        # PRODUCT.md, and reporting purpose uncovered beside it is how a second copy gets created.
        stem = doc.path.stem.lower().replace("_", " ").replace("-", " ")
        name_hit = stem in {k.lower() for k in keywords}
        # A single-file user guide is the CLI reference of a command-line tool: ripgrep's
        # 1,025-line GUIDE.md was reported as "no CLI doc" and build offered a skeleton beside it.
        if not name_hit and default_file.startswith("CLI_REFERENCE") and stem in ("guide", "manual", "usage", "handbook", "user guide"):
            name_hit = True
    if name_hit:
        score += 6
        how.append("file name")
    h1 = [t for _, lvl, t in doc.headings if lvl == 1]
    # H3 counts too, at the same weight as H2. Reading two of six heading levels meant a
    # README whose sections are ### - ripgrep's shape - covered nothing at all, and the skill
    # proposed a DEVELOPMENT.md beside an existing ### Building.
    h2 = [t for _, lvl, t in doc.headings if lvl in (2, 3)]
    hits: list[str] = []
    kw = {k: tokens(k).strip() for k in keywords}
    if not front_door:
        h1t = tokens(" ".join(h1))
        hits = sorted(k for k, t in kw.items() if f" {t} " in h1t)
        if hits:
            score += 3 * len(hits)
            how.append("H1: " + ", ".join(hits[:3]))
    h2t = tokens(" ".join(h2))
    hits2 = sorted(k for k, t in kw.items() if f" {t} " in h2t)
    if hits2:
        score += (2 if front_door else 1) * len(hits2)
        how.append(("README sections: " if front_door else "H2: ") + ", ".join(hits2[:3]))
    distinct = len(set(hits) | set(hits2))
    if front_door:
        if not hits2:
            return 0, ""
        return max(score, 3), "; ".join(how)
    if not name_hit and not (distinct >= 2 or (hits and hits2)):
        return 0, ""
    return score, "; ".join(how)


_INV_CACHE: dict[tuple, dict] = {}


def repo_inventory(repo: Path, cap_n: int = 100) -> dict:
    # One pass, kept. R7's citation extensions and the concern table each asked for the
    # inventory, so every run walked the repository twice: 2.5 s of a 3.0 s run on a large
    # monorepo, for the same answer.
    key = (str(repo), cap_n)
    if key in _INV_CACHE:
        return _INV_CACHE[key]
    if docs_evidence is None:
        warnings.append("docs_evidence.py not found beside this script; only the universal concerns apply")
        return {"kinds": [], "ecosystems": [], "unknown": True, "packages": [], "services": [], "env": [], "schema": None,
                "routes": None, "cli": [], "exports": [], "frontend": [], "tests": [], "ci": [], "ops": [], "decisions": None,
                "readme": None, "tree": {}, "release": [], "code_files_scanned": 0}
    saved = list(docs_evidence.warnings)
    # use_git=True: the licence gap in R11 and the contribute concern's public-remote fallback
    # both read `decisions`, which det_git leaves as None when git is skipped, so neither could
    # ever fire. A public repo with no LICENSE was never told.
    inv = docs_evidence.inventory(repo, cap_n, use_git=True)
    for w in inv.get("warnings", []):
        if w not in saved:
            warnings.append(f"evidence: {w}")
    _INV_CACHE[key] = inv
    return inv


def evidence_weight(cid: str, inv: dict) -> tuple[int, str]:
    """How much the inventory holds for a concern, as a count and a label for the report."""
    if cid == "http":
        n = int((inv.get("routes") or {}).get("count") or 0)
        return n, f"{n} routes"
    if cid == "data":
        n = int((inv.get("schema") or {}).get("table_count") or len((inv.get("schema") or {}).get("tables") or []))
        return n, f"{n} tables"
    if cid in ("deploy", "architecture"):
        names = {s.get("name") for s in inv.get("services") or [] if s.get("name")}
        return len(names), f"{len(names)} deployable units"
    return 0, ""


def pick_docs_root(repo: Path, roots: list[Path]) -> str:
    """Where new skeletons and the index go: the docs folder at the repo root if there is one, else
    the first root folder that is a direct child of the repo, else a new `docs/`. A nested folder
    such as `server/docs` belongs to one package and never becomes the whole repo's docs home."""
    tops = [r for r in roots if r.is_dir() and r.parent == repo]
    for r in tops:
        if r.name in DOCS_FOLDER_NAMES:
            return r.name
    return posix(tops[0], repo) if tops else "docs"


def unit_dirs(inv: dict, repo: Path) -> list[str]:
    """The packages of a monorepo that deploy on their own: a package folder holding its own
    Dockerfile or platform config. Each earns its own deployment guide; the root doc becomes a map."""
    if "monorepo" not in (inv.get("kinds") or []):
        return []
    pkgs = {str(Path(p.get("path", ".")).as_posix()) for p in inv.get("packages") or [] if p.get("path") not in (None, ".", "")}
    units: set[str] = set()
    for s_ in inv.get("services") or []:
        if s_.get("source") not in ("Dockerfile", "railway", "fly", "render", "Procfile", "app.yaml"):
            continue
        ev = str(s_.get("evidence") or "")
        folder = ev.rsplit("/", 1)[0] if "/" in ev else ""
        if folder and folder in pkgs:
            units.add(folder)
    return sorted(units)


def unit_has_ops(inv: dict, unit: str) -> str | None:
    for o in inv.get("ops") or []:
        ev = str(o.get("evidence") or "")
        if ev.startswith(unit + "/") and not o.get("hint"):
            return f"ops: {ev}"
    for c in (inv.get("jobs") or {}).get("cron") or []:
        if str(c).startswith(unit + "/"):
            return f"cron: {c}"
    return None


def concern_coverage(inv: dict, manifest: dict, docs: list["Doc"], repo: Path, roots: list[Path], root_docs: bool,
                     central_rel: str | None, front_rel: str, convention: str = "sibling", record_folders: list[str] | None = None) -> list[dict]:
    """One row per concern: whether it applies, why, its canonical path, and whether the doc at
    that path exists. A doc elsewhere whose headings match is `misplaced` - a move, not a cover;
    a README section that matches is a `seed`."""
    pins = manifest.get("requiredDocs")
    pin_map: dict[str, object] = {}
    if isinstance(pins, list):
        pin_map = {c: True for c in pins}
    elif isinstance(pins, dict):
        pin_map = dict(pins)
    docs_root = pick_docs_root(repo, roots)
    records = record_folders or []
    candidates = []
    for d in docs:
        if d.rel == central_rel and not root_docs and d.rel != front_rel:
            continue
        if any(part in FIXTURE_DIRS for part in Path(d.rel).parts[:-1]):
            continue  # a README describing test material is not the project's own documentation
        if PREFIX_RE.match(d.path.name) or DATE_RE.search(d.path.name):
            continue  # a dated plan or audit is a record, not the living doc for a concern
        if d.path.parent != repo and SPLIT_PART.search(d.raw[:800]):
            continue  # a part of a split doc; its index is the doc
        candidates.append(d)
    docs_only = "docs-only" in (inv.get("kinds") or [])
    monorepo = "monorepo" in (inv.get("kinds") or [])
    heavy_cfg = manifest.get("heavyEvidence") if isinstance(manifest.get("heavyEvidence"), dict) else {}
    # 1. which concerns apply
    rows: list[dict] = []
    for cid, bucket, applies, default_file, keywords, companions in CONCERNS:
        pin = pin_map.get(cid)
        if pin is False:
            continue
        if isinstance(pin, str) or pin is True:
            reason = "manifest"
        elif docs_only:
            continue  # a repo of notes is asked for nothing it did not ask for
        elif cid == "configuration" and int(heavy_cfg.get("configuration") or 0) and int(inv.get("env_count") or 0) < int(heavy_cfg["configuration"]):
            continue
        elif cid == "integrations" and int(heavy_cfg.get("integrations") or 0) and int((inv.get("integrations") or {}).get("count") or 0) < int(heavy_cfg["integrations"]) and len((inv.get("integrations") or {}).get("outward_env_names") or []) < 3:
            continue
        else:
            reason = applies(inv)
            if reason is None:
                continue
        rows.append({"concern": cid, "bucket": bucket, "applies": reason, "file": default_file(inv), "keywords": keywords,
                     "companions": list(companions), "pin": pin, "unit": None})
    # onboarding is earned by the size of the set, not by evidence: under seven docs its glossary folds into SETUP
    others = [r for r in rows if r["bucket"] and r["concern"] != "onboarding"]
    if len(others) < COLLAPSE_BELOW - 1 and not isinstance(pin_map.get("onboarding"), (str, bool)):
        rows = [r for r in rows if r["concern"] != "onboarding"]
    # per-unit rows in a monorepo: a package that deploys on its own owns its deployment and operations
    units = unit_dirs(inv, repo)
    unit_rows: list[dict] = []
    for u in units:
        ev = next((s_.get("evidence") for s_ in inv.get("services") or [] if str(s_.get("evidence") or "").startswith(u + "/")), u)
        unit_rows.append({"concern": "deploy", "bucket": "guides", "applies": f"unit with its own deploy config: {ev}", "file": "DEPLOYMENT.md",
                          "keywords": next(k for c, b, a, f, k, cs in CONCERNS if c == "deploy"), "companions": [], "pin": None, "unit": u})
        ops = unit_has_ops(inv, u)
        if ops:
            unit_rows.append({"concern": "operate", "bucket": "guides", "applies": f"unit {ops}", "file": "OPERATIONS.md",
                              "keywords": next(k for c, b, a, f, k, cs in CONCERNS if c == "operate"), "companions": [], "pin": None, "unit": u})
    # 2. canonical paths
    paths = canonical_paths(rows, docs_root, root_docs)
    for r in rows:
        r["default_path"] = r["pin"] if isinstance(r["pin"], str) else paths[r["concern"]]
        variant = "map" if (r["concern"] == "deploy" and units) else None
        r["template"] = concern_template(r["concern"], r["bucket"], r["file"], variant)
    for r in unit_rows:
        # a unit's own docs are few, so they sit flat under <unit>/docs
        r["default_path"] = f"{r['unit']}/docs/{r['file']}"
        r["template"] = concern_template(r["concern"], r["bucket"], r["file"])
    rows += unit_rows
    # 3. what exists at the path, else what sits elsewhere
    out = []
    for r in rows:
        cid, keywords = r["concern"], r["keywords"]
        default_path = r["default_path"]
        covered_by = default_path if exists_exact(repo / default_path) else None
        how = "canonical path" if covered_by else ""
        if covered_by and r["pin"] and isinstance(r["pin"], str):
            how = "manifest"
        misplaced, seed, runner_up, near = None, None, None, None
        if not covered_by and cid == "changelog" and tracked_file(repo, "CHANGELOG.md"):
            misplaced, how = "CHANGELOG.md", "the root changelog"
        elif not covered_by and r["bucket"] is not None:
            scope = (lambda d: d.rel.startswith(r["unit"] + "/")) if r["unit"] else (lambda d: not any(d.rel.startswith(u + "/") for u in units))
            scored = []
            for d in candidates:
                if not scope(d):
                    continue
                if matches_any(d.rel, records) and cid not in ("changelog", "research", "plan"):
                    continue  # a record never covers a living concern
                if is_community_file(d.rel) and not (cid == "contribute" and d.path.name.upper().startswith(("CONTRIBUTING", "CODE_OF_CONDUCT"))
                                                     or cid == "changelog" and d.path.name.upper().startswith("CHANGELOG")
                                                     or cid == "security" and d.path.name.upper().startswith("SECURITY")):
                    continue
                is_readme = d.rel == front_rel or (d.path.name.upper().startswith("README") and ("/" in d.rel or monorepo))
                sc = concern_score(d, keywords, r["file"], front_door=is_readme)
                if OLD_NAMES.get(d.path.name) == cid and not is_readme:
                    sc = (max(sc[0], 6), "old file name")
                if sc[0] >= 3:
                    scored.append((sc, d, is_readme))
            scored.sort(key=lambda x: -x[0][0])
            dedicated = [x for x in scored if not x[2]]
            readmes = [x for x in scored if x[2]]
            if dedicated:
                (sc, how), d, _ = dedicated[0]
                misplaced = d.rel
                if len(dedicated) > 1 and dedicated[1][0][0] >= sc - 1:
                    runner_up = dedicated[1][1].rel
            elif readmes:
                seed = readmes[0][1].rel
                how = f"{seed} has a section to seed from"
            if not misplaced:
                stem = Path(r["file"]).stem.split("_")[0].lower()
                aliases = {a for a in CONCERN_ALIASES.get(cid, ())}
                for d in candidates:
                    if not scope(d) or d.rel == front_rel:
                        continue
                    dn = d.path.stem.lower()
                    if len(dn) > 3 and any(a in dn or dn in a for a in aliases if len(a) > 3):
                        near = d.rel
                        break
                    if len(stem) > 3 and len(dn) > 3 and (stem in dn or dn in stem) and not re.search(r"plan|roadmap|todo|backlog", dn.replace(stem, "")):
                        near = d.rel
                        break
        elif not covered_by and cid == "agent":
            # a CLAUDE.md with content is the agent file under another name: keep it, import it
            if tracked_file(repo, "CLAUDE.md") and read(repo / "CLAUDE.md").strip() not in ("", "@AGENTS.md"):
                seed = "CLAUDE.md"
                how = "CLAUDE.md has content to seed from"
        matched_heading = None
        if seed and ": " in how and seed in (front_rel,):
            doc = next((d for d in candidates if d.rel == seed), None)
            if doc:
                kws = {tokens(k).strip() for k in keywords}
                matched_heading = next((t for _, lvl, t in doc.headings if lvl in (2, 3) and any(f" {k} " in tokens(t) for k in kws)), None)
        out.append({"concern": cid, "unit": r["unit"], "bucket": r["bucket"], "applies": r["applies"], "default_path": default_path,
                    "weak": False, "matched_heading": matched_heading, "near_name": near, "template": r["template"],
                    "companions": r["companions"], "covered_by": covered_by, "matched_by": how, "runner_up": runner_up,
                    "seed": seed, "misplaced": misplaced, "universal": cid in UNIVERSAL})
    return out


def section_states(doc: "Doc", template: Path) -> dict:
    """skeleton / draft / reviewed per template section, and template sections the doc lacks."""
    tsec = template_sections(template)
    guides = {slug(h): g for h, g in tsec}
    states: dict[str, str] = {}
    # bodies of the doc's H2s
    h2s = [(i, t) for i, lvl, t in doc.headings if lvl == 2]
    # One marker per document, on the owner line: a section under a drafted owner line is a
    # draft whether or not it repeats the marker. Seven markers per doc was ceremony.
    owner_draft = any(DRAFT_MARK in l for l in doc.lines[:12])
    for n, (line_no, text) in enumerate(h2s):
        end = h2s[n + 1][0] - 1 if n + 1 < len(h2s) else len(doc.lines)
        body = [l.strip() for l in doc.lines[line_no:end] if l.strip()]
        key = slug(text)
        if not body or (key in guides and guides[key] and body == [guides[key]]) or (len(body) == 1 and body[0].startswith("*") and body[0].endswith("*")):
            states[text] = "skeleton"
        elif body[-1] == DRAFT_MARK or owner_draft:
            states[text] = "draft"
        else:
            states[text] = "reviewed"
    have = {slug(t) for _, t in h2s}
    missing = [h for h, _ in tsec if slug(h) not in have]
    owner = "skeleton" if "(skeleton, write me)" in doc.raw else ("draft" if "(draft, review me)" in doc.raw else "reviewed")
    return {"owner": owner, "sections": states, "missing": missing}


def in_git_repo(repo: Path) -> bool:
    """Whether git can answer questions about this directory at all.

    A scratch copy built from `git ls-files` has no .git, and every root file then read as
    untracked - so the manifest apply writes dropped the README from the doc set and keyed the
    routing table to an agent file that does not exist.
    """
    if shutil.which("git") is None:
        return False
    try:
        p = subprocess.run(["git", "-C", str(repo), "rev-parse", "--git-dir"], capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=GIT_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return False
    return p.returncode == 0


def tracked_file(repo: Path, name: str) -> bool:
    """Present and, when git can answer, tracked: a gitignored CLAUDE.md is one person's file, not the repo's."""
    p = repo / name
    if not p.is_file():
        return False
    git = shutil.which("git")
    if git is None or not in_git_repo(repo):
        return True
    try:
        r = subprocess.run([git, "ls-files", "--error-unmatch", name], cwd=str(repo), text=True, timeout=GIT_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return True


RUN_WORDS = ("install", "installation", "getting started", "quickstart", "quick start", "setup", "usage", "running", "development")
LICENCE_FILES = ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md", "LICENCE.txt",
                 "COPYING", "COPYING.txt", "LICENSE-MIT", "LICENSE-APACHE")


def is_start_here_heading(text: str) -> bool:
    return any(w in text.lower() for w in START_HERE_WORDS)


def front_door_gaps(doc: "Doc", repo: Path, coverage: list[dict], inv: dict) -> list[str]:
    """What a reader landing here cannot find anywhere. Each gap is real, not a missing heading:
    the intro paragraph answers what this is; the Start here block's link answers how to run it
    when a doc covers `develop`; the licence is asked about only when a LICENSE file exists and the
    front door never mentions it - a remote host says nothing about whether a repo is public."""
    gaps = []
    if not [l for l in doc.lines[:12] if l.strip() and not l.lstrip().startswith("#")]:
        gaps.append("what this is - the first lines under the H1 are a heading, not a sentence")
    text = tokens(" ".join(t for _, lvl, t in doc.headings if lvl in (1, 2)))
    develop = next((r for r in coverage if r["concern"] == "develop"), None)
    if (develop is not None and not develop.get("covered_by")
            and not any(f" {tokens(w).strip()} " in text for w in RUN_WORDS)):
        gaps.append("how to run it - no doc covers `develop` and the front door has no setup section")
    # A listing, compared case-insensitively on every platform: is_file() accepted a
    # lowercase `license` on Windows and not on Linux, so the same repository was told
    # it had no licence by CI and not by the developer. Either answer is defensible;
    # two different ones are not.
    if (any(n.lower() in root_names_lower(repo) for n in LICENCE_FILES)
            and " licence " not in text and " license " not in text):
        gaps.append("its licence - a LICENSE file exists at the root and the front door never mentions it")
    return gaps


def agent_file(repo: Path) -> str | None:
    """The agent instruction file this repo actually ships. A gitignored one is a person's own."""
    return next((f for f in (AGENT_FILE, "CLAUDE.md") if tracked_file(repo, f)), None)


def has_start_here(doc: "Doc") -> bool:
    h2 = tokens(" ".join(t for _, lvl, t in doc.headings if lvl == 2))
    return any(f" {tokens(w).strip()} " in h2 for w in START_HERE_WORDS) or START_HERE_OPEN in doc.raw


PROJECT_NAME_SOURCES = (
    ("package.json", r'"name"\s*:\s*"(?:@[^/"]+/)?([^"]+)"'),
    ("pyproject.toml", r'^\s*name\s*=\s*"([^"]+)"'),
    ("Cargo.toml", r'^\s*name\s*=\s*"([^"]+)"'),
    ("go.mod", r"^module\s+(\S+)"),
    ("pom.xml", r"<artifactId>([^<]+)</artifactId>"),
    ("settings.gradle", r"rootProject\.name\s*=\s*[\'\"]([^\'\"]+)"),
    ("settings.gradle.kts", r"rootProject\.name\s*=\s*[\'\"]([^\'\"]+)"),
    ("composer.json", r'"name"\s*:\s*"(?:[^/"]+/)?([^"]+)"'),
)


def project_name(repo: Path) -> str:
    """What the project calls itself.

    The checkout folder is not the project: a clone into work/ or a sandbox copy renames the
    product in every doc the skill writes, and the error is invisible whenever the two happen
    to match. The first manifest that names itself wins; the folder is the last resort.
    """
    for fname, pat in PROJECT_NAME_SOURCES:
        f = repo / fname
        if not f.is_file():
            continue
        text = read(f)
        if fname == "pom.xml":
            # The first <artifactId> in a Spring project is its parent POM's, not its own.
            text = re.sub(r"<parent>.*?</parent>", "", text, flags=re.S)
        m = re.search(pat, text, re.M)
        if m and m.group(1).strip():
            return m.group(1).strip().rsplit("/", 1)[-1]
    return repo.name


def start_here_block(repo: Path, front_rel: str, docs_root: str, central_rel: str, coverage: list[dict]) -> str:
    """The README's hand-off section. Names files that exist or that apply creates; authors nothing else."""
    name = project_name(repo)
    agent_row = next((r for r in coverage if r["concern"] == "agent"), None)
    agent = (agent_row["covered_by"] or agent_row["default_path"]) if agent_row else agent_file(repo)
    steps = [f"1. **This file** - what {name} is and how the repository is laid out.",
             f"2. **[{central_rel}]({central_rel})** - the index of every doc: what each one owns and its state. Pick the one file you need there; do not read the folder."]
    if agent:
        steps.append(f"3. **[{agent}]({agent})** - the commands and conventions a coding agent or a new contributor needs, forty lines at most.")
    stops = []
    for cid, label in (("setup", "how to run it"), ("develop", "the daily loop"), ("architecture", "the architecture")):
        row = next((r for r in coverage if r["concern"] == cid and not r.get("unit")), None)
        if row is None:
            continue
        path = row["covered_by"] or row["default_path"]
        state = row.get("state") or ("reviewed" if row["covered_by"] else "skeleton")
        if state == "skeleton":
            continue  # a skeleton is not a first stop; the index says it exists
        stops.append(f"[{label}]({path})" + ("" if state == "reviewed" else f" ({state})"))
    lines = [START_HERE_OPEN, "## Start here", "",
             f"{'Three' if agent else 'Two'} files, in this order. Everything else is one hop from the {'second' if agent else 'last'} one.", ""]
    lines += steps
    first_stops = ("From the index, the usual first stops: " + ", ".join(stops) + ". " if stops
                   else "The docs a reader starts with are still skeletons; the index says which. ")
    lines += ["", first_stops + "The index says which file is which; this README keeps no list of its own, so the two cannot drift.", "",
              f"The docs have a shape and a checker: one index, five buckets by what a reader came to do, an owner line on every doc, no line-number citations. `docs_structure.py --repo .` from the docs-structure skill checks it; `{docs_root}/structure.json` is its manifest.",
              START_HERE_CLOSE]
    return "\n".join(lines) + "\n"


def package_description(repo: Path, folder: Path) -> str:
    """What a package says it is, from its own manifest: package.json description, pyproject
    description, Cargo.toml description. A README's first sentence was prose written for another
    context and came out as half a sentence with a link inside a table cell."""
    pj = folder / "package.json"
    if pj.is_file():
        try:
            d = json.loads(read(pj)).get("description")
            if isinstance(d, str) and d.strip():
                return d.strip()
        except ValueError:
            pass
    for name in ("pyproject.toml", "Cargo.toml"):
        f = folder / name
        if f.is_file():
            m = re.search(r"^description\s*=\s*\"([^\"\n]+)\"", read(f), re.M)
            if m:
                return m.group(1).strip()
    return ""


def head_month(repo: Path) -> str:
    """YYYY-MM of the head commit, else of today."""
    git = shutil.which("git")
    if git is not None:
        try:
            p = subprocess.run([git, "log", "-1", "--format=%cs"], cwd=str(repo), text=True, timeout=GIT_TIMEOUT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
            if p.returncode == 0 and re.match(r"\d{4}-\d{2}", p.stdout.strip()):
                return p.stdout.strip()[:7]
        except (OSError, subprocess.SubprocessError):
            pass
    return datetime.date.today().strftime("%Y-%m")


def index_tables(doc: "Doc") -> list[dict]:
    """Every table in an index with its group heading and header cells, so apply appends to
    the right one: a hand-grouped index ends with a `file | does` table, and 'the last table'
    put a doc row there."""
    out: list[dict] = []
    heading = None
    for i, line in enumerate(doc.clean, start=1):
        s_ = line.strip()
        if s_.startswith("## "):
            heading = s_[3:].strip()
        elif s_.startswith("|") and i < len(doc.clean) and set(doc.clean[i].replace("|", "").strip()) <= set("-: ") and doc.clean[i].strip().startswith("|"):
            cells = [c.strip().lower() for c in s_.strip("|").split("|")]
            out.append({"heading": heading, "header": cells, "line": i, "docs_table": cells[:3] == ["doc", "owns", "state"]})
    return out


def agent_skeleton(repo: Path, inv: dict, central_rel: str) -> str:
    """The agent file from evidence: the commands as the manifests name them, each with its source.
    Forty lines is the cap; this writes well under it and leaves the rest to a person."""
    name = project_name(repo)
    cmds: list[str] = []
    seen: set[str] = set()

    def add(label: str, cmd: str, src: str) -> None:
        if label in seen or len(cmds) >= 8:
            return
        seen.add(label)
        cmds.append(f"- {label}: `{cmd}` [{src}]")

    for p in inv.get("packages") or []:
        path = p.get("path") or "."
        pre = "" if path in (".", "") else f"cd {path} && "
        man = p.get("manifest") or ""
        scripts = p.get("scripts") or []
        if man == "package.json":
            add("install", f"{pre}npm ci", f"{p['evidence']}")
            for label, names in (("run", ("dev", "start", "dev:start", "serve")), ("build", ("build",)), ("test", ("test",)), ("lint", ("lint", "check"))):
                hit = next((n for n in names if n in scripts), None)
                if hit:
                    add(label, f"{pre}npm run {hit}", f"{p['evidence']}: scripts.{hit}")
        elif man == "pyproject.toml":
            add("install", f"{pre}pip install -e .", p["evidence"])
            if any(t.get("runners") and "pytest" in t["runners"] for t in inv.get("tests") or [] if t.get("package") == path):
                add("test", f"{pre}pytest", p["evidence"])
        elif man in ("requirements.txt",):
            add("install", f"{pre}pip install -r requirements.txt", p["evidence"])
        elif man == "go.mod":
            add("build", f"{pre}go build ./...", p["evidence"])
            add("test", f"{pre}go test ./...", p["evidence"])
        elif man == "Cargo.toml":
            add("build", f"{pre}cargo build", p["evidence"])
            add("test", f"{pre}cargo test", p["evidence"])
    for tr in (inv.get("tree") or {}).get("task_runners") or []:
        for t in tr.get("targets") or []:
            if t in ("test", "lint", "build", "run", "dev", "check", "fmt"):
                add(t, f"make {t}" if tr["file"].endswith("Makefile") else f"just {t}", tr["file"])
    lines = [f"# {name} - for agents", "",
             f"> **This document owns:** the commands that build, test, run and lint {name}, the conventions an agent cannot infer from the code, and the gotchas. Forty lines at most; the docs index holds everything else. *(draft, review me)*",
             "", "## Commands", ""]
    lines += cmds or ["- open question: no manifest scripts or task-runner targets were found; write the commands by hand"]
    lines += ["", "## Conventions", "", "- open question: branch, commit and PR rules an agent would get wrong without being told",
              "", "## Gotchas", "", "- open question: the thing that costs an afternoon here",
              "", "## Docs", "", f"- [{central_rel}]({central_rel}) - the map; read it before the folder."]
    return "\n".join(lines) + "\n"


def init_block(repo: Path, front_rel: str, coverage: list[dict], inv: dict, have_index: bool, have_manifest: bool,
               front_links_index: bool, root_docs: bool, docs_root: str = "docs", package_docs: list[str] | None = None,
               front_has_start_here: bool = True, central_rel: str | None = None, manifest_groups: dict | None = None,
               index_is_table: bool = False) -> dict | None:
    """What apply would create and move. Names templates, never carries content the agent could
    not read from the template itself; the index, the manifest and the agent file are built here."""
    files: dict[str, dict] = {}
    uncovered = [c for c in coverage if not c["covered_by"] and not c.get("misplaced")]
    moves = [{"from": c["misplaced"], "to": c["default_path"], "concern": c["concern"]} for c in coverage if c.get("misplaced")]
    plan_rows = [c for c in coverage if c["concern"] == "plan"]
    manifest = {
        "roots": ([docs_root] + [f for f in ROOT_FILES if tracked_file(repo, f)] + list(package_docs or [])) if not root_docs
                 else ["*.md"] + [p for p in (package_docs or []) if "/" in p],
        "centralIndex": (central_rel if have_index and central_rel
                         else "README.md" if root_docs else f"{docs_root}/INDEX.md"),
        "indexConvention": "sibling",
        "ownerLine": {"markers": DEFAULT_MANIFEST["ownerLine"]["markers"], "enforce": False},
        "splitAt": 1000,
        "pathPrefixes": [d for d in top_level_dirs(repo) if d not in ("tmp", "temp", "scratch", "public", "static", "assets")],
        "recordFolders": [c["default_path"].rsplit("/", 1)[0] + "/log" for c in coverage if c["concern"] == "research"],
        "counts": [{"index": c["default_path"], "folder": c["default_path"].rsplit("/", 1)[0] + "/tasklist"} for c in plan_rows],
        "frontDoor": front_rel,
        "ignore": [],
    }
    manifest = {k: v for k, v in manifest.items() if v not in ([], {}, None)}
    for k in ("ownerLine", "splitAt", "maxParts", "minPart"):
        if k in manifest and manifest[k] == DEFAULT_MANIFEST.get(k):
            manifest.pop(k)
    if not have_manifest:
        files[f"{docs_root}/structure.json" if not root_docs else "docs-structure.json"] = {"template": "generated", "lines": len(json.dumps(manifest, indent=2).splitlines()), "content": manifest}
    central_out = manifest["centralIndex"]
    lines_out: list[str] = []
    groups: dict[str, list[str]] = {}

    def link_to(path: str) -> str:
        if root_docs:
            return path
        base = central_out.rsplit("/", 1)[0] + "/" if "/" in central_out else ""
        if path.startswith(base):
            return path[len(base):]
        return "../" * base.count("/") + path

    def group_for(c: dict) -> str:
        if c.get("unit"):
            return "Packages"
        return BUCKET_TITLE.get(c.get("bucket") or "", "Root files")

    for c in uncovered:
        t = template_for(c["template"])
        if t is None:
            continue
        if c["concern"] == "agent":
            content = agent_skeleton(repo, inv, central_out)
            files[c["default_path"]] = {"template": f"references/templates/{c['template']}", "lines": len(content.splitlines()),
                                        "why": f"{c['concern']} ({c['applies']})", "concern": c["concern"], "content": content}
            if not tracked_file(repo, "CLAUDE.md") and not (repo / "CLAUDE.md").exists() and (repo / ".claude").is_dir():
                files["CLAUDE.md"] = {"template": "references/templates/CLAUDE.md", "lines": 1, "why": "imports the agent file for Claude Code", "concern": "agent"}
            continue
        files[c["default_path"]] = {"template": f"references/templates/{c['template']}", "lines": len(read(t).splitlines()),
                                    "why": f"{c['concern']} ({c['applies']})" + (f" for {c['unit']}" if c.get("unit") else ""), "concern": c["concern"]}
        base = c["default_path"].rsplit("/", 1)[0] + "/" if "/" in c["default_path"] else ""
        tbase = c["template"].rsplit("/", 1)[0] + "/" if "/" in c["template"] else ""
        for comp in c["companions"]:
            ct = template_for(tbase + comp) or template_for(tbase + comp.replace("ADR-0001-first-decision.md", "ADR-0000-template.md"))
            if ct is None:
                continue
            comp_out = comp.replace("YYYY-MM", head_month(repo)) if "YYYY-MM" in comp else comp
            if exists_exact(repo / (base + comp_out)):
                continue
            files[base + comp_out] = {"template": f"references/templates/{posix(ct, TEMPLATES) if ct.is_relative_to(TEMPLATES) else ct.name}",
                                      "lines": len(read(ct).splitlines()), "why": f"companion of {c['concern']}", "concern": c["concern"]}
        title = doc_title(t, c["default_path"].rsplit("/", 1)[-1][:-3].replace("_", " ").capitalize())
        line = index_line(title + (f" ({c['unit']})" if c.get("unit") else ""), link_to(c["default_path"]), owner_text(t), "skeleton")
        lines_out.append(line)
        groups.setdefault(group_for(c), []).append(line)
    # docs that exist - at their path or about to be moved there - keep their own title and owner line
    for c in coverage:
        src = c["covered_by"] or c.get("misplaced")
        if not src or c["concern"] == "agent" or src == front_rel or not (repo / src).is_file():
            continue
        d = Doc(repo / src, repo)
        t = template_for(c["template"])
        own = ""
        for l in d.lines[:12]:
            if "This document owns:" in l:
                own = re.sub(r"\s*\*\((skeleton|draft|auto)[^)]*\)\*\s*$", "", l.split("owns:**", 1)[-1]).strip(" *")
                break
        own = own or (owner_text(t) if t else "")
        title = doc_title(repo / src, c["default_path"].rsplit("/", 1)[-1][:-3].replace("_", " ").capitalize())
        line = index_line(title + (f" ({c['unit']})" if c.get("unit") else ""), link_to(c["default_path"]), own, doc_state(d))
        lines_out.append(line)
        groups.setdefault(group_for(c), []).append(line)
    agent = agent_file(repo)
    for p in (package_docs or []):
        if not (repo / p).is_file() or p in (front_rel, agent, central_rel, AGENT_FILE, "CLAUDE.md") or is_community_file(p):
            continue
        pd = Doc(repo / p, repo)
        h1 = next((t for _, lvl, t in pd.headings if lvl == 1), Path(p).stem)
        first = next((l.strip() for l in pd.clean[1:60] if l.strip() and not l.startswith(("#", "!", "<", ">", "|", "-", "*", "`", "["))), "")
        first = first.split(". ")[0].rstrip(".") if first else ""
        owns = (package_description(repo, (repo / p).parent) if "/" in p else "") or first or h1
        owns = re.sub(r"[*_`]+", "", owns)
        owns = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", owns).replace("|", "/")
        owns = (owns[:77].rsplit(" ", 1)[0] + "...") if len(owns) > 80 else owns
        line = index_line(p, link_to(p), owns, "unreviewed")
        lines_out.append(line)
        groups.setdefault("Packages" if "/" in p else "Root files", []).append(line)
    extra_order: list[str] = []
    if index_is_table and central_rel and (repo / central_rel).is_file():
        # every row the table index had, under its old heading, in the list grammar; a row whose
        # doc this run places or moves is already above and is skipped here
        cdoc = Doc(repo / central_rel, repo)
        placed = {re.search(r"\]\(([^)]+)\)", l).group(1) for l in lines_out if re.search(r"\]\(([^)]+)\)", l)}
        moved_from = {m["from"] for m in moves}
        cbase = (repo / central_rel).parent
        heading = None
        tables = index_tables(cdoc)
        for line in cdoc.clean:
            s_ = line.strip()
            if s_.startswith("## "):
                heading = s_[3:].strip()
                continue
            if not (heading and s_.startswith("| [") and any(t["docs_table"] and t["heading"] == heading for t in tables)):
                continue
            cells = [c.strip() for c in s_.strip("|").split("|")]
            m_ = re.search(r"\[([^\]]*)\]\(([^)#]+)", cells[0])
            if not m_ or len(cells) < 3:
                continue
            target = m_.group(2)
            rel_target = posix(cbase / target, repo)
            if target in placed or rel_target in moved_from or rel_target in placed:
                continue
            owns = re.sub(r"[*_`]+", "", cells[1]).strip()
            state = re.sub(r"[*_`]+", "", cells[-1]).strip() or "unreviewed"
            group = BUCKET_TITLE.get(heading.lower(), heading)
            if group not in INDEX_ORDER and group not in extra_order:
                extra_order.append(group)
            groups.setdefault(group, []).append(index_line(m_.group(1), target, owns, state))
    if (not have_index or index_is_table) and not root_docs:
        readme = inv.get("readme") or {}
        content = index_content(groups, project_name(repo), readme.get("first_paragraph") or "", extra_order)
        files[central_out] = {"template": "INDEX.md (built in)", "lines": len(content.splitlines()), "content": content,
                              "why": "rewrite in the list grammar" if index_is_table else "the central index"}
    if not files and not moves and front_links_index and (front_has_start_here or root_docs):
        return None
    out: dict = {"files": files, "moves": moves, "index_lines": lines_out, "index_groups": groups,
                 "agent_file": agent,
                 "then": "run the checker again; skeletons show up in the section states until written or filled"}
    if not root_docs and (not front_links_index or not front_has_start_here):
        out["front_door"] = {"path": front_rel,
                             "where": "after the intro paragraph under the H1, before the first H2; replace what sits between the markers on refill",
                             "content": start_here_block(repo, front_rel, docs_root, central_out, coverage),
                             "why": "so the front door hands off to the index in the same three-step shape on every repo (R11)"}
    return out


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
        # Two replacement characters in a hundred means the bytes were not text in any encoding
        # this reads. Judging that as a document with no heading, no owner line and no anchors
        # produced false failures; a file the checker could not read is reported as exactly that.
        self.undecodable = self.raw.count(chr(0xFFFD)) * 50 > max(len(self.raw), 1)
        if self.undecodable:
            self.skipped = True
        self.lines = self.raw.splitlines()
        # HTML comments are blanked before anything reads the text: parking a stale link in a
        # comment is routine, and reporting it as a P1 dead link punishes the tidy thing to do.
        # Fences first, then comments. The other order let a `<!--` shown inside a fenced
        # example - this skill's own start-here marker, for instance - blank everything up to
        # the next real comment, and R5 and R7 went silent with no warning.
        self.clean = strip_html_comments("\n".join(strip_fences(self.raw.splitlines()))).splitlines()
        # links and citations are scanned with inline code removed as well
        self.nocode = [CODESPAN_RE.sub("", l) for l in self.clean]
        self.balanced = fences_balanced(self.lines)
        self.headings = headings(self.clean)
        self.anchors = anchors(self.clean)
        self.fm_end = frontmatter_end(self.lines)

    def links(self):
        """(line_no, is_image, target) for every link outside fences."""
        for i, line in enumerate(self.nocode, start=1):
            for img, angled, plain in LINK_RE.findall(line):
                yield i, bool(img), (angled or plain).strip()


def resolve_target(doc_path: Path, repo: Path, file_part: str) -> Path:
    """Resolve a link target the way GitHub does: root-relative from the repo, else from the doc."""
    file_part = unquote(file_part)
    if file_part.startswith("/"):
        return repo / file_part.lstrip("/")
    return doc_path.parent / file_part


_INDEXES: dict[tuple[str, str], bool] = {}


def indexes_folder(cand: Path, folder: Path) -> bool:
    """Does this doc actually index that folder?

    A doc named after a folder is not automatically its index: docs/architecture.md beside
    docs/architecture/ is usually just a chapter. Calling it an index invented R4 failures on
    correct layouts and, worse, skipped R1 for the folder's docs, so a genuinely orphaned file
    passed. An index links at least half of what it indexes.
    """
    key = (str(cand), str(folder))
    if key in _INDEXES:
        return _INDEXES[key]
    try:
        names = sorted(p.name for p in folder.iterdir() if p.is_file() and p.suffix.lower() in DOC_EXTS)
    except OSError:
        names = []
    if not names:
        out = True
    else:
        text = read(cand)
        inside = cand.parent == folder
        linked = [n for n in names if n != cand.name and
                  ((f"({n})" in text or f"]({n}#" in text) if inside else f"{folder.name}/{n}" in text)]
        want = max(1, (len(names) - (1 if inside else 0)) // 2)
        out = len(linked) >= want
    _INDEXES[key] = out
    return out


def detect_convention(folders: list[Path], repo: Path) -> str:
    """Where this repo keeps a folder's index: beside the folder, or inside it.

    Read from what is on disk. A folder that holds its own index.md or README.md listing its
    chapters is the "inside" shape; a doc named after the folder beside it is "sibling".
    """
    inside = sibling = 0
    for f in folders:
        if sibling_index(f, repo, "sibling"):
            sibling += 1
        elif sibling_index(f, repo, "inside"):
            inside += 1
    return "inside" if inside > sibling else "sibling"


def sibling_index(folder: Path, repo: Path, convention: str) -> Path | None:
    if convention == "inside":
        for name in ("README.md", "INDEX.md", "index.md"):
            if exists_exact(folder / name) and indexes_folder(folder / name, folder):
                return folder / name
        return None
    parent = folder.parent
    try:
        parent.relative_to(repo)
    except ValueError:
        return None
    want = f"{folder.name}.md".lower()
    for p in parent.iterdir():
        if p.is_file() and p.name.lower() == want and indexes_folder(p, folder):
            return p
    return None


def index_for(doc: Doc, repo: Path, roots: list[Path], convention: str) -> Path | None:
    """Walk up from the doc's folder to a root looking for a sibling index. A bucket folder of
    the shape has none - the central index is its index, one hop - and `decisions/` carries its
    own README inside whatever the repo's convention is."""
    folder = doc.path.parent
    while True:
        if folder in roots or folder == repo:
            return None
        idx = sibling_index(folder, repo, convention)
        if idx is None and folder.name == "decisions" and convention != "inside":
            idx = sibling_index(folder, repo, "inside")
        if idx is not None and idx != doc.path:
            return idx
        folder = folder.parent


def part_groups(lines: list[str], cuts: list[int], min_part: int) -> list[tuple[int, int]]:
    """Cut points to (start, end) line ranges, 1-based start, exclusive end. A heading with no
    body merges into the part that follows; a part shorter than min_part merges into the
    part that follows it (or, last, into the one before). Eighteen six-line parts were the
    alternative."""
    n = len(lines)
    bounds = list(cuts) + [n + 1]
    raw: list[tuple[int, int]] = []
    i = 0
    while i < len(bounds) - 1:
        j = i
        while j + 1 < len(bounds) - 1 and not [l for l in lines[bounds[j]:bounds[j + 1] - 1] if l.strip()]:
            j += 1
        raw.append((bounds[i], bounds[j + 1]))
        i = j + 1
    merged: list[tuple[int, int]] = []
    carry: tuple[int, int] | None = None
    for start, end in raw:
        if carry is not None:
            start = carry[0]
            carry = None
        if end - start < min_part:
            carry = (start, end)
            continue
        merged.append((start, end))
    if carry is not None:
        if merged:
            s0, _ = merged.pop()
            merged.append((s0, carry[1]))
        else:
            merged.append(carry)
    return merged


def split_analysis(doc: Doc, split_at: int, max_parts: int, min_part: int = 80) -> dict:
    """Where a doc could be cut. Reports, never cuts."""
    # A manifest that lowers splitAt for a small repo keeps the ratio: a part is never asked to
    # be longer than a fifth of what counts as long, or every section merges into one.
    min_part = max(1, min(min_part, split_at // 5))
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
        parts = [end - start for start, end in part_groups(doc.lines, [c[0] for c in cuts], min_part)]
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
        if discovery["status"] == "root-docs":
            pass  # every top-level doc is a root; the README is the index
        # exists_exact, not is_file(): is_file() is case-insensitive on Windows, so a repo with
        # a lowercase readme.md was checked here as README.md and on Linux as readme.md - two
        # verdicts for the same tree, and a proposed manifest naming a root that CI reports as
        # missing. This is the divergence exists_exact was written for.
        elif discovery["status"] != "resolved":
            roots_rel = root_files_here(repo)
        else:
            roots_rel += root_files_here(repo)
        roots_rel += [p for p in discovery.get("package_docs", []) if p not in roots_rel]  # a monorepo's per-package READMEs
    expanded: list[str] = []
    for r in roots_rel:
        if any(ch in r for ch in "*?["):
            if r.endswith("*.md") or r.endswith("*.mdx"):
                folder = repo / r.rsplit("/", 1)[0] if "/" in r else repo
                hits = sorted(posix(p, repo) for p in folder.glob(r.rsplit("/", 1)[-1]) if p.is_file())
            else:
                hits = sorted(posix(p, repo) for p in repo.glob(r) if p.is_file())
            if not hits:
                # A pattern matching nothing used to leave the "root does not exist" loop with an
                # empty list, so a manifest glob that matched no files produced "Docs checked: 0"
                # and a green run. A checker silently checking nothing is what it exists to stop.
                warnings.append(f"root pattern {r} matches no files; nothing under it was checked")
            expanded += hits
        else:
            expanded.append(r)
    roots_rel = list(dict.fromkeys(expanded))
    roots = [repo / r for r in roots_rel if (repo / r).exists()]
    for r in roots_rel:
        if not (repo / r).exists():
            warnings.append(f"root {r} does not exist")

    root_docs = discovery is not None and discovery["status"] == "root-docs"
    root_files_only = discovery is not None and discovery["status"] not in ("resolved", "root-docs")
    generator = detect_generator(repo, roots)
    other_format_docs = []
    for base in [repo] + [r for r in roots if r.is_dir()]:
        try:
            other_format_docs += [posix(p, repo) for p in base.iterdir()
                                  if p.is_file() and p.suffix.lower() in OTHER_DOC_EXTS]
        except OSError:
            pass
    other_format_docs = sorted(set(other_format_docs))[:20]
    generated_docs = 0
    if generator and "/" in generator:
        gen_root = (repo / generator).parent
        try:
            generated_docs = sum(1 for _, _, files in walk(gen_root)
                                 for f in files if Path(f).suffix.lower() in DOC_EXTS)
        except OSError:
            generated_docs = 0

    # ---- doc set
    paths: list[Path] = []
    non_doc = 0
    for r in roots:
        if r.is_file():
            paths.append(r)
            continue
        for d, _, files in walk(r):
            for name in sorted(files):
                p = d / name
                if excluded(p, repo, skills, ignore):
                    continue
                if p.suffix.lower() in DOC_EXTS:
                    paths.append(p)
                elif p.name != "structure.json":
                    non_doc += 1
    paths = sorted(set(paths))
    docs = [Doc(p, repo) for p in paths]
    # After the docs are read: a tree ordered by frontmatter is generator-owned even when the
    # generator's config lives in another repository, which no file test here can see.
    if generator is None:
        generator = infer_generator(docs)
    by_rel = {d.rel: d for d in docs}

    folders = sorted({d.path.parent for d in docs if d.path.parent not in roots and d.path.parent != repo})
    detected_records = sorted(posix(f, repo) for f in folders if is_record_folder(f, paths))
    # A manifest that names recordFolders is authoritative; the heuristic only runs when it is
    # silent, so committing the proposed manifest freezes the result instead of re-guessing.
    explicit_records = manifest.get("recordFolders")
    record_folders = sorted(explicit_records) if explicit_records is not None and source == "found" and "recordFolders" in raw_keys else detected_records

    def in_record(rel: str) -> bool:
        return matches_any(rel, record_folders)

    def exempt(rule: str, rel: str) -> bool:
        return matches_any(rel, list((manifest.get("exempt") or {}).get(rule, [])))

    # Ambiguous discovery lists two competing docs folders and checks neither. SKILL.md says
    # to report them and ask; writing skeletons into a third place, having read none of the
    # candidates' docs, is the guess it forbids - so R12 stays quiet and apply writes nothing.
    ambiguous = bool(discovery and discovery.get("status") == "ambiguous")
    # Set once coverage exists, below: every concern scoring zero means the heading keywords
    # did not fit this repository - a Spanish docs set, a README written in HTML - not that the
    # documents are absent. Proposing the English skeleton set beside them is the confident
    # wrong answer, and "I could not tell" is the honest one.
    unreadable = False
    convention = manifest.get("indexConvention") or detect_convention(folders, repo)
    central_rel = manifest.get("centralIndex")
    # Only a discovery that actually found root docs, never root-files-only. Counting the root
    # files instead meant adding a CLAUDE.md flipped the whole layout: the same repository laid
    # its skeletons in docs/ without it and at the root with it, and lost its index.
    if discovery and discovery.get("status") == "root-docs":
        root_docs = True  # every root is a top-level file: the docs live at the repo root and the README is their index
    if not central_rel and root_docs:
        central_rel = "README.md"
    if not root_docs and central_rel and central_rel == (manifest.get("frontDoor") or "README.md") and not any(r.is_dir() for r in roots):
        # The front door is the index and no folder is a root: the docs live at the repo root.
        # Without this a manifest that names its docs one by one exempts every one of them from R1.
        root_docs = True
    if not central_rel and not root_files_only and not root_docs:
        for r in roots:
            if r.is_dir():
                # The conventional names first, then any doc in the folder that actually indexes
                # it: a complete docs/CONTENTS.md or docs/INDICE.md used to produce "no central
                # index" and one P1 per doc, including the index itself.
                names = ["INDEX.md", "index.md", "README.md"]
                try:
                    names += sorted(p.name for p in r.iterdir()
                                    if p.is_file() and p.suffix.lower() in DOC_EXTS and p.name not in names)
                except OSError:
                    pass
                for name in names:
                    # is_file() is case-insensitive on Windows, so docs/index.md would be recorded
                    # as docs/INDEX.md and then fail to match any case-exact link target.
                    # A file called INDEX.md is the index by name. Requiring it to link half the
                    # folder made an index that had fallen behind vanish - the checker then said
                    # the repo had no index at all, counted the index among the unreachable, and
                    # reported fewer findings than a healthier repo. The half-link test stays for
                    # a doc that merely shares a folder's name, which is what it was written for.
                    conventional = name.lower() in ("index.md", "readme.md")
                    if exists_exact(r / name) and (conventional or indexes_folder(r / name, r)):
                        central_rel = posix(r / name, repo)
                        break
            if central_rel:
                break
    central = repo / central_rel if central_rel else None
    central_exists = bool(central and exists_exact(central))

    # links out of a file, resolved to repo-relative paths (outside fences)
    def links_out(doc: Doc) -> set[str]:
        # Inline links, reference definitions and HTML hrefs. R5 already resolves the first two,
        # so an index written with [Guide][g] or <a href> reported its own docs unreachable.
        out = set()
        extra = [m.group(2).strip().strip("<>") for line in doc.clean
                 for m in [REF_DEF_TARGET.match(line)] if m]
        extra += [m.group(1) for line in doc.clean for m in HTML_HREF.finditer(line)]
        for target in [t for _, _, t in doc.links()] + extra:
            t = target.split("#")[0].strip()
            if not t or t.startswith(("http://", "https://", "mailto:", "<")):
                continue
            try:
                # normpath, not resolve(): resolve() returns the on-disk spelling on Windows, so
                # a link to guide.md pointing at Guide.md satisfied R1 here and failed it on the
                # Linux runner. exists_exact exists to stop exactly that divergence.
                tgt = resolve_target(doc.path, repo, t)
                out.add(posix(Path(os.path.normpath(str(tgt))), repo))
                # GitHub renders a link to a folder as that folder's README, and R11 already
                # reads it so. R1 did not, and an index that wrote [Guides](guides/) was told
                # docs/guides/README.md was unreachable - a P1 on a healthy tree.
                if tgt.is_dir():
                    for name in ("README.md", "readme.md", "index.md", "INDEX.md"):
                        if exists_exact(tgt / name):
                            out.add(posix(Path(os.path.normpath(str(tgt / name))), repo))
                            break
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
    # Escaped like pathPrefixes two lines up. Unescaped, a manifest holding "(" or "*" raised
    # re.PatternError and exited 1 - the same code --fail-on-findings uses, which is exactly the
    # confusion the validation above exists to prevent.
    # The default list is JavaScript-shaped, so a .NET or Kotlin repo got none of R7 and was
    # told nothing. When the manifest does not pin the list, add the extensions of whatever
    # languages the inventory actually found.
    # `inv` is built further down, and load_manifest always merges a non-empty default in, so
    # this branch both crashed on an explicit [] and never ran otherwise. The languages come
    # from the ecosystems the discovery step already knows, and the manifest wins only when it
    # actually names the key.
    if "citationExtensions" in raw_keys:
        ext_list = list(manifest.get("citationExtensions") or [])
    else:
        ext_list = list(DEFAULT_MANIFEST["citationExtensions"])
        for eco in (repo_inventory(repo).get("ecosystems") or []):
            ext_list += ECO_EXTENSIONS.get(str(eco).lower(), [])
    exts = "|".join(re.escape(e) for e in dict.fromkeys(ext_list))
    # The quantifier is bounded: unbounded, it backtracks quadratically over one long token
    # (16 KB took a second, and MAX_READ allows 2 MB), which hangs a CI run rather than failing it.
    cite = re.compile(r"[\w./\[\]-]{1,200}\.(?:%s):\d+(?:-\d+)?" % exts)

    for d in docs:
        # strip_fences blanks everything after an unclosed fence, so R5 and R7 stop finding
        # anything below it - and "Failures: 2" then reads exactly like a complete result.
        if not d.skipped and not d.balanced:
            add("R5", d.rel, 1, "a code fence is never closed; links and citations below it were not checked", "warn")
        rec = in_record(d.rel)
        if getattr(d, "undecodable", False):
            add("R5", d.rel, 1, "could not be decoded as UTF-8 or UTF-16, so nothing in it was checked - save it as UTF-8", "warn")
            continue
        if d.skipped:
            warnings.append(f"{d.rel} is over {MAX_READ} bytes and was not analysed")

        # ---- R1 / R4
        if (not r1_off and (d.path not in roots or root_docs) and central_rel != d.rel
                and not is_community_file(d.rel)):
            idx = index_for(d, repo, roots, convention)
            if idx is not None:
                irel = posix(idx, repo)
                if irel not in index_links:
                    index_links[irel] = links_out(by_rel[irel]) if irel in by_rel else links_out(Doc(idx, repo))
                if d.rel not in index_links[irel]:
                    add("R4", irel, 1, f"index does not link {d.rel}, which sits in its folder")
            elif central_exists:
                if d.rel not in central_links:
                    # Under discovery rule (c) the README is the index by fiat, not by anyone's
                    # decision, so a root file it does not link is advice: ripgrep went red in
                    # CI on its first run over AI_POLICY.md. Once a manifest names the index, the
                    # team has said so, and the finding is theirs.
                    add("R1", d.rel, 1, f"not linked from the central index {central_rel}"
                        + (" - the README is the index by discovery; confirm it in a manifest to enforce this"
                           if root_docs and manifest_path is None else ""),
                        "warn" if root_docs and manifest_path is None else "fail")
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
                if owner_marker_hit(line, markers):
                    has_owner = True
                    break
                if seen >= 12:
                    break
        if (not has_owner and not exempt("R2", d.rel) and not d.skipped and generator is None
                and not is_community_file(d.rel)
                and (root_docs and d.rel not in ROOT_FILES or d.path not in roots)):
            if rec:
                pass  # a record folder describes a moment; R6 and R7 already relax there, and so does this
            else:
                add("R2", d.rel, 1, "no owner line near the top and no frontmatter description",
                    "fail" if enforce else "warn")

        # ---- R5 links, anchors, images, reference definitions
        defs = {m.group(1).lower() for l in d.clean for m in [REF_DEF_RE.match(l)] if m}
        # A reference definition's target is a link like any other. The rule table promises
        # these resolve; only the use-without-definition half was ever checked, so a dead
        # [rb]: ./DOES-NOT-EXIST.md was invisible.
        if not d.skipped:
            for i, line in enumerate(d.clean, start=1):
                m = REF_DEF_TARGET.match(line)
                if not m:
                    continue
                target = m.group(2).strip().strip("<>")
                if target.startswith(("http://", "https://", "mailto:", "tel:", "data:", "#")):
                    continue
                if PLACEHOLDER_TARGET.search(target) or (GITHUB_REL.match(target) and d.path.parent == repo):
                    continue
                file_part = target.split("#")[0]
                if file_part and not exists_exact(resolve_target(d.path, repo, file_part)):
                    add("R5", d.rel, i, f"reference definition target does not exist: {file_part}")
        for i, is_img, target in ([] if d.skipped else d.links()):
            if target.startswith(("http://", "https://", "mailto:", "<", "tel:", "data:")):
                continue
            if PLACEHOLDER_TARGET.search(target):
                continue
            if GITHUB_REL.match(target) and d.path.parent == repo:
                continue  # ../../issues from a root file is the repository on github.com
            file_part, _, anchor = target.partition("#")
            # GitHub takes ?plain=1 and ?raw=true on a file link; the path in front of the
            # question mark is the file, and resolving the whole string reported it dead.
            file_part = file_part.split("?", 1)[0]
            anchor = unquote(anchor).lower()
            if generator is not None and (file_part.startswith("/") or (file_part and "." not in Path(file_part).name)):
                continue  # a site route, resolved by the generator, not a file
            if not file_part:
                if anchor and anchor not in d.anchors:
                    # Under a generator the slug is the generator's, not GitHub's: prometheus
                    # writes #modifier for a heading GitHub slugs as #-modifier, so the link is
                    # dead on github.com and live on the published site. Both readings are true;
                    # the checker does not know which one the team reads, so it advises.
                    add("R5", d.rel, i, f"dead anchor #{anchor} (no such heading in this file)"
                        + (" - GitHub's slug rules; the generator may resolve it" if generator else ""),
                        "warn" if generator else "fail")
                continue
            tgt = resolve_target(d.path, repo, file_part)
            if not exists_exact(tgt):
                add("R5", d.rel, i, f"{'image' if is_img else 'link'} target does not exist: {file_part}")
                continue
            tdoc = by_rel.get(posix(tgt, repo))
            if anchor and tdoc is not None and getattr(tdoc, "undecodable", False):
                add("R5", d.rel, i, f"{file_part} could not be decoded, so #{anchor} was not checked", "warn")
                continue
            if anchor and tgt.suffix.lower() in DOC_EXTS and tgt.stat().st_size > MAX_READ:
                # read() bails past MAX_READ and returns "", so every anchor into a large
                # CHANGELOG looked dead. Say what actually happened.
                add("R5", d.rel, i, f"{file_part} is too large to read, so #{anchor} was not checked", "warn")
                continue
            if anchor and tgt.suffix.lower() in DOC_EXTS:
                try:
                    trel = posix(tgt.resolve(), repo)
                except ValueError:
                    trel = None
                tdoc = by_rel.get(trel) if trel else None
                tanchors = tdoc.anchors if tdoc else anchors(strip_fences(read(tgt).splitlines()))
                if anchor not in tanchors:
                    # Same reasoning as the same-file anchor above: under a generator the slug
                    # rules are the generator's, and the link may be live on the published site.
                    add("R5", d.rel, i, f"dead anchor {file_part}#{anchor}"
                        + (" - GitHub's slug rules; the generator may resolve it" if generator else ""),
                        "warn" if generator else "fail")
        # `[text][id]` is a reference-style link only in a doc that defines at least one
        # reference; elsewhere adjacent brackets are tags like `[R7][R8]`.
        if defs and not d.skipped and generator is None:  # a site generator resolves shared reference definitions
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
            # clean, not nocode: backticks are how a path is written in Markdown, and scanning
            # the code-stripped copy meant the rule almost never fired on a real doc. A line
            # that tells the reader NOT to write one - "never line numbers", "instead of" - is
            # excused instead, which is the narrow case that motivated the earlier change.
            for i, line in enumerate(d.clean, start=1):
                if CITE_ADVICE.search(line):
                    continue
                for tok in line.split():
                    if "://" in tok or len(tok) > MAX_TOKEN:
                        continue
                    for m in cite.findall(tok):
                        # A citation names a file in this repository. "node.js:18" in a version
                        # table is not one, and neither is "Python:3.11". With no folder in the
                        # path the file has to actually be there before this reads as a line
                        # reference that has rotted.
                        stem = m.rsplit(":", 1)[0]
                        if "/" not in stem and not (d.path.parent / stem).is_file() and not (repo / stem).is_file():
                            continue
                        add("R7", d.rel, i, f'line-number citation "{m}" - cite a symbol or a log tag',
                            "warn" if rec else "fail")

    # ---- R13 a fact checked outside the repo carries a date; stale dates warn
    stale_days = int(manifest.get("verifiedStaleDays") or 90)
    today = datetime.date.today()
    for d in docs:
        if d.skipped or exempt("R13", d.rel):
            continue
        for i, line in enumerate(d.clean, start=1):
            for src, ymd in VERIFIED_RE.findall(line):
                try:
                    when = datetime.date.fromisoformat(ymd)
                except ValueError:
                    continue
                age = (today - when).days
                if age > stale_days:
                    add("R13", d.rel, i, f"verified against {src.strip()} on {ymd}, older than {stale_days} days - look again or strike the line", "warn")  # no day count: the snapshot must not change with the calendar

    # ---- R14 the index says where each doc stands, in words the checker can read
    if central_exists and not exempt("R14", central_rel):
        cdoc = by_rel.get(central_rel) or Doc(central, repo)
        for i, line in enumerate(cdoc.clean, start=1):
            s_ = line.strip()
            raw_state = None
            lm = INDEX_LINE.match(line)
            if lm:
                raw_state = lm.group(4) or ""
                if not raw_state:
                    add("R14", central_rel, i, "index line carries no state; end it with ' - skeleton', ' - draft', ' - unreviewed', ' - reviewed YYYY-MM-DD' or ' - stale YYYY-MM-DD'", "warn")
                    continue
            elif s_.startswith("|") and not set(s_.replace("|", "").strip()) <= set("-: "):
                cells = [c.strip() for c in s_.strip("|").split("|")]
                if len(cells) < 3 or cells[0].lower() in ("doc", "part", "phase") or not LINK_RE.search(cells[0]):
                    continue
                raw_state = cells[-1]
            if raw_state is None:
                continue
            state = raw_state.strip("*` ").lower()
            m = re.match(r"(skeleton|draft|unreviewed|reviewed|current|stale)\b(.*)$", state)
            if not m:
                add("R14", central_rel, i, f"state '{raw_state[:40]}' is not one of skeleton, draft, unreviewed, reviewed <date>, stale <date>", "warn")
            elif m.group(1) in ("reviewed", "current", "stale") and not re.search(r"\d{4}-\d{2}-\d{2}", m.group(2)):
                add("R14", central_rel, i, f"state '{m.group(1)}' carries no date; write {m.group(1)} YYYY-MM-DD so a reader knows when", "warn")

    # ---- R1 aggregate when no central index
    if not r1_off and not central_exists and unreachable:
        if manifest_path is not None and repo.resolve() in manifest_path.resolve().parents:
            anchor_path, anchor_line = posix(manifest_path, repo), 1
            for i, line in enumerate(read(manifest_path).splitlines(), start=1):
                if "centralIndex" in line:
                    anchor_line = i
                    break
        else:
            anchor_path, anchor_line = unreachable[0], 1
        add("R1", anchor_path, anchor_line,
            f"no central index - {len(unreachable)} doc(s) are linked only from the front door, if at all")

    # ---- R3 candidates
    split_at = int(manifest.get("splitAt") or 1000)
    max_parts = int(manifest.get("maxParts") or 12)
    min_part = int(manifest.get("minPart") or 80)
    candidates = []
    for d in docs:
        if d.skipped:
            if not is_community_file(d.rel):
                add("R3", d.rel, 1, f"over {MAX_READ} bytes, not analysed - oversize by any measure", "warn")
            continue
        if len(d.lines) > split_at and not exempt("R3", d.rel) and not is_community_file(d.rel):
            a = split_analysis(d, split_at, max_parts, min_part)
            candidates.append(a)
            if a["refuse"]:
                add("R3", d.rel, 1, f"{a['lines']} lines, oversize and unsplittable ({a['refuse']}) - needs a human restructure", "warn")
            else:
                add("R3", d.rel, 1, f"{a['lines']} lines - could become an index plus {a['parts']} parts at {a['level']} (largest {a['largest']})", "warn")

    # ---- R3, the other direction: a folder of parts averaging under minPart is confetti from an
    #      older cut, and the checker had no word for it.
    folders: dict[str, list[int]] = {}
    for d in docs:
        if d.path.parent != repo and not d.skipped and SPLIT_PART.search(d.raw[:800]):
            folders.setdefault(posix(d.path.parent, repo), []).append(len(d.lines))
    for folder, sizes in sorted(folders.items()):
        # phase files under tasklist/ and dated records are short by design, not confetti
        if Path(folder).name.lower() in ("tasklist", "tasks") or matches_any(folder, record_folders):
            continue
        if len(sizes) >= 3 and sum(sizes) / len(sizes) < min_part and not exempt("R3", folder):
            add("R3", folder + "/", 1, f"{len(sizes)} parts averaging {sum(sizes) // len(sizes)} lines, under minPart {min_part} - a merge candidate: rejoin them under the index, or into fewer chapters", "warn")

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
            # Silent when neither side exists yet: a counts entry for the TASKLIST pair apply
            # is about to create is a not-yet, not a drift, and warning about it on every run
            # until someone runs apply is noise. Warn only when one half is there.
            if (repo / str(spec.get("index", ""))).exists() or (repo / str(spec.get("folder", ""))).exists():
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
    #      Runs after R12 below, which supplies the coverage the checklist reads.
    front_rel = manifest.get("frontDoor") or "README.md"
    front = repo / front_rel
    front_doc: "Doc | None" = None  # set when R11 applies; the checklist below needs the coverage table
    # Same reason as the roots above: a lowercase readme.md is a different file, and saying
    # otherwise made R11 fire here and not on the Linux runner.
    front_here = exists_exact(front)
    if front_rel != "README.md" and not front_here:
        warnings.append(f"frontDoor {front_rel} does not exist")
    if (central_exists and front_here and not r1_off and not exempt("R11", front_rel)
            and os.path.normpath(str(front)) != os.path.normpath(str(central))):
        fdoc = by_rel.get(front_rel) or Doc(front, repo)
        outgoing = links_out(fdoc)
        # `[docs](docs/)` renders as docs/README.md on GitHub, so a folder link reaches an
        # index of that name.
        folder_hit = central.name.lower() == "readme.md" and posix(central.parent, repo) in outgoing
        if central_rel not in outgoing and not folder_hit:
            add("R11", front_rel, 1, f"front door does not link the central index {central_rel}")
        if not has_start_here(fdoc):
            add("R11", front_rel, 1, "front door has no 'Start here' section - apply inserts one after the intro, pointing at the index", "warn")
        front_doc = fdoc
        root_dirs = [posix(r, repo) for r in roots if r.is_dir()]
        parallel = sorted(t for t in outgoing if t != central_rel and any(t.startswith(rd + "/") for rd in root_dirs) and t in by_rel)
        if len(parallel) >= FRONT_DOOR_PARALLEL:
            add("R11", front_rel, 1,
                f"front door links {len(parallel)} docs directly - a second index that will drift from {central_rel}; keep a handful and point at the index", "warn")

    # ---- R12 concern coverage, and the init block that would create the skeletons
    global _TEMPLATES_DIR
    td = manifest.get("templatesDir")
    _TEMPLATES_DIR = (repo / td) if td and (repo / td).is_dir() else None
    if td and _TEMPLATES_DIR is None:
        warnings.append(f"templatesDir {td} does not exist; bundled templates used")
    docs_root = pick_docs_root(repo, roots)
    inv = repo_inventory(repo)
    coverage = concern_coverage(inv, manifest, docs, repo, roots, root_docs, central_rel, front_rel, convention, record_folders) if generator is None else []
    # Nothing scored AND there are documents to score. A greenfield repo also scores zero,
    # and there the right answer is the skeleton set - so the test is "docs exist that the
    # keywords could not read", not "coverage is empty".
    scorable = [d for d in docs if d.rel != front_rel and not d.skipped]
    # ...and a reason to believe the keywords could not read them. Without that test any small
    # English repository whose headings simply do not match - a README, an index and two notes -
    # was told "coverage could not be determined" and got no R12 findings and no skeletons,
    # which is the case build exists for. A script that cannot read the headings is looking at
    # another writing system; that is measurable, so measure it instead of guessing.
    heads = "".join(t for d in scorable for _, _, t in d.headings)
    foreign = sum(1 for ch in heads if ord(ch) > 127)
    unreadable = (bool(coverage) and len(scorable) >= 2
                  and not any(c.get("covered_by") or c.get("near_name") for c in coverage)
                  and bool(heads) and foreign * 5 > len(heads))
    if front_doc is not None:
        for gap in front_door_gaps(front_doc, repo, coverage, inv):
            add("R11", front_rel, 1, f"front door does not answer {gap} - advice, apply writes none of it", "warn")
        # "One doc owns each fact" was a sentence in the index and nothing checked it at the one
        # file every reader lands on: a README kept its own deployment section while
        # DEPLOYMENT.md sat beside it. A README H2 whose words match a concern another doc owns
        # is that drift in the making; the README keeps a line and a link.
        for cid, bucket, applies, default_file, keywords, companions in CONCERNS:
            row = next((r for r in coverage if r["concern"] == cid and not r.get("unit")), None)
            if not row or not row.get("covered_by") or row["covered_by"] == front_rel or not keywords:
                continue
            kw = {tokens(k).strip() for k in keywords}
            for ln, lvl, text in front_doc.headings:
                if lvl != 2:
                    continue
                t = tokens(text)
                if sum(1 for k in kw if f" {k} " in t) >= 1 and not is_start_here_heading(text):
                    # the section's own lines: stop at the next heading, or the next section's
                    # content made a one-line pointer look like forty lines
                    body = []
                    for l in front_doc.lines[ln:ln + 60]:
                        if l.startswith("#"):
                            break
                        if l.strip():
                            body.append(l)
                    if len(body) <= 1:
                        continue  # a line and a link is the shape asked for
                    # a name inside a link is a pointer, not a second home; a name in backticks
                    # in prose ("set `DATABASE_URL`") is exactly the second home
                    body_text = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", " ".join(body))
                    named = {n for e in (inv.get("env") or []) for n in (e.get("names") or [])} | {s.get("name") for s in (inv.get("services") or []) if s.get("name")}
                    hits = sum(1 for n in named if n and re.search(rf"(?<![A-Za-z0-9_]){re.escape(n)}(?![A-Za-z0-9_])", body_text))
                    # six lines that name two env variables are a second home; so are forty lines that name none
                    if len(body) > 6 or hits >= 2:
                        add("R11", front_rel, ln, f"section '{text}' is a second home for {cid}, which {row['covered_by']} owns - keep a line and a link, move the rest", "warn")
                    break
    if generator is None:
        for c in coverage:
            if c["covered_by"]:
                continue
            manifest_inside = manifest_path is not None and not posix(manifest_path, repo).startswith("/") and ":" not in posix(manifest_path, repo)
            # A finding anchors at something that exists. On a repo with no README at all,
            # nine findings pointed at README.md:1, against this skill's own rule about
            # path:line where a line exists.
            anchor_path = central_rel if central_exists else (posix(manifest_path, repo) if manifest_inside else None)
            if anchor_path is None:
                anchor_path = front_rel if exists_exact(repo / front_rel) else roots_rel[0] if roots_rel else "."
            why = "always" if c["applies"] == "always" else ("named in the manifest" if c["applies"] == "manifest" else f"the repo has {c['applies']}")
            seed = f"; {c['seed']} has a section to seed from" if c.get("seed") else ""
            # A doc this repository has never had is advice, not a failure. Left as a failure it
            # was 86% of every finding on six healthy open-source repositories - three of them
            # reported nothing else - and it turned --fail-on-findings red on day one for
            # every repository that tracks work somewhere other than a TASKLIST.md.
            # A team that wants the gate sets requireConcerns in the manifest.
            if ambiguous:
                continue  # two candidate docs folders went unread; their docs may cover this
            if unreadable:
                continue  # nothing scored anywhere; the report says coverage was not determined
            if c.get("misplaced"):
                # R15 carries the move; R12 says nothing twice
                continue
            unit = f" for {c['unit']}" if c.get("unit") else ""
            if c.get("near_name"):
                add("R12", anchor_path, 1,
                    f"no doc scored for '{c['concern']}'{unit} ({why}), but {c['near_name']} is named for it - confirm before creating {c['default_path']}", "warn")
                continue
            add("R12", anchor_path, 1, f"no doc covers '{c['concern']}'{unit} ({why}{seed}) - apply creates {c['default_path']} from the template",
                "fail" if manifest.get("requireConcerns") else "warn")
        # ---- R15 the layout: a doc that covers a concern sits at that concern's canonical path
        for c in coverage:
            if c.get("misplaced"):
                add("R15", c["misplaced"], 1, f"covers '{c['concern']}' but sits at the wrong path - move to {c['default_path']} (apply moves it and rewrites inbound links)")
    index_is_table = False
    if central_exists and generator is None and not root_docs:
        cdoc0 = by_rel.get(central_rel) or Doc(central, repo)
        if any(t["docs_table"] for t in index_tables(cdoc0)) and not index_lines(cdoc0):
            index_is_table = True
            add("R15", central_rel, 1, "the index is a table; the shape's index is a list - one line per doc, a link, a colon, what it owns, a dash, its state (apply rewrites it)")
    # R11 on the agent file
    if generator is None and not exempt("R11", AGENT_FILE):
        agent_max = int(manifest.get("agentFileMaxLines") or 40)
        if tracked_file(repo, AGENT_FILE):
            n_lines = len([l for l in read(repo / AGENT_FILE).splitlines() if l.strip()])
            if n_lines > agent_max:
                add("R11", AGENT_FILE, 1, f"{n_lines} non-blank lines, over {agent_max} - an agent file is commands, conventions and gotchas; explanation belongs in a doc the index lists", "warn")
            if tracked_file(repo, "CLAUDE.md"):
                ctext = read(repo / "CLAUDE.md").strip()
                if ctext and "@AGENTS.md" not in ctext:
                    add("R11", "CLAUDE.md", 1, "CLAUDE.md has content of its own beside AGENTS.md - make it the one line `@AGENTS.md` so the two cannot drift", "warn")
    states: dict[str, dict] = {}
    for c in coverage:
        if c["covered_by"] and c["covered_by"] in by_rel:
            t = template_for(c["template"])
            if t is not None:
                states[c["covered_by"]] = {"concern": c["concern"], **section_states(by_rel[c["covered_by"]], t)}
                c["state"] = states[c["covered_by"]]["owner"]
                c["missing_sections"] = states[c["covered_by"]]["missing"]
    state_totals = {"skeleton": 0, "draft": 0, "reviewed": 0, "missing": 0}
    for st in states.values():
        for v in st["sections"].values():
            state_totals[v] += 1
        state_totals["missing"] += len(st["missing"])
    # Against the index that exists, or the one init would create.
    front_links_index = True
    if front.is_file() and front_rel != (central_rel or "docs/INDEX.md"):
        fl = links_out(by_rel.get(front_rel) or Doc(front, repo))
        target = central_rel or "docs/INDEX.md"
        front_links_index = target in fl or (target.rsplit("/", 1)[0] in fl)
    front_has = has_start_here(by_rel.get(front_rel) or Doc(front, repo)) if front.is_file() else False
    init = None if (generator is not None or ambiguous or unreadable) else init_block(repo, front_rel, coverage, inv, central_exists, source == "found", front_links_index, root_docs, docs_root,
                                                          sorted(set(discovery.get("package_docs", []) if discovery else []) | {r for r in roots_rel if (repo / r).is_file()}
                                                                 # in a monorepo every package README is a row, linked or not: "one hop from the index" was false for exactly those
                                                                 | ({str(Path(p.get("path", ".")).as_posix()) + "/README.md" for p in (inv.get("packages") or []) if p.get("path") not in (None, ".", "") and (repo / p["path"] / "README.md").is_file()} if "monorepo" in (inv.get("kinds") or []) else set())), front_has,
                                                          central_rel, manifest_groups=manifest.get("indexGroups"), index_is_table=index_is_table)

    # ---- placeholders
    placeholders = 0
    for d in docs:
        for marker in PLACEHOLDER_MARKERS:
            placeholders += d.raw.count(marker)

    # ---- proposed manifest
    proposed = None
    if source == "none" and not root_files_only:
        conv = convention
        proposed = {
            "roots": ["*.md"] if root_docs else roots_rel,
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

    # One manifest, printed and written. The init block built its own with the convention
    # hardcoded and the detected record folders dropped, so the file apply wrote was not the file
    # the report showed, and committing either one changed the failure count. The proposal is the
    # base; init keeps only what it alone knows - the index and roots it is about to create.
    if proposed is not None and init and isinstance(init.get("files"), dict):
        for name, spec in init["files"].items():
            if not name.endswith("structure.json") or not isinstance(spec.get("content"), dict):
                continue
            merged = dict(proposed)
            for key in ("roots", "centralIndex", "counts", "frontDoor"):
                if spec["content"].get(key):
                    merged[key] = spec["content"][key]
            spec["content"] = merged
            spec["lines"] = len(json.dumps(merged, indent=2).splitlines())
            # And the report prints what apply writes. Merging into init alone left two
            # different files behind one name: the user consented to the printed one and
            # apply wrote the other, which is the thing this merge existed to stop.
            proposed.clear()
            proposed.update(merged)

    # Collapse a flood of identical R1s. Past this many, "not linked from the index" has stopped
    # being a fact about each document and become one fact about the repository.
    r1 = [f for f in findings if f["rule"] == "R1" and f["level"] == "fail"]
    if len(r1) > R1_COLLAPSE_AT:
        keep = [f for f in findings if f not in r1]
        first = ", ".join(f["path"] for f in r1[:3])
        keep.append({"rule": "R1", "severity": SEVERITY["R1"], "level": "fail",
                     "docs": [f["path"] for f in r1],
                     "path": central_rel or roots_rel[0] if roots_rel else ".", "line": 1,
                     "message": (f"{len(r1)} docs are not linked from {central_rel} (first: {first}). "
                                 f"One index that links them, or a manifest naming the one this repo uses."
                                 if central_rel else
                                 f"{len(r1)} docs are not linked from any index - this repository has none "
                                 f"(first: {first}). One index, or a manifest naming the one it uses.")})
        findings = keep

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
        "manifest": {"source": source, "path": posix(manifest_path, repo) if manifest_path else None,
                     "proposed_path": (("docs-structure.json" if root_docs else f"{pick_docs_root(repo, roots)}/structure.json")
                                       if proposed is not None else None)},
        "discovery": discovery,
        "coverage_determined": not unreadable,
        "roots": roots_rel,
        "central_index": central_rel if central_exists else None,
        "index_convention": convention,
        # Markdown a generated site owns. A docs/ folder that is itself a package is skipped
        # by discovery, so a 65-page Starlight site read as "Docs checked: 1, no findings" -
        # true, and silent about everything it did not look at.
        "generated_docs": generated_docs,
        # Documents in a format this tool does not parse. Laying Markdown skeletons beside a
        # working AsciiDoc or reStructuredText set, without mentioning it, is the confident
        # wrong answer where an honest one was available.
        "other_format_docs": other_format_docs,
        "generator": generator,
        "record_folders": record_folders,
        "totals": {"docs_checked": len(docs), "non_doc_files": non_doc,
                   "failures": sum(1 for f in findings if f["level"] == "fail"),
                   "warnings": sum(1 for f in findings if f["level"] == "warn"),
                   "placeholders": placeholders, "split_candidates": len(candidates),
                   "concerns_covered": sum(1 for c in coverage if c["covered_by"]), "concerns_missing": sum(1 for c in coverage if not c["covered_by"]),
                   "moves": sum(1 for c in coverage if c.get("misplaced")),
                   "states": state_totals},
        "rules": per_rule,
        "findings": findings,
        "split_candidates": candidates,
        "unreachable": unreachable,
        "proposed_manifest": proposed,
        "init": init,
        "kinds": inv.get("kinds", []),
        "ecosystems": inv.get("ecosystems", []),
        "concerns": coverage,
        "sections": states,
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
    elif disc and disc["status"] == "root-docs":
        L.append(f"Manifest: none, proposed below. The docs live at the repo root ({len(d['roots'])} files); README.md is the index.")
    else:
        L.append(f"Manifest: none, proposed below. Roots: {', '.join(d['roots'])}")
    if d.get("other_format_docs"):
        names = ", ".join(d["other_format_docs"][:4])
        more = "" if len(d["other_format_docs"]) <= 4 else f" and {len(d['other_format_docs']) - 4} more"
        L.append(f"{len(d['other_format_docs'])} document(s) here are not Markdown and were not read: "
                 f"{names}{more}. A concern they cover is still covered.")
    if d.get("generator") and d.get("generated_docs"):
        L.append(f"{d['generated_docs']} Markdown files under a generated site were not checked: "
                 f"{d['generator']} owns their navigation and URLs.")
    L.append(f"Docs checked: {t['docs_checked']}   non-doc files in docs folders: {t['non_doc_files']}")
    # Naming the generator without saying what it turns off read as a note. It decides whether
    # four of the thirteen rules ran at all, and a reader who is not told that reads "Failures: 0"
    # as a clean bill of health.
    gen = d["generator"] or "none"
    if d["generator"]:
        gen += " - R1, R4, R11 and R12 were not checked; dead anchors warn"
    L.append(f"Central index: {d['central_index'] or 'none'}   Index convention: {d.get('index_convention') or 'sibling'}"
             f"   Generator: {gen}")
    if d["record_folders"]:
        L.append(f"Record folders (R6/R7 warn, R8 skipped): {', '.join(d['record_folders'])}")
    L.append(f"Failures: {t['failures']}   Warnings: {t['warnings']}   Placeholders awaiting review: {t['placeholders']}")
    if d.get("kinds"):
        L.append(f"Kinds: {', '.join(d['kinds'])}   Ecosystems: {', '.join(d['ecosystems']) or 'none recognised'}")
    if d.get("concerns") and d.get("coverage_determined") is False:
        L.append("Coverage could not be determined: this repository has documents, and none of them")
        L.append("scored for any concern - the heading keywords are English and these may not be.")
        L.append("Nothing below is a claim that a document is missing, and apply creates nothing.")
        L.append("")
    if d.get("concerns"):
        st = t["states"]
        L.append(f"Concerns: {t['concerns_covered']} covered, {t['concerns_missing']} {'not determined' if d.get('coverage_determined') is False else 'missing'} ({t.get('moves', 0)} of them a move)   Sections: {st['skeleton']} skeleton, {st['draft']} draft, {st['reviewed']} reviewed, {st['missing']} template sections absent from hand-written docs (advice)")
        L.append("")
        L.append("| concern | applies because | covered by | matched by | state |")
        L.append("|---|---|---|---|---|")
        for c in d["concerns"]:
            cov = c["covered_by"] or (f"not determined" if d.get("coverage_determined") is False
                                      else (f"move {c['misplaced']} -> {c['default_path']}" if c.get("misplaced")
                                            else f"none - apply creates {c['default_path']}")) + (f" (seed: {c['seed']})" if c.get("seed") else "")
            extra = f" (also {c['runner_up']})" if c.get("runner_up") else ""
            # Reusing the outer quote inside an f-string expression is PEP 701, so 3.12 only.
            # The skill promises 3.11+, where this is a SyntaxError at import and every one of
            # the three scripts dies.
            weak = " (weak)" if c.get("weak") else ""
            unit = f" ({c['unit']})" if c.get("unit") else ""
            L.append(f"| {c['concern']}{unit} | {c['applies']} | {cov}{weak}{extra} | {c['matched_by'] or '-'} | {c.get('state', '-')} |")
    L.append("")
    L.append("| rule | severity | failures | warnings | first |")
    L.append("|---|---|---|---|---|")
    for r, info in d["rules"].items():
        if info["failures"] or info["warnings"]:
            # R12 anchors every concern at the same line, so this column read
            # "docs/INDEX.md:1, docs/INDEX.md:1, docs/INDEX.md:1". The concern table below
            # names them; here one anchor is the whole answer.
            where = list(dict.fromkeys(info['first']))
            L.append(f"| {r} {info['title']} | {info['severity']} | {info['failures']} | {info['warnings']} | {', '.join(where)} |")
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
        L.append(f"Proposed manifest ({d['manifest'].get('proposed_path') or 'docs/structure.json'}) - review before committing:")
        L.append(json.dumps(d["proposed_manifest"], indent=2))
    if d.get("init"):
        L.append("")
        L.append("Apply would create these skeletons for uncovered concerns (nothing is written now):")
        for path, info in d["init"]["files"].items():
            why = f"  - {info['why']}" if info.get("why") else ""
            L.append(f"  {path}  ({info['lines']} lines, {info['template']}){why}")
        for m in d["init"].get("moves", []):
            L.append(f"  move: {m['from']} -> {m['to']}  ({m['concern']})")
        for row in d["init"].get("index_lines", []):
            L.append(f"  index line: {row}")
        fd = d["init"].get("front_door")
        if fd:
            L.append(f"  {fd['path']}  + a 'Start here' section ({len(fd['content'].splitlines())} lines) {fd['where'].split(';')[0]}")
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
        # On a greenfield repo discovery is root-files-only, so there is no proposal - but apply
        # still writes a manifest, and printing the bare defaults told the operator nothing. The
        # flag answers with what apply would write.
        init_files = ((data.get("init") or {}).get("files") or {})
        written = next((v.get("content") for k, v in init_files.items()
                        if k.endswith("structure.json") and isinstance(v.get("content"), dict)), None)
        print(json.dumps(data["proposed_manifest"] or written or manifest, indent=2))
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
