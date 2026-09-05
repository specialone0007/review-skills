# `feature-brainstorm` on this repository

**Prompt:** "what could we improve here"  
**Repository:** `specialone0007/review-skills` at `cc100ad`  
**Files changed by the run:** none — the skill is read-only

Ran feature-brainstorm read-only against the review-skills repository itself, picking three surfaces (the shared skill contract across the seven SKILL.md files, the eval harness in evals/ and tools/, and the published examples/) and grounding each idea in cited lines plus the repo's own recorded eval and real-code trial results.

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Feature Brainstorm: the review-skills repository itself — the shared skill contract, the eval harness, and the published examples**

No code changed. I reviewed the seven `SKILL.md` files, `tools/validate_skills.py`, `tools/validate_evals.py`, `evals/` (cases, fixture, snapshots, recorded results), the README and CONTRIBUTING, to identify improvement opportunities rather than defects. `feature-brainstorm` ships no bundled script, so there was none to run; everything below comes from source inspection. `git status --short` was empty before and after.

You did not name a surface, so I inventoried the repo and picked the three highest-leverage ones:

1. **The shared contract across the seven skills** — the paragraphs every skill repeats (citation rules, count rules, report template). It is the product, and it is currently maintained by copy-paste.
2. **The eval harness** — the only thing that tells you a change to a skill did not make it worse.
3. **The published examples** — the shop window; `README.md:40` sends readers to `examples/`.

I skipped the five bundled Python scripts and the CI workflow: both look well-tended, and the interesting leverage is not there.

First, plainly: this repo is in good shape. `tools/validate_skills.py` already enforces frontmatter, display-name agreement with `agents/openai.yaml`, that a report header matches the display name (`tools/validate_skills.py:206`), that referenced bundled paths exist (`tools/validate_skills.py:212`), and that `## Related Skills` resolves (`tools/validate_skills.py:224`). CI runs it on two OSes plus first-party `plugin validate`. Ideas below are about the layer above that.

## Highest-Leverage Ideas

1. **A citation-checker the skills can run on their own report before emitting it**
   - Opportunity: a small standard-library script — `tools/verify_citations.py` — that reads a draft report, extracts every `path:line`, and checks the cited line literally contains the symbol or quoted text named beside it. Skills would call it as a last step, the way they call the other bundled scripts.
   - Why it matters: this is the one measured, still-open defect class in your own trial record. `evals/results/2026-09-05-real-code-trial.json` lists under `still_broken` "Fine-grained anchoring" — pointers landing on a blank line above a definition or on a decorator — and "Quoted-text drift", with one outlier 179 lines away. The current fix is prose in seven files asking the model to be careful. A deterministic check turns an instruction into a gate.
   - Evidence: `skills/security-audit/SKILL.md:78` states the rule ("the line you cite must literally contain the thing you name"); the trial file records that the rule did not fully take.
   - First step: write the extractor for the one report shape you already control — `Evidence: \`path:line\`` lines — and run it over `examples/repo-health-audit-self.md` to see whether it catches anything today.
   - Effort: Medium
   - Confidence: High

2. **Promote the repeated rule blocks into one shared contract, and validate that skills carry it verbatim**
   - Opportunity: the citation and count rules exist in five near-identical copies, one abbreviated copy, and one absence. Compare `skills/security-audit/SKILL.md:78` / `:81`, which are byte-identical to `skills/docs-sync-audit/SKILL.md:89` / `:92`, `skills/feature-audit/SKILL.md:102` / `:105`, `skills/repo-health-audit/SKILL.md:119` / `:122` and `skills/test-gap-audit/SKILL.md:92` / `:95` — against `skills/feature-brainstorm/SKILL.md:80` and `:81`, which are a shorter paraphrase, and `skills/pr-branch-summary/SKILL.md:108`, which has a count rule and no citation rule at all. Add the canonical text to `CONTRIBUTING.md` and a check in `tools/validate_skills.py` that every audit skill contains it unmodified.
   - Why it matters: you have already paid for this drift once. `evals/results/2026-09-03-opus-5.json` records a behavior-case failure whose root cause was exactly this — one skill's template embedded lowercase `evidence:` mid-sentence while three siblings used a labelled `Evidence:` line. Prose duplicated seven ways drifts silently; a validator makes drift a red build.
   - First step: decide whether the short form in `feature-brainstorm` is intentional (brainstorms cite fewer symbols) or just stale, then encode whichever answer you pick.
   - Effort: Small
   - Confidence: High

3. **Give `feature-brainstorm` and `pr-branch-summary` somewhere to put the commands their own rules demand**
   - Opportunity: `skills/feature-brainstorm/SKILL.md:81` requires that "Any number you state must appear next to the command that produced it" — but its Report Format (lines 87–121) has no **Checks Run** section, unlike the five skills that do (`skills/security-audit/SKILL.md:120`, `skills/feature-audit/SKILL.md:136`, `skills/docs-sync-audit/SKILL.md:127`, `skills/repo-health-audit/SKILL.md:156`, `skills/test-gap-audit/SKILL.md:138`). The rule points at a section that does not exist in the template.
   - Why it matters: a rule with no slot in the output contract is a rule the model has to improvise around, and improvisation is where the trial found count restatement failing twice.
   - First step: add an optional **Checks Run** block to the `feature-brainstorm` template, marked "include only if you stated a number".
   - Effort: Small
   - Confidence: High

