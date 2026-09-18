# `test-gap-audit` on this repository

**Prompt:** "what tests am I missing"  
**Repository:** `specialone0007/review-skills`, branch `fix/docs-structure-layout` on top of `5597942`, with the removal of `feature-brainstorm` and `pr-branch-summary` applied  
**Files changed by the run:** none — the skill is read-only

Full-repository read-only coverage audit, running the bundled coverage_map.py, reading `tools/validate_evals.py` and its nine snapshot entries end to end, and confirming each lead by opening the file and, where a claim was cheap to settle, by re-running the script with different flags.

Re-run it yourself and compare. Line numbers refer to the tree described above, so a later commit will shift them.

---

**Test Gap Audit: whole repository (review-skills)**

No code changed. I reviewed all seven bundled scripts, the three maintainer tools, the snapshot registry, the two fixtures and the CI workflow against the repo's test conventions. I ran the bundled coverage mapper, read the snapshot registry and every snapshot file, and re-ran `docs_split.py` with varied flags to settle what its snapshot actually pins. No P0s found.

**Headline: the deterministic half of the suite is broader than it was — all seven bundled scripts now have snapshots — but two of its load-bearing claims are not true.** One snapshot pins a refusal while its own comment says it pins a proof, and the thing that enforces every rule in this repo has no negative test at all.

1. **P1: the only snapshot for `docs_split.py` pins a refusal, not a split — and the comment above it says the opposite.**
   Gap: `docs_split.py` is 627 lines whose entire product is a split proposal plus a reversibility proof. The snapshot proves neither. `evals/snapshots/docs_split.json` contains `"parts": []`, `"files": {}`, `"proof": null`, `"rewrites": 0`, and `"refuse": "H2: 14 parts, over maxParts 12; H3: 14 parts, over maxParts 12"`. The configured args at `tools/validate_evals.py:62` are `["--doc", "docs/drafted.md", "--split-at", "30"]`, and `--split-at 30` on that fixture doc yields 14 candidate parts, which exceeds the default `maxParts` of 12 — so the script declines and the snapshot records the decline. Every line that builds a part, rewrites an inbound link, or assembles the proof block is unexercised.
   The comment directly above the entry, at `tools/validate_evals.py:60`, reads "cut low so it has parts to propose; the proof block is part of the snapshot, so a reversal that stops being line-identical shows." That is a precise description of a test that does not exist. A maintainer reading the registry has been told the reversibility proof is pinned; it is `null`.
   Current coverage: the refusal path only. I confirmed the split path works and produces a proof — the same invocation with `--max-parts 16` returns `"refuse": null`, 14 parts, and `"proof": {"ok": true, "problems": []}` — so this is a one-flag fix, not a missing feature.
   Evidence: code `skills/docs-structure/scripts/docs_split.py:406` (`def merge`), snapshot registry `tools/validate_evals.py:62`, its claim at `tools/validate_evals.py:60`, snapshot contents `evals/snapshots/docs_split.json`.
   Suggested test: add `--max-parts 16` to the existing `docs_split` entry's args and regenerate, so the snapshot pins parts, rewrites and the proof block. Then add a *second* entry — `docs_split_refuse` — keeping the current args, so the refusal stays pinned too. Two snapshots, both meaningful, and the comment becomes true.

