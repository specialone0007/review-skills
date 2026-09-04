#!/usr/bin/env python3
"""Validate the eval cases in evals/, and snapshot-test the bundled scripts.

Maintainer tool. Standard library only.

    python tools/validate_evals.py                    # validate cases + check snapshots
    python tools/validate_evals.py --update-snapshots # rewrite snapshots after a deliberate change
    python tools/validate_evals.py --checklist         # print every case as a manual checklist
    python tools/validate_evals.py --checklist security-audit

Two tiers, and the split is deliberate.

Tier 1, which runs in CI and needs no model: the eval files are well formed, every
skill they name exists, ids are unique, fixtures exist, and the bundled scripts
still produce exactly the output committed under evals/snapshots/. That last part is
real regression protection -- it is what keeps the scripts honest.

Tier 2, which is manual: `--checklist` prints the prompts and rubrics for a human to
run against a live agent. Whether a description triggers, and whether a report obeys
its contract, cannot be checked without a model. Deliberately not automated with an
LLM judge in CI: that costs money on every push, is flaky, needs a secret in a public
repo, and a solo maintainer will let it rot.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parent.parent
EVALS = REPO / "evals"
SKILLS = REPO / "skills"
SNAPSHOTS = EVALS / "snapshots"
FIXTURE = EVALS / "fixtures" / "mini-app"

KINDS = ("trigger", "anti-trigger", "behavior")
MIN_CASES = 3

# Scripts that get snapshot-tested against the fixture. --no-git-root keeps the
# survey inside the fixture instead of expanding to this repo.
#
# `drop` removes keys whose value depends on the machine rather than the fixture,
# so a snapshot stays comparable between a laptop and a CI runner. dependency_audit
# reports which auditors are installed, which legitimately differs per machine; its
# offline_signals are the deterministic part worth locking down.
SNAPSHOT_SCRIPTS = {
    "repo_inventory": {"path": "skills/repo-health-audit/scripts/repo_inventory.py", "drop": []},
    "coverage_map": {"path": "skills/test-gap-audit/scripts/coverage_map.py", "drop": []},
    "dependency_audit": {"path": "skills/security-audit/scripts/dependency_audit.py",
                         "drop": ["auditors"]},
}

errors: list[str] = []


def error(msg: str) -> None:
    errors.append(msg)


def load_cases() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for path in sorted(EVALS.glob("*.json")):
        try:
            docs[path.stem] = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            error(f"{path.name}: not valid JSON: {exc}")
    return docs


def validate_cases(docs: dict[str, dict], skill_names: set[str]) -> int:
    total = 0
    for skill in sorted(skill_names):
        if skill not in docs:
            error(f"evals/: no eval file for skill `{skill}`")
    for stem, doc in docs.items():
        name = f"evals/{stem}.json"
        declared = doc.get("skill")
        if declared != stem:
            error(f"{name}: `skill` is {declared!r} but the filename says {stem!r}")
        if declared not in skill_names:
            error(f"{name}: `skill` {declared!r} is not a skill directory in this repo")
        cases = doc.get("cases")
        if not isinstance(cases, list):
            error(f"{name}: `cases` must be a list")
            continue
        if len(cases) < MIN_CASES:
            error(f"{name}: {len(cases)} cases, at least {MIN_CASES} required")

        seen_ids: set[str] = set()
        kinds_present: set[str] = set()
        for i, case in enumerate(cases):
            where = f"{name}[{i}]"
            cid = case.get("id")
            if not cid:
                error(f"{where}: missing `id`")
            elif cid in seen_ids:
                error(f"{where}: duplicate id {cid!r}")
            else:
                seen_ids.add(cid)

            kind = case.get("kind")
            if kind not in KINDS:
                error(f"{where}: `kind` must be one of {', '.join(KINDS)}, got {kind!r}")
            else:
                kinds_present.add(kind)

            if not case.get("prompt"):
                error(f"{where}: missing `prompt`")

            if kind in ("trigger", "anti-trigger"):
                expect = case.get("expect_skill")
                if not expect:
                    error(f"{where}: {kind} case needs `expect_skill`")
                elif expect not in skill_names:
                    error(f"{where}: `expect_skill` {expect!r} is not a skill in this repo")
                if kind == "anti-trigger" and expect == declared:
                    error(f"{where}: an anti-trigger case must expect a different skill than {declared!r}")
                for alt in case.get("also_acceptable", []):
                    if alt not in skill_names:
                        error(f"{where}: `also_acceptable` names {alt!r}, which is not a skill in this repo")

            if kind == "behavior":
                if not case.get("must_include"):
                    error(f"{where}: behavior case needs `must_include`")
                if not case.get("rubric"):
                    error(f"{where}: behavior case needs `rubric`")

            fixture = case.get("fixture")
            if fixture and not (EVALS / fixture).exists():
                error(f"{where}: `fixture` {fixture!r} does not exist under evals/")
            total += 1

        # Anti-trigger cases are the whole point with seven overlapping skills.
        if "anti-trigger" not in kinds_present:
            error(f"{name}: no anti-trigger case; routing away from this skill is untested")
        if "behavior" not in kinds_present:
            error(f"{name}: no behavior case; the output contract is untested")
    return total


def run_script(rel: str, drop: list[str]) -> dict | None:
    """Run one bundled script against the fixture and return its normalised JSON."""
    proc = subprocess.run(
        [sys.executable, str(REPO / rel), "--repo", str(FIXTURE), "--no-git-root", "--format", "json"],
        cwd=str(REPO), text=True, timeout=180,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        encoding="utf-8", errors="replace",
    )
    if proc.returncode != 0:
        error(f"{rel}: exited {proc.returncode} against the fixture: {proc.stderr.strip()[:200]}")
        return None
    try:
        data = json.loads(proc.stdout)
    except ValueError as exc:
        error(f"{rel}: did not emit valid JSON: {exc}")
        return None
    # The absolute fixture path differs per machine, so it can never be snapshotted.
    data["repo"] = "<fixture>"
    for key in drop:
        data.pop(key, None)
    return data


def check_snapshots(update: bool) -> None:
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    for key, spec in SNAPSHOT_SCRIPTS.items():
        rel = spec["path"]
        actual = run_script(rel, spec["drop"])
        if actual is None:
            continue
        snap = SNAPSHOTS / f"{key}.json"
        text = json.dumps(actual, indent=2, sort_keys=True) + "\n"
        if update:
            snap.write_text(text, encoding="utf-8")
            print(f"updated snapshot: evals/snapshots/{key}.json")
            continue
        if not snap.is_file():
            error(f"evals/snapshots/{key}.json is missing; run --update-snapshots")
            continue
        expected = snap.read_text(encoding="utf-8")
        if expected != text:
            # Point at the first differing key so the failure is actionable.
            try:
                exp = json.loads(expected)
                diff = sorted(
                    k for k in set(exp) | set(actual)
                    if json.dumps(exp.get(k), sort_keys=True) != json.dumps(actual.get(k), sort_keys=True)
                )
                detail = f" Differing keys: {', '.join(diff)}." if diff else ""
            except ValueError:
                detail = ""
            error(
                f"{rel}: output no longer matches evals/snapshots/{key}.json.{detail}"
                " If the change was intended, rerun with --update-snapshots and review the diff."
            )


def check_secret_containment() -> None:
    """dependency_audit.py --secrets must report locations and never values.

    CodeQL flags that script's report print under py/clear-text-logging-sensitive-data.
    Its sensitive-data classifier is name-based, so it taints everything
    scan_secrets() returns without being able to see that the returned objects hold
    only a rule name, a path and a line number. We judge that a false positive -- but
    "we checked once" is not a guarantee, so this makes it an enforced invariant.

    Plants real-shaped credentials in a temporary directory, runs the script over it,
    and fails if any planted value reaches the output, or if a hit object carries any
    field beyond rule/path/line. The shapes live here rather than under evals/fixtures/
    so that nothing credential-shaped is ever committed to the repository.
    """
    script = REPO / "skills" / "security-audit" / "scripts" / "dependency_audit.py"
    if not script.is_file():
        return

    planted = {
        "aws": "AKIAIOSFODNN7EXAMPLE",
        "github": "ghp_0123456789abcdefghij0123456789abcdef",
        "npmrc_token": "npm_0123456789abcdefghij0123456789abcd",
        "url_password": "s3cr3tinurl",
    }
    config = "AWS={}\nGH={}\n".format(planted["aws"], planted["github"])
    npmrc = "//registry.npmjs.org/:_authToken={}\nregistry=https://internal.example.com/\n".format(
        planted["npmrc_token"])
    manifest = json.dumps({
        "name": "containment-check",
        "dependencies": {
            "private": "git+https://bot:{}@example.com/r.git".format(planted["url_password"]),
        },
    })

    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        (d / "config.txt").write_text(config, encoding="utf-8")
        (d / ".npmrc").write_text(npmrc, encoding="utf-8")
        (d / "package.json").write_text(manifest, encoding="utf-8")

        proc = subprocess.run(
            [sys.executable, str(script), "--repo", str(d), "--no-git-root",
             "--secrets", "--format", "json"],
            text=True, timeout=180, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode != 0:
            error("dependency_audit.py containment check: exited "
                  f"{proc.returncode}: {proc.stderr.strip()[:200]}")
            return

        raw = proc.stdout
        for label, value in planted.items():
            if value in raw:
                error(f"dependency_audit.py leaked the planted {label} credential into its "
                      "output. Any value read from a file must be redacted before it is reported.")
        try:
            data = json.loads(raw)
        except ValueError as exc:
            error(f"dependency_audit.py containment check: output was not valid JSON: {exc}")
            return

        hits = data.get("secret_shaped_locations") or []
        if not hits:
            error("dependency_audit.py containment check: --secrets matched none of the planted "
                  "shapes, so this guard is not exercising anything. Check SECRET_RULES.")
        for hit in hits:
            extra = sorted(set(hit) - {"rule", "path", "line"})
            if extra:
                error(f"dependency_audit.py secret hit carries unexpected field(s) {extra}; "
                      "hits must hold only rule, path and line.")


def checklist(docs: dict[str, dict], only: str | None) -> None:
    for stem in sorted(docs):
        if only and stem != only:
            continue
        doc = docs[stem]
        print(f"\n{'=' * 72}\n{stem}\n{'=' * 72}")
        for case in doc.get("cases", []):
            print(f"\n[ ] {case.get('id')}  ({case.get('kind')})")
            print(f"    prompt: {case.get('prompt')!r}")
            if case.get("fixture"):
                print(f"    run in: evals/{case['fixture']}")
            if case.get("expect_skill"):
                alts = case.get("also_acceptable")
                extra = f" (also acceptable: {', '.join(alts)})" if alts else ""
                print(f"    expect: {case['expect_skill']} fires{extra}")
            for field, label in (("must_include", "must include"), ("must_not_include", "must NOT include")):
                for item in case.get(field, []):
                    print(f"    [ ] {label}: {item!r}")
            for item in case.get("rubric", []):
                print(f"    [ ] {item}")
            if case.get("note"):
                print(f"    note: {case['note']}")
    print("\nRun these against a live agent and record what happened. Whether a description")
    print("triggers, and whether a report obeys its contract, cannot be checked without a model.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Validate eval cases and snapshot-test bundled scripts.")
    ap.add_argument("--update-snapshots", action="store_true",
                    help="Rewrite evals/snapshots/ from current script output. Review the diff before committing.")
    ap.add_argument("--checklist", nargs="?", const="", metavar="SKILL",
                    help="Print cases as a manual checklist, optionally for one skill.")
    args = ap.parse_args()

    if not EVALS.is_dir():
        print(f"error: {EVALS} not found", file=sys.stderr)
        return 2
    skill_names = {p.name for p in SKILLS.iterdir() if p.is_dir()}
    docs = load_cases()

    if args.checklist is not None:
        only = args.checklist or None
        if only and only not in docs:
            print(f"error: no eval file for {only!r}. Have: {', '.join(sorted(docs))}", file=sys.stderr)
            return 2
        checklist(docs, only)
        return 0

    total = validate_cases(docs, skill_names)
    if not FIXTURE.is_dir():
        error("evals/fixtures/mini-app is missing; snapshot tests cannot run")
    else:
        check_snapshots(args.update_snapshots)
    check_secret_containment()

    for line in errors:
        print(f"error: {line}")
    print()
    print(f"{len(docs)} eval files, {total} cases checked.")
    if errors:
        print(f"FAILED: {len(errors)} error(s).")
        return 1
    print("OK: 0 errors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
