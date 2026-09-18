#!/usr/bin/env python3
"""Check machine-verifiable documentation claims against the repository.

Read-only. Standard library only. Writes nothing.

    python docs_drift.py                     # text report
    python docs_drift.py --repo ../other     # a different repo
    python docs_drift.py --format json
    python docs_drift.py --no-git-root       # scope to one package of a monorepo

Only checks claims that have a definite answer:

  commands   `npm run x`, `make x`, `./scripts/x` in a fenced block, against the
             scripts, targets and files that actually exist
  links      relative Markdown links and images, against the filesystem
  paths      backticked paths, against the filesystem (opt-in, --check-paths)
  env vars   names documented in docs or .env.example, against names actually
             read by the code, in both directions
  staleness  a doc untouched for far longer than the code it describes

It does not judge prose. Wording, tone, completeness and accuracy of explanation
are the reviewing agent's job; this exists so the agent does not spend forty tool
calls confirming whether a path exists.

Backticked-path checking is opt-in. On real repositories most such references are
ambiguous -- a path the doc is telling you to create, or one an archived report
described accurately at the time -- and reporting them buries the findings that
are unambiguous. Markdown links are always checked, because a link is a promise
to resolve.

Values are never read out of environment files. Only the names to the left of `=`
are used, because the right-hand side is a credential by design.
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GIT_TIMEOUT = 30
MAX_READ = 2_000_000
STALE_DAYS = 120

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "venv", ".venv", "dist", "build", "target",
    "__pycache__", ".next", "coverage", ".terraform", "site-packages",
}
DOC_EXTS = {".md", ".mdx", ".rst", ".txt"}
# The languages where a module is imported by file name, which is the only case in which
# "nothing imports this file" can be decided from the text.
# Ruby is out: Rails autoloads app/ and lib/ by convention, so a .rb file nothing requires is
# the normal state of live code, not a module nothing imports.
FILE_IMPORT_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".php", ".vue", ".svelte"}
CODE_EXTS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
    ".go", ".rs", ".rb", ".php", ".java", ".kt", ".swift", ".cs", ".ex", ".exs", ".sh",
}

FENCE = re.compile(r"^(?:```|~~~)")
# Commands worth checking. Anything else in a fenced block is left alone.
CMD_NPM = re.compile(r"\b(?:npm|pnpm|yarn|bun)\s+run\s+([A-Za-z0-9:_.-]+)")
# `make VAR=value target` and `make -j4 target`: the target is the first word that is neither
# an assignment nor a flag.
CMD_MAKE = re.compile(r"\bmake\s+(?:(?:[A-Za-z0-9_.-]+=\S*|-\S+)\s+)*([A-Za-z0-9_.-]+)(?![=A-Za-z0-9_.-])")
CMD_SCRIPT = re.compile(r"(?:^|\s)(\./[A-Za-z0-9_./-]+|(?:python3?|node|bash|sh|ruby|elixir|php|perl|mix\s+run|deno\s+run|bun)\s+([A-Za-z0-9_./-]+\.[A-Za-z0-9]+))")
# `dotnet run --project src/Api` names a folder or a project file; `cargo run --bin worker`
# names a [[bin]] target or src/bin/worker.rs. Both are checkable, and both were silent.
CMD_DOTNET = re.compile(r"\bdotnet\s+(?:run|test|build|publish)\s+(?:[^\s]+\s+)*?--project\s+([A-Za-z0-9_./-]+)")
CMD_GO = re.compile(r"\bgo\s+(?:run|build|test|install)\s+(?:-\S+\s+)*(\./[A-Za-z0-9_./-]+)")
CMD_CARGO_BIN = re.compile(r"\bcargo\s+(?:run|build|install)\s+(?:[^\s]+\s+)*?--bin\s+([A-Za-z0-9_-]+)")

MD_LINK = re.compile(r"!?\[[^\]]*\]\((?:<([^>\n]+)>|([^)\s]+))")
BACKTICK = re.compile(r"`([^`\n]+)`")

# Placeholder shapes that are not meant to resolve.
PLACEHOLDER = re.compile(
    r"[<>{}$*]|^\.{3}|\.{3}$|(^|/)(path/to|your[-_]|my[-_]|example|foo|bar|baz|placeholder)|^(?:url|link|path|href|file)$",
    re.I)

ENV_IN_CODE = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"),
    re.compile(r"""process\.env\[\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""os\.environ(?:\.get)?\[?\(?\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""os\.getenv\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""getenv\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""ENV\[\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    # ENV.fetch("X") is the Rails idiom, and it was invisible.
    re.compile(r"""ENV\.fetch\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""\$_(?:SERVER|ENV)\[\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    re.compile(r"""\b(?:option_)?env!\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""System\.getenv\(\)\.get\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""\bConfiguration\[\s*"([A-Z][A-Z0-9_]*)"\s*\]"""),
    re.compile(r"""Deno\.env\.get\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
    # The languages CODE_EXTS lists and the patterns above did not read: Go, Rust, Elixir,
    # C#, Java, Vite/Astro, and a destructured process.env. Without these every documented
    # variable in a Go or Rust repository was "a knob that does not exist".
    re.compile(r"""os\.(?:Getenv|LookupEnv)\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""env::var(?:_os)?\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""System\.(?:get_env|fetch_env!?)\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""GetEnvironmentVariable\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""System\.getenv\(\s*"([A-Z][A-Z0-9_]*)\""""),
    re.compile(r"""import\.meta\.env\.([A-Z][A-Z0-9_]*)"""),
    re.compile(r"""\benv\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""),
]
# const { A, B } = process.env - one line, several names.
ENV_DESTRUCTURE = re.compile(r"\{([^}]*)\}\s*=\s*process\.env\b")
# Variables the platform, the shell or the runtime sets. Reading them is not a documentation
# promise, and reporting each one as undocumented was most of the noise on a Node repository.
PLATFORM_ENV = {
    "NODE_ENV", "CI", "HOME", "PATH", "PWD", "TERM", "SHELL", "USER", "LANG", "TZ", "TMPDIR", "TEMP", "TMP",
    "DEBUG", "PORT", "HOSTNAME", "HOST", "NODE_OPTIONS", "npm_package_version", "npm_lifecycle_event",
    "GITHUB_ACTIONS", "GITHUB_TOKEN", "GITHUB_SHA", "GITHUB_REF", "GITHUB_REPOSITORY", "GITHUB_WORKSPACE",
    "GITHUB_OUTPUT", "GITHUB_ENV", "RUNNER_OS", "VERCEL", "VERCEL_ENV", "VERCEL_URL", "NEXT_RUNTIME",
    "RAILWAY_ENVIRONMENT", "RAILWAY_PUBLIC_DOMAIN", "RAILWAY_STATIC_URL", "PYTHONPATH", "VIRTUAL_ENV",
    "RUST_LOG", "RUST_BACKTRACE", "CARGO_MANIFEST_DIR", "JAVA_HOME", "MIX_ENV",
    "DOCKER_HOST", "KUBERNETES_SERVICE_HOST", "LOG_LEVEL",
    "COLUMNS", "LINES", "NO_COLOR", "FORCE_COLOR", "EDITOR", "VISUAL", "XDG_CONFIG_HOME", "APPDATA",
    "LOCALAPPDATA", "USERPROFILE", "SYSTEMROOT", "COMSPEC", "OS", "PROCESSOR_ARCHITECTURE",
    "GOPATH", "GOROOT", "GOFLAGS", "GOOS", "GOARCH", "GOPROXY", "GOPRIVATE", "GOCACHE", "GOBIN", "CGO_ENABLED",
    "GOGC", "GODEBUG", "GOMAXPROCS", "GOTRACEBACK", "GOMEMLIMIT",
    "AWS_REGION", "AWS_DEFAULT_REGION", "AWS_PROFILE", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "AWS_LAMBDA_FUNCTION_NAME", "AWS_EXECUTION_ENV", "SENTRY_DSN", "SENTRY_ENVIRONMENT", "SENTRY_RELEASE",
    "HF_HOME", "HF_TOKEN", "HF_HUB_OFFLINE", "TRANSFORMERS_CACHE", "TOKENIZERS_PARALLELISM", "CUDA_VISIBLE_DEVICES",
    "GOOGLE_APPLICATION_CREDENTIALS", "AZURE_CLIENT_ID", "AZURE_TENANT_ID", "AZURE_CLIENT_SECRET",
    "OTEL_EXPORTER_OTLP_ENDPOINT", "OTEL_SERVICE_NAME", "OTEL_RESOURCE_ATTRIBUTES", "NEXT_PHASE",
    "DJANGO_SETTINGS_MODULE", "FLASK_APP", "FLASK_ENV", "FLASK_DEBUG", "DISPLAY", "WAYLAND_DISPLAY",
    # import.meta.env built-ins, set by Vite, not by an operator.
    "DEV", "PROD", "MODE", "SSR", "BASE_URL", "LANGUAGE",
    "JAVA_HOME", "JAVA_OPTS", "JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS",
}
# Prefixes that belong to a tool or a CI system wholesale; nothing an application names starts
# with these. Vendor names (AWS_, GOOGLE_, SENTRY_, HF_) are deliberately absent: an application
# names its own bucket AWS_S3_UPLOAD_BUCKET and its own token SENTRY_ORG_TOKEN.
PLATFORM_PREFIXES = ("npm_", "GITHUB_", "RUNNER_", "CI_", "VERCEL_", "RAILWAY_", "LC_", "WERKZEUG_",
                     "PLAYWRIGHT_", "PYTEST_", "JEST_", "VITEST", "TERM_", "SSH_", "XDG_", "CARGO_", "RUSTUP_",
                     "MAVEN_", "GRADLE_", "DOTNET_", "ASPNETCORE_", "KUBERNETES_", "LITELLM_", "TORCH_")
ENV_NAME = re.compile(r"\b([A-Z][A-Z0-9_]{2,})\b")
DEAD_CONTEXT = re.compile(r"\b(read by nothing|nothing (?:in [^.]{0,40})?reads|no code [^.]{0,30}reads|no longer (?:read|used)|unused|dead|deprecated|removed|retired|not (?:read|used)|legacy|third[- ]party|someone else's|set by [^.]{0,30}platform|never use|do not use|don't use|must not be used|avoid|its [^.]{0,30}variable)\b", re.I)
# (?<![\w-]) not \b: "zero-config" is not a word about configuration.
CONFIG_CONTEXT = re.compile(r"(?<![A-Za-z0-9_-])(env|environment|variable|export|secret|config|configur\w*|setting|\.env|dotenv|flag|knob)\b", re.I)
CONFIG_SUFFIX = re.compile(r"_(?:URL|URI|DSN|KEY|TOKEN|SECRET|PASSWORD|PASS|HOST|PORT|PATH|DIR|FILE|MODE|ENABLED|DISABLED|TIMEOUT|LIMIT|MAX|MIN|ID|NAME|REGION|BUCKET|ENDPOINT|BASE|VERSION|LEVEL|INTERVAL|SECONDS|MS|TTL|SIZE|COUNT|RATE)$")

# Import forms across the languages handled above. Four alternatives, so findall
# returns tuples and the caller takes the first non-empty group.
IMPORT_SPEC = re.compile(
    r"""(?:from|import)\s+['"]([^'"]+)['"]"""
    r"""|require\(\s*['"]([^'"]+)['"]\s*\)"""
    r"""|^\s*from\s+([A-Za-z0-9_.]+)\s+import"""
    r"""|^\s*import\s+([A-Za-z0-9_.]+)"""
    # from . import bird_x, bird_y  -  the relative form captured only the dot.
    r"""|^\s*from\s+\.+[A-Za-z0-9_.]*\s+import\s+([A-Za-z0-9_, ]+)""",
    re.M)

NL = chr(10)
FROM_IMPORT_NAMES = re.compile(r"^\s*from\s+[A-Za-z0-9_.]+\s+import\s+\(?([A-Za-z0-9_,\s]+?)\)?\s*(?:#.*)?$", re.M)
warnings: list[str] = []


def run_git(args: list[str], cwd: Path) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        p = subprocess.run([git, *args], cwd=str(cwd), text=True, timeout=GIT_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        warnings.append(f"git {' '.join(args[:2])} failed: {exc}")
        return None
    return p.stdout if p.returncode == 0 else None


def list_files(repo: Path) -> list[str]:
    out = run_git(["ls-files", "--cached", "--other", "--exclude-standard"], repo)
    if out is not None and out.strip():
        return sorted(x.strip() for x in out.splitlines() if x.strip())
    warnings.append("git unavailable or empty index; walking the filesystem instead")
    files = []
    for p in repo.rglob("*"):
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts):
            files.append(p.relative_to(repo).as_posix())
    return sorted(files)


_LISTING: dict[str, set[str]] = {}


def exists_exact(path: Path) -> bool:
    """Exists with this exact spelling. Path.exists() is case-insensitive on Windows and macOS,
    so a link to Guide.md pointing at guide.md passed here and broke on the Linux runner."""
    try:
        p = Path(os.path.normpath(str(path)))
        if not p.exists():
            return False
        cur = p
        for _ in range(64):
            parent = cur.parent
            if parent == cur or not cur.name:
                return True
            key = str(parent)
            if key not in _LISTING:
                try:
                    _LISTING[key] = {e.name for e in os.scandir(parent)}
                except OSError:
                    return True
            if cur.name not in _LISTING[key]:
                return False
            cur = parent
        return True
    except (OSError, ValueError):
        return False


def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        raw = path.read_bytes()
        if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
            return raw.decode("utf-16", errors="replace")
        return raw.decode("utf-8-sig", errors="replace")
    except OSError:
        return ""


def available_commands(repo: Path, files: list[str]) -> tuple[dict[str, set[str]], set[str]]:
    """Real npm scripts and make targets, keyed by the directory that declares them."""
    npm: dict[str, set[str]] = {}
    make: set[str] = set()
    for rel in files:
        base = Path(rel).name
        prefix = str(Path(rel).parent).replace("\\", "/")
        if base == "package.json":
            try:
                data = json.loads(read(repo / rel))
            except ValueError:
                continue
            if isinstance(data.get("scripts"), dict):
                npm.setdefault(prefix, set()).update(data["scripts"].keys())
        elif base in ("Makefile", "GNUmakefile", "makefile") or rel.endswith((".mk", "Makefile.common")):
            # Makefile.common and *.mk are what a Makefile includes; prometheus keeps promu:
            # there, and it was reported missing.
            targets = re.findall(r"^([A-Za-z0-9][A-Za-z0-9_.%/-]*):(?!=)", read(repo / rel), re.M)
            make.update(targets)
    return npm, make


# `cd` to an absolute path, `cd ~/deploy`, `cd "$DEPLOY_DIR"`, `ssh box` - from here to the end of the
# fence the commands run somewhere that is not this repository; a ./svc.sh there is not a
# missing file here.
AWAY = re.compile(r"^\s*(?:sudo\s+)?(?:cd\s+(?:/|~|\$|[\x22\x27][/~$])|ssh\s+\S|docker\s+(?:exec|run)\b|kubectl\s+exec\b)")


def fenced_blocks(text: str, *, skip_away: bool = False) -> list[tuple[int, str]]:
    """Yield (line_number, line) for lines inside fenced code blocks.

    With skip_away, a line after a `cd` out of the tree or an `ssh` is dropped until the
    fence closes: whatever runs there is not a path in this repository.
    """
    out: list[tuple[int, str]] = []
    inside = away = False
    for i, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line.strip()):
            inside = not inside
            away = False
            continue
        if not inside:
            continue
        if skip_away:
            if away:
                continue
            if AWAY.match(line):
                away = True
                continue
        out.append((i, line))
    return out


def env_names_from_code(repo: Path, files: list[str]) -> dict[str, list[str]]:
    """Env var names the code reads, mapped to every location that reads them."""
    found: dict[str, list[str]] = {}
    for rel in files:
        if Path(rel).suffix not in CODE_EXTS or any(p in SKIP_DIRS for p in Path(rel).parts):
            continue
        if any(p.startswith(".") and p != ".github" for p in Path(rel).parts[:-1]):
            continue  # tooling under a dot-folder; its docs are skipped, so its reads are too
        text = read(repo / rel)
        if not text or "env" not in text.lower():
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            # A JSDoc line "* The values above use `process.env.X`" is prose, not a read.
            if line.lstrip().startswith(("//", "* ", "*/", "/*", "#")):
                continue
            for pattern in ENV_IN_CODE:
                for name in pattern.findall(line):
                    found.setdefault(name, []).append(f"{rel}:{i}")
            for group in ENV_DESTRUCTURE.findall(line):
                for name in ENV_NAME.findall(group):
                    found.setdefault(name, []).append(f"{rel}:{i}")
    return found


def available_cargo_bins(repo: Path, files: list[str]) -> set[str]:
    """Binary targets: [[bin]] name, src/bin/<name>.rs, src/bin/<name>/main.rs, and the package
    name when src/main.rs exists. Empty when there is no Cargo.toml, and then nothing is checked."""
    bins: set[str] = set()
    for rel in files:
        if Path(rel).name != "Cargo.toml" or any(p in SKIP_DIRS for p in Path(rel).parts):
            continue
        text = read(repo / rel) or ""
        root = Path(rel).parent
        pkg = re.search(r"^\[package\][^\[]*?^name\s*=\s*\"([^\"]+)\"", text, re.M | re.S)
        if pkg and exists_exact(repo / root / "src" / "main.rs"):
            bins.add(pkg.group(1))
        for m in re.finditer(r"^\[\[bin\]\][^\[]*?^name\s*=\s*\"([^\"]+)\"", text, re.M | re.S):
            bins.add(m.group(1))
        prefix = (str(root).replace("\\", "/") + "/" if str(root) != "." else "") + "src/bin/"
        for f in files:
            if f.startswith(prefix):
                rest = f[len(prefix):]
                bins.add(rest[:-3] if rest.endswith(".rs") and "/" not in rest else rest.split("/")[0])
    return bins


def unreferenced_modules(repo: Path, files: list[str]) -> set[str]:
    """Code files that nothing imports, and that are not plausible entrypoints.

    A documented setting read only inside such a file is configuration that cannot
    take effect, which reads as working config in the docs. Deliberately
    conservative: basename matching, and anything entrypoint-shaped is excluded, so
    it under-reports rather than accusing live code of being dead.
    """
    # Only languages that import a file by its name. Elixir, Go, Rust, Java and C# resolve
    # modules by package path - Plausible.S3 says nothing about s3.ex - so the rule called
    # config/runtime.exs, the runtime entrypoint, a module nothing imports.
    code = [f for f in files
            if Path(f).suffix in FILE_IMPORT_EXTS and not any(p in SKIP_DIRS for p in Path(f).parts)
            and not any(p.startswith(".") for p in Path(f).parts[:-1])]
    # Names a framework loads by convention - Next's route/page/layout/middleware, SvelteKit's
    # +page/+server, Django's views/urls/models/admin/tasks - and the folders whose contents
    # are loaded or run by convention: app/, pages/, routes/, api/, migrations/, commands/,
    # scripts/, bin/. Three Next route handlers under src/app/api were called modules nothing
    # imports; nothing imports them because the framework mounts them.
    entrypoint = re.compile(
        r"(^|/)(server|main|index|app|cli|__init__|__main__|conftest|setup|wsgi|asgi|manage"
        r"|route|page|layout|template|loading|error|not-found|default|middleware|instrumentation|proxy"
        r"|\+page|\+layout|\+server|\+error|views|urls|models|admin|tasks|signals|apps|forms|serializers|celery"
        r"|vite\.config|next\.config|tailwind\.config|postcss\.config|jest\.config|vitest\.config|playwright\.config"
        r"|eslint\.config|prettier\.config|webpack\.config|rollup\.config|babel\.config|svelte\.config|astro\.config"
        r"|drizzle\.config|prisma|schema|seed|settings|gunicorn|uvicorn)(\.[A-Za-z0-9.]+)?$"
        r"|(^|/)(app|pages|routes|api|migrations|commands|management|scripts|bin|hooks|tasks|jobs|workers|plugins|extensions|middleware|functions|lambdas|handlers|cron|seeds|fixtures|tests?|__tests__|spec|specs|e2e|stories)/",
        re.I)
    imported: set[str] = set()
    for rel in code:
        text = read(repo / rel)
        if not text:
            continue
        # `from lib import bluesky, instagram` names two modules after the keyword; only
        # `lib` was recorded, and both files were called modules nothing imports.
        # from . import (
        #     bird_x,
        #     bluesky,
        # ) - the parenthesised form spans lines, and only the first name was recorded.
        flat = re.sub(r"\(([^)]*)\)", lambda m_: "(" + " ".join(m_.group(1).split()) + ")", text)
        for names in FROM_IMPORT_NAMES.findall(flat):
            for n_ in re.split(r"[,\s]+", names):
                n_ = n_.strip().split(" as ")[0].strip()
                if n_ and n_ != "*":
                    imported.add(n_.lower())
        for groups in IMPORT_SPEC.findall(flat):
            ref = next((g for g in groups if g), "").strip()
            if not ref:
                continue
            imported.add(Path(ref).name.lower())
            imported.add(Path(ref).stem.lower())
            for part in re.split(r"[./\:]", ref):
                if part:
                    imported.add(part.lower())
    # A script nothing imports is still live when something runs it by name: a package.json
    # script, a Makefile, a Dockerfile, a workflow, a compose file, or a command in a doc.
    # docs/verify-deploy.mjs read RAILWAY_TOKEN and was called dead because it is run with
    # `node docs/verify-deploy.mjs`, not imported - so the docs were told the knob did nothing.
    # Invocation is a command, not a mention. "see src/config.js" in a README is prose; `node
    # docs/verify-deploy.mjs` in a fenced block or a backticked command, a package.json script
    # value, a Makefile or Dockerfile line, a workflow step - those run the file.
    runner = re.compile(r"`((?:node|python3?|bash|sh|ruby|deno|bun|npx|pnpm|npm|yarn|make|\./)[^`]*)`")
    invoked_text = []
    for rel in files:
        if any(p in SKIP_DIRS for p in Path(rel).parts):
            continue
        name = Path(rel).name
        suffix = Path(rel).suffix
        if name == "package.json":
            try:
                scripts = json.loads(read(repo / rel)).get("scripts") or {}
            except (ValueError, AttributeError):
                scripts = {}
            invoked_text.extend(str(v) for v in scripts.values())
        elif (name in ("Makefile", "Dockerfile", "Procfile", "Justfile") or name.startswith(("docker-compose", "compose.", "Dockerfile."))
              or suffix in (".yml", ".yaml", ".sh", ".ps1")):
            invoked_text.append(read(repo / rel))
        elif suffix in DOC_EXTS:
            text = read(repo / rel)
            invoked_text.extend(line for _, line in fenced_blocks(text))
            invoked_text.extend(runner.findall(text))
    invoked = NL.join(invoked_text).replace(chr(92), "/")
    # A path built as a string - Path(__file__).parent / "evaluate.py" - or a dynamic import
    # names the file without importing it. The bare stem anywhere in code is a reference.
    # This kind carries the strongest wording in the script and was five for five wrong; it
    # now has to clear every cheap test before it speaks.
    # One pass: every file-name-shaped token in the code, as a set. A regex per code file over
    # the whole text was quadratic and took three minutes on prometheus.
    code_text = NL.join(read(repo / rel) for rel in code)
    named = set(re.findall(r"(?<![A-Za-z0-9_/.-])([A-Za-z0-9_-]+\.[A-Za-z0-9]{1,5})(?![A-Za-z0-9_])", code_text))
    out = set()
    for rel in code:
        if entrypoint.search(rel):
            continue
        stem = Path(rel).stem.lower()
        if stem in imported or Path(rel).name.lower() in imported:
            continue
        if Path(rel).name in invoked or rel in invoked:
            continue
        # The file name with its extension: "config" is a word and matched everywhere, so the
        # fixture's planted dead module disappeared; "evaluate_search_quality.py" in a string is
        # unmistakably this file.
        if Path(rel).name in named and code_text.count(Path(rel).name) > code_text.count(rel):
            continue  # named somewhere other than its own path
        out.add(rel)
    return out


def env_names_documented(repo: Path, files: list[str]) -> tuple[dict[str, str], dict[str, str]]:
    """Env var names named in docs or declared in an env sample file.

    Only the key to the left of `=` is ever read from an env file. The value is a
    credential by design and is never touched.
    """
    documented: dict[str, str] = {}
    # Weak evidence: a name in a comment sentence of an env sample, or a short backticked
    # token in prose (`CT0`). Enough to say "this is documented somewhere", never enough to
    # say "this is a promised knob": a Railway reference token in a comment, or `MIN_VOLUME_24H`
    # as shorthand for the real name, became "documented but nothing reads it".
    weak: dict[str, str] = {}
    for rel in files:
        base = Path(rel).name
        is_env_sample = base.startswith(".env")
        if not is_env_sample and Path(rel).suffix not in DOC_EXTS:
            continue
        if any(p.startswith(".") and p != ".github" for p in Path(rel).parts[:-1]):
            continue  # tooling under a dot-folder documents nothing for this repository's readers
        text = read(repo / rel)
        if not text:
            continue
        # `export KENER_URL=https://...` in a README fence is how a variable is most often
        # documented outside an env sample. The sample parser read that shape; the prose
        # path only read backticks and table cells, and reported the variable undocumented.
        fenced = set() if is_env_sample else {ln for ln, _ in fenced_blocks(text)}
        for i, line in enumerate(text.splitlines(), start=1):
            if i in fenced:
                m_f = re.match(r"^\s*(?:export\s+|set\s+|\$env:)?([A-Z][A-Z0-9_]{2,})=", line)
                if m_f and "_" in m_f.group(1):
                    # Weak: a blog post's `export ZSH_THEME=` and a prompt template's
                    # `QUERY_PLAN_FILE=` are not promises this repository makes.
                    weak.setdefault(m_f.group(1), f"{rel}:{i}")
                continue
            if is_env_sample:
                stripped = line.strip()
                # "# KENER_API_KEY=" is how an optional variable is documented in an env sample;
                # skipping every comment line made thirteen documented names "undocumented".
                stripped = re.sub(r"^#\s*(?=(?:export\s+)?[A-Z][A-Z0-9_]*\s*=)", "", stripped)
                if stripped.startswith("#"):
                    # "# FALKORDB_URL points the graph client at ..." - a comment in an env
                    # sample is documentation of whatever it names. Low confidence, and it only
                    # ever suppresses a finding.
                    for name in ENV_NAME.findall(stripped):
                        if "_" in name and not name.endswith("_"):
                            weak.setdefault(name, f"{rel}:{i}")
                    continue
                if not stripped or "=" not in stripped:
                    continue
                key = re.sub(r"^export\s+", "", stripped.split("=", 1)[0].strip()).strip()
                if ENV_NAME.fullmatch(key or ""):
                    documented.setdefault(key, f"{rel}:{i}")
            else:
                # In prose, a backticked all-caps token is weak evidence: `SKILL.md`
                # and `README` are not configuration. Require an underscore, which is
                # what actually distinguishes API_TOKEN from a shouted word, and skip
                # anything that looks like a filename.
                # Struck-through text is the doc recording that a name is gone; it is not a promise.
                line_live = re.sub(r"~~[^~]*~~", " ", line)
                # A table is the standard shape for env documentation, and the name is often a
                # bare cell: | TABLE_ONLY_TOKEN | api token |. Read the first cell of a table row.
                if line_live.lstrip().startswith("|"):
                    cells = [c.strip().strip("`") for c in line_live.strip().strip("|").split("|")]
                    if cells and re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", cells[0]) and "_" in cells[0] and not cells[0].endswith("_"):
                        documented.setdefault(cells[0], f"{rel}:{i}")
                for chunk in BACKTICK.findall(line_live):
                    c = chunk.strip()
                    if "." in c or "/" in c:
                        continue
                    # The whole span is the name. `RESOLVED_HANDLE = {handle}` and `TOPIC_A: ...`
                    # are prompt-template placeholders, and they were most of the false
                    # "documented but unused" findings on a repository with agent prompts in it.
                    m_ = re.fullmatch(r"(?:export\s+)?(?:\$\{?)?([A-Z][A-Z0-9_]{2,})\}?(?:=\S*)?", c)
                    if not m_:
                        continue
                    name = m_.group(1)
                    weak.setdefault(name, f"{rel}:{i}")
                    if "_" not in name or name.endswith("_") or (name + "*") in line or (name + "_*") in line:
                        continue  # PODCAST_S3_* names a family of variables, not one
                    # And it reads as configuration: the line talks about it as such, or the
                    # name itself carries a configuration suffix. A shouted identifier in prose
                    # does not become an environment variable by being in backticks.
                    at_ = line_live.find(chunk)
                    window = line_live[max(0, at_ - 80): at_ + len(chunk) + 80]
                    if not (CONFIG_CONTEXT.search(window) or CONFIG_SUFFIX.search(name)):
                        continue
                    documented.setdefault(name, f"{rel}:{i}")
    return documented, weak


def path_epochs(repo: Path) -> dict[str, int]:
    """The newest commit time of every path, from one git log pass.

    One `git log -1` per document was most of a 77-second run on 112 docs, and sampling forty
    directories from a set made the answer change between runs.
    """
    out = run_git(["log", "--format=%x01%at", "--name-only", "--no-renames"], repo)
    epochs: dict[str, int] = {}
    if not out:
        return epochs
    current = None
    for line in out.splitlines():
        if line.startswith(chr(1)):
            try:
                current = int(line[1:].strip())
            except ValueError:
                current = None
            continue
        p = line.strip()
        if p and current is not None and p not in epochs:
            epochs[p] = current
    return epochs


def build(repo: Path, files: list[str], check_paths: bool = False) -> dict:
    findings: list[dict] = []

    def add(kind: str, severity: str, doc: str, line: int | None, detail: str,
            source: str | None = None) -> None:
        if doc != "(docs)" and in_record(doc) and severity != "low":
            severity = "low"
            detail += " (in a record folder: history, not a live promise)"
        findings.append({"kind": kind, "severity": severity, "doc": doc, "line": line,
                         "detail": detail, "source": source})

    file_set = set(files)
    npm_scripts, make_targets = available_commands(repo, files)
    cargo_bins = available_cargo_bins(repo, files)
    all_npm = set().union(*npm_scripts.values()) if npm_scripts else set()
    # A dot-folder holds tooling - .claude/skills, .agents, .cursor - whose Markdown speaks to an
    # agent, not to a reader of this repository; .github is the one GitHub itself documents.
    docs = [f for f in files
            if Path(f).suffix in DOC_EXTS and not any(p in SKIP_DIRS for p in Path(f).parts)
            and not any(p.startswith(".") and p != ".github" for p in Path(f).parts[:-1])]
    # An archived report or a dated plan described the repository accurately at the time; its
    # commands and links are history, not promises. Findings there are advice and staleness is
    # expected. Same heuristic as docs-structure's record folders.
    record = re.compile(r"(^|/)(archive|archived|plans|specs|log|logs|builds|adr|adrs|decisions|rfcs|changelogs|audit-[^/]*|[^/]*\d{4}-\d{2}-\d{2}[^/]*)/", re.I)

    record_name = re.compile(r"^(changelog|changes|history|news|release[-_]?notes?|releases|upgrading|migration[-_]guide)\b", re.I)

    def in_record(path: str) -> bool:
        return bool(record.search(path)) or bool(record_name.match(Path(path).stem))

    for doc in docs:
        text = read(repo / doc)
        if not text:
            continue

        # 1. commands
        for lineno, line in fenced_blocks(text, skip_away=True):
            for script in set(CMD_NPM.findall(line)):
                if not all_npm:
                    continue
                if line.lstrip().startswith("#"):
                    continue
                if script not in all_npm:
                    near = ", ".join(sorted(s for s in all_npm if s.startswith(script.split(":")[0]))[:4])
                    hint = f" Closest existing: {near}." if near else ""
                    add("missing-script", "high", doc, lineno,
                        f"documents `{script}`, which is not a script in any package.json.{hint}",
                        source="package.json")
            for target in set(CMD_MAKE.findall(line)):
                if (make_targets and target not in make_targets
                        and target not in ("-j", "all", "sure", "the", "it", "a", "this", "that", "them", "changes", "any", "your", "these")):
                    add("missing-make-target", "high", doc, lineno,
                        f"documents `make {target}`, which is not a target in the Makefile.",
                        source="Makefile")
            if line.lstrip().startswith("#"):
                continue  # a comment inside a fenced block: "# make sure the port is free"
            for proj in set(CMD_DOTNET.findall(line)):
                if PLACEHOLDER.search(proj):
                    continue
                p_ = proj.rstrip("/")
                if not (exists_exact(repo / p_) or exists_exact(repo / Path(doc).parent / p_)
                        or any(f == p_ or f.startswith(p_ + "/") for f in file_set)):
                    add("missing-script-file", "high", doc, lineno,
                        f"documents `dotnet run --project {proj}`, and no such project exists.")
            for pkg in set(CMD_GO.findall(line)):
                p_ = pkg.rstrip("/").lstrip("./")
                if p_.endswith("...") or PLACEHOLDER.search(p_) or not p_:
                    continue
                if not (exists_exact(repo / p_) or exists_exact(repo / Path(doc).parent / p_)
                        or any(f.startswith(p_ + "/") for f in file_set)):
                    add("missing-script-file", "high", doc, lineno,
                        f"documents `go run {pkg}`, and no such package directory exists.")
            for bin_ in set(CMD_CARGO_BIN.findall(line)):
                if cargo_bins and bin_ not in cargo_bins and not PLACEHOLDER.search(bin_):
                    add("missing-script-file", "high", doc, lineno,
                        f"documents `cargo run --bin {bin_}`, which is not a binary target in any Cargo.toml.",
                        source="Cargo.toml")
            for whole, inner in CMD_SCRIPT.findall(line):
                candidate = (inner or whole).lstrip("./")
                # ./prometheus and ./promtool are built binaries; without an extension a
                # ./name is a build product until proven otherwise, not a documented file.
                if not inner and "." not in Path(candidate).name:
                    continue
                if not candidate or PLACEHOLDER.search(candidate):
                    continue
                if candidate.endswith("/") or any(part in SKIP_DIRS
                                                  for part in Path(candidate).parts):
                    continue
                # Written relative to the doc as often as to the repo root, and a shape that repeats
                # (scripts/x.py under a package) is the tail of a real path.
                here = (repo / Path(doc).parent / candidate)
                if (candidate not in file_set and not exists_exact(repo / candidate) and not exists_exact(here)
                        and not any(f.endswith("/" + candidate) for f in file_set)):
                    same = [f for f in file_set if f.endswith("/" + Path(candidate).name) or f == Path(candidate).name]
                    hint = f" A file of that name exists at {same[0]}." if same else ""
                    add("missing-script-file", "high", doc, lineno,
                        f"documents running `{candidate}`, which does not exist.{hint}")

        # 2 and 3. links and backticked paths
        for i, line in enumerate(text.splitlines(), start=1):
            for angled, plain in MD_LINK.findall(line):
                t = (angled or plain).split("#")[0].split("?")[0].strip()
                if not t or t.startswith(("http://", "https://", "mailto:", "#", "tel:", "data:")):
                    continue
                if PLACEHOLDER.search(t) or "/actions/workflows/" in t or t.startswith("../../"):
                    continue  # a GitHub-relative badge or repository URL, not a file
                # [`extract`](crate::extract) is a rustdoc link; (Router::fallback), (tower_http::trace)
                # and a bare identifier with neither a slash nor a dot are the language's own
                # references, not files. Twenty of axum's twenty-three findings were these.
                if "::" in t or ("/" not in t and "." not in t):
                    continue
                # A leading slash is root-relative on GitHub, not a path on this machine - and
                # with no file extension it is an application route (/dashboard/notifications
                # in a site's own content), which no file could satisfy.
                if t.startswith("/") and "." not in Path(t).name:
                    continue
                if "\\" in t:
                    add("broken-link", "high", doc, i,
                        f"relative link `{t}` uses a backslash; it resolves on Windows only, and not on GitHub.")
                    continue
                base = repo if t.startswith("/") else repo / Path(doc).parent
                target = base / t.lstrip("/")
                trimmed = t.rstrip("/").lstrip("/")
                if not any(exists_exact(p) for p in (target, base / (trimmed + ".md"), base / trimmed / "index.md",
                                                     base / trimmed / "README.md")):
                    add("broken-link", "high", doc, i,
                        f"relative link `{t}` does not resolve.")
            for chunk in (BACKTICK.findall(line) if check_paths else []):
                c = chunk.strip()
                # Only treat it as a path claim when it looks like one.
                if "/" not in c or " " in c or PLACEHOLDER.search(c):
                    continue
                # A leading slash means a slash-command or an absolute path, e.g.
                # `/security-review`. Neither is a claim about this repository.
                if c.startswith("/"):
                    continue
                if not re.match(r"^[A-Za-z0-9._/-]+$", c) or c.endswith("/"):
                    continue
                # Require a real file extension. Extensionless slashed tokens are
                # ambiguous by nature -- `origin/staging` is a git ref, `src/utils/billing`
                # is an illustrative example, `@scope/pkg` is a package. Accusing those
                # of being broken paths produced far more noise than signal.
                if not re.match(r"^\.[A-Za-z0-9]{1,5}$", Path(c).suffix):
                    continue
                if c in file_set or (repo / c).exists():
                    continue
                # Docs routinely write paths relative to their own directory.
                if (repo / Path(doc).parent / c).exists():
                    continue
                # A directory prefix that exists is close enough not to report.
                if any(f.startswith(c.rstrip("/") + "/") for f in file_set):
                    continue
                # Docs also reference a shape that repeats, e.g. `agents/openai.yaml`
                # when the real files are skills/<name>/agents/openai.yaml. If it is
                # the tail of a real path, the claim is true enough.
                tail = "/" + c
                if any(f.endswith(tail) for f in file_set):
                    continue
                add("missing-path", "medium", doc, i,
                    f"references `{c}`, which does not exist in the repository.")

    # 4. env vars, both directions
    in_code = env_names_from_code(repo, files)
    in_docs, weak_docs = env_names_documented(repo, files)
    dead = unreferenced_modules(repo, files)
    # A config module - a zod schema, a pydantic Settings class, a struct with env tags, a
    # compose file with ${NAME} - reads a variable without any of the patterns above. Before
    # saying nothing reads a documented name, look for the bare token anywhere outside the
    # docs. A negative claim from one regex is not evidence; SKILL.md says the same.
    non_doc = [f for f in files if Path(f).suffix not in DOC_EXTS and not Path(f).name.startswith(".env")
               and not any(p in SKIP_DIRS for p in Path(f).parts)]
    # Read once: every documented name used to re-read every non-doc file.
    non_doc_text = {rel: read(repo / rel) for rel in non_doc}
    non_doc_tokens = set(re.findall(r"[A-Z][A-Z0-9_]{2,}", NL.join(non_doc_text.values())))
    _token_cache: dict[str, str] = {}

    def mentioned_in_code(name: str) -> str | None:
        if name not in _token_cache:
            hit = None
            if name in non_doc_tokens:
                pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(name) + r"(?![A-Za-z0-9_])")
                hit = next((rel for rel, text in non_doc_text.items() if text and pat.search(text)), None)
            _token_cache[name] = hit or ""
        return _token_cache[name] or None

    _line_cache: dict[str, list[str]] = {}

    def doc_line_text(path: str, n: int) -> str:
        if path not in _line_cache:
            _line_cache[path] = read(repo / path).splitlines()
        lines = _line_cache[path]
        return lines[n - 1] if 0 < n <= len(lines) else ""

    if in_docs and not in_code:
        warnings.append("no environment reads were recognised in this repository's code, so documented "
                        "names were not compared against readers; the languages or the access pattern "
                        "are outside what this script parses")
    for name, where in sorted(in_docs.items()):
        readers = in_code.get(name, [])
        doc_path, _, doc_line = where.rpartition(":")
        if not readers and not in_code:
            continue
        if not readers and mentioned_in_code(name):
            continue  # read through a mechanism the patterns do not parse; not a missing knob
        if not readers and DEAD_CONTEXT.search(doc_line_text(doc_path, int(doc_line))):
            continue  # the doc itself says nothing reads it; that is the correct state, recorded
        if not readers:
            add("documented-unused-env", "medium", doc_path, int(doc_line),
                f"`{name}` is documented but nothing in the code reads it. "
                "Either it is dead configuration or the docs promise a knob that does not exist.",
                source="no reader found")
        elif all(r.rsplit(":", 1)[0] in dead for r in readers):
            where_read = ", ".join(readers[:3])
            add("documented-env-in-unreferenced-module", "medium", doc_path, int(doc_line),
                f"`{name}` is read only in a module nothing imports, so the documented setting "
                "cannot take effect. The docs describe a working knob that does nothing.",
                source=where_read)
    # Example, fixture and test code reads variables the product never does - a vendored sample
    # under examples/ read ANTHROPIC_API_KEY and the whole repository was told it was
    # undocumented. Those folders still count as readers for the other direction.
    sample = re.compile(r"(^|/)(examples?|fixtures?|__fixtures__|testdata|tests?|__tests__|specs?|samples?|demos?|benchmarks?)/", re.I)
    platform_skipped = 0
    for name, readers in sorted(in_code.items()):
        if all(sample.search(r.rsplit(":", 1)[0]) for r in readers):
            continue
        # Platform and toolchain names only. A two-letter "GO" prefix ate GOOGLE_CLIENT_SECRET
        # and GOTRUE_JWT_SECRET; AWS_ and SENTRY_ ate an application's own bucket and token
        # names - an undocumented secret dropped without a trace, on the kind that matters
        # most. Exact names for the vendors, and the count of what was skipped goes in totals.
        if name in PLATFORM_ENV or name.startswith(PLATFORM_PREFIXES):
            platform_skipped += 1
            continue
        if name not in in_docs and name not in weak_docs:
            add("undocumented-env", "medium", "(docs)", None,
                f"`{name}` is read by the code but is not documented anywhere, "
                "and is not in an env sample file.",
                source=sorted(readers, key=lambda r: bool(sample.search(r)))[0])

    # 5. staleness
    epochs = path_epochs(repo)
    newest_code = max((epochs[f] for f in files if Path(f).suffix in CODE_EXTS and f in epochs), default=None)
    if newest_code:
        stale: list[tuple[int, str]] = []
        for doc in docs:
            if in_record(doc):
                continue  # a record is supposed to be old
            doc_epoch = epochs.get(doc)
            if not doc_epoch:
                continue
            days = (newest_code - doc_epoch) / 86400
            if days > STALE_DAYS:
                stale.append((int(days), doc))
        # One row per doc drowned every other finding on a repository with a long history:
        # 305 of eclipse_fm's 376 findings were this. Past a handful it is one finding that
        # names the oldest, and the JSON keeps the full list under "stale_docs".
        stale.sort(reverse=True)
        if len(stale) <= 8:
            for days, doc in stale:
                add("stale-doc", "low", doc, None,
                    f"last changed {days} days before the most recent code change. "
                    "Not wrong by itself, but worth reading against current behavior.")
        else:
            oldest = ", ".join(f"{d} ({n}d)" for n, d in stale[:5])
            add("stale-doc", "low", stale[0][1], None,
                f"{len(stale)} docs last changed more than {STALE_DAYS} days before the most recent code "
                f"change; the oldest: {oldest}. Not wrong by itself; the full list is in --format json.")

    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order.get(f["severity"], 3), f["doc"], f["line"] or 0))
    return {
        "repo": str(repo),
        "stale_docs": [{"doc": d, "days": n} for n, d in (stale if newest_code else [])],
        "totals": {"docs_checked": len(docs), "findings": len(findings),
                   "npm_scripts_found": len(all_npm), "make_targets_found": len(make_targets),
                   "env_names_in_code": len(in_code), "env_names_documented": len(in_docs),
                   "env_names_skipped_as_platform": platform_skipped},
        "findings": findings,
        "warnings": warnings,
    }


def render(d: dict, top: int) -> str:
    t = d["totals"]
    L = ["# Documentation Drift Check", "", f"Repo: {d['repo']}",
         f"Docs checked: {t['docs_checked']}   Findings: {t['findings']}",
         f"Known npm scripts: {t['npm_scripts_found']}   make targets: {t['make_targets_found']}",
         f"Env names in code: {t['env_names_in_code']}   documented: {t['env_names_documented']}"
         f"   skipped as platform/toolchain: {t.get('env_names_skipped_as_platform', 0)}", ""]

    if not d["findings"]:
        L.append("No machine-verifiable drift found. Prose accuracy is still unchecked.")
    else:
        shown = d["findings"][:top] if top > 0 else d["findings"]
        if 0 < top < len(d["findings"]):
            L.append(f"TRUNCATED: showing {top} of {len(d['findings'])} findings")
            L.append("")
        for f in shown:
            loc = f"{f['doc']}:{f['line']}" if f.get("line") else f["doc"]
            L.append(f"- [{f['severity']}] {f['kind']} -- {loc}")
            L.append(f"  {f['detail']}")
            if f.get("source"):
                L.append(f"  source of truth: {f['source']}")
    L.append("")
    if d["warnings"]:
        L.append("## Warnings")
        L.extend(f"- {w}" for w in d["warnings"])
        L.append("")
    L.append("Checks only claims with a definite answer. Wording, completeness and whether an")
    L.append("explanation is actually correct are not checked here. Confirm each finding by")
    L.append("opening both the doc and the source before reporting it.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Check documentation claims against the repo. Read-only.")
    ap.add_argument("--repo", default=".", help="Path inside the repository.")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    ap.add_argument("--top", type=int, default=30, help="Findings to show in text output. Default 30; 0 shows all.")
    ap.add_argument("--check-paths", action="store_true",
                    help=("Also check backticked paths against the filesystem. Off by default: on "
                          "real repos most such references are ambiguous -- a path a doc tells you "
                          "to create, or one an archived report described at the time -- and the "
                          "noise buries the unambiguous findings. Markdown links are always checked."))
    ap.add_argument("--no-git-root", action="store_true",
                    help="Treat --repo literally instead of expanding to the enclosing git repository root.")
    args = ap.parse_args()

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

    data = build(repo, files, check_paths=args.check_paths)
    print(json.dumps(data, indent=2) if args.format == "json" else render(data, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
