#!/usr/bin/env python3
"""Survey dependency and supply-chain risk. A wrapper around real auditors, not a scanner.

Read-only. Standard library only. Installs nothing. Modifies nothing.

    python dependency_audit.py                       # offline signals only
    python dependency_audit.py --allow-network       # also run auditors that need a registry
    python dependency_audit.py --format json

Two halves, and the split matters.

The offline half always runs and needs no network: missing lockfiles, install
hooks in manifests, non-registry and unpinned version specs, custom registries,
and packages present in a lockfile but absent from the manifest. That is real
supply-chain signal a prose instruction cannot compute.

The online half shells out to whichever auditors are already installed
(npm/pnpm/yarn audit, pip-audit, cargo audit, govulncheck, bundler-audit,
composer audit, dotnet). It is OFF by default. A security skill in a public
collection must not silently contact a package registry, so --allow-network is an
explicit opt-in and the skill is told to ask first. Tools that are absent are
reported as skipped with a reason, never silently ignored.

This never installs, never runs a `fix` subcommand, and never passes a flag that
could rewrite a lockfile. Any value read out of a file -- a dependency spec, a
registry setting -- is redacted before it is reported, because a private
dependency URL routinely carries a credential.

Secret scanning is deliberately out of scope. Use gitleaks or trufflehog, which
do it properly.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TIMEOUT = 120
MAX_READ = 4_000_000

# Manifest -> (ecosystem, expected lockfiles)
ECOSYSTEMS = {
    "package.json": ("javascript", ["package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"]),
    "pyproject.toml": ("python", ["poetry.lock", "uv.lock", "pdm.lock"]),
    "requirements.txt": ("python", ["requirements.lock"]),
    "Pipfile": ("python", ["Pipfile.lock"]),
    "Cargo.toml": ("rust", ["Cargo.lock"]),
    "go.mod": ("go", ["go.sum"]),
    "Gemfile": ("ruby", ["Gemfile.lock"]),
    "composer.json": ("php", ["composer.lock"]),
    "mix.exs": ("elixir", ["mix.lock"]),
}

# Auditors, in preference order per ecosystem. `network` marks the ones that
# need to reach an advisory service; those only run under --allow-network.
AUDITORS = {
    "javascript": [
        ("pnpm", ["pnpm", "audit", "--json"], True),
        ("yarn", ["yarn", "npm", "audit", "--json"], True),
        ("npm", ["npm", "audit", "--json"], True),
    ],
    "python": [("pip-audit", ["pip-audit", "--format", "json"], True)],
    "rust": [("cargo-audit", ["cargo", "audit", "--json"], True)],
    "go": [("govulncheck", ["govulncheck", "-json", "./..."], True)],
    "ruby": [("bundler-audit", ["bundle-audit", "check"], True)],
    "php": [("composer", ["composer", "audit", "--format=json"], True)],
    "elixir": [("mix", ["mix", "deps.audit"], True)],
}

# Manifest content reaches the report, and a dependency spec routinely carries a
# credential: `git+https://user:token@github.com/org/repo.git` is the normal way
# private dependencies are wired. Everything echoed from a file goes through
# redact() first, so the useful shape survives and the credential does not.
CREDENTIAL_IN_URL = re.compile(r"//[^/\s:@]+:[^/\s@]+@")
TOKEN_IN_QUERY = re.compile(
    r"([?&](?:token|access_token|api_key|apikey|key|password|passwd|secret)=)[^&\s]+", re.I)


def redact(value: str, limit: int = 120) -> str:
    """Strip embedded credentials from anything read out of a file before it is reported."""
    if not isinstance(value, str):
        return ""
    v = CREDENTIAL_IN_URL.sub("//<redacted>@", value)
    v = TOKEN_IN_QUERY.sub(lambda m: m.group(1) + "<redacted>", v)
    return v[:limit]


# Which JS package manager the repository actually uses, keyed by its lockfile.
# Choosing by "first installed binary" instead told one real repo to run `pnpm audit`
# when its only lockfile was package-lock.json, which would simply have failed.
JS_LOCK_OWNER = {
    "pnpm-lock.yaml": "pnpm",
    "yarn.lock": "yarn",
    "package-lock.json": "npm",
    "bun.lockb": "bun",
}

INSTALL_HOOKS = ("preinstall", "install", "postinstall", "prepare", "prepublish")
NON_REGISTRY = re.compile(r"^(file:|link:|git\+|git:|https?:|github:|portal:)")
UNPINNED = re.compile(r"^(\*|latest|x|X)$")

# Noise directories to skip when git is unavailable and we walk the tree ourselves.
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "venv", ".venv", "dist", "build", "target",
    "__pycache__", ".next", "coverage", ".terraform",
}
warnings: list[str] = []


def run(cmd: list[str], cwd: Path) -> tuple[int, str, str]:
    exe = shutil.which(cmd[0])
    if exe is None:
        return (127, "", f"{cmd[0]} not found on PATH")
    try:
        p = subprocess.run(
            [exe, *cmd[1:]], cwd=str(cwd), text=True, timeout=TIMEOUT,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
        )
        return (p.returncode, p.stdout, p.stderr)
    except subprocess.TimeoutExpired:
        return (124, "", f"{cmd[0]} timed out after {TIMEOUT}s")
    except OSError as exc:
        return (1, "", str(exc))


def read(path: Path) -> str:
    try:
        if path.stat().st_size > MAX_READ:
            return ""
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def fully_pinned(text: str, manifest_name: str) -> bool:
    """True when every direct dependency in this manifest names an exact version.

    Only answers for the manifest formats where "exact" is unambiguous. A
    package.json range like ^4.17.21 is not a pin, so JS always returns False and
    keeps the stronger wording.
    """
    if manifest_name != "requirements.txt" or not text:
        return False
    entries = 0
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith(("#", "-r ", "--")):
            continue
        if NON_REGISTRY.match(s) or s.startswith("-e "):
            return False
        entries += 1
        # `==` is the only exact pin. ~=, >=, and a bare name are all ranges.
        if "==" not in s.split(";")[0]:
            return False
    return entries > 0


def list_files(repo: Path) -> list[str]:
    code, out, _ = run(["git", "ls-files", "--cached", "--other", "--exclude-standard"], repo)
    if code == 0 and out.strip():
        return sorted(x.strip() for x in out.splitlines() if x.strip())
    warnings.append("git unavailable or empty index; scanning the filesystem instead")
    files = []
    for p in repo.rglob("*"):
        if p.is_file() and not any(part in SKIP_DIRS for part in p.parts):
            files.append(p.relative_to(repo).as_posix())
    return sorted(files)


def offline_signals(repo: Path, files: list[str]) -> list[dict]:
    """Everything computable without a network. This is the half that always runs."""
    signals: list[dict] = []

    def add(kind: str, severity: str, path: str, detail: str, line: int | None = None) -> None:
        signals.append({"kind": kind, "severity": severity, "path": path,
                        "line": line, "detail": detail})

    manifests = [f for f in files if Path(f).name in ECOSYSTEMS]
    for rel in manifests:
        name = Path(rel).name
        ecosystem, locks = ECOSYSTEMS[name]
        directory = Path(rel).parent

        # Missing lockfile. Severity depends on whether the manifest already pins.
        # Calling a fully `==`-pinned requirements.txt "not reproducible" reads as
        # plainly wrong to the owner and costs the whole report credibility.
        if locks and not any((repo / directory / lock).is_file() for lock in locks):
            pinned = fully_pinned(read(repo / rel), name)
            if pinned:
                add("missing-lockfile", "low", rel,
                    f"{ecosystem}: no lockfile beside this manifest, but every direct "
                    "dependency is pinned to an exact version. Direct versions are therefore "
                    "reproducible; what is missing is hash pinning and pinned transitive "
                    "dependencies, so a compromised transitive release could still be picked up.")
            else:
                add("missing-lockfile", "medium", rel,
                    f"{ecosystem}: no lockfile beside this manifest (looked for {', '.join(locks)}), "
                    "and the manifest does not pin exact versions. Installs are not reproducible.")

        text = read(repo / rel)
        if not text:
            continue

        if name == "package.json":
            try:
                data = json.loads(text)
            except ValueError as exc:
                add("unparseable-manifest", "low", rel, f"could not parse: {redact(str(exc))}")
                continue
            scripts = data.get("scripts") or {}
            for hook in INSTALL_HOOKS:
                if hook in scripts:
                    # Deliberately does not echo the command body: an install hook can
                    # carry an inline credential, and this skill must never print one.
                    # The hook name plus the manifest path is enough to go look.
                    body = scripts[hook] if isinstance(scripts[hook], str) else ""
                    add("install-hook", "high", rel,
                        f"`{hook}` runs automatically on install ({len(body)} chars, not shown here). "
                        "Install hooks are the usual supply-chain execution path. "
                        f"Read the `{hook}` script in this manifest before trusting the package.")
            for field in ("dependencies", "devDependencies", "optionalDependencies"):
                for pkg, spec in (data.get(field) or {}).items():
                    if not isinstance(spec, str):
                        continue
                    if NON_REGISTRY.match(spec):
                        add("non-registry-dependency", "medium", rel,
                            f"{field}: `{pkg}` resolves from outside the registry ({redact(spec)}). "
                            "Not covered by registry advisories.")
                    elif UNPINNED.match(spec.strip()):
                        add("unpinned-dependency", "medium", rel,
                            f"{field}: `{pkg}` is `{redact(spec)}` -- any published version is accepted.")

            # A package in the lockfile but not the manifest tree is worth a look.
            lock = repo / directory / "package-lock.json"
            if lock.is_file():
                try:
                    ldata = json.loads(read(lock))
                    direct = set()
                    for field in ("dependencies", "devDependencies", "optionalDependencies"):
                        direct |= set((data.get(field) or {}).keys())
                    root = (ldata.get("packages") or {}).get("", {})
                    lock_direct = set()
                    for field in ("dependencies", "devDependencies", "optionalDependencies"):
                        lock_direct |= set((root.get(field) or {}).keys())
                    for pkg in sorted(lock_direct - direct):
                        add("lockfile-only-dependency", "medium",
                            (directory / "package-lock.json").as_posix(),
                            f"`{pkg}` is a direct dependency in the lockfile but not in package.json.")
                except ValueError:
                    pass

        elif name in ("requirements.txt", "Pipfile"):
            for i, line in enumerate(text.splitlines(), start=1):
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if NON_REGISTRY.match(s) or s.startswith("-e "):
                    add("non-registry-dependency", "medium", rel,
                        f"installs from outside PyPI: {redact(s)}", line=i)
                elif re.match(r"^[A-Za-z0-9._-]+$", s):
                    add("unpinned-dependency", "medium", rel,
                        f"`{s}` has no version constraint.", line=i)

    # Custom registries redirect where packages come from.
    for rel in files:
        base = Path(rel).name
        if base in (".npmrc", "pip.conf", ".pypirc", "Cargo.toml") or base == "pip.ini":
            text = read(repo / rel)
            for i, line in enumerate(text.splitlines(), start=1):
                m = re.match(r"\s*([A-Za-z0-9_-]*(?:registry|index-url|extra-index-url|replace-with))\s*=",
                             line, re.I)
                if m:
                    # Files like .npmrc hold auth tokens beside registry settings, so
                    # nothing read out of them is echoed. Only the matched setting NAME
                    # is reported, taken from a fixed alternation above rather than from
                    # the line, and never the remainder after the `=`.
                    setting = m.group(1).lower()
                    add("custom-registry", "medium", rel,
                        f"a `{setting}` setting redirects package resolution away from the default "
                        "registry. Value not shown; open the file to review it.",
                        line=i)

    for rel in files:
        if Path(rel).name.startswith(".env") and Path(rel).name != ".env.example":
            add("env-file-tracked", "high", rel,
                "an environment file appears in the file list; confirm it is not committed with real values. "
                "Contents were not read.")
    return signals


def run_auditors(repo: Path, files: list[str], allow_network: bool) -> list[dict]:
    present = {ECOSYSTEMS[Path(f).name][0] for f in files if Path(f).name in ECOSYSTEMS}
    results: list[dict] = []
    for ecosystem in sorted(present):
        candidates = AUDITORS.get(ecosystem, [])
        if not candidates:
            results.append({"ecosystem": ecosystem, "tool": None, "command": None, "ran": False,
                            "reason_skipped": "no known auditor for this ecosystem",
                            "findings": [], "raw_excerpt": None})
            continue

        # Prefer the manager the repository's own lockfile names. Only fall back to
        # "whatever is installed" when no lockfile identifies one, and say so.
        preferred = None
        lock_note = ""
        if ecosystem == "javascript":
            owners = {JS_LOCK_OWNER[Path(f).name] for f in files if Path(f).name in JS_LOCK_OWNER}
            if len(owners) == 1:
                preferred = owners.pop()
            elif len(owners) > 1:
                lock_note = (f" This repository has lockfiles for several managers "
                             f"({', '.join(sorted(owners))}); pick one deliberately.")
            else:
                lock_note = " No JS lockfile identifies a package manager, so this is a guess."

        ordered = candidates
        if preferred:
            ordered = ([c for c in candidates if c[0] == preferred]
                       + [c for c in candidates if c[0] != preferred])

        # Report the one auditor we would actually use, not every candidate. Listing
        # three skip reasons for one ecosystem obscures which tool is in play.
        chosen = next(((t, c, n) for t, c, n in ordered if shutil.which(c[0])), None)
        if preferred and chosen and chosen[0] != preferred:
            known = {t for t, _, _ in candidates}
            if preferred not in known:
                # e.g. a bun.lockb: we can identify the manager but have no auditor for it.
                lock_note = (f" The lockfile indicates {preferred}, which has no supported auditor here, "
                             f"so {chosen[0]} was used instead; its result may not match your install.")
            else:
                lock_note = (f" The lockfile indicates {preferred}, but {preferred} is not installed, "
                             f"so {chosen[0]} was used instead; its result may not match your install.")
        if chosen is None:
            names = ", ".join(c[0] for _, c, _ in candidates)
            results.append({"ecosystem": ecosystem, "tool": None, "command": None, "ran": False,
                            "reason_skipped": f"none of its auditors are installed ({names})",
                            "findings": [], "raw_excerpt": None})
            continue

        tool, cmd, needs_network = chosen
        entry = {"ecosystem": ecosystem, "tool": tool, "command": " ".join(cmd),
                 "ran": False, "reason_skipped": None, "findings": [], "raw_excerpt": None}
        if needs_network and not allow_network:
            entry["reason_skipped"] = ("needs network access; rerun with --allow-network to permit it"
                                       + lock_note)
            results.append(entry)
            continue
        code, out, err = run(cmd, repo)
        entry["ran"] = True
        entry["exit_code"] = code
        entry["findings"] = parse_findings(tool, out)
        if not entry["findings"]:
            excerpt = (out or err).strip()
            entry["raw_excerpt"] = excerpt[:600] or None
        results.append(entry)
    return results


def parse_findings(tool: str, out: str) -> list[dict]:
    """Normalise each auditor's very different JSON into one shape."""
    findings: list[dict] = []
    if not out.strip():
        return findings
    try:
        data = json.loads(out)
    except ValueError:
        # govulncheck streams one JSON object per line.
        for line in out.splitlines():
            try:
                obj = json.loads(line)
            except ValueError:
                continue
            osv = obj.get("osv") or {}
            if osv.get("id"):
                findings.append({"package": (osv.get("affected") or [{}])[0]
                                 .get("package", {}).get("name", "unknown"),
                                 "installed": None, "severity": "unknown",
                                 "advisory_id": osv.get("id"),
                                 "title": (osv.get("summary") or "")[:200], "fixed_in": None})
        return findings

    if tool in ("npm", "pnpm", "yarn"):
        for name, v in (data.get("vulnerabilities") or {}).items():
            if not isinstance(v, dict):
                continue
            via = v.get("via") or []
            title = next((x.get("title") for x in via if isinstance(x, dict) and x.get("title")), "")
            advisory = next((x.get("url") or x.get("source") for x in via if isinstance(x, dict)), None)
            findings.append({"package": name, "installed": v.get("range"),
                             "severity": v.get("severity", "unknown"),
                             "advisory_id": str(advisory) if advisory else None,
                             "title": str(title)[:200],
                             "fixed_in": (v.get("fixAvailable") or {}).get("version")
                                         if isinstance(v.get("fixAvailable"), dict) else None})
    elif tool == "pip-audit":
        for dep in (data if isinstance(data, list) else data.get("dependencies") or []):
            for vuln in dep.get("vulns") or []:
                findings.append({"package": dep.get("name"), "installed": dep.get("version"),
                                 "severity": "unknown", "advisory_id": vuln.get("id"),
                                 "title": (vuln.get("description") or "")[:200],
                                 "fixed_in": ", ".join(vuln.get("fix_versions") or []) or None})
    elif tool == "cargo-audit":
        for v in ((data.get("vulnerabilities") or {}).get("list") or []):
            adv = v.get("advisory") or {}
            findings.append({"package": (v.get("package") or {}).get("name"),
                             "installed": (v.get("package") or {}).get("version"),
                             "severity": adv.get("severity", "unknown"),
                             "advisory_id": adv.get("id"), "title": (adv.get("title") or "")[:200],
                             "fixed_in": ", ".join((v.get("versions") or {}).get("patched") or []) or None})
    elif tool == "composer":
        for pkg, entries in (data.get("advisories") or {}).items():
            for adv in entries if isinstance(entries, list) else [entries]:
                findings.append({"package": pkg, "installed": None,
                                 "severity": adv.get("severity", "unknown"),
                                 "advisory_id": adv.get("advisoryId") or adv.get("cve"),
                                 "title": (adv.get("title") or "")[:200], "fixed_in": None})
    return findings


