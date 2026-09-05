# `test-gap-audit` on this repository

**Prompt:** "what tests am I missing"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Full-repository test-gap audit of specialone0007/review-skills (7 SKILL.md skills, 5 bundled scripts, 2 validators, eval suite, CI), run with the skill's own scripts/coverage_map.py plus both validators.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Test Gap Audit: whole repository**

No code changed. I inventoried every testable surface in the repo — 7 skills, 5 bundled Python scripts, 2 maintainer validators, the eval suite, and 4 CI jobs — ran `scripts/coverage_map.py`, and ran both validators to see what they actually assert. 14 surfaces inventoried, 8 inspected in depth. No P0s found.

The honest headline: this repo's automated testing is one thing, and it is a good thing — `validate_evals.py` snapshot-tests bundled script output against a deliberately defective fixture. That is real regression protection and it works. The gaps are around its edges: the one script that enforces the repo's write-safety promise is the one script excluded from those snapshots, and the validator that enforces every other rule has nothing testing it at all.

1. **P1: The `--allow-repo-output` write guard has no test, and it is the repo's only guard against a skill writing into a user's repository.**
   Gap: `collect_pr_context.py` refuses to write a report inside the target repo unless `--allow-repo-output` is passed. Nothing exercises either branch of that check — not the allowed path, not the refused path, not the relative-path-resolution that decides which branch you land in (`Path(args.output)` is joined onto `repo` when relative, then `.resolve()`d, so `--output ../x.md` and symlinked repos both hinge on untested logic).
   Current coverage: none. The only CI exercise of this script is `.github/workflows/ci.yml:112`, which runs it with no `--output` at all, so line 230 is never reached.
   Evidence: guard at `skills/pr-branch-summary/scripts/collect_pr_context.py:230`; relative-path join at `:227`; CI invocation at `.github/workflows/ci.yml:112`. `CONTRIBUTING.md:120` makes this the mandated pattern for every future script — "be read-only on the target repo by default, following the `--allow-repo-output` pattern" — so a silent regression here propagates by copy-paste.
   Suggested test: a Python unit test (`tools/tests/test_collect_pr_context.py`, stdlib `unittest` to match the repo's zero-dependency posture) over a `tempfile` git repo. Cases: `--output report.md` inside the repo exits non-zero and writes nothing; the same with `--allow-repo-output` writes the file; `--output <tmpdir outside repo>/r.md` writes without the flag; `--output ../escape.md` resolves outside and is allowed. Assert both the exit code and `os.listdir` of the repo.

2. **P1: `tools/validate_skills.py` enforces the repo's entire quality contract and has no tests, so any rule can stop firing without CI noticing.**
   Gap: 333 lines and roughly two dozen rules — frontmatter shape, name regex, the 5000-char total description budget, report-header format, `## Related Skills` cross-references, bundled-path existence, machine-specific-path detection, README table sync. Every one is a regex or a path check that returns *silently* when it stops matching. There is no fixture that is supposed to fail. A validator whose only observed output is "OK: 0 errors" is indistinguishable from a validator that has quietly become a no-op.
   Current coverage: CI runs it once against the repo's own known-good skills (`.github/workflows/ci.yml:35`). That proves the good case passes. It proves nothing about the bad case failing.
   Evidence: `tools/validate_skills.py:248` (`check_paths_and_links`), `:276` (`check_readme`), `:45` (`REPORT_HEADER_RE`), `:47` (`BUNDLED_PATH_RE`). No test files exist for it — `grep -rn "validate_skills"` across the repo returns four hits, all of them CI or docs invocations, none a test.
   Suggested test: a negative-fixture table test. Add `tools/tests/fixtures/bad-skills/` holding small deliberately-broken skill folders (missing `description`, name with an underscore, a `` `scripts/nope.py` `` reference to a nonexistent file, a `## Related Skills` pointing at a skill that does not exist, a hardcoded `C:\Users\...` path). Parametrize `check_skill` / `check_paths_and_links` over them and assert each produces an error whose message contains the expected substring. This is the highest-leverage test in the repo: it is what keeps every other check honest.

3. **P1: `collect_pr_context.py` is the only bundled script excluded from snapshot tests, and its CI smoke run exercises a degenerate empty diff.**
   Gap: `SNAPSHOT_SCRIPTS` covers 4 scripts; the repo ships 5. The excluded one is also the most stateful — it shells out to git a dozen times, resolves base refs through a fallback chain, optionally runs `git fetch`, and caps diffs. Worse, its CI run passes `--base "$(git rev-parse HEAD)"`, which makes the merge-base equal to HEAD. Every diff, log, and numstat block is therefore empty, and `capped_diff`'s truncation branch (`:95`) can never be taken.
   Current coverage: `.github/workflows/ci.yml:108-117` proves the script exits 0 and leaves the tree clean on an empty comparison. That is worth keeping, but it is a liveness check, not a behavior check.
   Evidence: registry at `tools/validate_evals.py:52` (4 entries, ending `:57`); script count from `ls skills/*/scripts/*.py | wc -l` → `5`; degenerate base at `.github/workflows/ci.yml:113`; untaken truncation branch at `skills/pr-branch-summary/scripts/collect_pr_context.py:95`; ref-fallback chain at `:64`.
   Suggested test: build a scratch git repo in a `tempfile` dir (two branches, a rename, a deleted file, a 3000-line diff) and assert against the markdown: the truncation notice appears when `--max-diff-lines 100`, the commit list contains both subjects, `--base origin/main` resolves through the fallback when only `main` exists locally, and an unresolvable base exits with the `:80` message. No network, no `--fetch`.

4. **P2: Nothing enforces that a new bundled script gets a snapshot, which is exactly how script 5 of 5 ended up uncovered.**
   Gap: `SNAPSHOT_SCRIPTS` is a hand-maintained dict. Adding `skills/<new>/scripts/foo.py` with no snapshot entry produces a green build. The registry drifted once already.
   Current coverage: `validate_cases` checks that every skill directory has an eval file (`tools/validate_evals.py:80`). The equivalent check for scripts does not exist.
   Evidence: `tools/validate_evals.py:52`; the missing-eval-file check it should mirror at `tools/validate_evals.py:80`.
   Confidence: high.
   Suggested test: extend `validate_evals.py` with a check that globs `skills/*/scripts/*.py` and errors on any file not present in `SNAPSHOT_SCRIPTS`, with an explicit opt-out list for scripts that genuinely cannot be snapshotted (and a required one-line reason). Assert the check itself in the validator's own test file from finding 2.

5. **P2: Only the JSON output of the four snapshotted scripts is tested; the default text output — the format an agent actually reads — is never asserted.**
   Gap: `run_script` always passes `--format json` (`tools/validate_evals.py:151`). The text renderers are a separate code path of meaningful size, and they are where the cross-platform console-encoding risk the CI comments call out actually lives. A text renderer could raise `UnicodeEncodeError` on a Windows console, or emit an empty section, and every check stays green.
   Current coverage: the `scripts` CI job compiles them (`.github/workflows/ci.yml:123`) — syntax only, not execution.
   Evidence: JSON-only invocation at `tools/validate_evals.py:151`; the encoding workaround these renderers depend on at `tools/validate_evals.py:33` (mirrored in each script).
   Confidence: high.
   Suggested test: add a second snapshot per script for `--format text` against the same fixture, or — lighter and less brittle — assert that text output is non-empty, contains each expected section heading, and encodes cleanly to `cp1252` with `errors="strict"` on the Windows leg.

6. **P2: Two script flags that change real behavior are never executed.**
   Gap: `docs_drift.py --check-paths` (`skills/docs-sync-audit/scripts/docs_drift.py:445`) and `dependency_audit.py --allow-network` (`skills/security-audit/scripts/dependency_audit.py:479`) are absent from every CI command and from `run_script`'s fixed argument list. `--check-paths` in particular does filesystem work that can crash on a path shape the fixture does not contain.
   Current coverage: none beyond `py_compile`.
   Evidence: `tools/validate_evals.py:151` (the fixed arg list); flag definitions at the two lines above.
   Confidence: high.
   Suggested test: add a `docs_drift --check-paths` snapshot against the fixture — it is deterministic and cheap. Leave `--allow-network` out of CI deliberately, but add a unit test that the flag defaults to off and that the offline path makes no outbound call (assert the network helper is not invoked).

7. **P2: The "read-only on your files" promise is asserted for one script out of five.**
   Gap: the README's Safety section makes this claim for all seven skills, and `CONTRIBUTING.md:120` makes it a requirement for every bundled script. CI checks `git status --porcelain` after running `collect_pr_context.py` only.
   Current coverage: `.github/workflows/ci.yml:115`.
   Evidence: the single-script check at `.github/workflows/ci.yml:115`; the repo-wide promise at `CONTRIBUTING.md:120`.
   Confidence: high.
   Suggested test: move the porcelain assertion into a loop that runs all five scripts against the fixture and checks the tree after each. Note the ordering constraint: the `py_compile` step at `.github/workflows/ci.yml:123` writes `__pycache__` into `skills/`, so the clean-tree assertions must stay ahead of it (they currently do, by accident rather than by comment).

8. **P2: No error-path tests. Every script is only ever run against a well-formed fixture.**
   Gap: `resolve_repo` raises `SystemExit` outside a git repo (`skills/pr-branch-summary/scripts/collect_pr_context.py:47`); the survey scripts take `--repo` pointing anywhere. Behavior on a nonexistent path, an empty directory, a repo with zero test files, or a file that is not valid UTF-8 is unspecified and unexercised. For `coverage_map.py` specifically, "zero test files" is the state of a brand-new repo — a plausible first-run crash.
   Current coverage: none.
   Evidence: `skills/pr-branch-summary/scripts/collect_pr_context.py:47`; `--repo` definitions at `skills/test-gap-audit/scripts/coverage_map.py:383` and the three sibling scripts.
   Confidence: medium — these may degrade gracefully; I read the entry points but did not execute the failure cases.
   Suggested test: a small table test running each script with `--repo <empty tmpdir> --no-git-root`, asserting exit 0 and valid JSON with zeroed counts, plus `collect_pr_context.py --repo <non-git tmpdir>` asserting exit 1 and the "Not inside a git repository" message.

9. **P3: `tools/make_social_preview.py` is not run, not compiled, and not referenced anywhere.**
   Gap: 156 lines that generate `assets/social-preview.png`, a committed binary. Nothing verifies the committed PNG still matches what the generator produces, and the syntax check at `.github/workflows/ci.yml:123` globs `find skills -name '*.py'`, which excludes `tools/` entirely. The other two `tools/` scripts are covered incidentally because CI executes them; this one is not.
   Current coverage: none.
   Evidence: `tools/make_social_preview.py:77`; the `skills`-scoped find at `.github/workflows/ci.yml:123`. `grep -rn "make_social_preview" --include=*.yml --include=*.md --include=*.json .` returns no hits.
   Confidence: high.
   Suggested test: widen the `find` to `find skills tools -name '*.py'` (one-line fix, and it is the cheapest finding here), and optionally add a check that regenerating the preview into a temp path yields bytes identical to the committed asset.

10. **P3: `validate_evals.py --checklist` is never executed in CI.**
    Gap: the manual-eval path is the documented tier-2 workflow (`CONTRIBUTING.md:90`), and it is a distinct code path that indexes into case dicts. A malformed case could crash it, and nobody finds out until a maintainer tries to run the checklist.
    Current coverage: none — CI runs the validator in default mode only (`.github/workflows/ci.yml:88`).
    Evidence: `tools/validate_evals.py:205` (`checklist`); `tools/validate_evals.py:212` (the per-case print).
    Confidence: high.
    Suggested test: add `python tools/validate_evals.py --checklist > /dev/null` as a CI step. One line, catches every crash in that path.

**Suggested Test Plan**

Do these in order — the first two are the ones that change the repo's risk profile.

1. `tools/tests/test_validate_skills.py` with a `bad-skills/` negative fixture, one assertion per rule. This is the keystone: it is what stops the rest of the suite from silently rotting.
2. `tools/tests/test_collect_pr_context.py` over a temp git repo: the `--allow-repo-output` guard (both branches), diff truncation, base-ref fallback, unresolvable base.
3. Widen `find skills` to `find skills tools` at `.github/workflows/ci.yml:123`, and add `--checklist` as a CI step. Two lines, two findings closed.
4. Add the registry-completeness check to `validate_evals.py` so script 6 cannot repeat script 5's escape.
5. Loop the clean-tree assertion over all five scripts, keeping it ahead of the `py_compile` step.
6. Add a `docs_drift --check-paths` snapshot, and text-format assertions for the four snapshotted scripts.
7. Error-path table test: empty repo, non-git dir, missing path.

**Untested Or Weakly Tested Areas**

- `tools/validate_skills.py` (333 lines) — no tests, no negative fixture.
- `tools/make_social_preview.py` (156 lines) — not executed, not syntax-checked, unreferenced.
- `skills/pr-branch-summary/scripts/collect_pr_context.py` (245 lines) — smoke run on an empty diff only; excluded from snapshots.
- Text-format output of all four snapshotted scripts.
- Every script's error and empty-input path.
- `validate_evals.py --checklist` and `--update-snapshots` modes.

**Existing Coverage Worth Keeping**

- The snapshot suite (`tools/validate_evals.py:171`) is genuinely good regression protection: it runs the real scripts against a real fixture and compares exact bytes, with per-key diff reporting at `:196` so a failure says what broke. The `drop` mechanism at `:166` for machine-dependent keys is the right call.
- Running it on both Ubuntu and Windows (`.github/workflows/ci.yml:94-97`) is what makes byte-exact snapshots viable, and `.gitattributes` pinning fixture line endings closes the loop.
- The structural eval checks are stronger than most repos bother with: requiring an anti-trigger case (`tools/validate_evals.py:141`) and a behavior case (`:143`) per skill means routing between seven overlapping skills is at least specified, even though a model is needed to run it.
- `evals/fixtures/README.md` documents every planted defect and which skill should catch it. That is what makes the fixture a test rather than a pile of bad code.

**Surveyed But Not Deeply Inspected**

- The internal logic of `docs_drift.py` (475 lines), `dependency_audit.py` (514), `repo_inventory.py` (378), and `coverage_map.py` (417). Snapshots pin their *output* on one fixture; none of their branching is unit-tested. A focused pass on any one of them would likely find untested detection rules — `dependency_audit.py` is the one I would run next, since it carries the severity logic the fixture README says was already corrected once after a real-repo trial.
- The seven `agents/openai.yaml` files. `validate_skills.py` parses them (`:128`), but I did not check how much of their content is actually constrained.
- `.claude-plugin/marketplace.json` and `plugin.json`, which are validated only by the first-party CLI job.

**Checks Run**

- `git status --short` (session start): clean.
- `python skills/test-gap-audit/scripts/coverage_map.py --top 25`: 17 source files, 3 test files, 4 matched (24%), 13 unmatched; Vitest detected; flagged `evals/fixtures/mini-app/tests/smoke.test.js` as 1 case / 0 assertions.
- `ls skills/*/scripts/*.py | wc -l`: `5`.
- `python tools/validate_skills.py`: `7 skills checked. Descriptions total 3797/5000 chars. OK: 0 errors, 0 warning(s).`
- `python tools/validate_evals.py`: `7 eval files, 27 cases checked. OK: 0 errors.`
- `grep -rn "make_social_preview" --include=*.yml --include=*.md --include=*.json .`: no matches (exit 1).
- `grep -rn "validate_skills" --include=*.py --include=*.yml --include=*.md .`: 4 matches, all invocations (`.github/workflows/ci.yml:28`, `CONTRIBUTING.md:10`, `README.md:112`, and the script's own docstring) — none a test.

**Not Tested**

- I did not execute any script against a malformed or empty repository, which is why finding 8 carries medium confidence rather than high. Doing so writes nothing, but it was outside what I could confirm in this pass.
- I did not run `--update-snapshots`, `--allow-network`, or `--fetch`: all three either write to the repo or reach the network.
- I did not run `python -m py_compile` or `compileall`, since they emit `.pyc` files into the tree — gitignored, so `git status` would have looked clean while the tree was modified.
- Tier-2 evals need a live model per `tools/validate_evals.py:18`. Nothing in this audit says whether the skills' *reports* meet their contracts; only whether the code around them is tested.

**Assumptions**

- The unmatched files `coverage_map.py` reported under `evals/fixtures/mini-app/` are **not** gaps. `evals/fixtures/README.md` states that `exports.js` and `admin.js` having no tests, and `smoke.test.js` having no assertions, are planted defects the eval cases depend on. The script found exactly what it was supposed to find in the fixture. I excluded all of them from the findings above.
- One thing you should know: `.github/workflows/ci.yml` was modified between my first `git status` (clean) and a later one, adding a Windows matrix leg to the `validate` job. That was not me — this audit ran read-only and I made no edits. Another process or session is touching the file. All my `ci.yml` line citations are against the current on-disk version, which now has the `validate` job at lines 15-35; if that change is reverted, the line numbers in findings 3, 5, 7, 9, and 10 shift by 8.

