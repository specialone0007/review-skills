# `repo-health-audit` on this repository

**Prompt:** "is this codebase getting messy"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Full-repository read-only health audit of review-skills (62 tracked files: 7 skills, 5 bundled scripts, 3 maintainer tools, eval suite, CI), running the bundled repo_inventory.py plus both validators and reading all five scripts and the CI workflow end to end.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Repo Health Audit: whole repository (review-skills)**

No code changed. I checked the full repo — 62 tracked files across `skills/` (7 skills), `tools/` (3 maintainer scripts), `evals/`, `examples/`, `.github/`, and the two plugin manifests — for naming drift, file/folder placement, module boundaries, dead code, duplicate code, helper extraction opportunities, and convention drift. I ran the bundled inventory script, both validators, and read all five bundled scripts plus CI end to end. No P0s found.

**Short answer: no, it is not getting messy.** The layout is clean and self-describing, both validators pass with zero errors and zero warnings, every skill folder has the same three-part shape, and nothing is dead or orphaned. The four findings below are all convention drift concentrated in one place, not structural rot.

1. **P2: CI's last step writes `.pyc` files into the working tree, which is the exact thing this repo's own skill tells agents never to do.**
   `.github/workflows/ci.yml:123` runs `find skills -name '*.py' -print0 | xargs -0 -n1 python -m py_compile`. `py_compile` emits `__pycache__/*.pyc` next to each source file. `skills/repo-health-audit/SKILL.md:107` warns against precisely this: "`python -m compileall` and `py_compile` emit `.pyc` files ... `.pyc` output is usually gitignored, so `git status` will look clean while the tree has in fact been modified." The repo is living proof — my checkout has `skills/docs-sync-audit/scripts/__pycache__/docs_drift.cpython-314.pyc` and `skills/security-audit/scripts/__pycache__/dependency_audit.cpython-314.pyc`, both hidden by `.gitignore:1`. It also sits 8 lines after `.github/workflows/ci.yml:115`, `test -z "$(git status --porcelain)"`, a step whose whole point is asserting the tree was untouched. Nothing breaks today, because the two steps are ordered and `.pyc` is ignored — but the repo publishes this rule to other people's agents and then breaks it in its own CI, and reordering those steps would be a confusing red build.
   Evidence: `.github/workflows/ci.yml:123`, `.github/workflows/ci.yml:115`, `skills/repo-health-audit/SKILL.md:107`, `.gitignore:1`.
   Suggested cleanup direction: replace the `py_compile` sweep with a check that writes nothing — `python -c "import ast,pathlib,sys; [ast.parse(p.read_text(encoding='utf-8'), str(p)) for p in pathlib.Path('skills').rglob('*.py')]"` gives the same syntax guarantee with no output files. Judgment call on urgency; the inconsistency is confirmed.

2. **P2: `collect_pr_context.py` is the one bundled script sitting outside the shared script contract, in three separate ways at once.**
   `CONTRIBUTING.md:116` opens a "Scripts must:" list that the other four bundled scripts follow uniformly. `collect_pr_context.py` misses three items:
   - No `--format text|json`, required by `CONTRIBUTING.md:121`. Its parser at `skills/pr-branch-summary/scripts/collect_pr_context.py:100` defines `--base`, `--repo`, `--fetch`, `--fetch-remote`, `--prune`, `--output`, `--allow-repo-output` — no `--format`. The other four all have it: `skills/repo-health-audit/scripts/repo_inventory.py:340`, `skills/test-gap-audit/scripts/coverage_map.py:384`, `skills/docs-sync-audit/scripts/docs_drift.py:441`, `skills/security-audit/scripts/dependency_audit.py:475`.
   - No `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`, required by `CONTRIBUTING.md:122`. The other four have it at `repo_inventory.py:31`, `coverage_map.py:33`, `docs_drift.py:45`, `dependency_audit.py:43`. The rule's escape clause is "or stay strictly ASCII", and the file's own source *is* strictly ASCII — but that clause protects source literals, and this script's job is printing a live `git diff` and branch names to stdout. One non-ASCII character in a real diff crashes it on a default Windows console, which is the failure the rule exists to prevent.
   - It is the only bundled script with no snapshot test. `SNAPSHOT_SCRIPTS` at `tools/validate_evals.py:52` lists four scripts; this one is absent. CI does smoke-run it (`.github/workflows/ci.yml:108`), so it is not untested — but it is the only one where an output regression would pass CI silently.
   Evidence: as cited above.
   Suggested cleanup direction: add the two-line `reconfigure` guard first (smallest fix, real Windows risk), then `--format json` alongside the existing markdown render, then add it to `SNAPSHOT_SCRIPTS` with the machine-dependent keys in `drop`.