2. **P1: `merge()` — the reversibility half of the split contract — is never invoked by anything.**
   Gap: `skills/docs-structure/scripts/docs_split.py:406` defines `merge(repo, doc_rel)`, roughly 130 lines including its own proof construction at `:532`. `grep -rn -- "--merge"` across tracked Python, YAML and JSON finds the flag only inside `docs_split.py` itself. No snapshot entry passes it, CI does not call it, and the new all-scripts CI step at `.github/workflows/ci.yml:119` invokes `docs_split.py` with `--doc` only. The skill's documented promise is that a split is reversible; the code that reverses it has never been run by a test.
   This is not the same gap as finding 1. Fixing the args there pins the *forward* proof — the claim that a merge would restore the text. It still would not execute `merge()`.
   Current coverage: none. Confidence: high — confirmed by grep across all tracked non-Markdown files plus reading both the registry and the CI job.
   Evidence: code `skills/docs-structure/scripts/docs_split.py:406`; no test reference found in `tools/validate_evals.py`, `.github/workflows/ci.yml`, or `evals/snapshots/`.
   Suggested test: a round-trip snapshot. Add a registry entry that runs `docs_split.py --doc <index> --merge --format json` against a pre-split fixture doc and pins the merged output plus its proof. The strongest version materialises a split into a temp dir with `--out`, merges it back, and asserts the result is byte-identical to the original — that is the actual contract, and it is testable without writing into the repo.

3. **P1: nothing proves either validator still fires. A check that silently became a no-op would keep CI green forever.**
   Gap: `tools/validate_skills.py` (369 lines) and `tools/validate_evals.py` (286 lines) enforce every convention this repo publishes. Both are only ever run against review-skills itself, which currently passes. `REPO` is hard-coded at `tools/validate_skills.py:18` as `Path(__file__).resolve().parent.parent`, and `main()` at `:323` takes no arguments — there is no `argparse` and no `sys.argv` handling in the file, so it cannot be pointed at a deliberately bad skill. If `check_readme` at `:302` were edited to return early, or the `BODY_MAX_LINES` comparison flipped, the validator would print "OK: 0 errors" and CI would pass. Nothing would notice until a real violation shipped.
   This is the same class of gap the repo already solved for bundled scripts: the two fixtures exist precisely so a script can be run against known-bad input. That technique is not applied to the tools that check the fixtures.
   Current coverage: both validators run in CI (`.github/workflows/ci.yml:35` and `:88`) against a passing tree, which proves they do not crash. It proves nothing about whether any individual check still detects anything.
   Evidence: code `tools/validate_skills.py:18`, `tools/validate_skills.py:323`, `tools/validate_skills.py:302`; CI invocations `.github/workflows/ci.yml:35`, `.github/workflows/ci.yml:88`; no test file exists — `git ls-files | grep -i test` outside `evals/fixtures/` returns only skill and eval files, no test code.
   Suggested test: parameterise `REPO` — accept an optional path argument in `main()` — then add `evals/fixtures/bad-skill/`, a skill folder with three planted violations (an extra frontmatter key, a `## Related Skills` entry naming a skill that does not exist, and a `scripts/` path that does not resolve). Assert the validator exits non-zero and that its output contains the three expected `path:line:` diagnostics. That is one fixture and roughly 30 lines in `validate_evals.py`, and it converts every existing check from "runs" to "fires".

4. **P2: no script has a test for a hostile or degenerate `--repo`.**
   Gap: all seven bundled scripts accept `--repo`. Every snapshot points it at one of two well-formed fixtures. Behavior on a path that does not exist, an empty directory, a directory that is not a git repository, a repo with zero documents or zero test files, or a file that is not valid UTF-8 is unspecified and unexercised. "Zero docs" and "zero tests" are the state of a brand-new repository, which is a plausible first-run for `docs_structure.py` and `coverage_map.py` — a first-run crash is the worst possible first impression for a skill.
   Current coverage: the new CI step at `.github/workflows/ci.yml:106` runs every script against this repository in both formats, which adds a second real-world shape beyond the fixtures. It does not cover any degenerate input.
   Confidence: high on the gap; medium on the impact, since I did not run the scripts against those inputs to see whether they exit cleanly.
   Evidence: `--repo` definitions in all seven scripts; snapshot fixtures at `tools/validate_evals.py:40` and the per-entry `fixture` keys at `:58` and `:59`.
   Suggested test: a small parametrised loop in `validate_evals.py` running each script against `tempfile.mkdtemp()` — empty, no git — and asserting exit code 0 with parseable JSON rather than a traceback. Cheap, deterministic, and it does not need a committed fixture.

