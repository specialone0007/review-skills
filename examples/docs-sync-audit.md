# `docs-sync-audit` on this repository

**Prompt:** "check the docs against the code"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Full-repository documentation drift audit of the review-skills repo itself, comparing all 12 tracked Markdown surfaces against CI config, both validators, the five bundled scripts, the plugin manifests and the eval fixture, using the skill's bundled docs_drift.py plus targeted greps.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Docs Sync Audit: whole repository (12 tracked Markdown files, 5 bundled scripts, 2 validators, CI)**

No code changed. No scope was named, so this was a full-repo docs pass. I inventoried 12 tracked Markdown surfaces and compared them against the code they describe: `.github/workflows/ci.yml`, `tools/validate_skills.py`, `tools/validate_evals.py`, the five bundled `skills/*/scripts/*.py`, `.claude-plugin/*.json`, and the eval fixture. Six surfaces were deep-inspected, six skimmed. I ran the skill's bundled `docs_drift.py` and both repo validators; all three pass clean against the repo's own rules. **No P0s found. No P1s found.** Six findings, three P2 and three P3 — all internal to contributor and fixture documentation. The user-facing README's install commands, skill table, safety carve-out and script invocations all check out.

1. **P2: The README says CI runs the skills validator on Windows. It only runs on Ubuntu.**
   Drift: `README.md:116` reads "CI runs both, on Ubuntu and Windows." Only `validate_evals.py` runs on both. `validate_skills.py` runs in a single-OS job.
   Impact: a contributor trusts that a Windows-only path bug in `validate_skills.py` — it does `rglob`, `read_text`, and `relative_to(...).as_posix()` on every file — would be caught by CI. It would not be. Misleads exactly the people the sentence is written for.
   Evidence: docs `README.md:116`; source `.github/workflows/ci.yml:18` (`runs-on: ubuntu-latest` for the `validate` job that invokes it at `.github/workflows/ci.yml:28`) versus `.github/workflows/ci.yml:71` (`os: [ubuntu-latest, windows-latest]` for the `evals` job that invokes `validate_evals.py` at `.github/workflows/ci.yml:81`).
   Suggested update: change the sentence to say the eval and script jobs run on Ubuntu and Windows while the skills validator runs on Ubuntu — or add the matrix to the `validate` job and leave the README alone. The second is probably the better fix, since the claim is one a maintainer would want to be true.

2. **P2: CONTRIBUTING states a frontmatter rule the validator dropped, and that all seven shipped skills already break.**
   Drift: `CONTRIBUTING.md:19` documents the rule as "Frontmatter contains exactly `name` and `description`", justified by "Those are the only two fields in the Agent Skills spec." The validator disagrees on both counts: it accepts four optional keys, and its own comment says so. Every `SKILL.md` in the repo carries a third key, `license: MIT`.
   Impact: a contributor writing a new skill by following the table either omits `license` (breaking consistency with the other seven) or adds it and expects a red build that never comes. `CONTRIBUTING.md:45` repeats the error in the add-a-skill checklist: "`skills/<name>/SKILL.md` with the two frontmatter fields."
   Evidence: docs `CONTRIBUTING.md:19` and `CONTRIBUTING.md:45`; source `tools/validate_skills.py:32` (`OPTIONAL_FIELDS = ("license", "compatibility", "metadata", "allowed-tools")`), with the contradicting rationale at `tools/validate_skills.py:29` ("`name` and `description` are required; the rest are optional per the spec"); shipped counter-examples at `skills/docs-sync-audit/SKILL.md:4` and the same line 4 in all six other `SKILL.md` files.
   Suggested update: rewrite the row as "Frontmatter contains `name` and `description`, optionally `license`, `compatibility`, `metadata`, `allowed-tools`; anything else is rejected" and keep the `version:` note, which is still accurate (`tools/validate_skills.py:105`). Change line 45 to name `license: MIT` as the house convention.

3. **P2: The fixture's defect table contradicts the same file's own explanation of that defect.**
   Drift: `evals/fixtures/README.md:16` describes the planted env-var defect as "only one is wired to anything meaningful". Seventeen lines later the same file states the correct version: both are dead, because the module holding them is never imported. The code agrees with line 33, not line 16.
   Impact: this table is the contract that tells a maintainer what each planted defect is and which skill must find it. A maintainer reading line 16 would expect `docs_drift.py` to emit one finding and could "fix" a snapshot mismatch by deleting a correct one. The script in fact emits two, one per variable.
   Evidence: docs `evals/fixtures/README.md:16` versus the correct statement at `evals/fixtures/README.md:33`; source `evals/fixtures/mini-app/src/config.js:2` (`apiToken: process.env.API_TOKEN`) and `:3` (`maxExportRows: Number(process.env.MAX_EXPORT_ROWS ?? 1000)`), with `grep -rn "config" evals/fixtures/mini-app/src evals/fixtures/mini-app/tests` returning only the definition at `config.js:1` — nothing imports it. Confirmed by the bundled script, which reports both `API_TOKEN` and `MAX_EXPORT_ROWS` as `documented-env-in-unreferenced-module`.
   Suggested update: reword line 16 to "README documents `MAX_EXPORT_ROWS` and `API_TOKEN`; both are read only in a module nothing imports, so neither can take effect", matching line 33.