3. **P2: the four repo-walking scripts use two different names, and two different contents, for the same directory-ignore list.**
   `repo_inventory.py:37` and `coverage_map.py:39` call it `IGNORED_DIRS` with 24 entries; `docs_drift.py:52` and `dependency_audit.py:111` call it `SKIP_DIRS` with 12 and 11. The short lists omit `.hg`, `.svn`, `env`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.tox`, `out`, `.nuxt`, `.svelte-kit`, `.idea`, `.vscode`, `.gradle`, and `Pods`; `docs_drift` alone adds `site-packages`. That is a behavioral difference, not cosmetics: on the same repository the docs and dependency scripts will walk into `out/`, `.tox/`, and `.svelte-kit/` while the inventory and coverage scripts skip them. The divergence reads as organic rather than designed — nothing in `CONTRIBUTING.md` or the SKILL files explains why one audit should see build output and another should not.
   To be clear about what is *not* a finding: the duplication itself is correct and deliberate. `CONTRIBUTING.md:119` requires each script to "be self-contained inside their own skill, since people install skills individually", so the copied `run_git`, `list_files`, `read`, and `truncate` helpers are the right call. A shared `tools/` module would break single-skill installs. The problem is only that the copies have been allowed to drift apart.
   Evidence: `skills/repo-health-audit/scripts/repo_inventory.py:37`, `skills/test-gap-audit/scripts/coverage_map.py:39`, `skills/docs-sync-audit/scripts/docs_drift.py:52`, `skills/security-audit/scripts/dependency_audit.py:111`, `CONTRIBUTING.md:119`.
   Suggested cleanup direction: pick one name (`IGNORED_DIRS` is used by two and is the clearer word) and one canonical set, paste it into all four, and add a note in `CONTRIBUTING.md` that the block is deliberately duplicated and must be updated in all four together. The snapshot tests will show you exactly what the content change does to fixture output.

4. **P3: the "Scripts must:" contract is prose only — no validator enforces it, which is why findings 2 and 3 exist.**
   `tools/validate_skills.py` is thorough about `SKILL.md`: frontmatter keys, name and description limits, body line count, README cross-references. Its only contact with bundled scripts is `BUNDLED_PATH_RE` at `tools/validate_skills.py:47`, which checks that a path a SKILL.md mentions actually exists. Nothing checks `--format`, the stdout reconfigure, `shell=True`, or `shutil.which`. With seven skills and five scripts that is still manageable by hand; the drift in finding 2 shows the hand-checking has already slipped once.
   Evidence: `tools/validate_skills.py:47`, `CONTRIBUTING.md:116`-`124`.
   Suggested cleanup direction: add a `check_bundled_scripts()` to `tools/validate_skills.py` covering the three mechanically checkable rules — a `--format` argument exists, `reconfigure` is present or the file is pure ASCII, and `shell=True` appears nowhere. Roughly 20 lines, standard library only, matching the existing `path:line: message` output style.

**What is genuinely in good shape**

- **Top-level layout.** Eight directories, each with one obvious job, no catch-all. The only `utils`/`lib` folders the inventory flagged are `evals/fixtures/mini-app/src/utils` and `.../src/lib` — those are the deliberately defective test fixture, and being a bad example is their purpose.
- **Naming.** All seven skill folders are kebab-case and match their `SKILL.md` `name:` field; all five bundled scripts are snake_case; the folder shape (`SKILL.md` + `agents/openai.yaml` + optional `scripts/`) is identical across all seven with no exceptions.
- **No dead code found.** Every tracked file is reachable: skills from the manifests, scripts from their SKILL.md and from `SNAPSHOT_SCRIPTS`, fixtures from `validate_evals.py:38`, `assets/social-preview.png` from `tools/make_social_preview.py`. `evals/results/` is the only directory nothing references, and it is an intentional archive of dated trial write-ups, not orphaned code.
- **Docs match structure.** `README.md:40` points at `examples/`, which exists with one complete run; `README.md:95` describes the folder shape accurately; `README.md` says "seven skills" and the validator counts seven.
- **Both validators are green** with zero warnings, and CI covers Ubuntu and Windows on three of four jobs with load-bearing comments explaining why.

**Reuse Opportunities**

- `truncate(items, limit, label, out)` is byte-identical at `repo_inventory.py:253` and `coverage_map.py:330`. Leave it duplicated — self-containment is required — but it belongs in whatever "keep these copies in sync" note comes out of finding 3.
- `run_git` exists three times with the same signature and semantics (`repo_inventory.py:84`, `coverage_map.py:113`, `docs_drift.py:99`) and a fourth, differently-shaped variant at `collect_pr_context.py:14`. Same story: keep the copies, but converge them so a fix in one is trivially portable to the others.
- Minor naming drift in the same family: `MAX_READ` (`docs_drift.py:49`, `dependency_audit.py:47`) vs `MAX_READ_BYTES` (`coverage_map.py:37`); `GIT_TIMEOUT` (three files) vs `TIMEOUT` (`dependency_audit.py:46`); argparse variable `parser` in two scripts vs `ap` in three. Individually trivial, worth folding into one sync pass.

**Surveyed But Not Deeply Inspected**

- The seven `evals/*.json` case files (27 cases). I confirmed they validate and are one-per-skill, but did not read the rubrics for overlap or staleness. Worth a pass if you want to know whether trigger/anti-trigger cases have drifted from the current descriptions.
- The prose bodies of the seven `SKILL.md` files, for cross-skill contradiction or duplicated instruction blocks. I read `repo-health-audit/SKILL.md` in full and skimmed the rest. A dedicated "do the seven skills contradict each other" pass would be a good next run.
- `tools/make_social_preview.py` and `assets/social-preview.png` — confirmed reachable, not read closely.

**Checks Run**

- `python skills/repo-health-audit/scripts/repo_inventory.py --top 25`: 62 files, 5382 lines, 3 test files, 4 doc files; no directory with 25+ direct children; catch-all names only inside the eval fixture.
- `git ls-files | wc -l`: 62 tracked files.
- `git ls-files | grep -i pyc`: no output — no compiled artifacts are committed.
- `git check-ignore -v skills/docs-sync-audit/scripts/__pycache__/docs_drift.cpython-314.pyc`: matched by `.gitignore:1:__pycache__/`, confirming the tree can be modified while `git status` reads clean.
- `ls -la skills/docs-sync-audit/scripts/__pycache__/ skills/security-audit/scripts/__pycache__/`: two `.pyc` files present in my working tree.
- `python tools/validate_skills.py`: exit 0 — "7 skills checked. Descriptions total 3797/5000 chars. OK: 0 errors, 0 warning(s)."
- `python tools/validate_evals.py`: exit 0 — "7 eval files, 27 cases checked. OK: 0 errors."
- `grep -n "IGNORED_DIRS\|SKIP_DIRS\|def run_git\|def list_files\|ArgumentParser" skills/*/scripts/*.py`: produced the four ignore-set definitions and the parser lines cited above.
- `grep -Ln "reconfigure" skills/*/scripts/*.py tools/*.py`: three files lack it — `collect_pr_context.py`, `tools/make_social_preview.py`, `tools/validate_skills.py`.
- Python scan for bytes above U+007F in those three files: 0 hits each, confirming all three are strictly ASCII in source.
- `grep -rn "examples/" --include=*.md --include=*.py --include=*.yml .`: one reference, `README.md:40`.
- `grep -rn "results/" --include=*.md --include=*.py --include=*.yml .`: no references to `evals/results/`.

**Not Tested**

- No dependency-graph, dead-code, or duplicate-code tooling was installed or run. Dead-code and duplication conclusions come from `git ls-files` plus targeted grep and manual import tracing across a 62-file repo, which is small enough for that to be reliable, but they are not tool-confirmed.
- I did not run `py_compile` or `compileall` myself, per `SKILL.md:107` — so I did not empirically reproduce `.github/workflows/ci.yml:123` writing new `.pyc` files. The two `.pyc` files in my checkout predate this session. What is proven: the CI step invokes `py_compile`, `py_compile` writes `.pyc` by design, and matching `.pyc` files exist in this tree hidden behind `.gitignore`.
- I did not run `collect_pr_context.py` against a non-ASCII diff to demonstrate the Windows console crash. The reconfigure gap is confirmed by source; the crash is inferred from `CONTRIBUTING.md:122`'s own stated reason for the rule.
- No linter or type checker was run; the repo ships neither config, so there is nothing to run.

**Assumptions**

- `.github/workflows/ci.yml` has an uncommitted local edit (`git diff --stat`: 8 insertions, 1 deletion, adding an OS matrix to the `validate` job). I audited the working-tree version, which is what I quoted. My initial `git status --short` returned empty and a later one showed the modification; I did not edit the file and only read it. If that edit is not yours, check it before trusting the line numbers in finding 1.
- I treated `evals/fixtures/mini-app/` as a deliberately defective fixture rather than production source, so its duplicate `format-date.js`, its `utils/misc.js`, and its unused exports are not reported as findings. `evals/fixtures/README.md` and `tools/validate_evals.py:38` support that reading.