5. **P2: the canary assertion covers stdout only, and only for snapshot runs.**
   Gap: `tools/validate_evals.py:170` asserts the canary string, `real:secret`, and `SECRET_CANARY` never appear in `proc.stdout`. That is the right check, and it is the repo's best security test. Two things it does not cover: `proc.stderr`, where a traceback quoting a line of a `.env` file would land; and any script run that is not a snapshot entry — including the new all-scripts CI step, which runs all seven against this repository with output redirected to `/dev/null` and asserts nothing about content.
   Current coverage: nine snapshot runs, stdout only.
   Evidence: `tools/validate_evals.py:170`; canary definition `tools/validate_evals.py:66`; the uncovered CI step `.github/workflows/ci.yml:106`.
   Suggested test: extend the existing assertion to `proc.stdout + proc.stderr` — a one-line change — and plant a second canary in a `.env` file inside `mini-py` so both fixtures carry one.

6. **P3: `make_social_preview.py` is unreferenced by any check and silently went stale.**
   Gap: 156 lines, no snapshot, no CI step, no import. Its `SKILLS` list is a hand-maintained copy of the skill folder names, and until this change it listed six skills — two that no longer exist and omitting `docs-structure` entirely. Nothing detected that. The same file's sample finding still said "Security Audit" months after that skill was removed.
   Current coverage: none. `ast.parse` in the CI syntax step is the only thing that touches it.
   Evidence: code `tools/make_social_preview.py:43` (`SKILLS = [`); no reference in `tools/validate_evals.py` or `.github/workflows/ci.yml`.
   Suggested test: a three-line assertion in `validate_skills.py` that `SKILLS` in `make_social_preview.py` matches the `skills/` directory listing, parsed with `ast` rather than imported so Pillow stays optional. It is the same class of check as `check_readme`, which already exists and works.

**Suggested Test Plan**

1. Add `--max-parts 16` to the `docs_split` snapshot args and add a second `docs_split_refuse` entry (finding 1). Smallest change, highest value, makes an existing comment true.
2. Add the `merge()` round-trip snapshot (finding 2). This is the contract the skill advertises.
3. Add `evals/fixtures/bad-skill/` and a negative test for `validate_skills.py` (finding 3). Largest effort, and the one that stops the whole suite from rotting invisibly.
4. Extend the canary assertion to stderr (finding 5). One line.
5. Add the degenerate-`--repo` loop (finding 4) and the `SKILLS` list check (finding 6).

**Untested Or Weakly Tested Areas**

- `tools/` — three files, 811 lines, zero coverage of any kind. The coverage mapper ranks it as the second-largest unmatched directory in the repo.
- `skills/docs-structure/scripts/` — four files, 6,331 lines, the largest unmatched directory. Snapshot coverage exists for all four but exercises one invocation each, and for `docs_split.py` that invocation is a refusal.
- Every error path in every bundled script. The fixtures are well-formed by construction, so `except` branches are reached only by accident.
- The five `behavior` eval cases. They are real tests with `must_include` / `must_not_include` assertions, but they need a model and CI deliberately does not run them (`CONTRIBUTING.md:97` explains why). That is a defensible decision, not a gap — but it means the model-facing half of every skill is checked by hand or not at all.

**Existing Coverage Worth Keeping**

- **Nine snapshots covering all seven bundled scripts**, two of them (`docs_evidence_py`, `docs_structure_py`) against a second fixture in a different language. This is genuinely good: output regressions surface as a readable diff, and the Ubuntu/Windows matrix at `.github/workflows/ci.yml:78` means a line-ending or path-handling difference fails the build.
- **The canary assertion** at `tools/validate_evals.py:170`. A planted secret that no script may ever print is a better test of the "never leak a value" rule than any amount of code review.
- **The write-safety assertion** at `.github/workflows/ci.yml:122`. Running all seven scripts and then asserting `git status --porcelain` is empty is the direct test of the read-only claim, and it now covers every script rather than one.
- **The anti-trigger eval cases** — 10 of the 31. With five overlapping skills, proving a prompt routes *away* from a skill is harder and more valuable than proving it routes toward one.