4. **P3: The fixture doc cites a dependency spec that is not in the fixture.**
   Drift: `evals/fixtures/README.md:35` says "`package.json` covers the other branch, since a `^4.17.21` range is not a pin." No such spec exists in the fixture. That string appears only in a docstring example inside the security script — it looks like it was copied from there while writing the note.
   Impact: a maintainer verifying why the fixture holds a `low` severity goes looking for `^4.17.21` in `package.json`, does not find it, and cannot tell whether the fixture drifted or the doc did. The underlying point is still true — `left-pad: "*"` and `vitest: "^2.0.0"` are both unpinned — so the fix is to cite what is actually there.
   Evidence: docs `evals/fixtures/README.md:35`; source `evals/fixtures/mini-app/package.json:13` (`"left-pad": "*"`) and `:17` (`"vitest": "^2.0.0"`). `grep -rn "4\.17\.21"` over the repo returns two hits: the doc line, and `skills/security-audit/scripts/dependency_audit.py:148`, a docstring.
   Suggested update: replace `^4.17.21` with `left-pad: "*"`, the spec the fixture actually plants and that `evals/fixtures/README.md:20` already names.

5. **P3: Two contributor rules describe all bundled scripts, but one script is an unstated exception to each.**
   Drift: `CONTRIBUTING.md:121` states scripts must "support `--format text|json`". `CONTRIBUTING.md:76` states `validate_evals.py` "runs the bundled scripts against the fixture and compares their JSON output to `evals/snapshots/`". `collect_pr_context.py` has no `--format` flag and is not snapshot-tested — it emits markdown and is smoke-tested separately in CI instead. Neither exception is written down, and the same script is held up as the reference implementation for a third rule at `CONTRIBUTING.md:120`.
   Impact: minor but self-undercutting. A contributor comparing the rule to the named reference script finds the reference does not follow it, which makes the whole list read as aspirational. It also obscures a real design decision worth stating: a markdown-drafting helper has no JSON contract to snapshot.
   Evidence: docs `CONTRIBUTING.md:121` and `CONTRIBUTING.md:76`; source `skills/pr-branch-summary/scripts/collect_pr_context.py:100-132` (the full `add_argument` block — `--base`, `--repo`, `--fetch`, `--fetch-remote`, `--prune`, `--output`, `--allow-repo-output`, `--max-diff-lines`, and no `--format`); snapshot coverage listed at `tools/validate_evals.py:52-58`, four entries, `collect_pr_context` absent; its separate CI treatment at `.github/workflows/ci.yml:101-110`.
   Suggested update: add the carve-out to both lines — "except `collect_pr_context.py`, which drafts markdown for a human and is smoke-tested in CI rather than snapshotted."

6. **P3: `evals/results/` exists as a convention but is documented nowhere.**
   Drift: the repo has two committed trial-result records. `grep -rn "results" README.md CONTRIBUTING.md evals/fixtures/README.md tools/validate_evals.py` returns nothing (exit 1). CONTRIBUTING's `## Evals` section documents `evals/<skill>.json`, `evals/fixtures/`, and `evals/snapshots/`, and stops there.
   Impact: `CONTRIBUTING.md:99-112` tells a contributor how to write up a real-code trial and what not to leak, but never says where the write-up goes — while the repo already answers that with a dated JSON schema (`date`, `model`, `kind`, `target`, `method`, `runs`). The next contributor invents a different location or format. This is also the one directory a reader might mistake for machine-generated output, since it sits beside `snapshots/`.
   Evidence: source `evals/results/2026-09-03-opus-5.json` and `evals/results/2026-09-05-real-code-trial.json`; expected docs area is `CONTRIBUTING.md:99` (`## Trialling the skills on real code`), which is where a contributor would look.
   Suggested update: add two sentences to that section naming `evals/results/<date>-<label>.json`, its fields, and that it is hand-written and not validated by CI.

**What is in good shape**

Stated plainly, because it is most of the repo. The README's two install paths match the manifests (`.claude-plugin/marketplace.json:10` and `.claude-plugin/plugin.json:2` both give `review-skills`, so `/plugin install review-skills@review-skills` is correct). "Seven" is seven everywhere. "For most of them, a bundled script" is 5 of 7. Every `python <skill-dir>/scripts/*.py --top N --format json` line in all five script-bearing skills matches the real `add_argument` set. `docs-sync-audit/SKILL.md:50`'s description of what its own script checks — npm scripts, make targets, relative Markdown links, env names in both directions — matches the script's behaviour and docstring. The README safety carve-out for `pr-branch-summary` is precise and matches `skills/pr-branch-summary/SKILL.md:17-18`, including the explicit refusal of `--prune`. `examples/repo-health-audit-self.md` cites paths that no longer exist (`skills/repo-organization-audit/`), but it is pinned to commit `cbaba7f` and says so at lines 3-9 — that is a disclosed historical snapshot, not drift.

