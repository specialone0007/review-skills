# `pr-branch-summary` on this repository

**Prompt:** "summarise what shipped since v0.1.0 as a release note and a team update"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Compared the current branch against the v0.1.0 tag (22 commits, 49 files, 2431 insertions) using the skill's bundled collect_pr_context.py plus per-commit git show --stat verification, and drafted a release note and team update; both repo validators were run as evidence.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

Base resolved to the `v0.1.0` tag (`31bc4a6`), which is the only tag in the repo and matches what you asked for. Current branch is `docs/real-examples` at `cc100ad`; the merge base with the tag is the tag itself, so `31bc4a6..HEAD` is the whole delta. No fetch was performed — the base ref already exists locally.

One thing to separate out: the working tree is **not** clean. `.github/workflows/ci.yml` has an uncommitted change (adds a Windows leg to the `validate` job, 8 insertions / 1 deletion). It is not part of this release delta and I have excluded it from the notes below.

---

**PR Title**
`feat(skills): add an eval suite, two bundled scripts, and three evidence-accuracy correction passes`

**Squash Commit Header**
`feat(skills): add an eval suite, two bundled scripts, and three evidence-accuracy correction passes`

**PR Description**

## Summary
- **Testing infrastructure, new in this release.** 27 eval cases across all seven skills (trigger, anti-trigger, behavior), a deliberately defective 15-file fixture at `evals/fixtures/mini-app/`, JSON snapshot tests for every bundled script, and a new maintainer validator `tools/validate_evals.py`.
- **Two new bundled scripts.** `security-audit` gets `scripts/dependency_audit.py` (513 lines) for offline dependency and supply-chain signals; `docs-sync-audit` gets `scripts/docs_drift.py` (474 lines) for machine-verifiable doc claims. That takes the repo from three bundled scripts to five.
- **Three correction passes on skill evidence rules**, driven by running all seven skills against a real private repository and having an independent judge check every citation. Every skill picked up an explicit "the line you cite must literally contain the thing you name" rule; six of seven picked up "evidence every count with the command that produced it"; five picked up an explicit ban on commands that write into the repo as a side effect.
- **CI grew from one job to four**: the existing script smoke test, plus first-party manifest validation via the Claude Code CLI, plus a cross-platform eval/snapshot job, and the npx download is now cached on a weekly key.
- **Supply-chain hardening of our own new script.** `dependency_audit.py` shipped echoing manifest values and was tightened four times before release so it cannot print a credential.

## Why
`v0.1.0` shipped seven skills with no automated way to tell whether a description still routed correctly or whether a bundled script's output had drifted. It also had no evidence that the skills are accurate on code larger than a toy example. This release adds both: a deterministic CI-runnable half, and a documented real-code trial process whose results are committed under `evals/results/`.

The trial is what drove the skill edits. Per `evals/results/2026-09-05-real-code-trial.json`, the baseline run spot-checked 106 findings and confirmed 91; the systemic defect was that claims were usually true but the `path:line` pointers were not — one audit cited a range seventeen lines from the block it described, another attributed linter findings to four lines the linter never reported. Two absence errors were worse in kind: three packages were recommended for removal that were transitive dependencies of a package the project actually used, which would have broken the running service. One audit ran `compileall` and wrote `.pyc` files into the target tree, which `git status` reported as clean because `__pycache__/` is gitignored.

## Changes
- **Evals (`evals/`, new).** Seven `<skill>.json` files, 27 cases total (4 each except `feature-brainstorm` at 3). The validator rejects an eval file with no anti-trigger case — with seven overlapping skills, anti-triggers are the cases that matter. Evals live at the repo root, not in skill folders, because installing a skill copies its directory and in-folder evals would ship to users and pollute agent context.
- **Fixture and snapshots.** `evals/fixtures/mini-app/` is intentionally defective (documented in its README). `evals/snapshots/` pins the exact JSON output of `coverage_map`, `dependency_audit`, `docs_drift` and `repo_inventory` against that fixture. `.gitattributes` pins fixture files to `text eol=lf` because the snapshots compare byte counts and the Ubuntu and Windows CI legs would otherwise disagree.
- **`tools/validate_evals.py` (271 lines, new).** Tier 1 runs in CI with no model: well-formedness, unique ids, referenced skills exist, snapshots match. Tier 2 is `--checklist`, which prints prompts and rubrics for a human to run against a live agent. There is deliberately no LLM judge in CI — stated reasoning: cost on every push, flakiness, an API key in a public repo, and rot.
- **`dependency_audit.py`.** Offline by default: missing lockfiles, `postinstall`-style install hooks, `file:`/`git+` and unpinned specs, lockfile-only direct dependencies, custom registries. Real auditors (`npm audit`, `pip-audit`, `cargo audit`) are gated behind `--allow-network`, and the SKILL tells the agent to ask first and to state plainly when advisory data was not fetched.
- **`docs_drift.py`.** Checks only claims with a definite answer: documented `npm run`/`make`/script commands against what exists, relative Markdown links against the filesystem, env var names in both directions between docs and code, and doc-vs-code staleness. Backticked-path checking is opt-in behind `--check-paths` because it produced 211 findings on one real repo, almost all noise.
- **`repo_inventory.py`** gained `--no-git-root`, so a monorepo survey can be scoped to one package instead of always expanding to the git root.
- **`coverage_map.py`** stopped counting a `describe` block as a test case.
- **`validate_skills.py`** now skips `evals/fixtures/` in its absolute-path check, since policing the fixture would mean fixing the very drift it exists to contain.
- **Report format.** `feature-audit` and `repo-health-audit` findings moved from a run-on sentence to labelled lines: Evidence / Confidence / Suggested fix direction.
- **`marketplace.json`** gained the `description` field the first-party CLI requires.
- **`make_social_preview.py`** now auto-fits the title so a longer name cannot silently run off the canvas.
- **CONTRIBUTING.md** gained 63 lines: how evals work, how to update snapshots, and a "Trialling the skills on real code" section with explicit rules for writing up a private-repo trial in a public repo (do not name it, do not quote its paths or identifiers, numbers and ratios are fine).