**Surveyed But Not Deeply Inspected**

- The interiors of `docs_structure.py` (2,914 lines) and `docs_fill_gate.py` (1,499 lines). I read their argument parsers, their module constants and their snapshot output; I did not trace their rule engines to find which rules are actually exercised by the fixtures. "Which of the R-rules does a fixture actually trigger" is the obvious next pass and would likely produce several P2s.
- `evals/fixtures/mini-py/`. Confirmed it backs two snapshots; did not read its planted defects against `evals/fixtures/README.md` to check they are all still reachable.
- The `must_include` / `must_not_include` strings in the five behavior cases, for staleness against the current report formats.

**Checks Run**

- `python skills/test-gap-audit/scripts/coverage_map.py --top 25`: 27 source files, 3 test files, 5 matched (18%), 22 unmatched. Largest unmatched directories: `skills/docs-structure/scripts` (4 files, 6,331 lines), `tools` (3 files, 811 lines).
- `cat evals/snapshots/docs_split.json`: 297 bytes; `"parts": []`, `"files": {}`, `"proof": null`, `"rewrites": 0`, `"refuse": "H2: 14 parts, over maxParts 12; H3: 14 parts, over maxParts 12"`.
- `python skills/docs-structure/scripts/docs_split.py --repo evals/fixtures/mini-app --no-git-root --doc docs/drafted.md --split-at 30 --format json`: `refuse` set, 0 parts, `proof` None — reproduces the snapshot.
- Same command plus `--max-parts 16`: `refuse` None, 14 parts, `proof {'ok': True, 'problems': []}` — confirms the split path works and is simply not selected by the snapshot args.
- `grep -rn -- "--merge" --include=*.py --include=*.yml --include=*.json .`, excluding `docs_split.py` itself: no output.
- `ls evals/snapshots/`: nine files, covering all seven bundled scripts.
- `sed -n '14,25p' tools/validate_skills.py`: `REPO` defined at line 18 from `__file__`; `grep -n "argparse\|sys.argv\|def main" tools/validate_skills.py`: one hit, `def main()` at line 323 — no argument handling.
- `git ls-files | grep -i test`, excluding `evals/fixtures/`: six hits, all skill files, eval JSON, an example report and a doc template — no test code.
- `grep -n "CANARY" tools/validate_evals.py`: definition at line 66, single assertion at line 170 against `proc.stdout`.
- `grep -n "smoke\|assertion" evals/fixtures/README.md`: line 16 lists the zero-assertion smoke test as a deliberate planted defect for this skill.
- `python tools/validate_evals.py`: exit 0 — "5 eval files, 31 cases checked. OK: 0 errors."

**Not Tested**

- I did not run any script against a nonexistent path, an empty directory or a non-UTF-8 file, so finding 4 states the gap but not the consequence.
- I did not execute `merge()` to confirm it works. The finding is that nothing tests it, which is proven by grep; whether it is correct is unknown and is exactly the point.
- The five behavior eval cases were not run — they need a live agent, and `CONTRIBUTING.md:88` describes the checklist workflow for doing that by hand.
- No coverage instrumentation was used. There is no Python test runner configured in this repo, so line coverage numbers do not exist and were not estimated.

**Assumptions**

- I audited the working tree of `fix/docs-structure-layout` with the two-skill removal staged but not committed. The snapshot registry, the CI script step and the `SKILLS` list in `make_social_preview.py` were all edited in that change; findings 1 through 5 are unaffected by it, and finding 6 describes the staleness that change repaired.
- I treated `evals/fixtures/mini-app/tests/smoke.test.js` (1 case, 0 assertions) as a deliberate planted defect rather than a real gap, on the strength of `evals/fixtures/README.md:16`.
