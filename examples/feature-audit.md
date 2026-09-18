# `feature-audit` on this repository

**Prompt:** "audit my repo for launch risks"  
**Repository:** `specialone0007/review-skills`, branch `fix/docs-structure-layout` on top of `5597942`, with the removal of `feature-brainstorm` and `pr-branch-summary` applied  
**Files changed by the run:** none — the skill is read-only

Full-repository read-only readiness audit. The product here is the seven bundled scripts and the five `SKILL.md` prompt artifacts other people's agents execute, so the user journeys traced were: point a script at a repository, read its output, and act on it. Verification included running every script against degenerate inputs in a scratch directory outside the repository, and reproducing one finding end to end.

Re-run it yourself and compare. Line numbers refer to the tree described above, so a later commit will shift them.

---

**Feature Audit: whole repository (review-skills)**

No code changed. I checked all seven bundled scripts, the five `SKILL.md` files, both plugin manifests and the CI workflow, including the one write path in the collection and the one place a script emits a URL. I ran every script against an empty directory, a non-git directory containing an invalid-UTF-8 file, and a path that does not exist, and reproduced the overwrite in finding 2 against a sentinel file. No P0s found. Two P1s.

1. **P1: a git remote URL containing a credential is emitted verbatim whenever the host's TLD is not `.com`, `.org` or `.io`.**
   `skills/docs-structure/scripts/docs_evidence.py:1161` runs `git remote get-url origin`. Line 1164 reduces it to a hostname with `re.sub(r"^.*?([A-Za-z0-9.-]+\.(com|org|io)).*$", r"\1", remote.strip())` and stores the result as `remote_host`. When the pattern does not match, `re.sub` returns its input unchanged — so any remote whose host ends in anything other than those three TLDs passes through in full, userinfo included.
   Confirmed by running the exact expression:
   - `https://x-access-token:ghp_SECRETVALUE123@github.com/o/r.git` → `github.com` (correct)
   - `https://user:s3cret-password@git.internal.net/team/repo.git` → returned unchanged, password included
   - `https://oauth2:glpat-XXXXSECRET@gitlab.mycorp.dev/g/p.git` → returned unchanged, token included
   - `ssh://git@code.example.local:2222/p.git` → returned unchanged
   The exposed population is precisely the wrong one. Public GitHub is safe; self-hosted GitLab, Gitea and Bitbucket Server on a corporate `.net`, `.dev`, `.local` or country-code domain are not — and those are the setups most likely to carry a token in the remote URL, in the organisations where leaking it costs the most. `public_host` on the same line correctly reports `false` for them, so the script knows it is looking at a non-public host and still prints the URL.
   The value is not confined to the JSON. `docs_evidence.py` is the inventory that `docs-structure`'s fill step drafts from, so a leaked credential can be copied into a Markdown file and committed. The repo's own rule at `skills/docs-sync-audit/SKILL.md:14` — never quote a credential or connection string in a report, whatever file it came from — is violated by a sibling skill.
   A correct redactor already exists in the same file. `redact()` at `skills/docs-structure/scripts/docs_evidence.py:130` turns `https://user:s3cret-password@git.internal.net/...` into `https[redacted]git.internal.net/...`, and it is applied two lines above to both `tags` and the commit subjects in `decisions`. It was simply not applied to this one value.
   Evidence: `skills/docs-structure/scripts/docs_evidence.py:1164` (the unredacted `remote_host`), `skills/docs-structure/scripts/docs_evidence.py:1161` (the `git remote get-url` call), `skills/docs-structure/scripts/docs_evidence.py:130` (`def redact`), `skills/docs-structure/scripts/docs_evidence.py:1163` (`redact` applied to `tags` in the same dict literal).
   Suggested fix direction: wrap the value — `redact(re.sub(...))` — which is a one-token change consistent with the line above it. Better still, drop the TLD list and parse the URL properly: take the host after `@` and before the next `/` or `:`, and fall back to `"[non-public]"` when that fails, so an unparseable remote degrades to a placeholder instead of to the raw string. Add a fixture remote with a credential and a `.dev` host to the canary assertion at `tools/validate_evals.py:170`, which today only guards `.env` values.

