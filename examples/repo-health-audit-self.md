# Example: `repo-health-audit` run on this repository

A real, unedited-in-substance run of `repo-health-audit` against `review-skills` itself at commit
`cbaba7f`, with no scope named — so it took the full-repo path.

This is the audit that produced the `v0.1.0` cleanup. Every finding below was fixed afterwards, so
you can check the report against `git log` rather than taking it on trust. It is kept here as a
worked example of the output contract: severity, evidence, fix direction, and an explicit statement
of what was *not* checked.

---

**Repo Health Audit: whole repository (7 skills, 19 files)**

No code changed. I checked the whole repository, including naming, file/folder placement, module
boundaries, dead code, duplicate code, helper extraction opportunities, and convention drift.
Surveyed 7 skill directories and 4 root files; inspected all 7 `SKILL.md` files, all 7
`agents/openai.yaml` files, the one bundled script, and the README in depth. P0s found: 0.

1. **P1: One skill is called three different things, and the README propagated the wrong one.**
   The folder and H1 say "Repo Organization Audit", but `agents/openai.yaml` declares
   `display_name: "Repo Health Audit"`, the emitted report header is `**Repo Health Audit: <scope>**`,
   and the README's own example mirrors the header rather than the skill. Every other skill's
   `display_name` is exactly the title-case of its folder, so this one is the outlier in three
   places at once. Users searching for either name find half the surface.
   Evidence: `skills/repo-organization-audit/SKILL.md:6`, `:123`,
   `skills/repo-organization-audit/agents/openai.yaml:2`, `README.md:100`.
   Suggested cleanup direction: pick one name, apply it to folder, frontmatter `name`, H1,
   `display_name`, report header, and README together, and keep the discarded word as a description
   keyword so existing prompts still trigger.

2. **P1: The README's safety claim is not true of one skill.**
   `README.md` states that skills are read-only by default, but `pr-branch-summary` has no
   read-only posture statement anywhere in its body — the only one of seven without one — and its
   workflow runs `git fetch --all --prune`. That writes remote-tracking refs for every configured
   remote and deletes stale ones. It is a mild mutation rather than a dangerous one, but the
   documentation promises otherwise, and `--all` is gratuitous when exactly one base branch is needed.
   Evidence: `README.md:121`, `skills/pr-branch-summary/SKILL.md:22`, `:101`.
   Suggested cleanup direction: narrow the command to `git fetch origin <base>`, add the missing
   `## Core Rules` block stating the posture and the one carve-out, and rewrite the README claim to
   be precise instead of approximate.

3. **P2: Four of five audits cannot do the thing the README implies.**
   Only `test-gap-audit` defaults to a full-repository audit when no scope is given; it carries that
   default in its description, a Core Rule, and its discovery workflow. The other four say "infer the
   smallest useful boundary", and three descriptions require "a clearly named feature". So "review my
   repo" narrows to a guessed feature or asks a clarifying question in four of five cases. The
   capability exists, in one skill, and never propagated.
   Evidence: `skills/test-gap-audit/SKILL.md:13`, `:25`, `:36` versus
   `skills/feature-audit/SKILL.md:35`, `skills/security-audit/SKILL.md:31`,
   `skills/docs-sync-audit/SKILL.md:32`, `skills/repo-organization-audit/SKILL.md:31`.
   Suggested cleanup direction: copy the `test-gap-audit` pattern into the other four, and pair it
   with an explicit breadth-first-then-depth-limited rule so a full-repo pass on a large monorepo
   degrades into a ranked survey rather than shallow noise.

4. **P2: The README is the single largest drift source in the repo.**
   Routing is stated three times — the skills table, a second "Choose The Right Skill" table, and a
   prose list — and all seven report formats are duplicated in a "Compact Output Examples" block.
   That is roughly 48 lines hand-synced against seven files, with no check that they agree. This is
   the mechanism by which finding 1 reached the README: the example was copied from the header, and
   nothing compared it to the skill name.
   Evidence: `README.md:9-17`, `:21-29`, `:60-68`, `:74-117`.
   Suggested cleanup direction: collapse to one routing table, drop the prose restatement, keep one
   or two illustrative examples, and let each skill own its own report format.

