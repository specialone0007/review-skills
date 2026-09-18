#!/usr/bin/env python3
"""Propose the split of one oversize Markdown doc into an index plus parts, and prove it reversible.

Read-only. Standard library only. Writes nothing into the repository.

    python docs_split.py --repo . --doc docs/BIG.md --format json
    python docs_split.py --repo . --doc docs/BIG.md --out <scratch>   # materialise outside the repo

The rules are the ones in references/structure.md, "The split, exactly": fence-aware parse, refuse
on more than one H1 or reference-style definitions, cut at H2 (else H3) so that no part is over
`splitAt`, keep the intro in the original file as the index, rewrite every link so it resolves to
the same target from its new file, keep the line ending, and prove the cut by reversing it:
remove exactly the injected lines, undo the heading shift and the link rewrite, concatenate the
intro and the parts in table order, and compare every line with the original.

The proposal is data. `files` holds the index and the parts, `inbound` the other Markdown files
whose `X.md#anchor` links now point at a part, `mentions` the non-Markdown files that name the old
path and are reported, never edited. Nothing is written unless `--out` names a folder outside the
repository; the agent reading SKILL.md writes into the tree, and only when `proof.ok` is true.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docs_structure as ds  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_DIRS = {".git", "node_modules", "vendor", "venv", ".venv", "dist", "build", "target",
             "__pycache__", ".next", "coverage", "site-packages"}
OWNER_RE = re.compile(r"^>\s*\*\*(?:This document owns|Part of)[:*]")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "data:", "#", "/")


def dominant_newline(raw: str) -> str:
    return "\r\n" if raw.count("\r\n") * 2 > raw.count("\n") else "\n"


def fence_mask(lines: list[str]) -> list[bool]:
    """True for every line inside a fenced block, fence lines included."""
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


def tracked_markdown(repo: Path) -> list[str]:
    git = ds.shutil.which("git")
    if git is not None:
        try:
            p = subprocess.run([git, "ls-files", "-z"], cwd=str(repo), text=False, timeout=ds.GIT_TIMEOUT,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode == 0:
                names = [n.decode("utf-8", "replace") for n in p.stdout.split(b"\0") if n]
                return [n for n in names if not any(part in SKIP_DIRS for part in n.split("/"))]
        except (OSError, subprocess.SubprocessError):
            pass
    out = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            out.append(ds.posix(Path(root) / f, repo))
    return out


def rebase(target: str, old_dir: Path, new_dir: Path, repo: Path) -> str:
    """The same target, written relative to new_dir instead of old_dir."""
    file_part, _, anchor = target.partition("#")
    absolute = (old_dir / ds.unquote(file_part)).resolve()
    rel = os.path.relpath(absolute, new_dir.resolve()).replace("\\", "/")
    return rel + ("#" + anchor if anchor else "")


def splice(m: re.Match, new: str) -> str:
    """The link with only its target replaced. `[research/LOG.md](research/LOG.md)` has the target
    in its text as well, and a plain replace rewrote the text and left the link dead."""
    g = 2 if m.group(2) else 3
    off = m.start()
    return m.group(0)[:m.start(g) - off] + new + m.group(0)[m.end(g) - off:]


def unsplice(line: str, records: list[tuple[str, str]]) -> str:
    """Every link whose target is a recorded `new` gets its recorded `old` back, positionally."""
    if not records:
        return line
    back = {new: old for old, new in records}
    def sub(m: re.Match) -> str:
        target = (m.group(2) or m.group(3) or "").strip()
        return splice(m, back[target]) if target in back else m.group(0)
    return ds.LINK_RE.sub(sub, line)


def clean_slug(text: str) -> str:
    """A filename from a heading: code spans and paths out, parentheticals out, five words at
    most. `01-data-model-apps-web-src-db-schema-ts.md` was a heading slugged whole."""
    t = re.sub(r"`[^`]*`", " ", text)
    t = re.sub(r"\([^)]*\)", " ", t)
    t = re.sub(r"\S+[/\\]\S+", " ", t)
    t = re.sub(r"^\s*\d+[.)]\s*", "", t)
    words = [w for w in ds.slug(t).split("-") if w][:5]
    return "-".join(words) or ds.slug(text)


def propose(repo: Path, doc_rel: str, split_at: int, max_parts: int, min_part: int = 80) -> dict:
    doc_path = repo / doc_rel
    if not doc_path.is_file():
        sys.stderr.write(f"error: {doc_rel} is not a file under {repo}\n")
        raise SystemExit(2)
    doc = ds.Doc(doc_path, repo)
    out: dict = {"doc": doc.rel, "lines": len(doc.lines), "refuse": None, "level": None,
                 "parts": [], "files": {}, "inbound": {}, "mentions": [], "rewrites": 0,
                 "newline": "crlf" if dominant_newline(doc.raw) == "\r\n" else "lf", "proof": None}
    if doc.skipped or doc.undecodable:
        out["refuse"] = "the file could not be read as text"
        return out
    min_part = max(1, min(min_part, split_at // 5))
    analysis = ds.split_analysis(doc, split_at, max_parts, min_part)
    if analysis["refuse"]:
        out["refuse"] = analysis["refuse"]
        return out
    level = int(analysis["level"][1])
    out["level"] = analysis["level"]

    lines = doc.lines
    n = len(lines)
    mask = fence_mask(lines)
    heads = [(ln, lvl, text) for ln, lvl, text in doc.headings]
    h1 = next((t for _, lvl, t in heads if lvl == 1), Path(doc.rel).stem)
    cuts = [ln for ln, lvl, _ in heads if 2 <= lvl <= level]
    bounds = cuts + [n + 1]
    # Group: a heading with no body merges into the part that follows; so does a part shorter
    # than min_part, so a part is a chapter and not a heading.
    groups = ds.part_groups(lines, cuts, min_part)
    intro_lines = lines[:cuts[0] - 1]
    if len(intro_lines) > split_at:
        out["refuse"] = f"intro is {len(intro_lines)} lines"; return out
    if not (3 <= len(groups) <= max_parts):
        out["refuse"] = f"{len(groups)} parts"; return out

    parts_dir_name = Path(doc.rel).stem.lower()
    parts_dir = doc_path.parent / parts_dir_name
    index_rel = doc.rel
    # Where every heading slug ends up: intro (the index) or a part number.
    slug_home: dict[str, int] = {}  # 0 = index
    seen: dict[str, int] = {}

    def anchor_for(text: str) -> str:
        s = ds.slug(text)
        k = seen.get(s, 0); seen[s] = k + 1
        return s if k == 0 else f"{s}-{k}"

    for ln, lvl, text in heads:
        if ln < cuts[0]:
            slug_home[anchor_for(text)] = 0
    part_specs = []
    for idx, (start, end) in enumerate(groups, start=1):
        body = lines[start - 1:end - 1]
        levels = [lvl for ln, lvl, _ in heads if start <= ln < end]
        shift = min(levels) - 2
        first_text = next(t for ln, lvl, t in heads if ln == start)
        for ln, lvl, text in heads:
            if start <= ln < end:
                slug_home[anchor_for(text)] = idx
        part_specs.append({"n": idx, "start": start, "end": end, "shift": shift, "first": first_text,
                           "slug": clean_slug(first_text), "body": body, "group": None})
    # Part filenames.
    for p in part_specs:
        p["file"] = f"{p['n']:02d}-{p['slug']}.md"
        p["rel"] = ds.posix(parts_dir / p["file"], repo)

    def home_target(anchor: str, from_part: int) -> str | None:
        """The link target that reaches `anchor` from part `from_part` (0 = index)."""
        home = slug_home.get(anchor)
        if home is None:
            return None
        if home == from_part:
            return "#" + anchor
        if home == 0:
            return ("../" + Path(index_rel).name if from_part else "") + "#" + anchor
        target = part_specs[home - 1]["file"]
        return (f"{parts_dir_name}/{target}" if from_part == 0 else target) + "#" + anchor

    rewrites: list[tuple[str, int, str, str]] = []  # (file, line index, old, new)

    def rewrite_line(line: str, from_part: int, file_rel: str, li: int) -> str:
        def sub(m: re.Match) -> str:
            whole = m.group(0)
            target = (m.group(2) or m.group(3) or "").strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "data:", "/")):
                return whole
            if target.startswith("#"):
                new = home_target(target[1:], from_part)
            else:
                file_part, _, anchor = target.partition("#")
                new = rebase(target, doc_path.parent, parts_dir, repo) if from_part else target
                # A link into this very doc, with an anchor, follows the anchor to its part.
                if (doc_path.parent / ds.unquote(file_part)).resolve() == doc_path.resolve() and anchor:
                    new = home_target(anchor, from_part) or new
            if new is None or new == target:
                return whole
            rewrites.append((file_rel, li, target, new))
            return splice(m, new)
        return ds.LINK_RE.sub(sub, ds.CODESPAN_RE.sub(lambda m: m.group(0), line)) if "](" in line else line

    # Parts.
    files: dict[str, list[str]] = {}
    for p in part_specs:
        body = list(p["body"])
        pm = mask[p["start"] - 1:p["end"] - 1]
        new_body = []
        for li, line in enumerate(body):
            if not pm[li]:
                hm = HEADING_RE.match(line)
                if hm and p["shift"]:
                    line = hm.group(1)[p["shift"]:] + line[len(hm.group(1)):]
                line = rewrite_line(line, p["n"], p["rel"], li + 2)
            new_body.append(line)
        injected = [f"> Part of [{h1}](../{Path(index_rel).name})", ""]
        prev_ = part_specs[p["n"] - 2]["file"] if p["n"] > 1 else None
        next_ = part_specs[p["n"]]["file"] if p["n"] < len(part_specs) else None
        nav = " · ".join(x for x in (f"Previous: [{prev_}]({prev_})" if prev_ else None,
                                     f"Index: [{Path(index_rel).name}](../{Path(index_rel).name})",
                                     f"Next: [{next_}]({next_})" if next_ else None) if x)
        while new_body and not new_body[-1].strip():
            new_body.pop()
        files[p["rel"]] = injected + new_body + ["", nav]
        out["parts"].append({"n": p["n"], "path": p["rel"], "heading": p["first"], "lines": len(new_body)})
    # Index: intro, owner line if absent, a table of parts.
    intro = list(intro_lines)
    intro_mask = mask[:len(intro)]
    intro = [rewrite_line(l, 0, index_rel, i) if not intro_mask[i] else l for i, l in enumerate(intro)]
    injected_index: list[str] = []
    has_owner = any(OWNER_RE.match(l) for l in intro[:12] if l.strip())
    if not has_owner:
        injected_index += [f"> **This document owns:** {h1} - an index of its parts under `{parts_dir_name}/`. *(auto, review me)*", ""]
    injected_index += ["## Parts", "", "| part | covers | lines |", "|---|---|---|"]
    for p, info in zip(part_specs, out["parts"]):
        injected_index.append(f"| [{p['file']}]({parts_dir_name}/{p['file']}) | {p['first']} | {info['lines']} |")
    injected_index.append("")
    while intro and not intro[-1].strip():
        intro.pop()
    files[index_rel] = intro + [""] + injected_index
    out["index_injected"] = len(injected_index) + 1
    out["files"] = files

    # Inbound: other tracked Markdown files linking X.md#anchor into this doc.
    doc_abs = doc_path.resolve()
    for rel in tracked_markdown(repo):
        if rel == doc.rel:
            continue
        p = repo / rel
        if Path(rel).suffix.lower() not in (".md", ".mdx"):
            if doc.rel in (ds.read(p) or "") or Path(doc.rel).name in (ds.read(p) or ""):
                out["mentions"].append(rel)
            continue
        text = ds.read(p)
        if not text or Path(doc.rel).name not in text:
            continue
        src_lines = text.splitlines()
        m2 = fence_mask(src_lines)
        changed = False
        new_lines = []
        for li, line in enumerate(src_lines):
            if m2[li] or "](" not in line:
                new_lines.append(line); continue
            def sub(m: re.Match, _rel=rel, _li=li) -> str:
                whole = m.group(0)
                target = (m.group(2) or m.group(3) or "").strip()
                file_part, _, anchor = target.partition("#")
                if not anchor or not file_part or file_part.startswith(("http://", "https://")):
                    return whole
                if ds.resolve_target(p, repo, file_part).resolve() != doc_abs:
                    return whole
                home = slug_home.get(anchor)
                if not home:
                    return whole
                new_abs = parts_dir / part_specs[home - 1]["file"]
                new = os.path.relpath(new_abs.resolve(), p.parent.resolve()).replace("\\", "/") + "#" + anchor
                rewrites.append((_rel, _li + 1, target, new))
                return splice(m, new)
            nl = ds.LINK_RE.sub(sub, line)
            changed |= nl != line
            new_lines.append(nl)
        if changed:
            out["inbound"][rel] = new_lines
    out["rewrites"] = len(rewrites)

    # Proof: reverse everything and compare with the original, line for line.
    problems: list[str] = []
    # Two links on one line are two records; a dict of one per line kept only the last.
    rev: dict[tuple[str, int], list[tuple[str, str]]] = {}
    for f, li, old, new in rewrites:
        rev.setdefault((f, li), []).append((old, new))
    kept = files[index_rel][:len(files[index_rel]) - out["index_injected"]]
    rebuilt = []
    for i, line in enumerate(kept):
        line = unsplice(line, rev.get((index_rel, i), []))
        rebuilt.append(line)
    # the index had its trailing blank lines trimmed; the original's come back here
    rebuilt = rebuilt + intro_lines[len(rebuilt):] if len(intro_lines) > len(rebuilt) else rebuilt
    for p in part_specs:
        body = files[p["rel"]][2:-2]
        # the part had its trailing blank lines trimmed before the nav line; the original's come back
        body = body + p["body"][len(body):] if len(p["body"]) > len(body) else body
        pm = mask[p["start"] - 1:p["end"] - 1]
        restored = []
        for li, line in enumerate(body):
            if not pm[li]:
                line = unsplice(line, rev.get((p["rel"], li + 2), []))
                hm = HEADING_RE.match(line)
                if hm and p["shift"]:
                    line = "#" * p["shift"] + line
            restored.append(line)
        rebuilt += restored
    if rebuilt != lines:
        for k, (a, b) in enumerate(zip(rebuilt, lines)):
            if a != b:
                problems.append(f"reversal differs at line {k + 1}: {a[:60]!r} vs {b[:60]!r}"); break
        else:
            problems.append(f"reversal differs in length: {len(rebuilt)} vs {len(lines)}")
    for p, info in zip(part_specs, out["parts"]):
        body = files[p["rel"]][2:-2]
        pm = mask[p["start"] - 1:p["end"] - 1]
        hs = [HEADING_RE.match(l) for li, l in enumerate(body) if not pm[li] and HEADING_RE.match(l)]
        if any(len(h.group(1)) == 1 for h in hs):
            problems.append(f"{p['rel']}: an H1 inside a part")
        if not hs or len(hs[0].group(1)) != 2:
            problems.append(f"{p['rel']}: first heading is not H2")
        if f"{p['n']:02d}-" != p["file"][:3]:
            problems.append(f"{p['rel']}: number does not match table position")
        if hs and ds.slug(hs[0].group(2)) != p["slug"]:
            problems.append(f"{p['rel']}: filename slug differs from first-heading slug")
    # Every link in a touched file resolves in the new tree, and reaches the same absolute target.
    tree_anchors: dict[Path, set[str]] = {}
    for rel, content in list(files.items()) + list(out["inbound"].items()):
        tree_anchors[(repo / rel).resolve()] = ds.anchors(ds.strip_fences(content))

    def exists_in_tree(path: Path) -> bool:
        return path.resolve() in tree_anchors or path.is_file()

    def anchors_of(path: Path) -> set[str]:
        r = path.resolve()
        if r in tree_anchors:
            return tree_anchors[r]
        return ds.anchors(ds.strip_fences(ds.read(path).splitlines())) if path.is_file() else set()

    # A link that was dead before the split stays dead after it: the proof is that every link
    # reaches the same absolute target it reached from the original file, and that a target
    # which existed still exists. A badge URL under ../../actions never resolved and is not
    # the split's problem.
    for rel, content in list(files.items()) + list(out["inbound"].items()):
        new_base = (repo / rel).parent
        old_base = doc_path.parent if rel in files else new_base
        back = {new: old for f, li, old, new in rewrites if f == rel}
        m3 = fence_mask(content)
        for li, line in enumerate(content):
            if m3[li]:
                continue
            for img, angled, plain in ds.LINK_RE.findall(ds.CODESPAN_RE.sub("", line)):
                target = (angled or plain).strip()
                if not target or target.startswith(("http://", "https://", "mailto:", "tel:", "data:")):
                    continue
                if target.startswith("#"):
                    if target[1:] not in anchors_of(repo / rel):
                        problems.append(f"{rel}:{li + 1}: anchor `{target}` not found in {rel}")
                    continue
                old = back.get(target, target)
                file_part, _, anchor = target.partition("#")
                old_file, _, old_anchor = old.partition("#")
                tpath = ds.resolve_target(repo / rel, repo, file_part)
                if old_file.startswith("#") or not old_file:
                    opath = doc_path
                else:
                    opath = ds.resolve_target(old_base / "x.md", repo, old_file)
                was_live = opath.is_file() or opath.is_dir()
                if was_live and not exists_in_tree(tpath):
                    problems.append(f"{rel}:{li + 1}: link `{target}` does not resolve in the split tree")
                elif was_live and anchor and tpath.suffix.lower() in (".md", ".mdx") and anchor not in anchors_of(tpath):
                    problems.append(f"{rel}:{li + 1}: anchor `#{anchor}` not found in {ds.posix(tpath, repo)}")
                elif old != target and opath.resolve() != doc_abs and tpath.resolve() != opath.resolve():
                    problems.append(f"{rel}:{li + 1}: `{target}` no longer reaches what `{old}` reached")
    out["proof"] = {"ok": not problems, "problems": problems[:20]}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--repo", default=".", help="repository path (default: current directory)")
    ap.add_argument("--doc", required=True, help="the doc to split, relative to the repo")
    ap.add_argument("--no-git-root", action="store_true", help="do not expand --repo to its git root")
    ap.add_argument("--manifest", help="manifest path (default: <repo>/docs/structure.json, then docs-structure.json)")
    ap.add_argument("--split-at", type=int, help="override the manifest's splitAt (default 500)")
    ap.add_argument("--max-parts", type=int, help="override the manifest's maxParts (default 12)")
    ap.add_argument("--min-part", type=int, help="override the manifest's minPart (default 80): a shorter section merges into the next")
    ap.add_argument("--out", help="a folder OUTSIDE the repository to materialise the proposal into")
    ap.add_argument("--format", choices=("text", "json"), default="text")
    a = ap.parse_args()
    repo = Path(a.repo).resolve()
    if not a.no_git_root:
        root = ds.git_root(repo) if hasattr(ds, "git_root") else None
        repo = root or repo
    manifest, _, _ = ds.load_manifest(repo, a.manifest)
    split_at = a.split_at or int(manifest.get("splitAt") or 1000)
    max_parts = a.max_parts or int(manifest.get("maxParts") or 12)
    min_part = a.min_part or int(manifest.get("minPart") or 80)
    doc_rel = Path(a.doc).as_posix()
    if (repo / doc_rel).is_file() is False and Path(a.doc).is_file():
        doc_rel = ds.posix(Path(a.doc).resolve(), repo)
    result = propose(repo, doc_rel, split_at, max_parts, min_part)
    result["repo"] = str(repo)
    nl = "\r\n" if result["newline"] == "crlf" else "\n"
    if a.out and not result["refuse"] and result["proof"] and result["proof"]["ok"]:
        out_dir = Path(a.out).resolve()
        if out_dir == repo or repo in out_dir.parents:
            sys.stderr.write("error: --out must be outside the repository; the script never writes into it\n")
            return 2
        for rel, content in list(result["files"].items()) + list(result["inbound"].items()):
            p = out_dir / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes((nl.join(content) + nl).encode("utf-8"))
        result["written_to"] = str(out_dir)
    if a.format == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    L = [f"# Split proposal: {result['doc']} ({result['lines']} lines, {result['newline']})", ""]
    if result["refuse"]:
        L.append(f"REFUSED: {result['refuse']} - needs a human restructure")
    else:
        L.append(f"Cut at {result['level']}: {len(result['parts'])} parts")
        for p in result["parts"]:
            L.append(f"  {p['n']:02d}  {p['path']}  {p['lines']} lines  {p['heading']}")
        L.append(f"Links rewritten: {result['rewrites']}; inbound files touched: {len(result['inbound'])}; non-Markdown mentions: {len(result['mentions'])}")
        for m in result["mentions"][:10]:
            L.append(f"  mention (not edited): {m}")
        pr = result["proof"]
        L.append("Proof: " + ("ok - reversal is line-identical and every link resolves" if pr["ok"] else "FAILED"))
        for x in pr["problems"]:
            L.append(f"  {x}")
        if result.get("written_to"):
            L.append(f"Written to: {result['written_to']}")
        L.append("")
        L.append("Nothing was written into the repository. Write these files only when the proof is ok.")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
