# `repo-health-audit` on this repository

**Prompt:** "is this codebase getting messy"  
**Repository:** `specialone0007/review-skills`, branch `fix/docs-structure-layout` on top of `5597942`, with the removal of `feature-brainstorm` and `pr-branch-summary` applied  
**Files changed by the run:** none — the skill is read-only

Full-repository read-only health audit of review-skills (116 tracked files: 5 skills, 7 bundled scripts, 3 maintainer tools, eval suite, CI), running the bundled repo_inventory.py plus both validators and reading all seven bundled scripts and the CI workflow end to end.

Re-run it yourself and compare. Line numbers refer to the tree described above, so a later commit will shift them.

---

**Repo Health Audit: whole repository (review-skills)**

No code changed. I checked the full repo — 116 tracked files across `skills/` (5 skills), `tools/` (3 maintainer scripts), `evals/`, `examples/`, `.github/`, and the two plugin manifests — for naming drift, file/folder placement, module boundaries, dead code, duplicate code, helper extraction opportunities, and convention drift. I ran the bundled inventory script, both validators, and read all seven bundled scripts plus CI end to end. No P0s found.

**Short answer: not messy, but the weight has shifted.** Both validators pass with zero errors and zero warnings, every skill folder still has the same three-part shape, and nothing is dead or orphaned. What has changed since the last audit is proportion: one skill now carries four scripts and 79% of all bundled-script code, and the helper copies those four scripts share with each other have drifted apart in ways the repo's own self-containment rule does not excuse.

1. **P2: `docs-structure` holds 79% of the bundled-script code, and its four scripts duplicate each other's helpers in a place where the self-containment rule does not apply.**
   `CONTRIBUTING.md:119` requires each script to "be self-contained inside their own skill, since people install skills individually". That rule justifies copying a helper *across* skills — `docs-sync-audit` and `test-gap-audit` install separately, so each needs its own `run_git`. It does not justify copying one *within* a skill. `docs_structure.py` and `docs_evidence.py` ship in the same folder, install together, and are never separable, yet each defines its own `walk()` — `skills/docs-structure/scripts/docs_evidence.py:137` and `skills/docs-structure/scripts/docs_structure.py:385` — with different defaults (`max_depth=14` vs `max_depth=12`) and different skip sets (16 names vs 5). The practical effect: pointed at the same repository, `docs_evidence.py` skips `dist`, `build`, `target` and `.next`, and `docs_structure.py` walks straight into them. Nothing in the SKILL.md or `CONTRIBUTING.md` explains why the two halves of one feature should see different trees.
   What makes this a confirmed inconsistency rather than a style opinion: **the folder already shares code this way, and `walk()` was copied anyway.** `skills/docs-structure/scripts/docs_split.py:33` does `import docs_structure as ds`; `skills/docs-structure/scripts/docs_structure.py:69` and `skills/docs-structure/scripts/docs_fill_gate.py:58` both do `import docs_evidence`, each with the same inline comment — "sibling script, same folder, stdlib only". So the pattern is established, deliberate and commented. Three of the four scripts use it. The two `walk()` implementations are a copy made inside a folder where the shared-import route was already open.
   The size imbalance is the context that makes this matter. `docs-structure`'s four scripts are 6,327 lines against 1,730 for the other three script-carrying skills combined, and `docs_structure.py` alone is 2,913 lines — seven times the next-largest script outside the folder.
   Evidence: `skills/docs-structure/scripts/docs_evidence.py:137`, `skills/docs-structure/scripts/docs_structure.py:385`, `skills/docs-structure/scripts/docs_evidence.py:65` (`ALWAYS_SKIP`, 16 names), `skills/docs-structure/scripts/docs_structure.py:79` (`ALWAYS_SKIP`, 5 names), the existing sibling imports at `skills/docs-structure/scripts/docs_split.py:33`, `skills/docs-structure/scripts/docs_structure.py:69`, `skills/docs-structure/scripts/docs_fill_gate.py:58`, and `CONTRIBUTING.md:119`.
   Suggested cleanup direction: `docs_evidence.py` already has the richer `walk()` and is already imported by the other two — have `docs_structure.py` call it instead of defining its own, which is a deletion rather than a new file. Then add a line to `CONTRIBUTING.md` saying explicitly that a sibling import *inside* one skill folder is allowed and a shared module *across* skill folders is not, since that rule currently lives only in three code comments. Snapshot tests will show exactly what unifying the skip set does to fixture output, which is the point of having them.

