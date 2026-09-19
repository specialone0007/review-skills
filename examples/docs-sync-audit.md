# `docs-sync-audit` on this repository

**Prompt:** "check the docs against the code"  
**Repository:** `specialone0007/review-skills`, branch `fix/docs-structure-layout` on top of `5597942`, with the removal of `feature-brainstorm` and `pr-branch-summary` applied  
**Files changed by the run:** none — the skill is read-only

Full-repository read-only docs drift audit, running the bundled docs_drift.py across 49 documents, then checking the prose of all five root docs against the code they cite — including an AST scan of every import in the repository to settle two claims the script cannot see.

Re-run it yourself and compare. Line numbers refer to the tree described above, so a later commit will shift them.

> Dated example. The script has since gained the `version-pin`, `runtime-version`, `license-mismatch` and `port-mismatch` kinds, shell-style env reads, `pnpm x` shorthand and a `--claims <doc>` checklist, and the report format now carries a `Status:` line per finding, per-doc Checks Run lines and a floor marker; a run on the current version reports more rows and in that shape.

---

**Docs Sync Audit: whole repository (review-skills)**

No code changed. I compared the five root documents — `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `examples/README.md`, `evals/fixtures/README.md` — plus the two plugin manifests against the code, CI workflow and scripts they describe. I ran the bundled drift checker over 49 documents and confirmed each prose claim by opening both sides. No P0s found.

**The machine-checkable half is clean.** `docs_drift.py` returned two findings and both sit inside `evals/fixtures/`, which is deliberately defective by design — they are the planted defects, not drift. Everything below came from reading prose against source, which is where the real drift was.

1. **P2: `tools/make_social_preview.py` requires Pillow, and no document in the repository says so.**
   Drift: `tools/make_social_preview.py:25` does `from PIL import Image, ImageDraw, ImageFont`. Pillow is not in the standard library. The repository has no `requirements.txt`, no `pyproject.toml` and no `setup.py` at its root, and a case-insensitive search for "pillow" across every tracked Markdown, text, TOML and YAML file returns nothing. `ARCHITECTURE.md:37` lists the tool in the parts table — "social preview | generates the repository's preview image" — with no qualification. `CONTRIBUTING.md` never mentions it at all.
   The surrounding prose actively points the wrong way. `CONTRIBUTING.md:118` states the rule "use the Python 3 standard library only, and install nothing". That rule is scoped to bundled scripts under the `## Bundled scripts` heading at `:114`, and it is correct for all seven of them — but nothing anywhere records that one maintainer tool is the exception, so the reasonable inference from reading the repo's docs is that all its Python is dependency-free.
   Impact: adding or removing a skill means the preview image is stale until someone regenerates it — exactly the situation this change created. A contributor who tries hits `ModuleNotFoundError: No module named 'PIL'` and has no document to consult. It is a two-minute problem that reads like a broken tool.
   Evidence: source `tools/make_social_preview.py:25`; expected docs area `CONTRIBUTING.md:114` (the `## Bundled scripts` section, or a sibling section for maintainer tools) and `ARCHITECTURE.md:37`.
   Suggested update: one sentence in `CONTRIBUTING.md` under a short `## Maintainer tools` heading — the two validators are standard library only, `make_social_preview.py` needs `pip install Pillow`, and it must be re-run whenever the skill list changes. Add "(needs Pillow)" to the `ARCHITECTURE.md:37` row.

2. **P2: `ARCHITECTURE.md` attributes two claims to a file that checks neither of them.**
   Drift: `ARCHITECTURE.md:55` reads "Bundled scripts use the Python standard library only and never write, so they run anywhere without setup and cannot damage the repository they are pointed at [tools/validate_skills.py]." The validator does neither check. Its four check functions are `check_skill` (`tools/validate_skills.py:148`), `check_subprocess_encoding` (`:253`), `check_paths_and_links` (`:269`) and `check_readme` (`:302`) — frontmatter and metadata, one subprocess-decoding rule, path hygiene, and the README skill table. Nothing inspects imports and nothing inspects writes.
   This matters more than a normal miscitation because the bracket convention *is* the document's evidence mechanism. `ARCHITECTURE.md:7` promises "every sentence names the file it came from". A reader who follows this bracket to check the claim finds a file that does not support it, and the natural conclusion is that the brackets cannot be trusted.
   The claim itself is true. An AST scan of every import in `skills/*/scripts/*.py` returns only standard-library modules plus three sibling imports inside the `docs-structure` folder. It is the citation that is wrong, and the right sources exist: the rule is stated at `CONTRIBUTING.md:118` and enforced at `.github/workflows/ci.yml:122`, where CI runs all seven scripts and then asserts `git status --porcelain` is empty.
   Impact: a maintainer trusting the bracket would look for an import check in the validator, not find one, and either add a redundant one or conclude the doc is fiction.
   Evidence: docs `ARCHITECTURE.md:55` and its own rule at `ARCHITECTURE.md:7`; source `tools/validate_skills.py:148`, `:253`, `:269`, `:302`.
   Suggested update: re-bracket the sentence to `[CONTRIBUTING.md]` for the rule and `[.github/workflows/ci.yml]` for the enforcement. Leave the second and third sentences of that paragraph alone — both are correctly attributed.

