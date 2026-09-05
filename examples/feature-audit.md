# `feature-audit` on this repository

**Prompt:** "audit my repo for launch risks"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Full-repository launch-readiness audit of the review-skills repo itself — 7 skills, 5 bundled scripts, 2 validators, the CI workflow, the eval suite and the packaging manifests — verified by running both validators and two bundled scripts read-only, with no network access.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Feature Audit: whole repository (`review-skills`), no scope named**

No code changed. I inventoried the whole repository — 7 skills, 5 bundled scripts, 2 validators, a 4-job CI workflow, a 7-file / 27-case eval suite with a defective fixture app, the plugin and marketplace manifests, `README.md`, `CONTRIBUTING.md`, and `examples/` — and deep-inspected the packaging manifests, the CI workflow, all 5 bundled scripts, both validators, and the README's factual claims about the skills. Verification was source inspection plus running both validators and two bundled scripts read-only; no network calls, no live-agent eval runs, no GitHub Actions execution. No P0s found. No P1s found either — nothing here can lose data, leak anything, or stop a skill from working. The findings below are launch-credibility and cross-platform robustness issues.

1. **P2: `collect_pr_context.py` is the only bundled script without the UTF-8 stdout guard, and it prints arbitrary commit and diff text.**
   Four of the five bundled scripts and `tools/validate_evals.py` open with `sys.stdout.reconfigure(encoding="utf-8", errors="replace")`. `collect_pr_context.py` does not, and it is the one script whose output is *entirely* user content — commit subjects, `git status`, and a full diff. On Windows, where Python falls back to the console/locale codepage for a redirected stdout, a single emoji, arrow, or CJK character anywhere in the branch's commits or diff raises `UnicodeEncodeError` and the script dies with a traceback instead of producing the PR context. Repro on this machine: encoding `'→'` to cp1252 raises `'charmap' codec can't encode character '→' in position 6`. This matters more than a normal encoding nit because cross-platform behavior is a claim the repo makes about itself, in CI comments and in the README.
   Evidence: `skills/pr-branch-summary/scripts/collect_pr_context.py:239` (the unguarded `print(output)`), versus the guard at `skills/docs-sync-audit/scripts/docs_drift.py:45`, `skills/repo-health-audit/scripts/repo_inventory.py:31`, `skills/security-audit/scripts/dependency_audit.py:43`, `skills/test-gap-audit/scripts/coverage_map.py:33`.
   The Windows CI leg cannot catch this: the smoke test passes `--base "$(git rev-parse HEAD)"`, so the merge base is HEAD and both the commit list and the diff are empty. Nothing non-ASCII is ever printed.
   Evidence: `.github/workflows/ci.yml:106`.
   Suggested fix direction: add the same two-line `reconfigure` guard to `collect_pr_context.py`, and change the CI smoke test to compare against a base with at least one real commit (for example `HEAD~1`, guarded for shallow clones) so the diff path is actually exercised.

2. **P2: The README says CI runs the validators on Ubuntu and Windows. At `HEAD`, `validate_skills.py` runs on Ubuntu only.**
   `README.md:116` reads "CI runs both, on Ubuntu and Windows." Two of the four CI jobs are matrixed (`evals` and `scripts`), but the `validate` job that runs `tools/validate_skills.py` is pinned to a single runner. That validator does path handling (`Path.relative_to`, `as_posix`, `rglob`) and file decoding (`read_text(encoding="utf-8")`) — exactly the code where a Windows difference would show up — and it is the one job with no Windows leg.
   Evidence: `README.md:116`; `.github/workflows/ci.yml:17-18` at commit `13fdbd1` (`name: Validate skills` / `runs-on: ubuntu-latest`).
   Note: the working tree currently carries an *uncommitted* edit to `.github/workflows/ci.yml` that adds a `[ubuntu-latest, windows-latest]` matrix to precisely this job. That change was not made by this audit and appeared mid-session. If it is yours and it lands, this finding is already fixed — verify before acting on it.
   Suggested fix direction: commit the matrix, or correct the README sentence to name which jobs are cross-platform.

3. **P2: The README promises every skill has a `## Related Skills` section. `feature-audit` does not have one, and the validator does not check for it.**
   `README.md:54` says "Each skill names its nearest neighbours in its own `## Related Skills` section, so the agent can route itself if you pick the wrong one." Six of seven skills have the section; `feature-audit` has zero occurrences. That is the worst one to miss: it is the broadest skill, the first row of the skills table, and the one most likely to fire on a request that a specialist should handle.
   Routing is not actually absent — `skills/feature-audit/SKILL.md:3` names all six siblings in the description, and `skills/feature-audit/SKILL.md:22` is a Core Rule that routes to each of them by name. So the behavior is probably fine; the documented structure is what is missing, and a reader who checks the README's claim will find it false.
   `tools/validate_skills.py` enforces `## Agent Portability Notes` and an output contract, and it validates that any `- Use \`<skill>\`` line resolves to a real skill — but it never checks that the section exists. That is why this drifted silently.
   Evidence: `README.md:54`; absence in `skills/feature-audit/SKILL.md`; enforcement gap at `tools/validate_skills.py:234-243`.
   Suggested fix direction: add a `## Related Skills` section to `feature-audit` (its description already contains the routing text to reuse), and add a presence check to the required-sections block in the validator so this cannot drift again.