## Testing
- `python tools/validate_skills.py` — pass. Output: `7 skills checked. Descriptions total 3797/5000 chars. OK: 0 errors, 0 warning(s).`
- `python tools/validate_evals.py` — pass. Output: `7 eval files, 27 cases checked. OK: 0 errors.` This includes the script snapshot comparison.
- Counts in this report come from `git diff --stat 31bc4a6..HEAD` (49 files changed, 2431 insertions, 21 deletions), `git rev-list --count 31bc4a6..HEAD` (22 commits, 14 of them non-merge), and a JSON count over `evals/*.json` (27 cases).
- The model-dependent half of the eval suite (`--checklist`) was **not** run in this pass. Its last recorded results are the two runs in `evals/results/`.
- I did not re-run the real-code trial. Its numbers above are quoted from `evals/results/2026-09-05-real-code-trial.json`, not reproduced.

## Risk / Rollback
- **No runtime blast radius.** This repository ships Markdown and standard-library Python that other people's agents read. Nothing here runs in production, there are no migrations, no env vars, no feature flags, no billing or auth paths.
- **The real risk is behavioral drift in the skills.** The evidence rules added across all seven SKILL.md files are substantial new instruction text. If they are too heavy, the skills get slower and more hedged. The 2026-09-05 trial reports absence errors down to 0 and no read-only breaches, but also that citation accuracy was only *partly* fixed after the second pass — the third pass (`9a48dc5`) is the response to that and has not been re-trialled.
- **The first-party CI job tracks `@latest` on purpose** and will go red when the plugin spec moves. That is intentional (the workflow comment says so), but it means a red build here is not always this repo's fault.
- **Snapshot tests are byte-count sensitive.** They depend on `.gitattributes` holding fixture files at LF. If that line is lost, the Windows leg breaks.
- Rollback is `git revert` of the merge, or pinning users back to `v0.1.0`. No state to unwind.

---

**Telegram Message**

Since v0.1.0 the repo went from "seven skills and a linter" to something with actual test infrastructure behind it. There are now 27 eval cases covering all seven skills — trigger, anti-trigger, and behavior — running against a deliberately broken little app I keep in `evals/fixtures/`. Every bundled script's output is snapshotted and compared in CI, so if a script's behavior drifts it fails the build instead of quietly changing. CI went from one job to four and now runs on Ubuntu and Windows, including the first-party Claude Code CLI validation that the plugin directory itself uses.

Two new scripts shipped. `security-audit` got a dependency and supply-chain survey — lockfiles, install hooks, unpinned and `git+` specs, custom registries — offline by default, with real auditors like `npm audit` gated behind an explicit network flag. `docs-sync-audit` got a documentation drift check that only tests claims with a definite answer: documented commands that don't exist, Markdown links that don't resolve, env vars documented but never read and vice versa. That takes us from three bundled scripts to five.

The most useful work was less glamorous. I ran all seven skills against a real private codebase and had a separate judge open every cited file and check the line numbers rather than grade the writing. 91 of 106 findings held up, but the failures were the ones that matter: claims that were true while the path and line pointed somewhere else, advice to delete three packages that turned out to be transitive dependencies of something the project actually used, and one audit that wrote `.pyc` files into the target tree while `git status` looked clean. Three correction passes went in for those — every skill now has to anchor a citation on the line that literally contains the thing it names, evidence every number with the command that produced it, verify an absence claim against more than one grep, and never run a command that writes into the repo as a side effect. The re-run shows absence errors at zero and no read-only breaches; citation accuracy is improved but only partly, and the newest pass has not been re-trialled yet.

One housekeeping note: our own new dependency script shipped echoing manifest values and needed four follow-up commits before release to guarantee it can never print a credential, and there is now an eval that enforces that. Worth knowing given the script is the one we point at other people's `.npmrc` files.

Heads up before you cut the tag: `.github/workflows/ci.yml` has an uncommitted change sitting in the working tree (adds a Windows leg to the validate job). Commit it or stash it first.