3. **P2: `CONTRIBUTING.md`'s self-containment rule forbids what three scripts actually do, and the exception is recorded only in code comments.**
   Drift: `CONTRIBUTING.md:119` requires each script to "be self-contained inside their own skill, since people install skills individually". Read literally, that forbids one script importing another. Three do: `skills/docs-structure/scripts/docs_split.py:33` (`import docs_structure as ds`), `skills/docs-structure/scripts/docs_structure.py:69` and `skills/docs-structure/scripts/docs_fill_gate.py:58` (both `import docs_evidence`).
   Those imports are correct — all four files live in one folder that installs as a unit, so the rule's stated reason ("people install skills individually") is not violated. But the distinction between *within a skill* and *across skills* appears nowhere in the documentation. It survives only as an inline comment repeated in two of the three importers: "sibling script, same folder, stdlib only".
   `README.md:162` compounds it slightly, telling users each folder holds "a bundled read-only Python script that uses only the standard library" — singular, and true of four skills but not of `docs-structure`, which holds four scripts that depend on each other. Someone copying one file out of that folder gets an `ImportError`.
   Impact: a contributor adding a fifth `docs-structure` script follows `CONTRIBUTING.md` literally and duplicates a helper rather than importing it. That is how the divergent `walk()` implementations in that folder most plausibly arose.
   Evidence: docs `CONTRIBUTING.md:119`, `README.md:162`; source `skills/docs-structure/scripts/docs_split.py:33`, `skills/docs-structure/scripts/docs_structure.py:69`, `skills/docs-structure/scripts/docs_fill_gate.py:58`.
   Suggested update: amend `CONTRIBUTING.md:119` to "be self-contained inside their own skill folder — a sibling import within one folder is fine, since the folder installs as a unit; an import across skill folders is not". One clause, and it turns three code comments into a stated rule.

4. **P3: `evals/results/` holds three files and nothing documents the convention.**
   Drift: `evals/results/` contains `2026-09-03-opus-5.json`, `2026-09-05-real-code-trial.json` and `2026-09-16-fill-trial.json`. `grep -n "results" CONTRIBUTING.md` returns nothing. The natural home is `## Trialling the skills on real code` at `CONTRIBUTING.md:99`, which tells contributors at length how to write up a trial without privacy leaks and never says where the write-up goes or what shape the file takes.
   Impact: a contributor who runs a real-code trial — which `CONTRIBUTING.md:101` actively encourages before a release — has no way to learn that recording the result as dated JSON is the convention. The folder reads as an archive someone forgot.
   Evidence: docs `CONTRIBUTING.md:99`; source the three files under `evals/results/`.
   Suggested update: two sentences in that section naming `evals/results/<date>-<label>.json`, stating that it is hand-written, that nothing validates it, and what the fields mean.

5. **P3: the architecture diagram shows scripts as leaves, and three of them are not.**
   Drift: `ARCHITECTURE.md:14` draws `scripts/*.py` as a terminal branch under `skills/<name>/` with no edges between scripts. The `docs-structure` folder has a real internal dependency graph: `docs_split.py` → `docs_structure.py` → `docs_evidence.py`, and `docs_fill_gate.py` → `docs_evidence.py`. For the one skill that carries most of the repository's code, the diagram omits its only non-obvious structure.
   Impact: low — the diagram is a draft and labelled as such. Someone planning a change to `docs_evidence.py` would not learn from it that two other scripts depend on that file.
   Evidence: docs `ARCHITECTURE.md:14`; source the three import lines cited in finding 3.
   Suggested update: one extra line in the diagram under `scripts/*.py`, e.g. `└─ (docs-structure: split → structure → evidence)`.

**Likely Docs To Update**