2. **P2: the same directory-skip list has three names and seven different contents across seven scripts.**
   Counting the module-level definitions: `IGNORED_DIRS` with 26 entries at `skills/repo-health-audit/scripts/repo_inventory.py:37` and `skills/test-gap-audit/scripts/coverage_map.py:39`; `SKIP_DIRS` with 14 at `skills/docs-structure/scripts/docs_fill_gate.py:248`, 13 at `skills/docs-sync-audit/scripts/docs_drift.py:53`, and 12 at `skills/docs-structure/scripts/docs_split.py:38`; `ALWAYS_SKIP` with 16 at `skills/docs-structure/scripts/docs_evidence.py:65` and 5 at `skills/docs-structure/scripts/docs_structure.py:79`. Only the two 26-entry sets are identical.
   This is behavioral, not cosmetic. Against the 26-entry baseline, the three `SKIP_DIRS` copies all omit `.gradle`, `.hg`, `.idea`, `.nuxt`, `.ruff_cache`, `.svelte-kit`, `.svn` and `.vscode`; `docs_split.py` and `docs_drift.py` additionally omit `.mypy_cache`, `.pytest_cache` and `.tox`, and both add `site-packages`, which no other script has. So on one repository the docs scripts and the inventory scripts disagree about whether `out/`, `.tox/` and `.svelte-kit/` are part of the codebase. The divergence reads as organic rather than designed.
   The duplication itself is correct and deliberate — see finding 1 for where it is not. The problem is only that the copies have been allowed to drift.
   Evidence: the seven definitions cited above.
   Suggested cleanup direction: pick one name (`IGNORED_DIRS` is the clearest word and already has two users) and one canonical set, paste it into all seven, and note in `CONTRIBUTING.md` that the block is deliberately duplicated and must be updated everywhere together. `site-packages` looks like a real addition worth keeping in the canonical set rather than dropping.

3. **P2: `run_git` exists four times with three different argument orders.**
   `skills/docs-structure/scripts/docs_evidence.py:290` takes `(repo, args)`. `skills/docs-sync-audit/scripts/docs_drift.py:177` takes `(args, cwd)`. `skills/repo-health-audit/scripts/repo_inventory.py:84` and `skills/test-gap-audit/scripts/coverage_map.py:113` take `(args, repo)`. Three names for the second parameter and two orders for the same two values.
   Duplication across skills is required, so four copies are fine. Four copies with *incompatible signatures* are not: the copies exist so a fix found in one can be carried to the others, and a reviewer porting a timeout or encoding fix from `repo_inventory.py` into `docs_evidence.py` has to notice the arguments are reversed. That is the kind of difference a careful person misses, and neither validator nor snapshot would catch a silently swapped pair — `run_git(repo, args)` called as `run_git(args, repo)` fails at the subprocess boundary, not at import.
   Evidence: `skills/docs-structure/scripts/docs_evidence.py:290`, `skills/docs-sync-audit/scripts/docs_drift.py:177`, `skills/repo-health-audit/scripts/repo_inventory.py:84`, `skills/test-gap-audit/scripts/coverage_map.py:113`.
   Suggested cleanup direction: converge all four on `(args, repo)`, which two already use, and rename `cwd` to `repo` in `docs_drift.py`. Pure rename, no behavior change, and it makes the copies diffable against each other.

4. **P3: the "Scripts must:" contract is six rules of prose; the validator mechanically checks one of them.**
   `CONTRIBUTING.md:116` opens a six-item list every bundled script must satisfy. `tools/validate_skills.py` defines four check functions — `check_skill` at `:148`, `check_subprocess_encoding` at `:253`, `check_paths_and_links` at `:269`, `check_readme` at `:302`. Only `check_subprocess_encoding` inspects script bodies at all, and it covers one rule (subprocess decoding). `--format text|json`, the stdout reconfigure, `shell=True`, and `shutil.which` are checked by nobody. `BUNDLED_PATH_RE` at `:47` only confirms that a path a SKILL.md mentions exists.
   Today the contract happens to hold — all seven scripts have `--format` and the reconfigure guard, and `shell=True` appears nowhere. That is a better state than the last audit found, but it is held by hand, and findings 1 through 3 are all drift the hand-checking did not catch.
   Evidence: `CONTRIBUTING.md:116`, `tools/validate_skills.py:148`, `tools/validate_skills.py:253`, `tools/validate_skills.py:269`, `tools/validate_skills.py:302`, `tools/validate_skills.py:47`.
   Suggested cleanup direction: extend `check_subprocess_encoding` into a `check_bundled_scripts()` covering the three remaining mechanically checkable rules — a `--format` argument exists, `reconfigure` is present or the file is pure ASCII, and `shell=True` appears nowhere. Roughly 20 lines, standard library only, matching the existing `path:line: message` style. A skip-set consistency check would catch finding 2 as a bonus.

