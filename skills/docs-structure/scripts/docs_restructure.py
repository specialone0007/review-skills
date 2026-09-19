#!/usr/bin/env python3
"""Fit existing docs into the shape's sections without losing a line.

Read-only. Standard library only. Writes nothing into the repository.

    python docs_restructure.py --repo . --format json
    python docs_restructure.py --repo . --out <scratch>      # materialise outside the repo

For every doc that covers a concern (at its canonical path, or about to be moved there) and for
the README, this reads the doc's sections and the concern's template, and proposes the doc in the
template's order: each existing section lands under the template section its heading matches,
its text verbatim and only the heading renamed; a template section nothing matches keeps its
italic guidance line; an existing section that matches nothing is kept after the template ones,
in its original order, untouched. When two template sections match equally the first in
template order wins and the mapping is marked `ambiguous` for a person to confirm.

The README also gives away what other docs own: a README section whose heading matches a
concern another doc covers (an env table, deploy steps) is cut, pasted into that doc's matching
section, and replaced by one line and a link. That is R11's second-home warning, performed.

Proof, before anything is written: every non-heading, non-blank line of every input appears
exactly as often across the outputs (the only lines added are the pointer lines, the owner
lines and the template guidance, each counted), every original heading survives as a heading or
is recorded as renamed, and every relative link still resolves. Any failure: nothing is written.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docs_structure as ds  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

AUTO_MARK = "*(auto, review me)*"
# Words a template heading also answers to. The template heading's own words always count.
SYNONYMS: dict[str, set[str]] = {
    "what it is": {"about", "overview", "introduction", "description", "purpose", "summary"},
    "quickstart": {"quick start", "getting started", "setup", "install", "installation", "usage", "running", "run"},
    "repository layout": {"structure", "layout", "folders", "project structure", "directory", "tree", "monorepo"},
    "commands": {"scripts", "usage", "cli", "make", "npm scripts", "tasks"},
    "configuration": {"config", "environment", "env", "variables", "settings"},
    "status": {"license", "licence", "version", "badges", "ci"},
    "prerequisites": {"requirements", "before you start", "you need", "dependencies"},
    "install": {"installation", "setup", "getting started", "clone"},
    "run it": {"run", "running", "start", "usage", "development server", "dev server"},
    "first success": {"verify", "check", "smoke test", "hello"},
    "if it fails": {"troubleshooting", "problems", "common problems", "faq", "gotchas"},
    "daily loop": {"workflow", "development", "developing", "commands", "scripts"},
    "branch and pr": {"branching", "branches", "pull requests", "commits", "git"},
    "run and debug": {"debugging", "logs", "running locally", "local"},
    "lint and format": {"lint", "linting", "formatting", "style", "prettier", "eslint"},
    "common problems": {"troubleshooting", "faq", "known issues", "gotchas"},
    "units": {"services", "service", "apps", "components", "deployables"},
    "environment per unit": {"environment", "environment variables", "env", "variables", "secrets", "configuration"},
    "deploy steps": {"deploy", "deploying", "deployment", "release", "steps", "how to deploy", "railway", "production"},
    "rollback": {"rolling back", "revert", "recovery"},
    "known traps": {"gotchas", "pitfalls", "troubleshooting", "notes"},
    "health": {"health checks", "healthcheck", "monitoring", "status"},
    "scheduled jobs": {"cron", "jobs", "schedules", "workers"},
    "alerts": {"alerting", "monitoring", "notifications"},
    "when something is wrong": {"troubleshooting", "incidents", "runbook", "failures", "recovery"},
    "on call": {"on-call", "oncall", "escalation", "contacts"},
    "runners and layout": {"runners", "layout", "structure", "test files", "frameworks"},
    "running tests": {"run", "running", "commands", "how to run"},
    "what ci runs": {"ci", "continuous integration", "pipeline", "github actions", "workflows"},
    "coverage and gaps": {"coverage", "gaps", "todo", "missing"},
    "before you start": {"prerequisites", "license", "code of conduct", "getting started"},
    "making a change": {"workflow", "branching", "commits", "pull requests", "process"},
    "checks that must pass": {"ci", "checks", "lint", "tests", "validation"},
    "review": {"code review", "reviewers", "merging", "approval"},
    "context": {"overview", "system context", "background", "scope"},
    "containers": {"services", "components", "packages", "apps", "in one diagram", "diagram"},
    "building blocks": {"modules", "components", "structure", "layers", "folders"},
    "runtime": {"data flow", "flow", "request lifecycle", "sequence", "how it works"},
    "deployment view": {"deployment", "infrastructure", "hosting", "environments"},
    "quality and risks": {"risks", "open questions", "tradeoffs", "trade-offs", "decisions", "key decisions", "non-functional"},
    "variables by unit": {"environment variables", "variables", "env", "settings", "environment"},
    "files": {"config files", "configuration files"},
    "flags": {"feature flags", "toggles", "options"},
    "tables by area": {"tables", "models", "entities", "schema", "collections"},
    "relationships": {"relations", "foreign keys", "erd", "associations"},
    "conventions": {"naming", "rules", "migrations"},
    "inventory": {"counts", "summary"},
    "authentication": {"auth", "login", "sessions", "tokens", "jwt"},
    "endpoints": {"routes", "api", "resources", "paths"},
    "errors": {"error handling", "error codes", "status codes"},
    "typical end-to-end call": {"example", "examples", "walkthrough", "flow"},
    "notes": {"limits", "rate limits", "pagination", "versioning"},
    "authorisation and roles": {"authorization", "roles", "permissions", "rbac", "access control"},
    "secrets handling": {"secrets", "keys", "credentials", "env"},
    "data classes": {"pii", "personal data", "sensitive data", "privacy"},
    "known gaps": {"todo", "risks", "open questions", "gaps"},
    "foundations": {"tokens", "colors", "colours", "typography", "spacing", "theme"},
    "components - reuse, do not rebuild": {"components", "primitives", "ui"},
    "patterns": {"layouts", "pages", "states"},
    "do and do not": {"rules", "guidelines", "dos and donts"},
    "pre-flight checklist": {"checklist", "before merging"},
    "what it is becoming": {"vision", "what it is", "overview", "about", "mission"},
    "who it is for": {"users", "audience", "personas", "customers"},
    "core concept": {"concept", "concepts", "model", "how it works"},
    "how success is measured": {"metrics", "kpis", "success", "goals"},
    "principles": {"values", "philosophy", "rules"},
    "what we said no to": {"non-goals", "out of scope", "not doing", "decisions"},
    "what it does": {"overview", "about", "features", "introduction"},
    "who uses it, and how": {"users", "usage", "use cases", "audience"},
    "concepts": {"terminology", "glossary", "model"},
    "non-goals": {"out of scope", "limitations", "what it is not"},
    "roadmap and principles": {"roadmap", "principles", "future", "plans"},
    "jobs": {"workers", "tasks", "background jobs"},
    "queues": {"queue", "topics", "brokers"},
    "schedules": {"cron", "scheduled", "timers"},
    "data flows": {"flow", "pipeline", "processing"},
    "failure and retry": {"retries", "errors", "dead letter", "failures"},
    "integrations": {"third parties", "third-party", "external services", "providers", "vendors"},
    "not integrated": {"excluded", "not used"},
    "read in this order": {"reading order", "start here", "where to start"},
    "by role": {"roles", "for developers", "for operators", "teams"},
    "glossary": {"terminology", "terms", "vocabulary", "definitions"},
    "install and invoke": {"installation", "install", "usage", "invoke"},
    "exit codes and output": {"exit codes", "output", "return codes"},
    "install and import": {"installation", "import", "usage"},
    "exported surface": {"api", "exports", "functions", "classes"},
    "stability and versioning": {"versioning", "stability", "semver", "compatibility"},
    "versioning": {"version", "semver", "tags"},
    "release steps": {"releasing", "publish", "publishing", "how to release"},
    "what a release contains": {"artifacts", "changelog", "contents"},
    "rolling back a release": {"rollback", "unpublish", "yank"},
}

PART_OF = re.compile(r"^\s*>\s*(?:\*\*)?Part of(?:\*\*)?\s*\[", re.M)


def fence_mask(lines: list[str]) -> list[bool]:
    out, fence = [], None
    for line in lines:
        m = ds.FENCE_RE.match(line)
        if fence is None and m:
            fence = m.group(1); out.append(True); continue
        if fence is not None:
            if m and m.group(1)[0] == fence[0] and len(m.group(1)) >= len(fence):
                fence = None
            out.append(True); continue
        out.append(False)
    return out


def sections_of(lines: list[str]) -> tuple[list[str], list[dict]]:
    """The lead (everything before the first H2) and one dict per H2 block: heading, level, body
    lines (H3s and deeper stay inside their H2). Headings inside fences are text."""
    mask = fence_mask(lines)
    lead: list[str] = []
    secs: list[dict] = []
    cur = None
    for i, line in enumerate(lines):
        m = None if mask[i] else ds.HEADING_RE.match(line)
        if m and len(m.group(1)) == 2:
            cur = {"heading": m.group(2).strip(), "line": i, "body": []}
            secs.append(cur)
            continue
        if cur is None:
            lead.append(line)
        else:
            cur["body"].append(line)
    return lead, secs


def words(text: str) -> set[str]:
    return {w for w in ds.tokens(text).split() if len(w) > 2 and w not in ("the", "and", "for", "with", "how", "what")}


def match_score(existing: str, template_h2: str) -> int:
    """How well an existing heading fits a template section: its own words, then the synonyms."""
    ew = words(existing)
    tw = words(template_h2)
    score = 3 * len(ew & tw)
    key = template_h2.strip().lower()
    for syn in SYNONYMS.get(key, set()):
        st = ds.tokens(syn).strip()
        if f" {st} " in ds.tokens(existing):
            score += 2
    if ds.tokens(existing).strip() == ds.tokens(template_h2).strip():
        score += 10
    return score


def best_template_section(existing: str, tsecs: list[tuple[str, str]]) -> tuple[str | None, bool]:
    scored = [(match_score(existing, h), h) for h, _ in tsecs]
    scored_sorted = sorted(scored, key=lambda x: -x[0])
    if not scored_sorted or scored_sorted[0][0] <= 0:
        return None, False
    top = scored_sorted[0][0]
    ties = [h for s, h in scored if s == top]
    # ties resolve in template order; the caller marks the mapping ambiguous
    winner = next(h for h, _ in tsecs if h in ties)
    return winner, len(ties) > 1


def strip_owner(lines: list[str]) -> tuple[list[str], str | None]:
    """The lead without its owner line and its trailing marker line; the owner line if any."""
    out, owner = [], None
    for l in lines:
        if owner is None and ds.owner_marker_hit(l, ["This document owns:", "Part of"]):
            owner = l
            continue
        out.append(l)
    return out, owner


def restructure_doc(doc_lines: list[str], template: Path, concern: str, extra_in: dict[str, list[list[str]]] | None = None,
                    give_away: dict[str, tuple[str, str]] | None = None) -> dict:
    """One doc into the template's order.

    extra_in: {template section: [lines, ...]} bodies pasted here from other docs (a README's env table).
    give_away: {existing heading: (target doc rel, pointer line)} sections cut out of this doc.
    """
    tsecs = ds.template_sections(template)
    tlines = ds.read(template).splitlines()
    # a Start-here block between the markers is the skill's own and moves whole, into the slot the
    # template keeps for it (after the section that precedes the placeholder in the template)
    block: list[str] = []
    if ds.START_HERE_OPEN in doc_lines and ds.START_HERE_CLOSE in doc_lines:
        i0, i1 = doc_lines.index(ds.START_HERE_OPEN), doc_lines.index(ds.START_HERE_CLOSE)
        if i0 < i1:
            block = doc_lines[i0:i1 + 1]
            doc_lines = doc_lines[:i0] + doc_lines[i1 + 1:]
    slot_after = None
    if ds.START_HERE_OPEN in tlines:
        j = tlines.index(ds.START_HERE_OPEN)
        prev = [ds.HEADING_RE.match(l).group(2).strip() for l in tlines[:j] if ds.HEADING_RE.match(l) and len(ds.HEADING_RE.match(l).group(1)) == 2]
        slot_after = prev[-1] if prev else ""
    lead, secs = sections_of(doc_lines)
    h1 = next((l for l in lead if ds.HEADING_RE.match(l) and len(ds.HEADING_RE.match(l).group(1)) == 1), None)
    lead_wo_h1 = [l for l in lead if l is not h1]
    lead_body, owner = strip_owner(lead_wo_h1)
    # the template's own lead lines that are not the H1/owner: the read-this-if line and the concern comment
    t_lead, _ = sections_of(tlines)
    t_owner = next((l for l in t_lead if "This document owns:" in l), "")
    t_comment = next((l for l in t_lead if l.strip().startswith("<!-- concern:")), "")
    mapping: list[dict] = []
    placed: dict[str, list[dict]] = {}
    kept: list[dict] = []
    given: list[dict] = []
    for s_ in secs:
        if give_away and s_["heading"] in give_away:
            target, pointer = give_away[s_["heading"]]
            given.append({"heading": s_["heading"], "to": target})
            kept.append({"heading": s_["heading"], "body": ["", pointer, ""], "pointer": True})
            continue
        h, amb = best_template_section(s_["heading"], tsecs)
        if h is None:
            kept.append(s_)
            continue
        placed.setdefault(h, []).append(s_)
        mapping.append({"from": s_["heading"], "to": h, "ambiguous": amb})
    out: list[str] = []
    title = h1 or (tlines[0] if tlines and tlines[0].startswith("# ") else f"# {Path(template).stem.replace('_', ' ').title()}")
    out.append(title)
    out.append("")
    if owner:
        own = owner.rstrip()
        if "(auto, review me)" not in own and "(draft, review me)" not in own and "(skeleton" not in own:
            own = own + " " + AUTO_MARK
        out.append(own)
    else:
        out.append((t_owner.replace("*(skeleton, write me)*", AUTO_MARK).rstrip()) if t_owner else f"> **This document owns:** {title.lstrip('# ').strip()} {AUTO_MARK}")
    out.append("")
    body_lead = [l for l in lead_body if not l.strip().startswith("<!-- concern:")]
    while body_lead and not body_lead[0].strip():
        body_lead.pop(0)
    while body_lead and not body_lead[-1].strip():
        body_lead.pop()
    if t_comment:
        out.append(t_comment)
        out.append("")
    if body_lead:
        out.extend(body_lead)
        out.append("")
    added_lines = [out[2]] + ([t_comment] if t_comment else [])
    if block and slot_after == "":
        out.extend(block)
        out.append("")
    for h, guide in tsecs:
        out.append(f"## {h}")
        out.append("")
        got = placed.get(h, [])
        extra = (extra_in or {}).get(h, [])
        if not got and not extra:
            out.append(guide)
            out.append("")
            added_lines.append(guide)
            if block and slot_after == h:
                out.extend(block)
                out.append("")
            continue
        if len(got) == 1 and not extra:
            body = got[0]["body"]
        else:
            body = []
            for s_ in got:
                body.append(f"### {s_['heading']}")
                body.extend(s_["body"])
                if body and body[-1].strip():
                    body.append("")
            for lines_ in extra:
                body.extend(lines_)
                if body and body[-1].strip():
                    body.append("")
        while body and not body[0].strip():
            body = body[1:]
        while body and not body[-1].strip():
            body = body[:-1]
        out.extend(body)
        out.append("")
        if block and slot_after == h:
            out.extend(block)
            out.append("")
    if block and slot_after is None:
        out.extend(block)
        out.append("")
    for s_ in kept:
        out.append(f"## {s_['heading']}")
        body = list(s_["body"])
        while body and not body[0].strip():
            body = body[1:]
        while body and not body[-1].strip():
            body = body[:-1]
        out.append("")
        out.extend(body)
        out.append("")
        if s_.get("pointer"):
            added_lines.append(s_["body"][1])
    while out and not out[-1].strip():
        out.pop()
    return {"lines": out, "mapping": mapping, "kept": [s_["heading"] for s_ in kept if not s_.get("pointer")],
            "given": given, "added": added_lines, "concern": concern, "template": ds.posix(template, ds.TEMPLATES) if template.is_relative_to(ds.TEMPLATES) else template.name}


def content_lines(lines: list[str]) -> Counter:
    """Every line that carries a person's text: not blank, not a heading, not the owner line or the
    concern comment (both are the shape's, replaced on purpose), not the pointer or guidance the
    restructure adds."""
    mask = fence_mask(lines)
    c: Counter = Counter()
    for i, l in enumerate(lines):
        if not l.strip():
            continue
        if not mask[i] and (ds.HEADING_RE.match(l) or ds.owner_marker_hit(l, ["This document owns:", "Part of"])
                            or l.strip().startswith("<!-- concern:")):
            continue
        c[re.sub(r"\]\([^)]*\)", "](#)", l.rstrip())] += 1
    return c


def headings_in(lines: list[str]) -> Counter:
    mask = fence_mask(lines)
    return Counter(ds.HEADING_RE.match(l).group(2).strip() for i, l in enumerate(lines) if not mask[i] and ds.HEADING_RE.match(l))


def propose(repo: Path, manifest: dict, mpath: Path | None, source: str) -> dict:
    data = ds.build(repo, manifest, mpath, source, False)
    coverage = data.get("concerns") or []
    init = data.get("init") or {}
    moves = {m["from"]: m["to"] for m in init.get("moves", [])}
    front_rel = manifest.get("frontDoor") or "README.md"
    out: dict = {"repo": str(repo), "docs": {}, "files": {}, "delete": [], "proof": None, "refuse": None, "newline": {}}
    # which doc, at which output path, for which concern; a moved doc is read from its old path
    targets: list[tuple[str, str, dict]] = []  # (source rel, output rel, coverage row)
    seen: set[str] = set()
    for c in coverage:
        src = c.get("covered_by") or c.get("misplaced")
        if not src or c["concern"] == "agent" or src in seen or not (repo / src).is_file():
            continue
        if c["concern"] == "readme" and src != front_rel:
            continue
        seen.add(src)
        targets.append((src, c["default_path"] if c.get("misplaced") else src, c))
    moved = {src: dst for src, dst, c in targets if src != dst}

    prerebased: set[str] = set()

    def rewrite(lines: list[str], old_dir: Path, new_dir: Path, skip: set[str] | None = None) -> list[str]:
        mask = fence_mask(lines)
        res = []
        for i, l in enumerate(lines):
            if mask[i] or "](" not in l or (skip and l in skip):
                res.append(l)
                continue

            def sub(m: re.Match) -> str:
                target = (m.group(2) or m.group(3) or "").strip()
                fp, _, anchor = target.partition("#")
                if not fp or fp.startswith(("http://", "https://", "mailto:", "/")):
                    return m.group(0)
                absr = (old_dir / fp).resolve()
                try:
                    r = ds.posix(absr, repo)
                except ValueError:
                    return m.group(0)
                dest = repo / moved.get(r, r)
                new = os.path.relpath(dest, new_dir.resolve()).replace("\\", "/") + (("#" + anchor) if anchor else "")
                if new == target:
                    return m.group(0)
                g = 2 if m.group(2) else 3
                off = m.start()
                return m.group(0)[:m.start(g) - off] + new + m.group(0)[m.end(g) - off:]
            res.append(ds.LINK_RE.sub(sub, l))
        return res

    # the README gives sections away to the docs that own them
    readme_row = next((c for c in coverage if c["concern"] == "readme" and c.get("covered_by")), None)
    give_away: dict[str, tuple[str, str]] = {}
    extra_for: dict[str, dict[str, list[list[str]]]] = {}
    readme_template = ds.template_for("README.md")
    if readme_row and readme_template:
        rlines = ds.read(repo / front_rel).splitlines()
        _, rsecs = sections_of(rlines)
        readme_h2 = {ds.slug(h) for h, _ in ds.template_sections(readme_template)}
        # output path of each concern's doc, existing or moved; new skeletons are not targets
        home_of = {c["concern"]: (c["default_path"] if c.get("misplaced") else c["covered_by"])
                   for c in coverage if (c.get("covered_by") or c.get("misplaced")) and not c.get("unit") and c["concern"] not in ("readme", "agent")}
        for s_ in rsecs:
            if ds.slug(s_["heading"]) in readme_h2 or ds.is_start_here_heading(s_["heading"]):
                continue
            body_text = "\n".join(s_["body"])
            if len([l for l in s_["body"] if l.strip()]) <= 1:
                continue  # a line and a link is already the shape asked for
            best, best_score = None, 0
            for cid, bucket, applies, default_file, keywords, companions in ds.CONCERNS:
                if cid not in home_of or not keywords:
                    continue
                kw = {ds.tokens(k).strip() for k in keywords}
                ht = ds.tokens(s_["heading"])
                sc = sum(3 for k in kw if f" {k} " in ht)
                if sc > best_score:
                    best, best_score = cid, sc
            if not best:
                continue
            home = home_of[best]
            t = ds.template_for(next(c["template"] for c in coverage if c["concern"] == best and not c.get("unit")))
            if t is None:
                continue
            tsec, _ = best_template_section(s_["heading"], ds.template_sections(t))
            if tsec is None:
                continue
            rel_link = os.path.relpath(repo / home, (repo / front_rel).parent).replace("\\", "/")
            pointer = f"See [{Path(home).stem.replace('_', ' ')}]({rel_link}#{ds.slug(tsec)})."
            give_away[s_["heading"]] = (home, pointer)
            body_rebased = rewrite(s_["body"], (repo / front_rel).parent.resolve(), (repo / home).parent.resolve())
            prerebased.update(body_rebased)
            extra_for.setdefault(home, {}).setdefault(tsec, []).append([f"### {s_['heading']} (from {front_rel})"] + body_rebased)
            out["docs"].setdefault(front_rel, {}).setdefault("rehomed", []).append({"section": s_["heading"], "to": home, "to_section": tsec})
    inputs: Counter = Counter()
    outputs: Counter = Counter()
    in_heads: Counter = Counter()
    out_heads: Counter = Counter()
    renamed: Counter = Counter()
    added: Counter = Counter()
    for src, dst, c in targets:
        t = ds.template_for(c["template"])
        if t is None:
            continue
        raw = ds.read(repo / src)
        nl = "\r\n" if raw.count("\r\n") * 2 > raw.count("\n") else "\n"
        lines = raw.splitlines()
        if PART_OF.search(raw[:800]):
            continue  # a part of a split: its index is the doc
        res = restructure_doc(lines, t, c["concern"], extra_for.get(dst) or extra_for.get(src), give_away if src == front_rel else None)
        out["files"][dst] = res["lines"]
        out["newline"][dst] = "crlf" if nl == "\r\n" else "lf"
        if dst != src:
            out["delete"].append(src)
        d = out["docs"].setdefault(src, {})
        d.update({"to": dst, "concern": c["concern"], "template": res["template"], "mapping": res["mapping"], "kept": res["kept"], "given": res["given"]})
        inputs.update(content_lines(lines))
        outputs.update(content_lines(res["lines"]))
        in_heads.update(headings_in(lines))
        out_heads.update(headings_in(res["lines"]))
        for m in res["mapping"]:
            renamed[m["from"]] += 1
        for g in res["given"]:
            renamed[g["heading"]] += 1
        added.update(re.sub(r"\]\([^)]*\)", "](#)", l.rstrip()) for l in res["added"] if l.strip())
    # given-away bodies moved into other docs: their "### <heading> (from README)" line is a heading, not content
    problems: list[str] = []
    missing = inputs - (outputs - added)
    extra = (outputs - added) - inputs
    for l, n in missing.items():
        problems.append(f"line lost ({n}x): {l[:80]}")
    for l, n in extra.items():
        problems.append(f"line invented ({n}x): {l[:80]}")
    for h, n in in_heads.items():
        have = out_heads.get(h, 0) + renamed.get(h, 0)
        if have < n:
            problems.append(f"heading lost: {h}")
    # links, after the structure proof: a moved doc's own relative links are rebased to its new folder,
    # and every Markdown file that links a moved path - restructured or not - points at the new one
    for src, dst, c in targets:
        if dst in out["files"]:
            out["files"][dst] = rewrite(out["files"][dst], (repo / src).parent.resolve(), (repo / dst).parent.resolve(), prerebased)
    if moved:
        for rel in _tracked(repo):
            if rel in out["delete"] or rel in out["files"] or Path(rel).suffix.lower() not in (".md", ".mdx"):
                continue
            text = ds.read(repo / rel)
            if not text or not any(Path(sname).name in text for sname in moved):
                continue
            lines = text.splitlines()
            new = rewrite(lines, (repo / rel).parent.resolve(), (repo / rel).parent.resolve())
            if new != lines:
                out["files"][rel] = new
                out["newline"][rel] = "crlf" if text.count("\r\n") * 2 > text.count("\n") else "lf"
                out["docs"].setdefault(rel, {})["inbound_links_rewritten"] = True
    # every relative link in an output resolves against the output tree
    future = set(out["files"]) | {p for p in _tracked(repo) if p not in out["delete"]}
    for rel, lines in out["files"].items():
        base = (repo / rel).parent
        mask = fence_mask(lines)
        for i, l in enumerate(lines):
            if mask[i] or "](" not in l:
                continue
            for m in ds.LINK_RE.finditer(l):
                target = (m.group(2) or m.group(3) or "").strip()
                fp = target.partition("#")[0]
                if not fp or fp.startswith(("http://", "https://", "mailto:", "/")):
                    continue
                absr = (base / ds.unquote(fp)).resolve() if hasattr(ds, "unquote") else (base / fp).resolve()
                try:
                    r = ds.posix(absr, repo)
                except ValueError:
                    continue
                if r not in future and not (repo / r).is_dir():
                    problems.append(f"{rel}: link {target} does not resolve after restructure")
    out["proof"] = {"ok": not problems, "problems": problems[:60], "docs": len(out["files"]),
                    "lines_in": sum(inputs.values()), "lines_out": sum((outputs - added).values())}
    if not out["files"]:
        out["refuse"] = "nothing to restructure: no doc covers a concern and the README is absent"
    return out


def _tracked(repo: Path) -> list[str]:
    git = ds.shutil.which("git")
    if git is not None:
        try:
            p = ds.subprocess.run([git, "ls-files", "-z"], cwd=str(repo), text=False, timeout=ds.GIT_TIMEOUT,
                                  stdout=ds.subprocess.PIPE, stderr=ds.subprocess.PIPE)
            if p.returncode == 0:
                return [n.decode("utf-8", "replace") for n in p.stdout.split(b"\0") if n]
        except (OSError, ds.subprocess.SubprocessError):
            pass
    out = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("node_modules", "vendor", "dist", "build", "target", "__pycache__")]
        for f in files:
            out.append(ds.posix(Path(root) / f, repo))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--no-git-root", action="store_true")
    ap.add_argument("--manifest")
    ap.add_argument("--out", help="a folder OUTSIDE the repository to materialise the proposal into")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    if not a.no_git_root:
        root = ds.git_root(repo) if hasattr(ds, "git_root") else None
        repo = root or repo
    manifest, mpath, source = ds.load_manifest(repo, a.manifest)
    result = propose(repo, manifest, mpath, source)
    if a.out and not result["refuse"] and result["proof"]["ok"]:
        out_dir = Path(a.out).resolve()
        if out_dir == repo or repo in out_dir.parents:
            sys.stderr.write("error: --out must be outside the repository\n")
            return 2
        for rel, lines in result["files"].items():
            nl = "\r\n" if result["newline"].get(rel) == "crlf" else "\n"
            p = out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((nl.join(lines) + nl).encode("utf-8"))
        result["written_to"] = str(out_dir)
    if a.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    L = ["# Restructure proposal", ""]
    if result["refuse"]:
        L.append(f"REFUSED: {result['refuse']}")
    for src, d in result["docs"].items():
        if "to" in d:
            L.append(f"{src}" + (f" -> {d['to']}" if d["to"] != src else "") + f"  ({d['concern']}, {d['template']})")
            for m in d["mapping"]:
                L.append(f"    {m['from']!r} -> {m['to']!r}" + ("  AMBIGUOUS - confirm" if m["ambiguous"] else ""))
            for k in d["kept"]:
                L.append(f"    kept as is: {k!r}")
            for g in d["given"]:
                L.append(f"    given to {g['to']}: {g['heading']!r}")
        for r in d.get("rehomed", []):
            L.append(f"    rehomed: {r['section']!r} -> {r['to']} § {r['to_section']}")
    pr = result["proof"]
    if pr:
        L.append("")
        L.append(f"Proof: {'ok' if pr['ok'] else 'FAILED'} - {pr['docs']} docs, {pr['lines_in']} content lines in, {pr['lines_out']} out")
        L += [f"  {x}" for x in pr["problems"]]
    if result.get("written_to"):
        L.append(f"Written to: {result['written_to']}")
    L.append("")
    L.append("Nothing was written into the repository. Write these files, delete the moved-from paths, only when the proof is ok.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
