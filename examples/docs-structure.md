# `docs-structure` on this repository

**Prompt:** "is our docs folder organised"  
**Repository:** `specialone0007/review-skills` at `eae49b9`  
**Files changed by the run:** none — the skill is read-only

Structure audit of the review-skills repo's own Markdown, using the skill's bundled `docs_structure.py`.

This repo has no `docs/` folder. Without a manifest, discovery rule (b) finds two folders linked from the README that hold two or more Markdown files — `examples/` (8) and `evals/` (2) — and asks which one is the docs root rather than guessing. Neither is: `examples/` holds verbatim skill output and `evals/` holds test cases. So this run used an explicit manifest naming the four prose files as roots and turning owner-line enforcement off, which is what a maintainer would commit here:

```json
{ "roots": ["README.md", "CONTRIBUTING.md", "evals/fixtures/README.md", "examples/README.md"],
  "ownerLine": { "enforce": false } }
```

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Docs Structure: whole repository (4 prose Markdown files; skill folders and fixtures excluded)**
Plan only, no files changed.

apply would touch 0 files: 0 index rows, 0 owner lines, 0 splits, 0 deletions. 1 finding needs a human — top 1: a line-number citation in the fixture README.

4 docs under `README.md`, `CONTRIBUTING.md`, `evals/fixtures/README.md`, `examples/README.md` (0 non-doc files). Manifest: explicit, quoted above; discovery alone would have asked between `examples/` and `evals/`. Record folders: none. Generator: none. Checker: 1 failure, 0 warnings, 0 placeholders awaiting review. R1 and R4 do not apply: with only root-level files named there is no folder for an index to disagree with, and the README is the index.

| rule | severity | failures | warnings | first three |
| --- | --- | --- | --- | --- |
| R7 line-number citations | P2 | 1 | 0 | `evals/fixtures/README.md:26` |

1. **P2: The fixture README cites a line number into a source file.**
   Evidence: `evals/fixtures/README.md:26` reads `src/config.js:12`.
   In apply: needs a human. The row is the fixture's own description of a defect it plants on purpose — the same citation appears in `evals/fixtures/mini-app/docs/setup.md` so that this skill can find it there. Rewording the description to avoid the pattern would make the table less exact; leave it, or add `"exempt": { "R7": ["evals/fixtures/README.md"] }` to the manifest so the checker stops reporting it.

**Checks Run**
- `python skills/docs-structure/scripts/docs_structure.py --repo . --manifest <the manifest above> --check-paths --format json`: 4 docs, 1 failure, 0 warnings, 0 split candidates. R6 was on (`--check-paths`) and found nothing: every backticked repo path in the four files exists.
- `python skills/docs-structure/scripts/docs_structure.py --repo .` with no manifest: discovery returned `ambiguous` with candidates `examples/` (8) and `evals/` (2), checked the root files only, and proposed nothing — the expected result for a repo without a project docs folder.

**Not Checked**
- The eight `skills/*/SKILL.md` files and their `references/`: excluded by design, a directory holding a `SKILL.md` is tooling, not project docs. Their frontmatter `description` would satisfy R2 anyway.
- Prose accuracy — that is `docs-sync-audit`, whose report on this repo is in `examples/docs-sync-audit.md`.
- The eval fixture's own `docs/`: intentionally defective; its findings are the snapshot in `evals/snapshots/docs_structure.json`, not a result about this repository.