4. **P3: CI's own syntax check writes `.pyc` files into the checkout — the exact side effect `feature-audit` tells agents never to cause.**
   `skills/feature-audit/SKILL.md:64` instructs the agent: "Never run a command that writes into the repository as a side effect. `python -m compileall` and `py_compile` emit `.pyc` files… `.pyc` output is usually gitignored, so `git status` will look clean while the tree has in fact been modified." The `scripts` job then runs `python -m py_compile` over every bundled script. The build stays green — the clean-tree assertion at `.github/workflows/ci.yml:108` runs *before* the compile step at `:116`, and `__pycache__/` is gitignored — so this is a credibility problem, not a broken build. It has already leaked into the maintainer's working tree: 3 `__pycache__` directories exist under `skills/` and `tools/` right now.
   Evidence: `skills/feature-audit/SKILL.md:64`; `.github/workflows/ci.yml:116`; `.gitignore:1`.
   Suggested fix direction: replace `py_compile` with a check that writes nothing — `python -c "import ast,sys,pathlib; [ast.parse(pathlib.Path(p).read_text(encoding='utf-8'), p) for p in sys.argv[1:]]"` over the same file list — so the repository practices the rule its flagship skill preaches.

5. **P3: `dependency_audit.py` can print a flatly false explanation when the lockfile is `bun.lockb`.**
   `JS_LOCK_OWNER` maps `bun.lockb` to `"bun"`, so a bun repo sets `preferred = "bun"`. But `AUDITORS["javascript"]` has no bun entry, so `chosen` can only ever be pnpm/yarn/npm. The mismatch branch then emits "The lockfile indicates bun, but bun is not installed, so npm was used instead" — which is wrong whether or not bun is installed, because bun was never a candidate. In a security report, a confidently wrong sentence about tooling is worse than silence.
   Evidence: `skills/security-audit/scripts/dependency_audit.py:99-104` (the map), `:316` (`owners = ...`), `:333-335` (the message).
   Suggested fix direction: check whether `preferred` is among the candidate tool names before using the "not installed" wording, and emit a distinct note — "the lockfile indicates bun, which has no supported auditor here" — otherwise.

6. **P3: `repo_inventory.py --format json` has no size cap, and emits the full file list twice.**
   `--top` is applied only in `render()`; the JSON branch returns everything. `largest_files` is one row per file and `deepest_paths` is the entire sorted file list, so both scale 1:1 with repo size. Measured on this repository: 62 files, 62 `largest_files` entries, 62 `deepest_paths` entries, 10,996 characters of JSON versus 2,511 for the text report. On a 5,000-file repo that is roughly 10,000 rows of raw path enumeration handed to an agent that has only a 25-row budget in the text path.
   `skills/repo-health-audit/SKILL.md:74` documents JSON as the "filter the results yourself" mode, so unfiltered output is intentional — but "unfiltered" and "unbounded" are different, and `deepest_paths` is enumeration rather than findings.
   Confidence: medium (the design intent is documented; the unbounded scaling is the part I am calling a defect).
   Evidence: `skills/repo-health-audit/scripts/repo_inventory.py:242`, `:248`; `skills/repo-health-audit/SKILL.md:74`.
   Suggested fix direction: apply `--top` to `largest_files` and `deepest_paths` in the JSON payload too, with a `truncated: true` marker, or cap them at a generous fixed number.