def render(d: dict, top: int) -> str:
    L = ["# Dependency And Supply-Chain Survey", "", f"Repo: {d['repo']}",
         f"Ecosystems detected: {', '.join(d['ecosystems']) or 'none'}", ""]

    L.append("## Offline signals")
    sig = d["offline_signals"]
    if sig:
        order = {"high": 0, "medium": 1, "low": 2}
        shown = sorted(sig, key=lambda s: order.get(s["severity"], 3))[:top]
        if len(sig) > top:
            L.append(f"  TRUNCATED: showing {top} of {len(sig)} signals")
        for s in shown:
            loc = f"{s['path']}:{s['line']}" if s.get("line") else s["path"]
            L.append(f"- [{s['severity']}] {s['kind']} -- {loc}")
            L.append(f"  {s['detail']}")
    else:
        L.append("- none found")
    L.append("")

    L.append("## Auditors")
    if not d["auditors"]:
        L.append("- no ecosystem with a known auditor was detected")
    for a in d["auditors"]:
        label = f"{a['ecosystem']}/{a['tool']}" if a.get("tool") else a["ecosystem"]
        if not a["ran"]:
            L.append(f"- {label}: SKIPPED -- {a['reason_skipped']}")
            continue
        L.append(f"- {a['ecosystem']}/{a['tool']}: ran (`{a['command']}`), "
                 f"{len(a['findings'])} finding(s)")
        for f in a["findings"][:top]:
            fixed = f", fixed in {f['fixed_in']}" if f.get("fixed_in") else ""
            L.append(f"    [{f['severity']}] {f['package']} {f.get('installed') or ''} "
                     f"-- {f.get('advisory_id') or 'no id'}: {f.get('title') or ''}{fixed}")
        if len(a["findings"]) > top:
            L.append(f"    TRUNCATED: showing {top} of {len(a['findings'])}")
        if a.get("raw_excerpt"):
            L.append(f"    tool output: {a['raw_excerpt'].splitlines()[0][:200]}")
    L.append("")

    if d["warnings"]:
        L.append("## Warnings")
        L.extend(f"- {w}" for w in d["warnings"])
        L.append("")

    if not d["network_allowed"]:
        L.append("Network auditors were not run. Absence of advisory findings here is NOT")
        L.append("evidence that dependencies are free of known vulnerabilities.")
    L.append("Survey only. Confirm anything you intend to report as a finding.")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="Survey dependency and supply-chain risk. Read-only.")
    ap.add_argument("--repo", default=".", help="Path inside the repository.")
    ap.add_argument("--format", choices=["text", "json"], default="text", help="Output format.")
    ap.add_argument("--top", type=int, default=25, help="Rows per section. Default 25.")
    ap.add_argument("--allow-network", action="store_true",
                    help="Permit auditors that contact a package registry or advisory service. Off by default.")
    ap.add_argument("--no-git-root", action="store_true",
                    help="Treat --repo literally instead of expanding to the enclosing git repository root.")
    args = ap.parse_args()

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        print(f"error: not a directory: {repo}", file=sys.stderr)
        return 2
    if not args.no_git_root:
        code, out, _ = run(["git", "rev-parse", "--show-toplevel"], repo)
        if code == 0 and out.strip():
            repo = Path(out.strip()).resolve()

    files = list_files(repo)
    if not files:
        print(f"error: no files found under {repo}", file=sys.stderr)
        return 2

    ecosystems = sorted({ECOSYSTEMS[Path(f).name][0] for f in files if Path(f).name in ECOSYSTEMS})
    data = {
        "repo": str(repo),
        "ecosystems": ecosystems,
        "network_allowed": args.allow_network,
        "offline_signals": offline_signals(repo, files),
        "auditors": run_auditors(repo, files, args.allow_network),
        "warnings": warnings,
    }
    print(json.dumps(data, indent=2) if args.format == "json" else render(data, args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