4. **A second, larger eval fixture built specifically so line numbers can drift**
   - Opportunity: every behavior case in `evals/` targets the same `fixtures/mini-app` (all seven eval JSON files name it, except `pr-branch-summary`, which uses git history instead). Add a second fixture — a few files of several hundred lines each, with decorators, multi-line dicts and long comment blocks — aimed at anchoring rather than at planted defects.
   - Why it matters: your own record says the current fixture structurally cannot catch the open defect class. `evals/results/2026-09-05-real-code-trial.json:48`: "The 15-file fixture cannot surface this class of defect at all, because it is too small for line numbers to drift." Right now the only instrument for it is a manual private-repo trial you cannot publish.
   - First step: one file, ~400 lines, with three symbols each preceded by a decorator and a blank line, and one behavior case that requires citing them.
   - Effort: Medium
   - Confidence: High

5. **Publish one example report per skill, and document how to regenerate them**
   - Opportunity: `README.md:40` says "A complete run is in [examples/](examples/)", and `examples/` holds exactly one file, `examples/repo-health-audit-self.md` — one of seven skills. Add a run per skill against this repository (this report is one), plus a short CONTRIBUTING section naming the exact prompt each was produced from.
   - Why it matters: examples are how a stranger evaluates skills they cannot run cheaply, and they double as regression evidence: a report generated from a recorded prompt is a diffable artifact when you change a Report Format. Six of seven skills currently have no public sample of their output.
   - First step: record the prompt used for `repo-health-audit-self.md` next to it, so later examples follow one convention.
   - Effort: Small
   - Confidence: High

## Quick Wins

- **Even out trigger-case coverage.** Counting cases by kind (`python -c` over `evals/*.json`, output above): five skills have 2 trigger cases and 1 anti-trigger; `feature-brainstorm` has 1 trigger; `test-gap-audit` has 1 trigger and 2 anti-triggers. Routing is what descriptions are for, and it is cheap to add one more trigger phrasing to the two thin ones.
- **Name the prompt in `examples/`.** One line at the top of each example — the verbatim prompt and the model — turns a sample into something a reader can re-run and compare. Cheap, and it makes every future example self-describing.
- **State the script coverage explicitly in the skills table.** `README.md` says most skills bundle a script; `git ls-files` shows five do (`docs_drift.py`, `collect_pr_context.py`, `repo_inventory.py`, `dependency_audit.py`, `coverage_map.py`) and `feature-audit` and `feature-brainstorm` do not. A column in the skills table answers "does this one have an accelerator" without a directory listing.

## Bigger Bets

- **A scored, repeatable trial protocol instead of a hand-written trial write-up.** The two files in `evals/results/` are narrative JSON with different shapes — the 2026-09-03 file has `routing`/`behavior` keys, the 2026-09-05 file has `runs` with per-run keys that themselves differ (run 1 has `errors`, run 2 has `citation_errors`/`substantive_errors`/`absence_errors`). The file even flags this: run 2's `grading` says it is "deliberately not comparable to run 1 as a percentage". A fixed result schema plus a checked-in judge prompt would make releases comparable over time. Worth it only if you intend to keep running trials every release; otherwise the prose is fine.
- **Ship the report contract as a machine-readable schema.** If the seven report formats were one small schema (severity vocabulary, required `Evidence:` line, optional Checks Run), you could validate real reports in CI, generate the Markdown templates into each `SKILL.md`, and give downstream users something to parse. This is the natural end state of ideas 1–3, but it is a rewrite of how skills are authored — do not start here.

## Not Pursuing

- **An LLM judge in CI.** Tempting, and it is the obvious answer to "the eval harness is half manual" (`tools/validate_evals.py:18` documents that tier 2 is a human checklist). But `CONTRIBUTING.md` already rejects it with four concrete reasons — cost per push, flakiness, an API key in a public repo, and rot. I agree, and idea 1 gets much of the benefit deterministically.
- **Splitting the seven skills into separate repos or packages.** One marketplace, one validator, one eval suite, one CI is the reason the contract holds at all. The shared surface is the asset.
- **Adding a bundled script to `feature-brainstorm` for symmetry.** There is no deterministic input a brainstorm needs that `repo_inventory.py` does not already produce. A script added for consistency would be a script nobody runs.

## Audit Candidates

- Nothing rising to a defect. One thing a `docs-sync-audit` run would likely flag rather than a brainstorm: `README.md:40` points at `examples/` in the plural while the directory holds a single skill's report.

## Assumptions

- I treated `evals/results/*.json` as trustworthy records of real runs rather than re-running any trial; ideas 1 and 4 lean on them heavily.
- I assumed the abbreviated evidence rules in `feature-brainstorm` are drift rather than a deliberate exception for non-audit skills. If deliberate, idea 2 shrinks to "write down why".
