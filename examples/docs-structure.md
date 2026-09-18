# `docs-structure` on this repository

**Prompt:** "is our docs folder organised"  
**Repository:** `specialone0007/review-skills`, branch `fix/docs-structure-layout` on top of `5597942`, with the removal of `feature-brainstorm` and `pr-branch-summary` applied  
**Files changed by the run:** none — the skill is read-only

Structure check of the review-skills repo's own Markdown, using the skill's bundled checker and inventory. This repository now commits a manifest, so discovery did not have to guess:

```json
{
  "roots": ["README.md", "CONTRIBUTING.md", "ARCHITECTURE.md", "examples/README.md", "evals/fixtures/README.md"],
  "centralIndex": "README.md",
  "requiredDocs": { "purpose": "README.md", "plan": false },
  "exempt": { "R7": ["evals/fixtures/README.md"] }
}
```

Re-run it yourself and compare. Line numbers refer to the tree described above, so a later commit will shift them.

---

**Docs Structure: whole repository (5 prose Markdown files; skill folders and fixtures excluded)**
Plan only, no files changed.

**Nothing to apply.** Every rule passes: apply would touch 0 files, create 0 skeletons, add 0 index rows, add 0 owner lines, propose 0 splits and delete nothing. `apply fill` has nothing to draft, because no concern is uncovered. The two things worth a person's attention are advisory, not failures, and both are at the bottom of this report.

The previous run of this skill on this repository found three missing concerns and a stray line-number citation. All four are gone: `ARCHITECTURE.md` now exists and covers the architecture concern, the manifest records that `README.md` owns `purpose` and that this repository has no `plan` doc by choice, and the fixture README's citation is exempted by name rather than by the checker's silence.

5 docs under `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md`, `examples/README.md`, `evals/fixtures/README.md` (0 non-doc files in docs folders). Kinds: unclassified — ten Python tools and no manifest naming a package. Ecosystems: none recognised. Manifest: explicit, quoted above. Index convention: inside. Record folders: none. Generator: none. Split candidates: 0. Checker: **0 failures, 0 warnings**.
Concerns: 3 applied, 3 covered, 0 missing. Sections: 0 skeleton, 0 draft, 15 reviewed; 9 template sections absent from hand-written docs (advice). Placeholders awaiting review: 8.

| concern | applies because | covered by | matched by | state |
| --- | --- | --- | --- | --- |
| purpose | manifest | `README.md` | manifest | reviewed |
| develop | always | `README.md` (weak) | README sections: install | reviewed |
| contribute | governance: LICENSE, CONTRIBUTING.md | `CONTRIBUTING.md` | file name; H1: contributing | reviewed |

Concerns that do not apply here, and why: the inventory found 0 packages, 0 services, no schema, no HTTP routes, no frontend, no health checks or cron, and no version field or publish script — so no deploy, data, http, design, operate or release doc is asked for. `plan` is switched off in the manifest rather than discovered absent, which is the honest way to record "we decided not to". `architecture` is covered by a doc that declares the concern in an HTML comment, and the checker does not raise it.

| rule | severity | failures | warnings | first |
| --- | --- | --- | --- | --- |
| — | — | 0 | 0 | all fourteen rules clean |

**No structural findings.** What follows is advice the checker separates from findings on purpose, because acting on either is a judgment call rather than a fix.

1. **Advice: `develop` is covered weakly, by an `## Install` heading rather than by a setup doc.**
   Evidence: `README.md:135` is the `## Install` heading the matcher used. The concern is satisfied, and for a collection of prompt files with no build step that is probably correct — there is nothing to install but the skills themselves. The five template sections the checker would expect of a develop doc are absent: Prerequisites, Setup, Daily commands, How to know it works, Common problems. Of those, only "Daily commands" has a real answer here (`python tools/validate_skills.py`, `python tools/validate_evals.py`), and `README.md:177` already gives it under `## Contributing`.
   In apply: nothing. Raising this to a finding would mean creating a `docs/DEVELOP.md` that says "there is nothing to install", which is worse than the README section that exists.