5. **P2: A required section is missing from two of seven skills.**
   `## Agent Portability Notes` is present in five skills and absent from `pr-branch-summary` and
   `repo-organization-audit`. For a collection whose entire pitch is portability across agents, the
   section that describes graceful degradation is not optional.
   Evidence: present at `skills/feature-brainstorm/SKILL.md`, `skills/security-audit/SKILL.md`,
   `skills/docs-sync-audit/SKILL.md`, `skills/feature-audit/SKILL.md`,
   `skills/test-gap-audit/SKILL.md`; absent from the other two.
   Suggested cleanup direction: add the section to both, with a skill-specific degradation line
   rather than boilerplate.

6. **P3: The bundled script is referenced two incompatible ways.**
   Step 2 of the workflow says `scripts/collect_pr_context.py`, while the example command below it
   uses `/path/to/pr-branch-summary/scripts/collect_pr_context.py`. Neither is right on its own: the
   real install path varies by host (`.claude/skills/`, `~/.codex/skills/`, and others), so the
   correct instruction is "relative to this skill's own directory".
   Evidence: `skills/pr-branch-summary/SKILL.md:24`, `:28-29`.
   Suggested cleanup direction: one phrasing in both places, with a `<skill-dir>/` placeholder and a
   `python`/`python3` fallback note.

7. **P3: Nothing mechanically enforces any of the above.**
   There is no CI and no validator, so every convention in this repo is upheld by memory. Findings
   1, 5, and 6 are all drift that a fifty-line script would have caught the day it appeared.
   Evidence: no `.github/` directory; no `tools/` directory.
   Suggested cleanup direction: a standard-library validator plus one GitHub Actions job, checking
   the conventions this audit had to verify by hand.

**Reuse Opportunities**
- All seven skills restate the same read-only posture, repo-agnostic rule, and evidence standard in
  their own words. This duplication is correct and should be kept — skills are installed
  individually, so a shared reference file would not ship with them — but the *wording* should be
  aligned so drift between them is visible.

**Surveyed But Not Deeply Inspected**
- `LICENSE`, `.gitignore`, `.gitattributes`: read, and all three are appropriate. `.gitattributes`
  already normalizes `md`/`yaml`/`py` to LF, which removes the usual Windows-checkout hazard.
- The prose *quality* of each skill's discovery workflow, as opposed to its structure. A pass focused
  on whether the instructions actually elicit good audits — rather than whether they are internally
  consistent — is the natural next run, and is better done with evals than by reading.

**Checks Run**
- `git log -3 --format="%h %ad %s" --date=short`: last commit `2026-05-06`, four months stale, one commit unpushed.
- `grep -rn "repo-organization-audit\|Repo Organization"`: 10 references across 5 files.
- `wc -l` and `wc -c` over all 7 `SKILL.md` files: 109–158 lines, ~1,777–3,693 tokens each. All well
  inside the 500-line spec guidance.
- Description length sum across 7 skills: 3,713 chars, ~928 tokens resident on every request.
- `grep -c "Agent Portability Notes"`: present in 5 of 7.
- `python -c "import ast; ast.parse(...)"` on `collect_pr_context.py`: parses cleanly. Reviewed for
  shell injection and found none — `subprocess.run` with list arguments throughout, no `shell=True`,
  no network access, and `write_text(..., encoding="utf-8")` on the output path.

**Not Tested**
- No dependency-graph, dead-code, or duplicate-code tooling was run; this repo has no dependency
  manifest, so there is nothing for those tools to analyze. Duplication findings come from reading.
- No linter or type checker exists in the repo, so neither was run.
- The skills were not executed end-to-end against a target repository. This audit checked the
  instructions, not the behavior they produce. Findings 3 and 7 are the ones most likely to shift
  once behavior is actually measured.

**Assumptions**
- I assumed the skills are meant to be installed individually as well as together, which is what
  makes the per-skill duplication in Reuse Opportunities correct rather than a defect. The README's
  per-skill install command supports this.
