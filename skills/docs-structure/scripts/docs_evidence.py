#!/usr/bin/env python3
"""Inventory what a repository contains, as evidence for its documentation.

Read-only. Standard library only. Writes nothing. Prints no secret values.

    python docs_evidence.py                         # text summary, repo = git root of cwd
    python docs_evidence.py --repo ../other --format json
    python docs_evidence.py --no-git                # skip git history
    python docs_evidence.py --cap 200               # items per list (default 400)

Every fact it emits carries the path it came from, so a doc drafted from this inventory can
cite its evidence sentence by sentence. It describes; it never judges and never drafts.

Keys, the same for every stack:

  ecosystems  which manifest families were recognised (node, python, go, rust, java, ruby,
              php, dotnet, elixir, move); `unknown: true` when none matched
  kinds       what the repo is: application, library, cli, infrastructure, docs-only, monorepo
  packages    units of code: name, path, language, manifest, script names, dependency names
  services    deployable units from Dockerfiles, compose, platform configs, k8s, Helm, Terraform
  env         configuration NAMES per source; values are never read
  schema      tables and migrations by tool
  routes      HTTP surface by framework pattern, or from an OpenAPI file
  cli         command entry points
  exports     the public surface of a library
  frontend    UI framework, tokens, component folders
  tests       runners, folders, CI test jobs
  ci          pipelines and their jobs
  ops         health checks, cron, alerts
  decisions   dated decision-like commits, tags, ADR folders
  auth        authentication and authorisation: libraries, middleware files, roles in the schema
  jobs        background work: queue, worker and scheduler libraries, cron signals, worker files
  integrations third parties the code talks to: SDK dependencies by service, the env names that
              point outside (`_API_KEY`, `_DSN`, `_WEBHOOK_URL`, `_CLIENT_ID`), the count
  changelog   CHANGELOG.md presence, its first headings, the tag count
  env_count   distinct environment names across every source
  readme      the README's headings and first paragraph
  tree        top-level layout and governance files

Detectors are rows in a registry. Adding a stack is adding a row, not a code path.

Secret safety is structural: env files are opened only from an allow-list of example files
(.env.example, .env.sample, .env.template, .env.*.example, .env.*.sample, example.env, env.example); only the key side
of `=` or `:` is kept; ports come from EXPOSE and `ports:` never from a PORT value; and every
free string that leaves this script passes `redact()`.
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

try:  # 3.11+
    import tomllib  # type: ignore
except ImportError:  # pragma: no cover
    tomllib = None

MAX_READ = 1_500_000
GIT_TIMEOUT = 30
MAX_CODE_FILES = 6000

ALWAYS_SKIP = {"node_modules", ".venv", "venv", "__pycache__", ".git", "dist", "build", "target",
               "vendor", ".next", ".nuxt", "coverage", ".terraform", "site-packages", ".tox", ".mypy_cache"}
# A documentation website is about the repository, not part of it: counting its Tailwind
# config as frontend turned a Go command-line tool into an application needing a design doc.
# Skip-list names that can still hold the application itself.
RESCUABLE = {"www", "site", "public", "app"}
MANIFEST_NAMES = ("package.json", "pyproject.toml", "setup.py", "go.mod", "Cargo.toml", "pom.xml",
                  "build.gradle", "build.gradle.kts", "Gemfile", "composer.json", "mix.exs",
                  "Move.toml", "Dockerfile", "requirements.txt")
EVIDENCE_SKIP = {"website", "site", "docs-site", "doc-site", "www", "docs", "doc", "documentation",
                 "fixtures", "fixture", "__fixtures__", "testdata", "examples", "example", "test", "tests",
                 "__tests__", "spec", "specs", "__mocks__", "mocks", "benches", "bench", "benchmarks"}
CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".rs", ".rb",
             ".php", ".java", ".kt", ".swift", ".cs", ".ex", ".exs", ".move"}
# `phoenix` routes live in .ex files, Ecto migrations in .exs

# example.env and env.example are the same file under another name - an AgentOS service kept its
# sample that way and every name in it was reported as undocumented.
ENV_ALLOW = re.compile(r"^(?:\.env(\.[A-Za-z0-9_-]+)?\.(example|sample|template)|(?:example|sample)\.env|env\.(?:example|sample))$")
SECRET_NAME = re.compile(r"(SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE|API_KEY|APIKEY|CREDENTIAL|AUTH)", re.I)

REDACT = [
    re.compile(r"\b(sk|pk|rk)[-_][A-Za-z0-9_-]{12,}"),        # Stripe writes sk_live_, not sk-
    re.compile(r"\bAIza[A-Za-z0-9_-]{20,}"),                   # Google
    re.compile(r"\bglpat-[A-Za-z0-9_-]{16,}"),                 # GitLab
    re.compile(r"\b(hf|npm)_[A-Za-z0-9]{20,}"),                # Hugging Face, npm
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    re.compile(r"\b[0-9a-fA-F]{32,}\b"),
    re.compile(r"\b[A-Za-z0-9+/]{40,}={0,2}\b"),
    re.compile(r"://[^/\s:@]+:[^/\s@]+@"),
    # A long path segment only looks like a token when it also looks random. Length alone
    # redacted ordinary slugs - /webhooks/stripe-payment-intent-succeeded became
    # /webhooks/[redacted] - and a drafted endpoint table then documented a route that does
    # not exist, with the bracket still resolving. Require mixed case with digits, or a long
    # unbroken run of hex or base64, and let hyphenated lowercase words through.
    re.compile(r"(?<=/)(?=[A-Za-z0-9_-]{24,}(?:/|$))(?![a-z0-9]+(?:-[a-z0-9]+)+(?:/|$))(?:[A-Za-z0-9_-]*[A-Z][A-Za-z0-9_-]*\d|[A-Za-z0-9_-]*\d[A-Za-z0-9_-]*[A-Z]|[0-9a-f]{24,})[A-Za-z0-9_-]*"),
]

# Surfaces read off dependency names. A name in these tables is a fact about the manifest, not
# about how the code uses it, so every hit carries its package as evidence and nothing more.
AUTH_LIBS = {
    "passport", "next-auth", "@auth/core", "better-auth", "lucia", "@clerk/nextjs", "@clerk/clerk-sdk-node",
    "auth0", "@auth0/nextjs-auth0", "jose", "jsonwebtoken", "express-jwt", "@fastify/jwt", "firebase-admin",
    "@supabase/auth-helpers-nextjs", "@supabase/ssr", "bcrypt", "bcryptjs", "argon2", "oauth4webapi",
    "authlib", "python-jose", "pyjwt", "django-allauth", "djangorestframework-simplejwt", "flask-login",
    "flask-jwt-extended", "fastapi-users", "passlib", "devise", "omniauth", "warden", "spring-boot-starter-security",
    "spring-security-core", "laravel/sanctum", "laravel/passport", "microsoft.aspnetcore.authentication.jwtbearer",
    "guardian", "pow", "golang.org/x/oauth2", "github.com/golang-jwt/jwt", "github.com/golang-jwt/jwt/v5",
}
JOB_LIBS = {
    "bullmq", "bull", "bee-queue", "agenda", "node-cron", "cron", "croner", "@temporalio/worker", "inngest",
    "@trigger.dev/sdk", "kafkajs", "amqplib", "@aws-sdk/client-sqs", "sqs-consumer", "graphile-worker", "pg-boss",
    "celery", "rq", "dramatiq", "huey", "apscheduler", "arq", "temporalio", "kombu", "pika", "aiokafka",
    "sidekiq", "resque", "delayed_job", "good_job", "solid_queue", "oban", "broadway", "quartz",
    "spring-boot-starter-batch", "hangfire", "quartz.net", "github.com/hibiken/asynq", "github.com/robfig/cron",
}
# third-party services by the package that talks to them; the value is the service name a doc uses
INTEGRATION_LIBS = {
    "stripe": "Stripe", "@stripe/stripe-js": "Stripe", "twilio": "Twilio", "@sendgrid/mail": "SendGrid",
    "sendgrid": "SendGrid", "resend": "Resend", "postmark": "Postmark", "nodemailer": "SMTP mail",
    "openai": "OpenAI", "@anthropic-ai/sdk": "Anthropic", "anthropic": "Anthropic", "@google/generative-ai": "Google AI",
    "google-generativeai": "Google AI", "cohere-ai": "Cohere", "replicate": "Replicate", "@elevenlabs/elevenlabs-js": "ElevenLabs",
    "elevenlabs": "ElevenLabs", "aws-sdk": "AWS", "boto3": "AWS", "@google-cloud/storage": "Google Cloud",
    "google-cloud-storage": "Google Cloud", "firebase": "Firebase", "firebase-admin": "Firebase",
    "@supabase/supabase-js": "Supabase", "supabase": "Supabase", "@zep-cloud/zep-js": "Zep", "zep-cloud": "Zep",
    "zep-python": "Zep", "langchain": "LangChain", "@langchain/core": "LangChain", "langchain-core": "LangChain",
    "@sentry/node": "Sentry", "@sentry/nextjs": "Sentry", "sentry-sdk": "Sentry", "dd-trace": "Datadog",
    "posthog-js": "PostHog", "posthog-node": "PostHog", "posthog": "PostHog", "analytics-node": "Segment",
    "@segment/analytics-node": "Segment", "mixpanel": "Mixpanel", "@slack/web-api": "Slack", "@slack/bolt": "Slack",
    "slack-sdk": "Slack", "discord.js": "Discord", "discord.py": "Discord", "telegraf": "Telegram",
    "python-telegram-bot": "Telegram", "grammy": "Telegram", "@octokit/rest": "GitHub", "pygithub": "GitHub",
    "algoliasearch": "Algolia", "@pinecone-database/pinecone": "Pinecone", "pinecone-client": "Pinecone",
    "weaviate-client": "Weaviate", "@upstash/redis": "Upstash", "ioredis": "Redis", "redis": "Redis",
    "@aws-sdk/client-s3": "AWS S3", "@aws-sdk/client-ses": "AWS SES", "cloudinary": "Cloudinary",
    "@vercel/blob": "Vercel Blob", "mapbox-gl": "Mapbox", "@googlemaps/google-maps-services-js": "Google Maps",
    "plaid": "Plaid", "@paypal/checkout-server-sdk": "PayPal", "braintree": "Braintree", "razorpay": "Razorpay",
    "intercom-client": "Intercom", "hubspot": "HubSpot", "@hubspot/api-client": "HubSpot", "airtable": "Airtable",
    "notion": "Notion", "@notionhq/client": "Notion", "twitter-api-v2": "X/Twitter", "tweepy": "X/Twitter",
    "spotify-web-api-node": "Spotify", "spotipy": "Spotify", "expo-server-sdk": "Expo push", "web-push": "Web push",
    "onesignal-node": "OneSignal", "@onesignal/node-onesignal": "OneSignal", "kener": "Kener",
}
OUTWARD_ENV = re.compile(r"_(API_KEY|APIKEY|DSN|WEBHOOK_URL|WEBHOOK_SECRET|CLIENT_ID|CLIENT_SECRET|ACCESS_TOKEN|BUCKET|PROJECT_ID)$")
ROLE_RE = re.compile(r"\b(enum\s+\w*(Role|Permission)\w*|role\s*[:=]|permissions?\s*[:=]|is_admin|isAdmin)\b", re.I)

DECISION_RE = re.compile(r"\b(decid|switch|migrat|replace|remov|adopt|revert|drop|deprecat|instead)", re.I)
DEPLOY_ISH = re.compile(r"(deploy|railway|fly|vercel|netlify|heroku|render|kubectl|helm|terraform|docker/build-push|aws-actions|gcloud|azure/)", re.I)

warnings: list[str] = []


# ------------------------------------------------------------------ helpers

def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        return path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return ""


def posix(p: Path, repo: Path) -> str:
    try:
        return p.relative_to(repo).as_posix()
    except ValueError:
        return p.as_posix()


def redact(s: str) -> str:
    out = s
    for rx in REDACT:
        out = rx.sub("[redacted]", out)
    return out


def walk(root: Path, skip_names: set[str] | None = None, max_depth: int = 14,
         pruned: list[str] | None = None, keep=None):
    """os.walk with pruning. Sorted dirnames AND filenames, so output is the same on NTFS and ext4.

    `keep(path)` rescues a folder the skip list would otherwise drop. A folder named www/ or
    site/ that holds a package manifest is the application, not decoration, and pruning it by
    name made a whole repository read as a folder of notes.
    """
    skip = ALWAYS_SKIP | (skip_names or set())
    base = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        d = Path(dirpath)
        if len(d.parts) - base >= max_depth:
            if dirnames:
                warnings.append(f"depth cap {max_depth} reached under {d.relative_to(root).as_posix()}; deeper files not scanned")
            dirnames[:] = []
        rescued = {n for n in dirnames if keep and n in (skip_names or set()) and keep(d / n)}
        for n in sorted(rescued):
            warnings.append(f"{(d / n).relative_to(root).as_posix()} is on the skip list but holds a build manifest; scanned as code")
        if pruned is not None:
            pruned.extend((d / n).as_posix() for n in dirnames
                          if n in (skip_names or set()) and n not in rescued)
        # A folder holding a SKILL.md is an agent skill: its templates, fixtures and scripts describe
        # other repositories, and reading them as this one's evidence proposed a decisions folder
        # and a changelog to the skill collection itself.
        dirnames[:] = sorted(n for n in dirnames
                             if (n not in skip or n in rescued) and not n.startswith(".")
                             and not (d / n / "SKILL.md").is_file())
        yield d, dirnames, sorted(filenames)


def load_json(path: Path):
    try:
        return json.loads(read(path))
    except ValueError:
        return None


def load_toml(path: Path) -> dict:
    text = read(path)
    if tomllib is not None:
        try:
            return tomllib.loads(text)
        except Exception:  # noqa: BLE001 - malformed TOML falls back to the line scanner
            pass
    out: dict = {}
    table = out
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = re.match(r"^\[([^\]]+)\]$", s)
        if m:
            table = out
            for part in m.group(1).replace('"', "").split("."):
                nxt = table.get(part.strip())
                if not isinstance(nxt, dict):
                    nxt = {}
                    table[part.strip()] = nxt
                table = nxt
            continue
        m = re.match(r'^([A-Za-z0-9_.-]+)\s*=\s*"?([^"#]*)"?', s)
        if m:
            table[m.group(1)] = m.group(2).strip()
    return out


def yaml_scan(text: str):
    """A small indent-based YAML reader for compose, k8s manifests, GitHub Actions and platform
    configs: mappings, lists of scalars or mappings (at the same indent as their key or deeper),
    block scalars (| > |- >+), one-line flow lists and maps. Anchors and multi-line flow are ignored.
    Not a YAML parser; enough to read names and shapes, never values that matter."""
    toks: list[tuple[int, str]] = []
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or raw.strip() == "---":
            continue
        toks.append((len(raw) - len(raw.lstrip(" ")), raw.strip()))

    def scalar(v: str):
        v = v.strip()
        if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
            return v[1:-1]
        if v.startswith("[") and v.endswith("]"):
            return [scalar(x) for x in v[1:-1].split(",") if x.strip()]
        if v.startswith("{") and v.endswith("}"):
            d = {}
            for kv in v[1:-1].split(","):
                if ": " in kv:
                    k, _, val = kv.partition(": ")
                    d[k.strip().strip("'\"")] = scalar(val)
            return d
        return v

    def is_pair(t: str) -> bool:
        if t.startswith(("'", "\"", "[", "{")):
            return False
        return ": " in t or t.endswith(":")

    def parse_block(i: int, indent: int):
        """Parse the block whose first token is toks[i] at `indent`. Returns (value, next_i)."""
        if i >= len(toks):
            return {}, i
        if toks[i][1].startswith("- ") or toks[i][1] == "-":
            return parse_list(i, indent)
        return parse_map(i, indent)

    def parse_list(i: int, indent: int):
        out: list = []
        while i < len(toks) and toks[i][0] == indent and (toks[i][1].startswith("- ") or toks[i][1] == "-"):
            body = toks[i][1][2:].strip()
            if not body:
                i += 1
                if i < len(toks) and toks[i][0] > indent:
                    v, i = parse_block(i, toks[i][0])
                    out.append(v)
                else:
                    out.append(None)
                continue
            if is_pair(body):
                # a mapping item: its first pair sits on the dash line, the rest two columns in
                toks[i] = (indent + 2, body)
                v, i = parse_map(i, indent + 2)
                out.append(v)
            else:
                out.append(scalar(body))
                i += 1
        return out, i

    def parse_map(i: int, indent: int):
        out: dict = {}
        while i < len(toks) and toks[i][0] == indent and is_pair(toks[i][1]):
            k, _, v = toks[i][1].partition(":")
            k = k.strip().strip("'\"")
            v = v.strip()
            i += 1
            if v[:1] in ("|", ">"):
                # block scalar: swallow every deeper line, keep nothing of it
                while i < len(toks) and toks[i][0] > indent:
                    i += 1
                out[k] = ""
            elif v == "":
                if i < len(toks) and toks[i][0] > indent:
                    out[k], i = parse_block(i, toks[i][0])
                elif i < len(toks) and toks[i][0] == indent and toks[i][1].startswith("- "):
                    out[k], i = parse_list(i, indent)
                else:
                    out[k] = None
            else:
                out[k] = scalar(v)
        return out, i

    if not toks:
        return {}
    v, _ = parse_block(0, toks[0][0])
    return v if isinstance(v, dict) else {"_": v}


def run_git(repo: Path, args: list[str]) -> str | None:
    git = shutil.which("git")
    if git is None:
        return None
    try:
        p = subprocess.run([git, *args], cwd=str(repo), text=True, timeout=GIT_TIMEOUT,
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        warnings.append(f"git {' '.join(args[:2])} failed: {exc}")
        return None
    return p.stdout if p.returncode == 0 else None


# ------------------------------------------------------------------ context

class Ctx:
    def __init__(self, repo: Path, cap: int, use_git: bool):
        self.repo = repo
        self.cap = cap
        self.use_git = use_git
        self.files: list[Path] = []
        self.code_files: list[Path] = []
        self.dirs: set[str] = set()
        self.pruned: list[str] = []
        truncated = False
        # A folder holding a build manifest is the application, whatever it is called. Pruning
        # www/ or site/ by name made an Express app with a Dockerfile read as a folder of
        # notes with no findings at all - the most confident possible wrong answer.
        def keep(d: Path) -> bool:
            # Only names that could plausibly BE the application. A docs site, an examples
            # package and a test fixture all carry manifests too, and rescuing those put a
            # documentation site back into the product's inventory.
            return d.name.lower() in RESCUABLE and any((d / m).is_file() for m in MANIFEST_NAMES)

        for d, dirnames, filenames in walk(repo, EVIDENCE_SKIP, pruned=self.pruned, keep=keep):
            rel_d = posix(d, repo)
            if rel_d != ".":
                self.dirs.add(rel_d)
            for n in filenames:
                p = d / n
                self.files.append(p)
                if p.suffix.lower() in CODE_EXTS:
                    if len(self.code_files) >= MAX_CODE_FILES:
                        truncated = True
                        continue
                    self.code_files.append(p)
        if truncated:
            warnings.append(f"code scan capped at {MAX_CODE_FILES} files")
        self.by_name: dict[str, list[Path]] = {}
        for p in self.files:
            self.by_name.setdefault(p.name.lower(), []).append(p)

    def named(self, *names: str) -> list[Path]:
        out: list[Path] = []
        for n in names:
            out.extend(self.by_name.get(n.lower(), []))
        return sorted(out)

    def glob_name(self, pattern: str) -> list[Path]:
        rx = re.compile("^" + re.escape(pattern).replace(r"\*", ".*") + "$", re.I)
        return sorted(p for p in self.files if rx.match(p.name))

    def rel(self, p: Path) -> str:
        return posix(p, self.repo)

    def top_level_dirs(self) -> list[str]:
        return sorted(d for d in self.dirs if "/" not in d)


def _redact_any(v):
    if isinstance(v, str):
        return redact(v)
    if isinstance(v, list):
        return [_redact_any(x) for x in v]
    if isinstance(v, dict):
        return {k: _redact_any(x) for k, x in v.items()}
    return v


def item(ctx: Ctx, detector: str, src: Path, **fields) -> dict:
    d = {"detector": detector, "evidence": ctx.rel(src)}
    for k, v in fields.items():
        d[k] = _redact_any(v)
    return d


def each(ctx: Ctx, paths, fn, name: str) -> None:
    """Run fn on every path; one malformed file warns and is skipped, never taking the detector down."""
    for p in paths:
        try:
            fn(p)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name}: skipped {ctx.rel(p)}: {type(exc).__name__}")


def first_token(cmd: str) -> str:
    """A start command's binary is all a doc needs; arguments can carry values."""
    cmd = cmd.strip().strip("[]").split(",")[0].strip().strip("\"'")
    return cmd.split()[0] if cmd.split() else ""