7. **P3: `docs_drift.py` uses `lstrip("export ")` where it means "remove the `export ` prefix".**
   `str.lstrip` takes a character set, not a prefix, so this strips any leading run of `e`, `x`, `p`, `o`, `r`, `t`, and space. It happens to be harmless today only because `ENV_NAME` requires the key to start with an uppercase letter, and none of those six characters are uppercase — so no real env var name is currently mangled. It is a latent trap: the moment the name pattern is relaxed, or an env sample uses a lowercase key, keys start getting silently truncated.
   Evidence: `skills/docs-sync-audit/scripts/docs_drift.py:240`.
   Suggested fix direction: `key = key[len("export "):] if key.startswith("export ") else key`, or `re.sub(r"^export\s+", "", key)`.

8. **P3: `collect_pr_context.py` reports "not a git repository" cleanly but dies with a traceback on other git failures.**
   `resolve_repo` handles the non-repo case with a readable `SystemExit`, but `git_out(["merge-base", ...])` at line 153 runs with `check=True`. Two branches with unrelated histories — a real situation when someone points `--base` at a freshly created orphan branch — makes `git merge-base` exit non-zero, and the user gets a `CalledProcessError` stack trace instead of the guidance `resolve_base_ref` already knows how to give.
   Confidence: high on the code path, medium on how often a user hits it.
   Evidence: `skills/pr-branch-summary/scripts/collect_pr_context.py:153`, versus the clean handling at `:46-48` and `:80-82`.
   Suggested fix direction: wrap the `merge-base` call and raise `SystemExit` with the same "try fetching, or pass an explicit ref" advice.

9. **P3: Installing the plugin ships a deliberately vulnerable Express app and a file named `.env.example` onto the user's machine.**
   `.claude-plugin/marketplace.json` sets `"source": "./"`, so a `/plugin install` brings the whole repository, `evals/fixtures/mini-app/` included: an export handler with no ownership check, an admin delete with no role check, and an env sample containing `API_TOKEN=`. Everything is labelled — the `.env.example` first line says "FAKE VALUES - eval fixture only", and both handlers carry a comment naming their planted defect — and `evals/fixtures/README.md` documents the whole set. The realistic cost is a security scanner or a curious reviewer flagging a plugin directory, not an actual exploit.
   Confidence: medium — this is a packaging-hygiene judgement, not a defect.
   Evidence: `.claude-plugin/marketplace.json` (`"source": "./"`); `evals/fixtures/mini-app/src/routes/exports.js:4`; `evals/fixtures/mini-app/src/routes/admin.js:4`; `evals/fixtures/mini-app/.env.example:1`.
   Suggested fix direction: decide deliberately and say so. Either leave it and add one line to the README's Safety section noting the fixture is intentionally defective, or narrow what the plugin ships.

**What is in good shape**

Worth saying plainly, because padding this list would be the easy failure mode of a launch audit:

- Both validators pass clean on the current tree, and neither writes anything: `validate_skills.py` reports 0 errors / 0 warnings, `validate_evals.py` reports 0 errors across 7 eval files and 27 cases including byte-exact snapshot comparison of 4 bundled scripts.
- The read-only claim holds up under inspection. Every script uses `subprocess.run` with list arguments and no `shell=True`; the only write path in the whole collection is `collect_pr_context.py --output`, and it actively refuses to write inside the target repository without `--allow-repo-output` (`:230-234`). Running `docs_drift.py` and `repo_inventory.py` against this repo left `git status` unchanged.
- Secret handling in `dependency_audit.py` is genuinely careful rather than decorative: `redact()` strips URL credentials and query tokens before anything read from a file is echoed, install-hook bodies are counted rather than printed, and `.npmrc`-style registry findings report only the matched setting *name* taken from a fixed alternation, never the value.
- The `--allow-network` default-off posture in a security skill is the right call and is explained where a reader will find it.
- The eval result files are unusually honest — `evals/results/2026-09-03-opus-5.json` records a behavior-case failure and its root cause, and `2026-09-05-real-code-trial.json` records 15 citation errors out of 106 spot-checked findings in the baseline run. That is a real measurement, not marketing.
- `.gitattributes` normalizes `md`/`yaml`/`py` to LF and pins `evals/fixtures/**` to LF with a comment explaining that the snapshot tests compare byte counts. That is the correct fix for the hazard the Windows CI leg exists to catch.
- `README.md:95`'s "for most of them, a bundled read-only Python script" is accurate (5 of 7), and `README.md:8`'s "each ships an `agents/openai.yaml`" is accurate (7 of 7). I checked both because they are the kind of claim that rots.