**Likely Docs To Update**
- `README.md:116`: CI OS coverage claim.
- `CONTRIBUTING.md:19`, `:45`: stale frontmatter rule.
- `CONTRIBUTING.md:76`, `:121`: unstated `collect_pr_context.py` exceptions.
- `CONTRIBUTING.md:99-112`: add where trial write-ups are stored.
- `evals/fixtures/README.md:16`, `:35`: self-contradiction and a citation to a spec not in the fixture.

**Surveyed But Not Deeply Inspected**
- The five `SKILL.md` bodies I did not read end to end — `feature-audit`, `feature-brainstorm`, `repo-health-audit`, `security-audit`, `test-gap-audit`. I checked their script-invocation lines against the real flags and their `license` frontmatter, but not their prose against their scripts' actual behaviour. `security-audit/SKILL.md:56` makes the most specific behavioural claim in the repo (five named detections) and is the best next target.
- The seven `agents/openai.yaml` files beyond what the validator enforces. `short_description` is unchecked by anything and is user-facing in Codex.
- `evals/*.json` prompts and rubrics against the current skill descriptions. The validator checks structure, never whether a rubric still describes the contract the skill emits.
- `tools/make_social_preview.py` and `assets/social-preview.png`. Neither is mentioned in README or CONTRIBUTING; I did not determine whether the committed image is current with the generator.

**Checks Run**
- `git status --short`: clean, before and after.
- `git ls-files '*.md' | wc -l`: 12 tracked Markdown files.
- `python skills/docs-sync-audit/scripts/docs_drift.py --top 30`: "Docs checked: 13 Findings: 3". All three land in `evals/fixtures/`, and all three are planted defects the fixture exists to hold — one `missing-script` (`npm run dev` vs `dev:start`) and two `documented-env-in-unreferenced-module`. Zero findings outside the fixture. The two env findings are what corroborate finding 3.
- `python tools/validate_skills.py`: "7 skills checked. Descriptions total 3797/5000 chars. OK: 0 errors, 0 warning(s)." Exit 0.
- `python tools/validate_evals.py`: "7 eval files, 27 cases checked. OK: 0 errors." Exit 0 — so all four script snapshots still match on this machine.
- `grep -n "^license" skills/*/SKILL.md`: 7 matches, line 4 in each. Basis for finding 2.
- `grep -c '"--format"' skills/pr-branch-summary/scripts/collect_pr_context.py`: 0. Basis for finding 5.
- `grep -rn "4\.17\.21" . --include=*.json --include=*.md --include=*.txt --include=*.py`: 2 matches, neither in any `package.json`. Basis for finding 4.
- `grep -rn "config" evals/fixtures/mini-app/src evals/fixtures/mini-app/tests`: 1 match, the definition line. Basis for finding 3.
- `grep -rn "results" README.md CONTRIBUTING.md evals/fixtures/README.md tools/validate_evals.py`: no matches, exit 1. Basis for finding 6.
- Per-file kind census of `evals/*.json` via a one-line `json.load` + `Counter`: every one of the 7 files has at least one `trigger`, one `anti-trigger`, and one `behavior` case, so `README.md:116` and `CONTRIBUTING.md:62` are accurate on that point.

**Not Tested**
- `npx @anthropic-ai/claude-code plugin validate` (`.github/workflows/ci.yml:59`, `:62`) was not run. It needs a network download, and the audit is read-only. Residual risk: a first-party manifest-spec drift in `.claude-plugin/*.json` would not have been caught here. CI covers it on every push.
- No Python compile check. `python -m compileall` and `py_compile` write `.pyc` files into the tree, which the skill's own rule forbids during an audit — and `.gitignore` would have hidden the change from `git status`. CI does this at `.github/workflows/ci.yml:116`. Residual risk: none for docs accuracy; a syntax error in a script would not have surfaced in this pass. The four snapshot-tested scripts and `docs_drift.py` all executed successfully, so five of five are known to at least import and run.
- No external link checking. The README's badge and skills.sh URLs (`README.md:3-4`) were not fetched. Relative Markdown links are covered — `validate_skills.py` resolves them repo-wide and reported none broken.
- `tools/make_social_preview.py` was not run, so I cannot say whether `assets/social-preview.png` is current with its generator. That is the one generated artifact in the repo and it was not rebuilt; treat its freshness as unverified.

**Assumptions**
- I treated `evals/fixtures/README.md` as real documentation rather than part of the deliberately defective fixture. `evals/fixtures/mini-app/**` is the planted-defect surface; the parent README is the maintainer's map of it, and `tools/validate_skills.py:262` skips only paths under `fixtures/`, which includes it. If findings 3 and 4 are themselves intentional plants, nothing in the repo says so — and that would be worth writing down either way.