def as_dict(x) -> dict:
    return x if isinstance(x, dict) else {}


def cap(lst: list, n: int, key: str, inv: dict) -> list:
    if len(lst) > n:
        inv.setdefault("truncated", {})[key] = len(lst)
        return lst[:n]
    return lst


# ------------------------------------------------------------------ package detectors

def det_node(ctx: Ctx, inv: dict) -> None:
    def one(p: Path) -> None:
        data = load_json(p)
        if not isinstance(data, dict):
            return
        deps = {**as_dict(data.get("dependencies")), **as_dict(data.get("devDependencies"))}
        scripts = as_dict(data.get("scripts"))
        lang = "typescript" if (p.parent / "tsconfig.json").exists() or "typescript" in deps else "javascript"
        inv["packages"].append(item(ctx, "node", p, name=str(data.get("name") or p.parent.name), path=ctx.rel(p.parent),
                                    language=lang, manifest="package.json", scripts=sorted(scripts.keys())[:60],
                                    dependencies=sorted(deps.keys())[:80], private=bool(data.get("private")),
                                    version=str(data.get("version") or ""), workspaces=bool(data.get("workspaces"))))
        inv["_eco"].add("node")
        fe = [d for d in ("react", "next", "vue", "nuxt", "svelte", "@sveltejs/kit", "@angular/core", "solid-js", "astro", "remix", "@remix-run/react") if d in deps]
        if fe:
            inv["frontend"].append(item(ctx, "node", p, frameworks=fe, package=ctx.rel(p.parent)))
        ui = [d for d in deps if d in ("tailwindcss", "@radix-ui/react-slot", "@mui/material", "@chakra-ui/react", "antd", "shadcn", "class-variance-authority") or d.startswith("@radix-ui/")]
        if ui:
            inv["frontend"].append(item(ctx, "node", p, ui_dependencies=sorted(set(ui))[:20], package=ctx.rel(p.parent)))
        b = data.get("bin")
        if b:
            names = list(b.keys()) if isinstance(b, dict) else [str(data.get("name") or "cli")]
            inv["cli"].append(item(ctx, "node", p, commands=names, entry=str(b if isinstance(b, str) else "")))
        if not data.get("private") and (data.get("main") or data.get("exports") or data.get("module") or data.get("types")):
            inv["exports"].append(item(ctx, "node", p, entry=str(data.get("main") or data.get("module") or ""), has_exports_map=isinstance(data.get("exports"), dict), types=str(data.get("types") or "")))
        test_scripts = sorted(k for k in scripts if k.startswith("test") or k in ("vitest", "jest", "e2e"))
        runners = [d for d in ("jest", "vitest", "mocha", "playwright", "@playwright/test", "cypress", "ava") if d in deps]
        if test_scripts or runners:
            inv["tests"].append(item(ctx, "node", p, scripts=test_scripts, runners=runners, package=ctx.rel(p.parent)))
        if any(k in scripts for k in ("publish", "release", "prepublishOnly", "changeset")) or (data.get("version") and not data.get("private")):
            inv["release"].append(item(ctx, "node", p, version=str(data.get("version") or ""), scripts=[k for k in scripts if k in ("publish", "release", "prepublishOnly", "changeset", "version")]))
        if any(d in deps for d in ("commander", "yargs", "oclif", "@oclif/core", "clipanion", "cac")) and not b:
            inv["cli"].append(item(ctx, "node", p, commands=[], parser=[d for d in deps if d in ("commander", "yargs", "oclif", "@oclif/core", "clipanion", "cac")][0]))
    each(ctx, ctx.named("package.json"), one, "node")
    for ws in ctx.named("pnpm-workspace.yaml", "lerna.json", "turbo.json", "nx.json"):
        inv["_mono"] = True
        inv["tree"]["workspace_tool"] = ws.name