2. **Advice: eight placeholders are awaiting review, and they are all one doc.**
   Evidence: seven `*(draft, review me)*` markers in `ARCHITECTURE.md` — the owner line at `ARCHITECTURE.md:3` and one at the foot of each of its six sections — plus the `| draft |` state in the index row at `README.md:190`. Nothing else in the repository carries a placeholder.
   That is exactly what a drafted-then-not-yet-reviewed doc should look like, and the index agrees with the doc, which is the property R14 checks. The point of the count is that it does not drift downward on its own: a doc marked `draft` stays marked until a person reads it and dates the review.
   In apply: nothing. A human reads `ARCHITECTURE.md`, removes the markers, and changes the index row to `reviewed 2026-09-18`. The checker will then report 0 placeholders and will not let the row say `reviewed` without a date.

3. **Advice: `CONTRIBUTING.md` is missing four of the template's contribute sections.**
   Evidence: the checker reports `Before you start`, `Making a change`, `Checks that must pass` and `Review` absent from `CONTRIBUTING.md`, whose seven headings are `Before you open a PR`, `What the validator enforces`, `Conventions the validator cannot check`, `Adding a new skill`, `Evals`, `Trialling the skills on real code` and `Bundled scripts` — all reviewed.
   This is template advice, not drift. `Before you open a PR` at `CONTRIBUTING.md:5` is `Before you start` and `Checks that must pass` under a different name, and the doc covers more ground than the template asks for. The one genuinely absent topic is `Review` — what happens to a PR after it is opened, who looks at it, what gets it merged. For a single-maintainer repository that may simply not exist yet.
   In apply: nothing, unless you want the `Review` section. The template is a checklist to think against, not a shape to conform to.

**Checks Run**
- `python skills/docs-structure/scripts/docs_structure.py --repo . --format json`: 5 docs, 0 failures, 0 warnings, 0 split candidates, 0 unreachable docs, 0 record folders, 0 other-format docs, 3 concerns applied and 3 covered, 8 placeholders. Section states: 15 reviewed, 0 draft, 0 skeleton, 9 template sections absent.
- Same command with `--check-paths` (R6, opt-in): 0 failures. Every backticked repository path in the five docs resolves.
- `python skills/docs-structure/scripts/docs_evidence.py --repo . --format json`: 64 files scanned, 0 packages, 0 services, 1 env source with 1 name read by code, 9 CLI hints (argparse scripts, not a product command), 1 CI workflow, 142 commits scanned from 2026-04-25 to 2026-09-18, 1 tag, governance files `LICENSE` and `CONTRIBUTING.md`.
- `python -c` over the checker's own `PLACEHOLDER_MARKERS`, applied to the five root docs: `ARCHITECTURE.md` 7, `README.md` 1, the rest 0 — which accounts for all eight.
- `git status --short` before and after: unchanged apart from the staged work already present when the check began.

**Not Checked**
- The five `skills/*/SKILL.md` files and their `references/`: excluded by design. A directory holding a `SKILL.md` is tooling, not project docs, and `skills/docs-structure/references/structure.md` is prompt content rather than documentation of this repository.
- Prose accuracy. Whether any of these five documents is still *true* is `docs-sync-audit`'s job, and its report on this repository is in [docs-sync-audit.md](docs-sync-audit.md). It found three things this check cannot see, including a sentence in `ARCHITECTURE.md` that cites a file which does not support it — structurally perfect, factually wrong.
- The eval fixtures' own `docs/`: intentionally defective. Their findings are the snapshots under `evals/snapshots/`, not a result about this repository.
- Anchors inside the two fixture READMEs beyond what R5 checks automatically.

**Assumptions**
- I checked the working tree of `fix/docs-structure-layout` with the two-skill removal staged but not committed. `README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md` and `examples/README.md` were all edited in that change, so a clean result here partly reflects edits made minutes earlier rather than a state that has held for weeks.
- The manifest is treated as the maintainer's stated intent. `"plan": false` and the `R7` exemption are decisions recorded in a file, which is the point of having a manifest — the checker does not second-guess either, and neither did I.