5. **P3: `evals/results/` is a convention nothing in the repo documents.**
   Three dated JSON files live there — `2026-09-03-opus-5.json`, `2026-09-05-real-code-trial.json`, `2026-09-16-fill-trial.json`. `grep -rn "results/"` over the tracked Markdown, Python and YAML finds no reference outside `examples/`, which is generated output. `CONTRIBUTING.md` has the natural home for it — `## Trialling the skills on real code` at `:99` — and does not mention the folder, its filename shape, or whether anything validates it. A contributor who runs a trial has nowhere to learn that writing the result down is the convention.
   Evidence: `CONTRIBUTING.md:99`; `grep -n "results" CONTRIBUTING.md` returns nothing; the three files under `evals/results/`.
   Suggested cleanup direction: two sentences in that section naming `evals/results/<date>-<label>.json`, saying it is hand-written and not validated by CI, and saying what the fields mean. This one is really `docs-sync-audit`'s territory; it is listed here because the folder reads as orphaned from a structure pass.

**What is genuinely in good shape**

- **The script contract is now uniformly met.** All seven bundled scripts accept `--format text|json`, all seven call `sys.stdout.reconfigure`, and `grep -rn "shell=True" skills/ tools/` returns nothing. The previous audit's three-way contract violation left with the script that carried it.
- **CI no longer writes into the tree it checks.** `.github/workflows/ci.yml:135` uses `ast.parse` rather than `py_compile`, so the syntax check emits no `.pyc`. The step above it runs every bundled script against the checkout in both formats and then asserts `git status --porcelain` is empty — the read-only claim is now tested for all seven scripts rather than one.
- **Naming.** All five skill folders are kebab-case and match their `SKILL.md` `name:` field; all seven bundled scripts are snake_case; the folder shape (`SKILL.md` + `agents/openai.yaml` + optional `scripts/`/`references/`) is identical across all five with no exceptions.
- **No dead code found.** Every tracked file is reachable: skills from the manifests, scripts from their SKILL.md and from `SNAPSHOT_SCRIPTS` at `tools/validate_evals.py:51`, fixtures from the same file, `assets/social-preview.png` from `tools/make_social_preview.py`. `evals/results/` is the only directory nothing references, and it is an intentional archive, not orphaned code — see finding 5.
- **No catch-all folders in source.** The only `utils`/`lib` directories the inventory flagged are `evals/fixtures/mini-app/src/utils` and `.../src/lib`, which are the deliberately defective fixture. No directory has 25 or more direct children.
- **Both validators are green** with zero warnings, and CI covers Ubuntu and Windows on three of four jobs, each with a load-bearing comment explaining why.

**Reuse Opportunities**

- `truncate(items, limit, label, out)` is byte-identical — all five lines — at `skills/repo-health-audit/scripts/repo_inventory.py:253` and `skills/test-gap-audit/scripts/coverage_map.py:330`. Leave it duplicated; self-containment is required across skills. It belongs in whatever "keep these copies in sync" note comes out of finding 2.
- `list_files(repo)` has the same shape at `skills/docs-sync-audit/scripts/docs_drift.py:191`, `skills/repo-health-audit/scripts/repo_inventory.py:103`, and `skills/test-gap-audit/scripts/coverage_map.py:129`. Same story as `run_git`: keep the copies, converge them.
- Read-cap naming drift in the same family: `MAX_READ` at `docs_evidence.py:61` (1,500,000), `docs_fill_gate.py:66` (2,000,000), `docs_structure.py:76` (2,000,000) and `docs_drift.py:50` (2,000,000), versus `MAX_READ_BYTES` at `coverage_map.py:37` (400,000). Two names, and a 5× spread in the value with nothing recording why. Worth folding into one sync pass.