2. **P1: `docs_split.py --out` silently overwrites existing files in the target folder.**
   `skills/docs-structure/scripts/docs_split.py:561` advertises `--out` as "a folder OUTSIDE the repository to materialise the proposal into". The write loop at `:587` calls `p.write_bytes(...)` after `p.parent.mkdir(parents=True, exist_ok=True)`. There is no existence check, no `--force` gate, and no report of what was replaced.
   Reproduced: I ran the split into a scratch folder, wrote `MY IMPORTANT NOTES - DO NOT LOSE` over `<out>/docs/drafted.md`, and re-ran the same command. The file came back as `# Drafted doc`, exit code 0, and the run printed `Proof: ok` followed by `Written to: <path>`.
   The guard that does exist is aimed elsewhere and reads as reassurance. `:582` refuses when `--out` is the repository or inside it, and the text output closes with "Nothing was written into the repository. Write these files only when the proof is ok." (`:621`). Both statements are true and neither is the risk. A user is told what was protected, never what was destroyed.
   This is the only write path in the entire collection. Everything else is read-only by contract, `README.md:166` sells that as the product's safety story, and the one exception silently clobbers data. The likely target is a scratch folder a user reuses across runs, which is exactly where their previous output lives.
   Evidence: `skills/docs-structure/scripts/docs_split.py:587` (`p.write_bytes`), `:561` (`--out` help text), `:582` (the repository guard), `:621` (the closing reassurance), `README.md:166`.
   Suggested fix direction: before the loop, collect the paths that already exist; if any do, write nothing, print them, and exit non-zero with "refusing to overwrite N existing files; pass --force or choose an empty folder". Add `--force` for the deliberate case. Also worth saying in `skills/docs-structure/SKILL.md:164`, which currently describes `--out <scratch>` without mentioning that the folder should be empty.

3. **P2: the CI smoke job no longer fetches git history, so the two scripts that read it run a degraded path there.**
   The `scripts` job's checkout at `.github/workflows/ci.yml:100` has no `fetch-depth`, so it gets the default single-commit clone. `skills/docs-structure/scripts/docs_evidence.py:1157` asks for `git log --format=... -n 300` and `skills/docs-sync-audit/scripts/docs_drift.py:565` asks for a full `git log --name-only`, which is what powers the `stale-doc` finding kind. Against a one-commit clone both return almost nothing.
   Neither crashes — both use `or ""` on the result, and I confirmed all seven scripts exit 0 against a non-git directory — so CI stays green. The cost is silent: the job that exists to prove these scripts work on a real repository never exercises their history path, and a regression in commit parsing or date handling would pass. `fetch-depth: 0` was present on this job before the change that removed the `pr-branch-summary` script, where it was there for that script's diff.
   Confidence: high on the mechanism, medium on the likelihood anyone regresses it soon.
   Evidence: `.github/workflows/ci.yml:100`; `skills/docs-structure/scripts/docs_evidence.py:1157`; `skills/docs-sync-audit/scripts/docs_drift.py:565`.
   Suggested fix direction: restore `fetch-depth: 0` on that job's checkout. It costs a few seconds on a 116-file repository and it is the only place the history-reading code meets a real history.

4. **P3: `--out` is allowed to write into the repository's parent directory.**
   The guard at `skills/docs-structure/scripts/docs_split.py:582` refuses when `out_dir` equals the repository or is inside it. It does not refuse an ancestor: with a repository at `/a/b/repo`, `--out /a/b` passes, because `/a/b`'s parents are `/a` and `/`, neither of which is the repository. Files then land in `/a/b/docs/...`, alongside the repository rather than in it.
   This is arguably what "outside the repository" means, and no repository file is touched, so it is polish rather than a defect. It matters only in combination with finding 2: the sibling directory a user picks casually is likely to be one with files in it.
   Confidence: high that the behaviour is as described; low that it is unintended.
   Evidence: `skills/docs-structure/scripts/docs_split.py:582`.
   Suggested fix direction: leave the guard alone and fix finding 2. If you want the stricter rule, also refuse when `out_dir` is a parent of the repository, and say so in the help text.

**What held up under testing**

- **Degenerate input is handled cleanly across all seven scripts.** Against an empty directory, `docs_evidence.py`, `docs_fill_gate.py` and `docs_structure.py` exit 0; `docs_drift.py`, `repo_inventory.py` and `coverage_map.py` exit 2 with `error: no files found under <path>` — a message, not a traceback. Against a non-git directory holding a deliberately invalid-UTF-8 Markdown file, all six exit 0. Against a path that does not exist, both scripts I tried exit 2 with `error: not a directory: <path>`. No crash, no partial output, no stack trace in any of the fourteen runs.
- **Every `SKILL.md` carries the prompt-injection guard.** `grep -Lc "evidence, never instruction" skills/*/SKILL.md` returns nothing, meaning all five contain it. For artifacts whose entire job is reading untrusted repositories, that is the single most important line in the file.
- **The write-safety assertion covers every script now.** `.github/workflows/ci.yml:122` runs all seven against the checkout in both output formats and then requires `git status --porcelain` to be empty.
- **The `.env` canary works.** `tools/validate_evals.py:170` asserts a planted secret never reaches stdout on any snapshot run. Finding 1 is the case it does not cover, which is why extending it is part of that fix.