**Surveyed But Not Deeply Inspected**
- The prose bodies of the six non-`feature-audit` `SKILL.md` files. I checked their structure, required sections, report headers, and script invocation lines, but did not read each discovery workflow for whether it actually elicits a good audit. The repo's own eval suite is the right instrument for that — run `python tools/validate_evals.py --checklist` against a live agent.
- `CONTRIBUTING.md` beyond the eval-kind definitions.
- The `evals/fixtures/mini-app/` source beyond the two route handlers and the env sample. It is intentionally defective by design and `evals/fixtures/README.md` is the answer key, so auditing it would be auditing the wrong thing.
- `tools/make_social_preview.py` (155 lines) and `assets/social-preview.png`. Not on any user-facing path and not run by CI.
- `examples/repo-health-audit-self.md` is a historical artifact pinned to commit `cbaba7f` and refers to a `repo-organization-audit` skill that no longer exists. That is stated in its own header, so it is not drift, but a second example from the current tree would age better.

**Checks Run**
- `python tools/validate_skills.py`: pass, exit 0. "7 skills checked. Descriptions total 3797/5000 chars. OK: 0 errors, 0 warning(s)."
- `python tools/validate_evals.py`: pass, exit 0. "7 eval files, 27 cases checked. OK: 0 errors." Working tree unchanged afterwards.
- `python skills/docs-sync-audit/scripts/docs_drift.py --repo .`: 13 docs checked, 3 findings, all three inside `evals/fixtures/` and all three expected per `evals/fixtures/README.md:33`. No drift found in `README.md` or `CONTRIBUTING.md`.
- `python skills/repo-health-audit/scripts/repo_inventory.py --repo . --format json`: 62 files; `largest_files` 62 entries, `deepest_paths` 62 entries, 10,996 chars. Text mode for comparison: 2,511 chars. (Finding 6.)
- `ls skills/*/SKILL.md | wc -l` → 7. `ls skills/*/scripts/*.py | wc -l` → 5. `ls skills/*/agents/openai.yaml | wc -l` → 7.
- `for f in skills/*/SKILL.md; do grep -c "^## Related Skills" "$f"; done` → 1 for every skill except `feature-audit`, which returns 0. (Finding 3.)
- `grep -n reconfigure -r skills tools` → 6 hits: `docs_drift.py:45`, `repo_inventory.py:31`, `dependency_audit.py:43`, `coverage_map.py:33`, `validate_evals.py:33`. `collect_pr_context.py` and `validate_skills.py` do not appear. (Finding 1.)
- `python -c` encoding a `'→'` through a strict cp1252 `TextIOWrapper`: raises `UnicodeEncodeError: 'charmap' codec can't encode character '→' in position 6`. (Finding 1.)
- `find . -name __pycache__` outside `.git`: 3 directories. (Finding 4.)
- `git ls-files | grep -i pycache`: no matches — the `.pyc` files are untracked, which is exactly why `git status` stays clean while the tree is dirty.
- `git check-attr -a .github/workflows/ci.yml` → `text: set`, `eol: lf`; `git config core.autocrlf` → `true`.
- `git status --short` at the start of the audit: clean.

**Not Tested**
- Nothing was run over the network. The `skills.sh` badge (`README.md:4`), `npx skills add specialone0007/review-skills`, the `/plugin marketplace add` flow, the `npx @anthropic-ai/claude-code plugin validate` CI job, and every `--allow-network` auditor in `dependency_audit.py` are all unverified here. The two install paths in particular are the highest-value thing left to check before launch, and neither can be checked from source.
- No GitHub Actions run was executed. All CI findings come from reading the workflow file.
- Tier-2 evals were not run. Whether a description triggers, and whether a report obeys its contract, needs a live model, which is the repo's own stated position at `tools/validate_evals.py:18-22`.
- The Windows encoding failure in finding 1 was reproduced at the codec level, not by running `collect_pr_context.py` on a Windows console against a branch containing non-ASCII commits. The mechanism is confirmed; the end-to-end crash is inferred from it.
- `dependency_audit.py` was not run against a bun repository; finding 5 is from reading the code path, not from observing the message.

**Assumptions**
- The working tree changed during this audit. `git status --short` was clean when I started and reported `M .github/workflows/ci.yml` partway through — an uncommitted edit adding a Windows matrix to the `validate` job. I did not make it and did not touch it. I audited the committed state at `13fdbd1` and flagged the overlap in finding 2; if that edit is yours, confirm before acting on finding 2.
- "Launch" means publishing this as a public plugin and skills collection for other people to install, so I weighted claims a stranger can check (the README, the manifests, cross-platform behavior) above internal polish.
- Paths are repo-relative because `tools/validate_skills.py:250` rejects machine-specific absolute paths in committed Markdown, and this report is destined for `examples/`.