**Surveyed But Not Deeply Inspected**

- The interior of `docs_structure.py` (2,913 lines). I read its `walk()`, its module constants, and its argument parser; I did not trace its rule engine. Whether that file should itself be split is the obvious next question and this pass does not answer it.
- The five `evals/*.json` case files (31 cases). Confirmed they validate and are one-per-skill; did not read the rubrics for overlap or staleness.
- The prose bodies of the five `SKILL.md` files, for cross-skill contradiction or duplicated instruction blocks. I read `repo-health-audit/SKILL.md` in full and skimmed the rest. A dedicated "do the five skills contradict each other" pass is worth a run.
- `skills/docs-structure/references/structure.md` (326 lines) — confirmed reachable from its SKILL.md, not read closely.

**Checks Run**

- `python skills/repo-health-audit/scripts/repo_inventory.py --top 25`: 116 files, 14,882 lines, 3 test files, 20 doc files; no directory with 25+ direct children; catch-all names only inside the eval fixture.
- `git ls-files | wc -l`: 116 tracked files.
- `wc -l skills/*/scripts/*.py tools/*.py | sort -rn`: `docs_structure.py` 2913, `docs_fill_gate.py` 1498, `docs_evidence.py` 1289, `docs_drift.py` 937, `docs_split.py` 627, `coverage_map.py` 416, `repo_inventory.py` 377; maintainer tools 368/285/155.
- Python sum over `skills/**/scripts/*.py`: docs-structure 6,327 lines, other skills 1,730, share 79%.
- Regex scan for `^(IGNORED_DIRS|SKIP_DIRS|ALWAYS_SKIP)\s*=\s*\{`: seven definitions, sizes 26, 26, 16, 14, 13, 12, 5. Set difference against the 26-entry baseline produced the omitted names listed in finding 2.
- `grep -n "^def run_git" skills/*/scripts/*.py`: four hits, at `docs_evidence.py:290`, `docs_drift.py:177`, `repo_inventory.py:84`, `coverage_map.py:113`; signatures read off those lines.
- `grep -Ln "reconfigure" skills/*/scripts/*.py tools/*.py`: two files lack it, both maintainer tools (`make_social_preview.py`, `validate_skills.py`), no bundled script.
- `grep -Ln '"--format"' skills/*/scripts/*.py`: no output — every bundled script defines it.
- `grep -rn "shell=True" skills/ tools/`: no output.
- Python function-body comparison of `truncate` in `repo_inventory.py` and `coverage_map.py`: identical, 5 lines.
- `grep -n "^def check_" tools/validate_skills.py`: four functions, at `:148`, `:253`, `:269`, `:302`.
- `grep -rn "results/" --include=*.md --include=*.py --include=*.yml .`: four hits, all inside `examples/`.
- `grep -n "results" CONTRIBUTING.md`: no output.
- `python tools/validate_skills.py`: exit 0 — "5 skills checked. Descriptions total 3407/5000 chars. OK: 0 errors, 0 warning(s)."
- `python tools/validate_evals.py`: exit 0 — "5 eval files, 31 cases checked. OK: 0 errors."

**Not Tested**

- No dependency-graph, dead-code, or duplicate-code tooling was installed or run. Dead-code and duplication conclusions come from `git ls-files` plus targeted grep, regex extraction and manual import tracing across a 116-file repo, which is small enough for that to be reliable, but they are not tool-confirmed.
- I did not run the two `walk()` implementations side by side against a repo containing `dist/` to demonstrate the divergence in finding 1 empirically. What is proven: the two skip sets differ by 11 names, and both functions prune `dirnames` from their skip set.
- No linter or type checker was run; the repo ships neither config, so there is nothing to run.
- I did not run `py_compile` or `compileall`, per this skill's own rule against commands that write into the tree.

**Assumptions**

- I audited the working tree of `fix/docs-structure-layout` with the two-skill removal staged but not committed, because that is the state the repository is in. Line numbers hold once it is committed; if the removal is reverted, findings 2 and 3 gain back a copy each.
- I treated `evals/fixtures/mini-app/` and `evals/fixtures/mini-py/` as deliberately defective fixtures rather than production source, so their duplicate helpers, `utils/misc.js` and unused exports are not reported. `evals/fixtures/README.md` and `tools/validate_evals.py` support that reading.