def _dep_name(spec: str) -> str:
    return re.split(r"[<>=!~\[ ;@]", spec.strip())[0]


def det_python(ctx: Ctx, inv: dict) -> None:
    seen: set[str] = set()

    def pyproject(p: Path) -> None:
        data = load_toml(p)
        proj = as_dict(data.get("project"))
        poetry = as_dict(as_dict(data.get("tool")).get("poetry"))
        name = str(proj.get("name") or poetry.get("name") or p.parent.name)
        deps: list[str] = []
        if isinstance(proj.get("dependencies"), list):
            deps = [_dep_name(d) for d in proj["dependencies"] if isinstance(d, str) and "://" not in d]
        elif isinstance(poetry.get("dependencies"), dict):
            deps = list(poetry["dependencies"].keys())
        scripts = as_dict(proj.get("scripts")) or as_dict(poetry.get("scripts"))
        inv["packages"].append(item(ctx, "python", p, name=name, path=ctx.rel(p.parent), language="python", manifest="pyproject.toml",
                                    scripts=sorted(scripts.keys())[:40], dependencies=sorted(set(d for d in deps if d))[:80], version=str(proj.get("version") or poetry.get("version") or "")))
        inv["_eco"].add("python")
        seen.add(ctx.rel(p.parent))
        if scripts:
            inv["cli"].append(item(ctx, "python", p, commands=sorted(scripts.keys())[:40], parser="console_scripts"))
        low = {d.lower() for d in deps}
        if low & {"pytest", "nose2", "hypothesis", "tox"} or (p.parent / "tests").is_dir() or (p.parent / "test").is_dir():
            inv["tests"].append(item(ctx, "python", p, runners=sorted(low & {"pytest", "nose2", "tox"}), package=ctx.rel(p.parent)))
        if proj.get("version") or poetry.get("version"):
            inv["release"].append(item(ctx, "python", p, version=str(proj.get("version") or poetry.get("version") or ""), scripts=[]))

    def other(p: Path) -> None:
        if ctx.rel(p.parent) in seen:
            return
        seen.add(ctx.rel(p.parent))
        deps: list[str] = []
        if p.suffix == ".txt":
            for l in read(p).splitlines():
                l = l.strip()
                if not l or l.startswith(("#", "-")) or "://" in l:
                    continue  # a URL requirement can carry credentials; the name is not worth it
                deps.append(_dep_name(l))
        inv["packages"].append(item(ctx, "python", p, name=p.parent.name, path=ctx.rel(p.parent), language="python", manifest=p.name, scripts=[], dependencies=sorted(set(d for d in deps if d))[:80], version=""))
        inv["_eco"].add("python")

    each(ctx, ctx.named("pyproject.toml"), pyproject, "python")
    each(ctx, ctx.glob_name("requirements*.txt") + ctx.named("Pipfile", "setup.cfg", "setup.py"), other, "python")
    for p in ctx.named("manage.py"):
        inv["frontend"].append(item(ctx, "python", p, frameworks=["django-templates"], package=ctx.rel(p.parent)))