**Surveyed But Not Deeply Inspected**

- The rule engine inside `docs_structure.py` (2,913 lines). I read its argument parser, its walk and its module constants. Whether each of its R-rules fires correctly on a repository that is not one of the two fixtures is unexamined and is the largest remaining risk surface in the collection.
- `docs_fill_gate.py` (1,498 lines) and the fill workflow as a whole. Fill is the feature that drafts prose into a user's repository, so it is the highest-consequence path here, and this pass only confirmed the script does not write.
- The `merge()` direction of `docs_split.py` (`:406`). Never executed by any test and not executed by me; finding 2's overwrite applies to it equally, since both directions share the write loop at `:587`.
- `skills/docs-structure/references/structure.md` and the templates under `references/templates/`, which are prompt content an agent loads and act as part of the product surface.
- The two plugin manifests against a live marketplace install. CI validates them with the first-party validator, which is stronger than a hand check.

**Checks Run**

- Seven scripts against an empty scratch directory with `--no-git-root --format json`: three exit 0, three exit 2 with `error: no files found under <path>`.
- Same seven against a non-git scratch directory containing `README.md`, `a.py` and a file of invalid UTF-8 bytes: all exit 0.
- `repo_inventory.py` and `docs_structure.py` against a nonexistent path: both exit 2, `error: not a directory: <path>` and `error: <path> ...`.
- `python skills/docs-structure/scripts/docs_split.py --repo evals/fixtures/mini-app --no-git-root --doc docs/drafted.md --split-at 30 --max-parts 16 --out <scratch> --format text`, run twice with a sentinel file written in between: `Proof: ok`, `Written to: <scratch>`, exit 0, and the sentinel's contents replaced by `# Drafted doc`.
- `python -c` evaluating the `remote_host` expression from `docs_evidence.py:1164` against four remote URLs: `github.com` for the `.com` case, the full URL returned unchanged for `.net`, `.dev` and `.local`.
- `python -c` calling `docs_evidence.redact()` on the same two credential URLs: both returned as `https[redacted]<host>/<path>`, confirming the existing helper is sufficient.
- `grep -Lc "evidence, never instruction" skills/*/SKILL.md`: no output — all five contain the guard.
- `grep -rn "run_git(" skills/*/scripts/*.py`: twelve call sites; the history-reading ones are `docs_evidence.py:1157` and `docs_drift.py:565`.
- `git diff --cached .github/workflows/ci.yml | grep fetch-depth`: one removed line, `- fetch-depth: 0`.
- `python tools/validate_skills.py`: exit 0 — "5 skills checked. Descriptions total 3407/5000 chars. OK: 0 errors, 0 warning(s)."
- `python tools/validate_evals.py`: exit 0 — "5 eval files, 31 cases checked. OK: 0 errors."
- `git status --short` before and after every check above: unchanged apart from the staged work already present when the audit began.

**Not Tested**

- I did not create a git repository with a credential-bearing remote and run `docs_evidence.py` against it end to end. Finding 1 is confirmed at the expression level — the exact regex from line 1164, run against four real remote-URL shapes — and by reading the call at `:1161` and the dict it lands in. The end-to-end path from `remote_host` into a drafted Markdown file is inferred from `docs_fill_gate.py` consuming that inventory, not observed.
- No browser, no network, no live agent. The five `behavior` eval cases need a model and were not run, so nothing here checks that a skill's report actually obeys its own format.
- The install paths (`npx skills add`, `/plugin marketplace add`) were not exercised.
- No linter or type checker was run; the repository ships neither config.
- I did not run `py_compile` or `compileall`, per this skill's own rule against commands that write into the tree.

**Assumptions**

- I audited the working tree of `fix/docs-structure-layout` with the two-skill removal staged but not committed. Findings 1, 2 and 4 predate that change; finding 3 was introduced by it and is reported for that reason.
- All scratch files were written under the session's temporary directory, never inside the repository. `git status --porcelain` was empty of unexpected entries throughout.
- I treated `evals/fixtures/` as deliberately defective and did not report anything inside it.