- `CONTRIBUTING.md`: the Pillow note (finding 1), the self-containment clause (finding 3), the `evals/results/` convention (finding 4). Three small edits, all in one file.
- `ARCHITECTURE.md`: re-bracket line 55 (finding 2) and extend the diagram (finding 5). It is still marked `draft` in the README index, which is honest — these are exactly the kind of thing a review pass is for.
- `README.md`: soften "a bundled read-only Python script" at line 162 to acknowledge that one skill carries several (finding 3).

**Surveyed But Not Deeply Inspected**

- `skills/docs-structure/references/structure.md` (326 lines) and the template files under `references/templates/`. Confirmed reachable from their SKILL.md and that the paths resolve; did not check their prose against `docs_structure.py`'s actual rule set. That file is the largest un-audited doc surface in the repo and is the obvious next pass.
- The five `SKILL.md` bodies end to end. I checked their script-invocation lines against real flags and their `## Related Skills` entries against the skills that exist — all resolve — but did not read each body against its script's behaviour. `docs-structure/SKILL.md` makes the most specific behavioural claims in the repo and is the best next target.
- `evals/fixtures/README.md` against the fixtures' actual contents. The drift script's two findings there are planted defects listed in that README; I did not verify the whole defect table is still accurate.
- The plugin manifests against what a marketplace actually installs. Both validate under the first-party plugin validator in CI (`.github/workflows/ci.yml:66`), which is stronger than anything I could check by hand.

**Checks Run**

- `python skills/docs-sync-audit/scripts/docs_drift.py --repo . --format text`: 49 docs checked, 2 findings — `missing-script` at `evals/fixtures/mini-app/README.md:12` and `broken-link` at `evals/fixtures/mini-app/docs/drafted.md:62`. Both are planted fixture defects, listed as such in `evals/fixtures/README.md`.
- Same command with `--format json`: same two findings, no others; env names in code 4, documented 8, none skipped.
- AST scan of every `import` in `skills/*/scripts/*.py`: `argparse`, `collections`, `datetime`, `fnmatch`, `json`, `os`, `pathlib`, `re`, `shutil`, `subprocess`, `sys`, `tomllib`, `urllib`, `xml`, `__future__`, plus `docs_evidence` and `docs_structure` — standard library plus two sibling modules, no third-party package.
- Same scan over `tools/*.py`: the same standard-library set plus `PIL`.
- `grep -rniI "pillow" --include=*.md --include=*.txt --include=*.toml --include=*.yml .`: one hit, inside `examples/test-gap-audit.md`, which is generated output from this session. No hit in any hand-written document.
- `ls requirements*.txt pyproject.toml setup.py`: none exist at the repository root.
- `grep -n "^def check_" tools/validate_skills.py`: four functions, at lines 148, 253, 269, 302.
- `grep -n "import docs_" skills/docs-structure/scripts/*.py`: three hits, at `docs_fill_gate.py:58`, `docs_split.py:33`, `docs_structure.py:69`.
- `grep -n "results" CONTRIBUTING.md`: no output.
- `sed -n '55p' ARCHITECTURE.md` and `sed -n '7p' ARCHITECTURE.md`: the sentence and the "every sentence names the file it came from" promise, quoted above as written.
- `python tools/validate_skills.py`: exit 0 — "5 skills checked. Descriptions total 3407/5000 chars. OK: 0 errors, 0 warning(s)." This includes the check that the README presents exactly the skills that exist, so the README skill list is machine-confirmed current.

**Not Tested**

- No docs build or external link check was run. The repository has no docs generator, so there is no generated output that could be stale; external `https://` links (the CI badge, the skills.sh badge, the plugin marketplace instructions) were not fetched, so a dead external URL would not have been caught.
- I did not run `npx skills add` or `/plugin marketplace add`, so the install commands at `README.md:140` and `README.md:147` are unverified against the live registries. The manifests they depend on do pass the first-party validator in CI.
- I did not run `tools/make_social_preview.py` in a clean environment to observe the `ModuleNotFoundError` in finding 1. The import at `tools/make_social_preview.py:25` and the absence of any dependency manifest are both confirmed by reading; the failure mode is inferred from them.
- Prose in `skills/docs-structure/references/` was not compared against its script. See **Surveyed But Not Deeply Inspected**.

**Assumptions**

- I treated `evals/fixtures/mini-app/` and `evals/fixtures/mini-py/` as deliberately defective, so the drift script's two findings there are not reported as drift. `evals/fixtures/README.md` lists both as planted defects assigned to specific skills.
- I audited the working tree of `fix/docs-structure-layout` with the two-skill removal staged but not committed. `README.md`, `CONTRIBUTING.md` and `ARCHITECTURE.md` were all edited in that change; findings 1 through 5 describe drift that predates it and that the change did not address.