def det_go(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("go.mod"):
        text = read(p)
        m = re.search(r"^module\s+(\S+)", text, re.M)
        inv["packages"].append(item(ctx, "go", p, name=m.group(1) if m else p.parent.name, path=ctx.rel(p.parent), language="go", manifest="go.mod", scripts=[], dependencies=re.findall(r"^\s+(\S+)\s+v[\d.]", text, re.M)[:80], version=""))
        inv["_eco"].add("go")
        cmd = p.parent / "cmd"
        if cmd.is_dir():
            bins = sorted(d.name for d in cmd.iterdir() if d.is_dir() and any(f.suffix == ".go" for f in d.iterdir() if f.is_file()))
            if bins:
                inv["cli"].append(item(ctx, "go", cmd, commands=bins, parser="cmd/"))
        if (p.parent / "main.go").is_file():
            inv["cli"].append(item(ctx, "go", p.parent / "main.go", commands=[p.parent.name], parser="main.go"))
        if any(f.name.endswith("_test.go") for f in ctx.code_files if f.suffix == ".go"):
            inv["tests"].append(item(ctx, "go", p, runners=["go test"], package=ctx.rel(p.parent)))
    if ctx.named("go.work"):
        inv["_mono"] = True


def det_rust(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("Cargo.toml"):
        data = load_toml(p)
        pkg = data.get("package", {}) if isinstance(data.get("package"), dict) else {}
        ws = data.get("workspace", {}) if isinstance(data.get("workspace"), dict) else {}
        deps = list((data.get("dependencies") or {}).keys()) if isinstance(data.get("dependencies"), dict) else []
        if pkg:
            src = p.parent / "src"
            kind = "bin" if (src / "main.rs").is_file() or (p.parent / "src" / "bin").is_dir() or data.get("bin") else ("lib" if (src / "lib.rs").is_file() else "unknown")
            inv["packages"].append(item(ctx, "rust", p, name=str(pkg.get("name") or p.parent.name), path=ctx.rel(p.parent), language="rust", manifest="Cargo.toml", scripts=[], dependencies=sorted(deps)[:80], version=str(pkg.get("version") or ""), crate_kind=kind))
            inv["_eco"].add("rust")
            if kind == "bin":
                parser = next((d for d in deps if d in ("clap", "structopt", "argh", "lexopt", "pico-args", "bpaf")), "main.rs")
                inv["cli"].append(item(ctx, "rust", p, commands=[str(pkg.get("name") or p.parent.name)], parser=parser))
            if (src / "lib.rs").is_file():
                inv["exports"].append(item(ctx, "rust", src / "lib.rs", entry="src/lib.rs", has_exports_map=False, types=""))
            if pkg.get("version") and not (pkg.get("publish") is False):
                inv["release"].append(item(ctx, "rust", p, version=str(pkg.get("version")), scripts=[]))
        if ws:
            inv["_mono"] = True
            inv["_eco"].add("rust")
        if (p.parent / "tests").is_dir():
            inv["tests"].append(item(ctx, "rust", p, runners=["cargo test"], package=ctx.rel(p.parent)))


def det_java(ctx: Ctx, inv: dict) -> None:
    import xml.etree.ElementTree as ET
    for p in ctx.named("pom.xml"):
        try:
            root = ET.fromstring(read(p))
        except ET.ParseError:
            continue
        ns = root.tag.split("}")[0] + "}" if "}" in root.tag else ""
        art = root.findtext(f"{ns}artifactId") or p.parent.name
        modules = [m.text or "" for m in root.findall(f"{ns}modules/{ns}module")]
        deps = [(d.findtext(f"{ns}groupId") or "") + ":" + (d.findtext(f"{ns}artifactId") or "") for d in root.findall(f".//{ns}dependency")]
        inv["packages"].append(item(ctx, "java", p, name=art, path=ctx.rel(p.parent), language="java", manifest="pom.xml", scripts=[], dependencies=sorted(set(deps))[:80], version=str(root.findtext(f"{ns}version") or ""), modules=modules))
        inv["_eco"].add("java")
        if modules:
            inv["_mono"] = True
        if any("junit" in d or "testng" in d for d in deps) or (p.parent / "src" / "test").is_dir():
            inv["tests"].append(item(ctx, "java", p, runners=["maven test"], package=ctx.rel(p.parent)))
    for p in ctx.glob_name("build.gradle*"):
        text = read(p)
        deps = re.findall(r"""(?:implementation|api|compileOnly|runtimeOnly)\s*\(?\s*['"]([^'"]+)['"]""", text)
        lang = "kotlin" if p.name.endswith(".kts") or (p.parent / "src" / "main" / "kotlin").is_dir() else "java"
        settings = next((s for s in (p.parent / "settings.gradle", p.parent / "settings.gradle.kts") if s.is_file()), None)
        gname = re.search(r"""rootProject\.name\s*=\s*['"]([^'"]+)""", read(settings)) if settings else None
        inv["packages"].append(item(ctx, "java", p, name=gname.group(1) if gname else p.parent.name, path=ctx.rel(p.parent), language=lang, manifest=p.name, scripts=[], dependencies=sorted(set(deps))[:80], version=""))
        inv["_eco"].add("java")
        if (p.parent / "src" / "test").is_dir():
            inv["tests"].append(item(ctx, "java", p, runners=["gradle test"], package=ctx.rel(p.parent)))
    for p in ctx.glob_name("settings.gradle*"):
        if re.search(r"^\s*include\b", read(p), re.M):
            inv["_mono"] = True


def det_ruby(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("Gemfile"):
        gems = re.findall(r"""^\s*gem\s+['"]([^'"]+)['"]""", read(p), re.M)
        rails = (p.parent / "config" / "application.rb").is_file()
        inv["packages"].append(item(ctx, "ruby", p, name=p.parent.name, path=ctx.rel(p.parent), language="ruby", manifest="Gemfile", scripts=[], dependencies=sorted(set(gems))[:80], version="", framework="rails" if rails else ""))
        inv["_eco"].add("ruby")
        if "rspec" in gems or "minitest" in gems or (p.parent / "spec").is_dir():
            inv["tests"].append(item(ctx, "ruby", p, runners=[g for g in ("rspec", "minitest") if g in gems], package=ctx.rel(p.parent)))
        if rails:
            inv["frontend"].append(item(ctx, "ruby", p, frameworks=["rails-views"], package=ctx.rel(p.parent)))
    for p in ctx.glob_name("*.gemspec"):
        inv["exports"].append(item(ctx, "ruby", p, entry=p.name, has_exports_map=False, types=""))
        inv["release"].append(item(ctx, "ruby", p, version="", scripts=[]))


def det_php(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("composer.json"):
        data = load_json(p)
        if not isinstance(data, dict):
            continue
        deps = list((data.get("require") or {}).keys()) if isinstance(data.get("require"), dict) else []
        inv["packages"].append(item(ctx, "php", p, name=str(data.get("name") or p.parent.name), path=ctx.rel(p.parent), language="php", manifest="composer.json", scripts=sorted((data.get("scripts") or {}).keys())[:40] if isinstance(data.get("scripts"), dict) else [], dependencies=sorted(deps)[:80], version=str(data.get("version") or ""), framework="laravel" if (p.parent / "artisan").is_file() else ""))
        inv["_eco"].add("php")
        if (p.parent / "artisan").is_file():
            inv["cli"].append(item(ctx, "php", p.parent / "artisan", commands=["artisan"], parser="artisan"))
        if "phpunit/phpunit" in deps or (p.parent / "tests").is_dir():
            inv["tests"].append(item(ctx, "php", p, runners=["phpunit"], package=ctx.rel(p.parent)))


def det_dotnet(ctx: Ctx, inv: dict) -> None:
    for p in ctx.glob_name("*.csproj"):
        text = read(p)
        sdk = re.search(r'Sdk="([^"]+)"', text)
        pkgs = re.findall(r'PackageReference\s+Include="([^"]+)"', text)
        inv["packages"].append(item(ctx, "dotnet", p, name=p.stem, path=ctx.rel(p.parent), language="csharp", manifest=p.name, scripts=[], dependencies=sorted(set(pkgs))[:80], version="", sdk=sdk.group(1) if sdk else ""))
        inv["_eco"].add("dotnet")
        if any("xunit" in x.lower() or "nunit" in x.lower() or "mstest" in x.lower() for x in pkgs):
            inv["tests"].append(item(ctx, "dotnet", p, runners=["dotnet test"], package=ctx.rel(p.parent)))
    if ctx.glob_name("*.sln"):
        inv["_mono"] = True


def det_elixir(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("mix.exs"):
        text = read(p)
        m = re.search(r"app[:]\s*:(\w+)", text)
        deps = re.findall(r"\{:(\w+),", text)
        inv["packages"].append(item(ctx, "elixir", p, name=m.group(1) if m else p.parent.name, path=ctx.rel(p.parent), language="elixir", manifest="mix.exs", scripts=[], dependencies=sorted(set(deps))[:80], version=str((re.search(r"version[:]\s*\"([^\"]+)\"", text) or [None, ""])[1] if re.search(r"version[:]\s*\"([^\"]+)\"", text) else "")))
        inv["_eco"].add("elixir")
        if (p.parent / "test").is_dir():
            inv["tests"].append(item(ctx, "elixir", p, runners=["mix test"], package=ctx.rel(p.parent)))
        if "phoenix" in deps:
            inv["frontend"].append(item(ctx, "elixir", p, frameworks=["phoenix"], package=ctx.rel(p.parent)))


def det_move(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("Move.toml"):
        data = load_toml(p)
        pkg = data.get("package", {}) if isinstance(data.get("package"), dict) else {}
        inv["packages"].append(item(ctx, "move", p, name=str(pkg.get("name") or p.parent.name), path=ctx.rel(p.parent), language="move", manifest="Move.toml", scripts=[], dependencies=list((data.get("dependencies") or {}).keys())[:40] if isinstance(data.get("dependencies"), dict) else [], version=str(pkg.get("version") or "")))
        inv["_eco"].add("move")


# ------------------------------------------------------------------ agnostic detectors

PORT_TOKEN = re.compile(r"^\d{1,5}(?:/(?:tcp|udp))?$", re.I)


def det_dockerfiles(ctx: Ctx, inv: dict) -> None:
    def one(p: Path) -> None:
        text = read(p)
        froms = re.findall(r"^FROM\s+(\S+)", text, re.M | re.I)
        # \s matches the newline and re.I lets [tcpud] match the C of a following CMD, so the
        # old class ran past the end of the line and reported a port named "C". Take the rest of
        # the EXPOSE line, then keep only tokens that are actually a port.
        expose = re.findall(r"^EXPOSE[ \t]+([^\r\n]*)", text, re.M | re.I)
        envs = re.findall(r"^(?:ENV|ARG)\s+([A-Za-z_][A-Za-z0-9_]*)", text, re.M | re.I)
        cmd = re.search(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.M | re.I)
        inv["services"].append(item(ctx, "dockerfile", p, name=p.parent.name if p.parent != ctx.repo else (p.name if p.name != "Dockerfile" else "root"), root=ctx.rel(p.parent),
                                    runtime=froms[:4], ports=sorted({x for e_ in expose for x in e_.split() if PORT_TOKEN.match(x)}), start=first_token(cmd.group(1)) if cmd else "", source="Dockerfile"))
        if envs:
            inv["env"].append({"source": ctx.rel(p), "kind": "dockerfile", "names": sorted(set(envs))[:60]})
    each(ctx, ctx.glob_name("Dockerfile*"), one, "dockerfiles")


def container_port(spec) -> str:
    """`8080`, `"5432:5432"`, `"127.0.0.1:8080:80/tcp"` or `"${HOST:-8000}:8000"` -> the container port."""
    s = re.sub(r"\$\{[^}]*?:-([^}]*)\}", r"\1", str(spec))
    s = re.sub(r"\$\{[^}]*\}|\$\w+", "", s)
    last = s.rsplit(":", 1)[-1].split("/")[0].strip()
    return last if last.isdigit() or re.fullmatch(r"\d+-\d+", last) else ""


def det_compose(ctx: Ctx, inv: dict) -> None:
    def one(p: Path) -> None:
        data = yaml_scan(read(p))
        services = data.get("services") if isinstance(data, dict) else None
        if not isinstance(services, dict):
            return
        for name, svc in services.items():
            if not isinstance(svc, dict):
                continue
            ports = svc.get("ports") if isinstance(svc.get("ports"), list) else []
            env = svc.get("environment")
            env_names: list[str] = []
            if isinstance(env, dict):
                env_names = list(env.keys())
            elif isinstance(env, list):
                env_names = [re.split(r"[=:]", str(x), maxsplit=1)[0].strip() for x in env if isinstance(x, str)]
            build = svc.get("build")
            root = build.get("context") if isinstance(build, dict) else (build if isinstance(build, str) else "")
            dep = svc.get("depends_on")
            inv["services"].append(item(ctx, "compose", p, name=str(name), root=str(root or ""), image=str(svc.get("image") or ""),
                                        ports=[pp for pp in (container_port(x) for x in ports if isinstance(x, (str, int))) if pp][:8],
                                        depends_on=list(dep.keys()) if isinstance(dep, dict) else (dep if isinstance(dep, list) else []),
                                        healthcheck=isinstance(svc.get("healthcheck"), dict), env_file=svc.get("env_file") if isinstance(svc.get("env_file"), (str, list)) else "", source="compose"))
            if env_names:
                inv["env"].append({"source": ctx.rel(p), "kind": "compose", "service": str(name), "names": sorted(set(n for n in env_names if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", n)))[:80]})
            if isinstance(svc.get("healthcheck"), dict):
                inv["ops"].append(item(ctx, "compose", p, kind="healthcheck", service=str(name)))
    each(ctx, ctx.glob_name("docker-compose*.yml") + ctx.glob_name("docker-compose*.yaml") + ctx.named("compose.yml", "compose.yaml"), one, "compose")


def det_platforms(ctx: Ctx, inv: dict) -> None:
    def railway(p: Path) -> None:
        data = load_json(p) if p.suffix == ".json" else load_toml(p)
        if not isinstance(data, dict):
            return
        svcs = data.get("services") if isinstance(data.get("services"), list) else [data]
        for s in svcs:
            if not isinstance(s, dict):
                continue
            build = as_dict(s.get("build"))
            dep = as_dict(s.get("deploy"))
            sname = str(s.get("name") or p.parent.name)
            inv["services"].append(item(ctx, "railway", p, name=sname, root=str(s.get("root") or s.get("rootDirectory") or ctx.rel(p.parent)), builder=str(build.get("builder") or ""),
                                        start=first_token(str(dep.get("startCommand") or "")), healthcheck=bool(dep.get("healthcheckPath")), cron=str(dep.get("cronSchedule") or ""), source="railway"))
            if dep.get("cronSchedule"):
                inv["ops"].append(item(ctx, "railway", p, kind="cron", schedule=str(dep.get("cronSchedule")), service=sname))
            if dep.get("healthcheckPath"):
                inv["ops"].append(item(ctx, "railway", p, kind="healthcheck", path=str(dep.get("healthcheckPath")), service=sname))
            vars_ = s.get("variables")
            if isinstance(vars_, dict):
                inv["env"].append({"source": ctx.rel(p), "kind": "railway", "names": sorted(vars_.keys())[:80]})

    def fly(p: Path) -> None:
        data = load_toml(p)
        inv["services"].append(item(ctx, "fly", p, name=str(data.get("app") or p.parent.name), root=ctx.rel(p.parent), source="fly", healthcheck="checks" in data or "http_service" in data))
        env = data.get("env")
        if isinstance(env, dict):
            inv["env"].append({"source": ctx.rel(p), "kind": "fly", "names": sorted(env.keys())[:80]})

    def render(p: Path) -> None:
        data = yaml_scan(read(p))
        for s in data.get("services", []) if isinstance(data.get("services"), list) else []:
            if isinstance(s, dict):
                inv["services"].append(item(ctx, "render", p, name=str(s.get("name") or ""), root=str(s.get("rootDir") or ""), type=str(s.get("type") or ""), start=first_token(str(s.get("startCommand") or "")), source="render"))
                ev = s.get("envVars")
                if isinstance(ev, list):
                    inv["env"].append({"source": ctx.rel(p), "kind": "render", "names": sorted(str(e_.get("key")) for e_ in ev if isinstance(e_, dict) and e_.get("key"))[:80]})

    def vercel(p: Path) -> None:
        data = load_json(p)
        rewrites = data.get("rewrites") if isinstance(data, dict) else None
        inv["services"].append(item(ctx, "vercel", p, name=p.parent.name, root=ctx.rel(p.parent), source="vercel", rewrites=len(rewrites) if isinstance(rewrites, list) else 0, note="settings live outside the repo"))

    def netlify(p: Path) -> None:
        inv["services"].append(item(ctx, "netlify", p, name=p.parent.name, root=ctx.rel(p.parent), source="netlify"))

    def procfile(p: Path) -> None:
        procs = [l.split(":", 1)[0].strip() for l in read(p).splitlines() if ":" in l and not l.startswith("#")]
        inv["services"].append(item(ctx, "procfile", p, name=p.parent.name, root=ctx.rel(p.parent), processes=procs, source="Procfile"))

    def appyaml(p: Path) -> None:
        data = yaml_scan(read(p))
        inv["services"].append(item(ctx, "appengine", p, name=p.parent.name, root=ctx.rel(p.parent), runtime=str(data.get("runtime") or ""), source="app.yaml"))
        if isinstance(data.get("env_variables"), dict):
            inv["env"].append({"source": ctx.rel(p), "kind": "appengine", "names": sorted(data["env_variables"].keys())[:80]})

    each(ctx, ctx.named("railway.json", "railway.toml"), railway, "railway")
    each(ctx, ctx.named("fly.toml"), fly, "fly")
    each(ctx, ctx.named("render.yaml"), render, "render")
    each(ctx, ctx.named("vercel.json"), vercel, "vercel")
    each(ctx, ctx.named("netlify.toml"), netlify, "netlify")
    each(ctx, ctx.named("Procfile"), procfile, "procfile")
    each(ctx, ctx.named("app.yaml"), appyaml, "appengine")


def det_k8s(ctx: Ctx, inv: dict) -> None:
    for p in ctx.named("Chart.yaml"):
        data = yaml_scan(read(p))
        inv["services"].append(item(ctx, "helm", p, name=str(data.get("name") or p.parent.name), root=ctx.rel(p.parent), source="helm", templates=len(list((p.parent / "templates").glob("*.y*ml"))) if (p.parent / "templates").is_dir() else 0))
        inv["_infra"] = True
    def manifest(p: Path) -> None:
        if p.suffix.lower() not in (".yml", ".yaml") or p.name in ("Chart.yaml", "values.yaml") or ".github" in p.parts or "docker-compose" in p.name:
            return
        text = read(p)
        if "kind:" not in text or "apiVersion:" not in text:
            return
        for doc in text.split("\n---"):
            data = yaml_scan(doc)
            kind = str(data.get("kind") or "")
            if not kind:
                continue
            meta = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            name = str(meta.get("name") or "")
            if kind in ("Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"):
                inv["_infra"] = True
                spec = data.get("spec") if isinstance(data.get("spec"), dict) else {}
                tmpl = spec.get("template", {}).get("spec", {}) if isinstance(spec.get("template"), dict) and isinstance(spec["template"].get("spec"), dict) else {}
                containers = tmpl.get("containers") if isinstance(tmpl.get("containers"), list) else []
                images = [str(c.get("image") or "") for c in containers if isinstance(c, dict)]
                ports = [str(pp.get("containerPort")) for c in containers if isinstance(c, dict) for pp in (c.get("ports") or []) if isinstance(pp, dict) and pp.get("containerPort")]
                envn = [str(e.get("name")) for c in containers if isinstance(c, dict) for e in (c.get("env") or []) if isinstance(e, dict) and e.get("name")]
                probes = any(isinstance(c, dict) and (c.get("livenessProbe") or c.get("readinessProbe")) for c in containers)
                inv["services"].append(item(ctx, "k8s", p, name=name or p.stem, kind=kind, images=[redact(i) for i in images][:6], ports=sorted(set(ports))[:8], healthcheck=probes, source="k8s"))
                if envn:
                    inv["env"].append({"source": ctx.rel(p), "kind": "k8s", "service": name, "names": sorted(set(envn))[:80]})
                if probes:
                    inv["ops"].append(item(ctx, "k8s", p, kind="healthcheck", service=name))
                if kind == "CronJob":
                    inv["ops"].append(item(ctx, "k8s", p, kind="cron", schedule=str(spec.get("schedule") or ""), service=name))
            elif kind == "Ingress":
                inv["_infra"] = True
                inv["ops"].append(item(ctx, "k8s", p, kind="ingress", service=name))
            elif kind == "Service":
                inv["_infra"] = True
            elif kind == "ConfigMap" and isinstance(data.get("data"), dict):
                inv["env"].append({"source": ctx.rel(p), "kind": "configmap", "names": sorted(data["data"].keys())[:80]})
            elif kind == "Secret":
                inv["env"].append({"source": ctx.rel(p), "kind": "secret-manifest", "names": [], "note": f"Secret {name}: keys not read"})
            elif kind in ("PrometheusRule",):
                inv["ops"].append(item(ctx, "k8s", p, kind="alert-rules", service=name))
    each(ctx, ctx.files, manifest, "k8s")


def det_terraform(ctx: Ctx, inv: dict) -> None:
    resources: list[dict] = []
    variables: set[str] = set()
    providers: set[str] = set()
    for p in ctx.files:
        if p.suffix != ".tf":
            continue
        text = read(p)
        for typ, name in re.findall(r'^\s*resource\s+"([^"]+)"\s+"([^"]+)"', text, re.M):
            resources.append({"type": typ, "name": name, "evidence": ctx.rel(p)})
        variables.update(re.findall(r'^\s*variable\s+"([^"]+)"', text, re.M))
        providers.update(re.findall(r'^\s*provider\s+"([^"]+)"', text, re.M))
    if resources or providers:
        inv["_infra"] = True
        inv["services"].append({"detector": "terraform", "evidence": resources[0]["evidence"] if resources else "", "name": "terraform", "source": "terraform",
                                "resources": resources[:ctx.cap], "providers": sorted(providers), "resource_count": len(resources)})
        if variables:
            inv["env"].append({"source": "*.tf", "kind": "terraform-variables", "names": sorted(variables)[:80]})


def det_ci(ctx: Ctx, inv: dict) -> None:
    wf = ctx.repo / ".github" / "workflows"
    if wf.is_dir():
        for p in sorted(wf.glob("*.y*ml")):
            text = read(p)
            data = yaml_scan(text)
            jobs = data.get("jobs") if isinstance(data.get("jobs"), dict) else {}
            uses = re.findall(r"^\s*-?\s*uses[:]\s*(\S+)", text, re.M)
            env_names = set(re.findall(r"\$\{\{\s*(?:secrets|vars|env)\.([A-Za-z_][A-Za-z0-9_]*)", text))
            if isinstance(data.get("env"), dict):
                env_names.update(data["env"].keys())
            on = data.get("on")
            inv["ci"].append(item(ctx, "github-actions", p, name=str(data.get("name") or p.stem), on=list(on.keys()) if isinstance(on, dict) else ([on] if isinstance(on, str) else on if isinstance(on, list) else []),
                                  jobs=list(jobs.keys())[:20], deploy=bool(any(DEPLOY_ISH.search(u) for u in uses) or DEPLOY_ISH.search(str(data.get("name") or ""))),
                                  tests=bool(re.search(r"\b(test|pytest|vitest|jest|cargo test|go test|gradle test|mvn test|phpunit|dotnet test)\b", text, re.I))))
            if env_names:
                inv["env"].append({"source": ctx.rel(p), "kind": "github-actions", "names": sorted(env_names)[:80]})
    for p in ctx.named(".gitlab-ci.yml"):
        data = yaml_scan(read(p))
        inv["ci"].append(item(ctx, "gitlab-ci", p, name=".gitlab-ci.yml", on=[], jobs=[k for k in data.keys() if not k.startswith(".") and k not in ("stages", "variables", "default", "include", "image", "workflow")][:20], deploy=bool(DEPLOY_ISH.search(read(p))), tests=bool(re.search(r"\btest\b", read(p), re.I))))
    for p in ctx.named("Makefile", "justfile", "Taskfile.yml"):
        targets = re.findall(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?!=)", read(p), re.M)
        inv["tree"].setdefault("task_runners", []).append({"file": ctx.rel(p), "targets": sorted(set(targets))[:40]})


def det_envfiles(ctx: Ctx, inv: dict) -> None:
    for p in ctx.files:
        if not ENV_ALLOW.match(p.name):
            continue
        names = []
        for line in read(p).splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            key = s.split("=", 1)[0].strip()
            key = key[len("export "):].strip() if key.startswith("export ") else key
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                names.append(key)
        if names:
            inv["env"].append({"source": ctx.rel(p), "kind": "env-example", "package": ctx.rel(p.parent), "names": sorted(set(names))[:120],
                               "secret_like": sorted({n for n in names if SECRET_NAME.search(n)})[:60]})


CODE_READS = [
    (re.compile(r"process\.env\.([A-Z][A-Z0-9_]*)"), "node"),
    (re.compile(r"""process\.env\[\s*['"]([A-Z][A-Z0-9_]*)['"]"""), "node"),
    (re.compile(r"""import\.meta\.env\.([A-Z][A-Z0-9_]*)"""), "node"),
    (re.compile(r"""os\.environ(?:\.get)?\[?\(?\s*['"]([A-Z][A-Z0-9_]*)['"]"""), "python"),
    (re.compile(r"""os\.getenv\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""), "python"),
    (re.compile(r"""os\.Getenv\(\s*"([A-Z][A-Z0-9_]*)"\)"""), "go"),
    (re.compile(r"""env::var\(\s*"([A-Z][A-Z0-9_]*)"\)"""), "rust"),
    (re.compile(r"""System\.getenv\(\s*"([A-Z][A-Z0-9_]*)"\)"""), "java"),
    (re.compile(r"""ENV(?:\.fetch)?\[?\(?\s*['"]([A-Z][A-Z0-9_]*)['"]"""), "ruby"),
    (re.compile(r"""\benv\(\s*['"]([A-Z][A-Z0-9_]*)['"]"""), "php"),
    (re.compile(r"""GetEnvironmentVariable\(\s*"([A-Z][A-Z0-9_]*)"\)"""), "dotnet"),
]


def det_code_reads(ctx: Ctx, inv: dict) -> None:
    found: dict[str, str] = {}
    for p in ctx.code_files:
        text = read(p)
        if "env" not in text.lower():
            continue
        for rx, _ in CODE_READS:
            for name in rx.findall(text):
                found.setdefault(name, ctx.rel(p))
    if found:
        inv["env"].append({"source": "code", "kind": "code-reads", "names": sorted(found.keys())[:200], "first_seen": {k: found[k] for k in sorted(found)[:200]}})


SCHEMA_PATTERNS = [
    ("sql", re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"']?([A-Za-z_][\w.]*)", re.I), (".sql",)),
    ("drizzle", re.compile(r"(?:pgTable|mysqlTable|sqliteTable)\(\s*['\"]([A-Za-z_]\w*)['\"]"), (".ts", ".js")),
    ("prisma", re.compile(r"^model\s+(\w+)\s*\{", re.M), (".prisma",)),
    ("knex-typeorm", re.compile(r"createTable\(\s*['\"]([A-Za-z_]\w*)['\"]"), (".ts", ".js")),
    ("alembic", re.compile(r"op\.create_table\(\s*['\"]([A-Za-z_]\w*)['\"]"), (".py",)),
    ("django", re.compile(r"migrations\.CreateModel\(\s*name=['\"](\w+)['\"]"), (".py",)),
    ("rails", re.compile(r"create_table\s+[:'\"](\w+)"), (".rb",)),
    ("laravel", re.compile(r"Schema::create\(\s*['\"](\w+)['\"]"), (".php",)),
    ("ef", re.compile(r"CreateTable\(\s*name[:]\s*\"(\w+)\""), (".cs",)),
    ("liquibase", re.compile(r"createTable\s+tableName=\"(\w+)\""), (".xml",)),
    ("ecto", re.compile(r"create\s+table\(:(\w+)"), (".exs",)),
]
SCHEMA_DIRS = {"migrations", "migration", "drizzle", "prisma", "alembic", "supabase", "db", "sql", "schema", "flyway", "liquibase"}
FK_RE = re.compile(r"REFERENCES\s+[`\"']?([A-Za-z_][\w.]*)|references\(\s*\(\)\s*=>\s*(\w+)\.|@relation|foreign_key\s*[:=]|add_foreign_key|belongsTo|HasOne|HasMany", re.I)


def det_schema(ctx: Ctx, inv: dict) -> None:
    tables: dict[str, dict] = {}
    migrations: list[str] = []
    fks = 0
    for p in ctx.files:
        parts = {x.lower() for x in p.relative_to(ctx.repo).parts[:-1]}
        in_schema_dir = bool(parts & SCHEMA_DIRS)
        ext = p.suffix.lower()
        if ext == ".prisma" or (in_schema_dir and ext in (".sql", ".ts", ".js", ".py", ".rb", ".php", ".cs", ".xml", ".exs")):
            text = read(p)
            # Prisma puts the timestamp on the folder (20260812_x/migration.sql) and Alembic
            # uses a revision hash, so matching the filename alone reported zero migrations for
            # both - in the doc the skill makes the owner of that count.
            stamped = re.compile(r"^\d{3,}|^V\d|^\d{4}-\d{2}|^\d{14}")
            here = p.parent.name.lower()
            above = p.parent.parent.name.lower() if p.parent.parent != ctx.repo else ""
            if in_schema_dir and (stamped.match(p.name) or stamped.match(p.parent.name)
                                  or here in ("versions", "migrations")
                                  or above in ("versions", "migrations")) \
                    and p.name.lower() not in ("__init__.py", "env.py", "migration_lock.toml"):
                migrations.append(ctx.rel(p))
            for tool, rx, exts in SCHEMA_PATTERNS:
                if ext not in exts:
                    continue
                for name in rx.findall(text):
                    tables.setdefault(name, {"name": name, "tool": tool, "evidence": ctx.rel(p)})
            fks += len(FK_RE.findall(text))
    if tables or migrations:
        migrations.sort()
        inv["schema"] = {"tables": cap(sorted(tables.values(), key=lambda t: t["name"]), ctx.cap, "schema.tables", inv), "table_count": len(tables),
                         "migrations": {"count": len(migrations), "first": migrations[0] if migrations else "", "last": migrations[-1] if migrations else "", "folders": sorted({m.rsplit("/", 1)[0] for m in migrations if "/" in m})[:10]},
                         "foreign_key_mentions": fks}


ROUTE_PATTERNS = [
    # The path starts with a slash. Without that, r.get("session:1") on a redis client and
    # api.get("new-checkout") on a feature-flag client were counted as HTTP routes, and the
    # gate then told an author their correct route count disagreed with the inventory.
    ("express-like", re.compile(r"\b(?:app|router|server|api|r)\.(get|post|put|patch|delete|all)\(\s*['\"`](/[^'\"`]*)['\"`]"), (".js", ".ts", ".mjs", ".cjs")),
    ("nestjs", re.compile(r"@(Get|Post|Put|Patch|Delete)\(\s*['\"]?([^'\")]*)['\"]?\s*\)"), (".ts",)),
    ("fastapi-flask", re.compile(r"@(?:app|router|api|bp|blueprint)\.(get|post|put|patch|delete|route)\(\s*['\"]([^'\"]+)['\"]"), (".py",)),
    ("django", re.compile(r"\b(?:path|re_path|url)\(\s*r?['\"]([^'\"]*)['\"]"), (".py",)),
    ("go-net-http", re.compile(r"\.(?:HandleFunc|Handle|GET|POST|PUT|PATCH|DELETE|Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\""), (".go",)),
    ("axum", re.compile(r"\.route\(\s*\"([^\"]+)\"\s*,\s*(get|post|put|patch|delete)"), (".rs",)),
    ("actix", re.compile(r"#\[(get|post|put|patch|delete)\(\s*\"([^\"]+)\""), (".rs",)),
    ("spring", re.compile(r"@(Get|Post|Put|Patch|Delete|Request)Mapping\(\s*(?:value\s*=\s*)?\{?\s*\"([^\"]*)\""), (".java", ".kt")),
    ("rails", re.compile(r"^\s*(get|post|put|patch|delete|resources|resource)\s+['\":]([^'\",\s]+)", re.M), (".rb",)),
    ("phoenix", re.compile(r"^\s*(get|post|put|patch|delete|resources|live)\s+\"([^\"]+)\"", re.M), (".ex",)),
    ("laravel", re.compile(r"Route::(get|post|put|patch|delete|resource|apiResource)\(\s*['\"]([^'\"]+)['\"]"), (".php",)),
    ("dotnet", re.compile(r"\[Http(Get|Post|Put|Patch|Delete)\(\s*\"?([^\"\)]*)\"?\s*\)\]|app\.Map(Get|Post|Put|Patch|Delete)\(\s*\"([^\"]+)\""), (".cs",)),
]
VERB_LESS = {"django", "go-net-http", "rails"}
# A Spring controller puts a path prefix on the class and the rest on each method. Reading the
# methods alone reported every path short, and emitted the class-level annotation as a route
# of its own with the method "REQUEST". Both were wrong in a drafted endpoint table.
CLASS_MAPPING = re.compile(r'@RequestMapping\(\s*(?:value\s*=\s*)?\{?\s*"([^"]*)"[^)]*\)'
                          r'(?:\s*@\w+(?:\([^)]*\))?)*\s*(?:public\s+|final\s+|abstract\s+)*class\b', re.S)
COMMENT_LINE = re.compile(r"^\s*(//|#|\*|/\*|--|<!--)")
TEST_FILE = re.compile(r"(_test\.go|\.test\.[jt]sx?|\.spec\.[jt]sx?|^test_.*\.py|_test\.py|Tests?\.java|Test\.kt|_spec\.rb|Tests?\.cs|_test\.exs|_test\.rs)$")


def strip_comment_lines(text: str) -> str:
    """Drop whole-line comments so a route in a doc-comment example is not a route."""
    return "\n".join(l for l in text.splitlines() if not COMMENT_LINE.match(l))


def det_routes(ctx: Ctx, inv: dict) -> None:
    routes: list[dict] = []
    # OpenAPI first
    for p in ctx.glob_name("openapi*.json") + ctx.glob_name("openapi*.y*ml") + ctx.glob_name("swagger*.json") + ctx.glob_name("swagger*.y*ml"):
        data = load_json(p) if p.suffix == ".json" else yaml_scan(read(p))
        paths = data.get("paths") if isinstance(data, dict) and isinstance(data.get("paths"), dict) else {}
        for path, ops in paths.items():
            verbs = [v.upper() for v in ops.keys() if isinstance(ops, dict) and v.lower() in ("get", "post", "put", "patch", "delete")] if isinstance(ops, dict) else []
            routes.append({"method": "/".join(verbs) or "?", "path": redact(str(path)), "framework": "openapi", "evidence": ctx.rel(p)})
        if paths:
            inv["tree"]["openapi"] = ctx.rel(p)
    # Next.js file routers
    for p in ctx.code_files:
        rel = ctx.rel(p)
        m = re.search(r"(?:^|/)(?:src/)?app/(.+)/route\.(ts|js|tsx|jsx)$", rel)
        if m:
            text = read(p)
            verbs = re.findall(r"export\s+(?:async\s+)?function\s+(GET|POST|PUT|PATCH|DELETE)\b", text) or re.findall(r"export\s+const\s+(GET|POST|PUT|PATCH|DELETE)\b", text)
            routes.append({"method": "/".join(sorted(set(verbs))) or "?", "path": "/" + re.sub(r"\([^)]*\)/?", "", m.group(1)), "framework": "next-app-router", "evidence": rel})
            continue
        m = re.search(r"(?:^|/)(?:src/)?pages/api/(.+)\.(ts|js|tsx|jsx)$", rel)
        if m:
            routes.append({"method": "?", "path": "/api/" + re.sub(r"/index$", "", m.group(1)), "framework": "next-pages-api", "evidence": rel})
    # framework patterns; test files never define the surface
    lib_roots = [pk["path"] for pk in inv.get("packages", []) if pk.get("crate_kind") == "lib"]
    for p in ctx.code_files:
        if TEST_FILE.search(p.name):
            continue
        ext = p.suffix.lower()
        text = None
        for fw, rx, exts in ROUTE_PATTERNS:
            if ext not in exts:
                continue
            if text is None:
                text = strip_comment_lines(read(p))
                if not text:
                    break
            prefix, class_at = "", -1
            if fw == "spring":
                cm = CLASS_MAPPING.search(text)
                if cm:
                    prefix, class_at = cm.group(1).rstrip("/"), cm.start()
            for mt in rx.finditer(text):
                if fw == "spring" and mt.start() == class_at:
                    continue  # the class-level prefix is not itself a route
                g = [x for x in mt.groups() if x is not None]
                if fw in VERB_LESS:
                    if fw == "rails":
                        method, path = g[0].upper(), g[1]
                    else:
                        method, path = "?", g[0]
                elif fw == "dotnet":
                    method, path = g[0].upper(), (g[1] if len(g) > 1 else "")
                else:
                    method, path = g[0].upper(), (g[1] if len(g) > 1 else "")
                if fw == "django" and (path.endswith((".html",)) or "static" in path):
                    continue
                if fw == "spring" and prefix:
                    path = prefix + ("" if not path or path == "/" else path if path.startswith("/") else "/" + path)
                rel = ctx.rel(p)
                in_lib = any(rel.startswith(root + "/") or root == "." for root in lib_roots)
                routes.append({"method": method, "path": redact(path), "framework": fw, "evidence": rel, **({"hint": True} if in_lib else {})})
    # de-duplicate
    seen = set()
    uniq = []
    for r in routes:
        k = (r["method"], r["path"], r["evidence"])
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    real = [r for r in uniq if not r.get("hint")]
    if uniq:
        by_fw: dict[str, int] = {}
        for r in real:
            by_fw[r["framework"]] = by_fw.get(r["framework"], 0) + 1
        inv["routes"] = {"count": len(real), "hints_in_library_code": len(uniq) - len(real), "by_framework": by_fw,
                         "items": cap(sorted(real, key=lambda r: (r["path"], r["method"])), ctx.cap, "routes.items", inv),
                         "auth_hints": sorted({ctx.rel(p) for p in ctx.code_files if re.search(r"(auth|guard|middleware|session)", p.name, re.I)})[:20]}


def det_cli_parsers(ctx: Ctx, inv: dict) -> None:
    hints = []
    for p in ctx.code_files:
        text = read(p)
        if not text:
            continue
        if re.search(r"\b(argparse\.ArgumentParser|click\.(command|group)|typer\.Typer|cobra\.Command|clap::Parser|#\[derive\(Parser|new Command\(|yargs\(|commander)", text):
            subs = re.findall(r"add_parser\(\s*['\"]([^'\"]+)['\"]|@\w+\.command\(\s*['\"]?([^'\")\s]*)|\.command\(\s*['\"]([^'\"]+)['\"]|Use[:]\s*\"([^\"]+)\"", text)
            names = sorted({x for tup in subs for x in tup if x})[:40]
            hints.append(item(ctx, "cli-parser", p, commands=names, parser="argparse/click/typer/cobra/clap/commander", hint=True))
    if hints:
        inv["cli"].extend(hints[:20])


def det_frontend_tokens(ctx: Ctx, inv: dict) -> None:
    for p in ctx.glob_name("tailwind.config.*"):
        text = read(p)
        keys = re.findall(r"^\s{4,8}(colors|fontFamily|fontSize|spacing|borderRadius|boxShadow|transitionTimingFunction|keyframes|animation|screens)\s*:", text, re.M)
        inv["frontend"].append(item(ctx, "tailwind-config", p, tokens=sorted(set(keys))))
    css_props: dict[str, str] = {}
    comp_dirs: set[str] = set()
    for p in ctx.files:
        if p.suffix.lower() in (".css", ".scss", ".less") and len(css_props) < 400:
            text = read(p)
            for name in re.findall(r"(--[A-Za-z][\w-]*)\s*:", text):
                css_props.setdefault(name, ctx.rel(p))
            if "@theme" in text:
                inv["frontend"].append(item(ctx, "css-theme", p, note="@theme block (Tailwind v4)"))
        rel = ctx.rel(p)
        m = re.search(r"(?:^|/)(components|ui)/([^/]+)/", rel)
        if m and p.suffix.lower() in CODE_EXTS:
            comp_dirs.add(rel[: m.end()].rstrip("/"))
    if css_props:
        inv["frontend"].append({"detector": "css-custom-properties", "evidence": sorted(set(css_props.values()))[0], "count": len(css_props), "names": sorted(css_props.keys())[:80]})
    if comp_dirs:
        inv["frontend"].append({"detector": "component-folders", "evidence": sorted(comp_dirs)[0], "folders": sorted(comp_dirs)[:40], "count": len(comp_dirs)})


def det_tests_folders(ctx: Ctx, inv: dict) -> None:
    folders = sorted(posix(Path(d), ctx.repo) for d in ctx.pruned if Path(d).name.lower() in ("tests", "test", "__tests__", "spec", "e2e", "cypress"))
    folders += sorted(d for d in ctx.dirs if Path(d).name.lower() in ("e2e", "cypress") and d not in folders)
    configs = [ctx.rel(p) for p in ctx.files if re.match(r"^(jest|vitest|pytest|playwright|cypress|karma|mocha)\.config\.|^pytest\.ini$|^tox\.ini$|^\.mocharc|^phpunit\.xml", p.name)]
    if folders or configs:
        inv["tests"].append({"detector": "test-layout", "evidence": (folders or configs)[0], "folders": folders[:20], "configs": configs[:20]})


def det_ops_signals(ctx: Ctx, inv: dict) -> None:
    for p in ctx.code_files:
        if TEST_FILE.search(p.name):
            continue
        rel = ctx.rel(p)
        if re.search(r"(^|/)(health|healthz|ready|readiness|liveness)(\.|/)", rel, re.I):
            inv["ops"].append(item(ctx, "code", p, kind="health-route"))
    for p in ctx.files:
        if re.search(r"(alert|alerts|alerting).*\.(ya?ml|json)$", p.name, re.I) or p.name in ("alertmanager.yml", "prometheus.yml"):
            inv["ops"].append(item(ctx, "file", p, kind="alert-config"))
    cron_hits = 0
    for p in ctx.code_files[:2000]:
        text = read(p)
        if re.search(r"(cron\.schedule|@Scheduled|node-cron|croniter|schedule\.every|cron[:]\s*['\"])", text):
            inv["ops"].append(item(ctx, "code", p, kind="scheduler", hint=True))
            cron_hits += 1
            if cron_hits >= 10:
                break


def det_readme_tree(ctx: Ctx, inv: dict) -> None:
    readme = ctx.repo / "README.md"
    if readme.is_file():
        lines = read(readme).splitlines()
        h1 = next((l.lstrip("# ").strip() for l in lines if l.startswith("# ")), "")
        para = ""
        for l in lines[1:80]:
            if l.strip() and not l.startswith(("#", "!", "[", "<", ">", "|", "-", "*", "`")):
                para = l.strip()
                break
        inv["readme"] = {"evidence": "README.md", "title": redact(h1), "first_paragraph": redact(para)[:300],
                         "headings": [redact(l.strip("# ").strip()) for l in lines if re.match(r"^#{1,3} ", l)][:40], "lines": len(lines)}
    present = [n for n in ("LICENSE", "LICENSE.md", "LICENCE", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md", "CHANGELOG.md", "CLAUDE.md", "AGENTS.md") if (ctx.repo / n).is_file()]
    # A file git ignores is one developer's copy, not the repository's: a gitignored CLAUDE.md
    # was quoted eight times into drafts before the gate caught it. `git check-ignore -q` exits 0
    # for an ignored path, which run_git returns as "" rather than None.
    ignored = [n for n in present if run_git(ctx.repo, ["check-ignore", "-q", n]) is not None]
    gov = [n for n in present if n not in ignored]
    inv["tree"].update({"top_level_dirs": ctx.top_level_dirs(), "governance_files": gov, "ignored_governance_files": ignored,
                        "pr_template": any((ctx.repo / ".github" / n).exists() for n in ("PULL_REQUEST_TEMPLATE.md", "pull_request_template.md")),
                        "adr_folders": sorted(d for d in ctx.dirs if Path(d).name.lower() in ("adr", "adrs", "decisions", "rfcs"))[:5],
                        "plan_like_docs": sorted(ctx.rel(p) for p in ctx.files if p.suffix.lower() == ".md" and re.search(r"\b(plan|plans|roadmap|todo|backlog|tasklist|tasks)\b", p.name, re.I))[:20]})


def det_git(ctx: Ctx, inv: dict) -> None:
    if not ctx.use_git:
        inv["decisions"] = None
        return
    top = run_git(ctx.repo, ["rev-parse", "--show-toplevel"])
    if top is None or Path(top.strip()).resolve() != ctx.repo.resolve():
        inv["decisions"] = None  # not its own git root (a fixture, say): keep output deterministic
        return
    log = run_git(ctx.repo, ["log", "--format=%h%x09%ad%x09%s", "--date=short", "-n", "300"]) or ""
    commits = [l.split("\t", 2) for l in log.splitlines() if l.count("\t") == 2]
    decisions = [{"sha": c[0], "date": c[1], "subject": redact(c[2])[:140]} for c in commits if DECISION_RE.search(c[2])]
    tags = (run_git(ctx.repo, ["tag", "--sort=-creatordate"]) or "").split()
    remote = run_git(ctx.repo, ["remote", "get-url", "origin"]) or ""
    inv["decisions"] = {"commits_scanned": len(commits), "first": commits[-1][1] if commits else "", "last": commits[0][1] if commits else "",
                        "decision_like": cap(decisions, ctx.cap, "decisions", inv), "tags": [redact(t) for t in tags[:20]], "tag_count": len(tags),
                        "public_host": bool(re.search(r"github\.com|gitlab\.com|bitbucket\.org", remote)), "remote_host": re.sub(r"^.*?([A-Za-z0-9.-]+\.(com|org|io)).*$", r"\1", remote.strip()) if remote.strip() else ""}


def det_surfaces(ctx: Ctx, inv: dict) -> None:
    """Auth, jobs, integrations and the changelog, read from what the other detectors collected.
    Runs last on purpose: it needs every package's dependency list and every env source."""
    deps: dict[str, list[str]] = {}
    manifest_of: dict[str, str] = {}
    for p in inv["packages"]:
        manifest_of.setdefault(p["path"], p["evidence"])
        for d in p.get("dependencies") or []:
            deps.setdefault(d.lower(), []).append(p["path"])
    env_names: dict[str, list[str]] = {}
    for e in inv["env"]:
        for n in e.get("names") or []:
            env_names.setdefault(n, []).append(e["source"])
    inv["env_count"] = len(env_names)

    auth_libs = sorted({d: pk for d, pk in deps.items() if d in AUTH_LIBS}.items())
    middleware = sorted(ctx.rel(p) for p in ctx.code_files if not TEST_FILE.search(p.name)
                        and re.search(r"(^|/)(auth|authn|authz|guard|guards|middleware|session|permissions?|rbac)(\.|/|_)", ctx.rel(p), re.I))[:40]
    roles: list[str] = []
    for t in ((inv.get("schema") or {}).get("tables") or []):
        text = read(ctx.repo / t["evidence"]) if t.get("evidence") else ""
        if text and ROLE_RE.search(text):
            roles.append(t["evidence"])
            if len(roles) >= 5:
                break
    secret_env = sorted(n for n in env_names if re.search(r"_(SECRET|TOKEN|PASSWORD)$", n))
    if auth_libs or middleware or roles or secret_env:
        inv["auth"] = {"libraries": [{"name": d, "packages": sorted(set(pk))} for d, pk in auth_libs][:20],
                       "middleware_files": middleware, "roles_in_schema": sorted(set(roles)),
                       "secret_env_names": secret_env[:40], "evidence": (manifest_of[auth_libs[0][1][0]] if auth_libs else (middleware or roles or [env_names[secret_env[0]][0]])[0])}
    else:
        inv["auth"] = None

    job_libs = sorted({d: pk for d, pk in deps.items() if d in JOB_LIBS}.items())
    cron = [o for o in inv["ops"] if o.get("kind") == "scheduler"]
    workers = sorted(ctx.rel(p) for p in ctx.code_files if not TEST_FILE.search(p.name)
                     and re.search(r"(^|/)(workers?|jobs?|queues?|schedulers?|tasks|consumers?|cron)(\.|/|_)", ctx.rel(p), re.I))[:40]
    scheduled_ci = [c["evidence"] for c in inv["ci"] if "schedule" in (c.get("on") or [])]
    if job_libs or cron or scheduled_ci:
        inv["jobs"] = {"libraries": [{"name": d, "packages": sorted(set(pk))} for d, pk in job_libs][:20],
                       "cron": [c["evidence"] for c in cron][:20], "worker_files": workers, "scheduled_workflows": scheduled_ci[:10],
                       "evidence": (manifest_of[job_libs[0][1][0]] if job_libs else (cron[0]["evidence"] if cron else scheduled_ci[0]))}
    else:
        inv["jobs"] = None

    sdks: dict[str, dict] = {}
    for d, pk in sorted(deps.items()):
        svc = INTEGRATION_LIBS.get(d)
        if svc:
            row = sdks.setdefault(svc, {"service": svc, "packages": [], "units": set()})
            row["packages"].append(d)
            row["units"].update(pk)
    outward = sorted(n for n in env_names if OUTWARD_ENV.search(n))
    if sdks or outward:
        inv["integrations"] = {"sdks": [{"service": r["service"], "packages": sorted(set(r["packages"])), "units": sorted(r["units"])} for r in sdks.values()],
                               "count": len(sdks), "outward_env_names": outward[:60],
                               "evidence": manifest_of[sorted(next(iter(sdks.values()))["units"])[0]] if sdks else env_names[outward[0]][0]}
    else:
        inv["integrations"] = None

    ch = next((p for p in ctx.named("CHANGELOG.md") if p.parent == ctx.repo or p.parent.name.lower() in ("docs", "history")), None)
    tag_count = (inv.get("decisions") or {}).get("tag_count", 0) if isinstance(inv.get("decisions"), dict) else 0
    if ch or tag_count:
        heads = [redact(l.lstrip("# ").strip()) for l in read(ch).splitlines() if l.startswith("## ")][:3] if ch else []
        inv["changelog"] = {"file": ctx.rel(ch) if ch else "", "headings": heads, "tag_count": tag_count,
                            "evidence": ctx.rel(ch) if ch else "(git tags)"}
    else:
        inv["changelog"] = None


DETECTORS = [
    ("node", det_node), ("python", det_python), ("go", det_go), ("rust", det_rust), ("java", det_java),
    ("ruby", det_ruby), ("php", det_php), ("dotnet", det_dotnet), ("elixir", det_elixir), ("move", det_move),
    ("dockerfiles", det_dockerfiles), ("compose", det_compose), ("platforms", det_platforms), ("k8s", det_k8s),
    ("terraform", det_terraform), ("ci", det_ci), ("envfiles", det_envfiles), ("code_reads", det_code_reads),
    ("schema", det_schema), ("routes", det_routes), ("cli_parsers", det_cli_parsers), ("frontend", det_frontend_tokens),
    ("tests", det_tests_folders), ("ops", det_ops_signals), ("readme_tree", det_readme_tree), ("git", det_git),
    ("surfaces", det_surfaces),
]


# ------------------------------------------------------------------ kinds

def derive_kinds(inv: dict, code_files: int) -> list[str]:
    kinds: list[str] = []
    has_code = bool(inv["packages"]) or code_files > 0
    has_services = any(s.get("source") in ("Dockerfile", "compose", "railway", "fly", "render", "vercel", "netlify", "Procfile", "app.yaml", "k8s", "helm") for s in inv["services"])
    has_routes = bool(inv["routes"]) and inv["routes"].get("count", 0) > 0
    has_cli = any(not c.get("hint") for c in inv["cli"])
    has_exports = bool(inv["exports"])
    if inv.get("_infra") and not has_code:
        kinds.append("infrastructure")
    if has_services or has_routes or inv["frontend"]:
        kinds.append("application")
    if has_exports and not has_services:
        kinds.append("library")
    if has_cli and not has_routes and not inv["frontend"]:
        kinds.append("cli")
    if inv.get("_mono") or len({p["path"] for p in inv["packages"]}) > 2:
        kinds.append("monorepo")
    if not has_code and not inv.get("_infra"):
        kinds.append("docs-only")
    return kinds or (["unknown"] if not has_code else ["unclassified"])


def _reset_warnings() -> None:
    """Module state, so a second inventory() in one process does not inherit the first's
    warnings. The fill gate calls inventory() itself, in the same process as the checker."""
    del warnings[:]


def inventory(repo: Path, cap_n: int = 400, use_git: bool = True) -> dict:
    _reset_warnings()
    ctx = Ctx(repo, cap_n, use_git)
    inv: dict = {"packages": [], "services": [], "env": [], "schema": None, "routes": None, "cli": [], "exports": [],
                 "frontend": [], "tests": [], "ci": [], "ops": [], "decisions": None, "readme": None, "tree": {},
                 "release": [], "auth": None, "jobs": None, "integrations": None, "changelog": None, "env_count": 0,
                 "_eco": set(), "_mono": False, "_infra": False}
    for name, fn in DETECTORS:
        try:
            fn(ctx, inv)
        except Exception as exc:  # noqa: BLE001 - one detector must never take the inventory down
            warnings.append(f"detector {name} failed: {type(exc).__name__}: {redact(str(exc))[:120]}")
    inv["packages"] = cap(inv["packages"], cap_n, "packages", inv)
    inv["services"] = cap(inv["services"], cap_n, "services", inv)
    eco = sorted(inv.pop("_eco"))
    kinds = derive_kinds(inv, len(ctx.code_files))
    inv.pop("_mono", None)
    inv.pop("_infra", None)
    out = {"repo": str(repo), "ecosystems": eco, "unknown": not eco, "kinds": kinds,
           "files_scanned": len(ctx.files), "code_files_scanned": len(ctx.code_files)}
    out.update({k: v for k, v in inv.items()})
    out["warnings"] = warnings
    return out


def render(d: dict, top: int = 20) -> str:
    L = ["# Repository evidence", "", f"Repo: {d['repo']}",
         f"Ecosystems: {', '.join(d['ecosystems']) or 'none recognised (unknown)'}   Kinds: {', '.join(d['kinds'])}",
         f"Files scanned: {d['files_scanned']}   code files: {d['code_files_scanned']}", ""]
    L.append(f"Packages ({len(d['packages'])}):")
    for p in d["packages"][:top]:
        L.append(f"  {p['name']}  [{p['language']}, {p['manifest']}]  {p['path']}")
    L.append(f"Services ({len(d['services'])}):")
    for s in d["services"][:top]:
        L.append(f"  {s.get('name')}  via {s.get('source')}  <- {s['evidence']}")
    L.append(f"Env sources ({len(d['env'])}):")
    for e in d["env"][:top]:
        L.append(f"  {e['kind']}  {len(e.get('names', []))} names  <- {e['source']}")
    if d["schema"]:
        L.append(f"Schema: {d['schema']['table_count']} tables, {d['schema']['migrations']['count']} migrations ({', '.join(d['schema']['migrations']['folders'][:3])})")
    if d["routes"]:
        L.append(f"Routes: {d['routes']['count']} ({', '.join(f'{k} {v}' for k, v in d['routes']['by_framework'].items())})")
    for key in ("cli", "exports", "frontend", "tests", "ci", "ops", "release"):
        if d[key]:
            L.append(f"{key}: {len(d[key])} item(s)  e.g. {d[key][0]['evidence']}")
    L.append(f"Env names: {d.get('env_count', 0)} distinct")
    if d.get("auth"):
        L.append(f"Auth: {', '.join(x['name'] for x in d['auth']['libraries']) or 'no library'}; {len(d['auth']['middleware_files'])} middleware file(s)")
    if d.get("jobs"):
        L.append(f"Jobs: {', '.join(x['name'] for x in d['jobs']['libraries']) or 'no library'}; {len(d['jobs']['cron'])} cron signal(s)")
    if d.get("integrations"):
        L.append(f"Integrations: {d['integrations']['count']} ({', '.join(x['service'] for x in d['integrations']['sdks'][:8])}); {len(d['integrations']['outward_env_names'])} outward env name(s)")
    if d.get("changelog"):
        L.append(f"Changelog: {d['changelog']['file'] or 'none'}; {d['changelog']['tag_count']} tags")
    if d["decisions"]:
        L.append(f"Decisions: {len(d['decisions']['decision_like'])} decision-like commits of {d['decisions']['commits_scanned']} ({d['decisions']['first']} .. {d['decisions']['last']}), {d['decisions']['tag_count']} tags")
    elif d["decisions"] is None:
        L.append("Decisions: git history not read")
    if d["tree"]:
        L.append(f"Tree: {', '.join(d['tree'].get('top_level_dirs', [])[:12])}   governance: {', '.join(d['tree'].get('governance_files', []))}")
    if d.get("truncated"):
        L.append(f"Truncated lists: {d['truncated']}")
    for w in d["warnings"]:
        L.append(f"note: {w}")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Inventory a repository as evidence for its docs. Read-only, names only, no values.")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--no-git-root", action="store_true", help="do not expand --repo to its git root")
    ap.add_argument("--no-git", action="store_true", help="skip git history")
    ap.add_argument("--cap", type=int, default=400, help="max items per list (default 400)")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    args = ap.parse_args()
    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        sys.stderr.write(f"error: {repo} is not a directory\n")
        return 2
    if not args.no_git_root:
        top = run_git(repo, ["rev-parse", "--show-toplevel"])
        if top:
            repo = Path(top.strip()).resolve()
    data = inventory(repo, args.cap, not args.no_git)
    if args.format == "json":
        print(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        print(render(data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
