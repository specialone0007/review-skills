# `docs-structure` on this repository

**Prompt:** "is our docs folder organised"  
**Repository:** `specialone0007/review-skills` at the head of the pull request that added the concern model (the tree already contains `skills/docs-structure/` with both scripts)  
**Files changed by the run:** none — the skill is read-only

Structure audit of the review-skills repo's own Markdown, using the skill's two bundled scripts.

This repo has no `docs/` folder. Without a manifest, discovery rule (b) finds two folders linked from the README that hold two or more Markdown files — `examples/` (9) and `evals/` (8) — and asks which one is the docs root rather than guessing. Neither is: `examples/` holds verbatim skill output and `evals/` holds test cases and two deliberately defective fixtures. So this run used an explicit manifest naming the four prose files as roots, which is what a maintainer would commit here:

```json
{ "roots": ["README.md", "CONTRIBUTING.md", "evals/fixtures/README.md", "examples/README.md"] }
```

Re-run it yourself and compare. Line numbers refer to the commit above, so a later commit will shift them.

---

**Docs Structure: whole repository (4 prose Markdown files; skill folders and fixtures excluded)**
Plan only, no files changed.

apply would touch 4 files: 0 index rows, 0 owner lines, 0 splits, 3 skeletons plus the central index, 0 deletions. apply fill would draft 0 docs (the three uncovered concerns are purpose, architecture and plan, which fill leaves to people). 1 finding needs a human — a line-number citation in the fixture README.

4 docs under `README.md`, `CONTRIBUTING.md`, `evals/fixtures/README.md`, `examples/README.md` (0 non-doc files). Kinds: unclassified (ten Python tools, no manifest that names a package). Ecosystems: none recognised. Manifest: explicit, quoted above. Record folders: none. Generator: none. Checker: 4 failures, 0 warnings.
Concerns: 2 covered, 3 missing. Sections: 0 skeleton, 0 draft, 14 reviewed; 9 template sections absent from hand-written docs (advice).

| concern | applies because | covered by | matched by | state |
| --- | --- | --- | --- | --- |
| purpose | always | none — apply creates `docs/PRODUCT.md` | — | — |
| architecture | always | none — apply creates `docs/ARCHITECTURE.md` | — | — |
| develop | always | `README.md` | README sections: install | reviewed |
| plan | always | none — apply creates `docs/TASKLIST.md` | — | — |
| contribute | governance: LICENSE, CONTRIBUTING.md | `CONTRIBUTING.md` | file name; H1: contributing | reviewed |

Concerns that do not apply here, and why: no deployable unit, no schema, no HTTP routes, no frontend, no health checks or cron, no version field or publish script — the inventory found none of them, so no deploy, data, http, design, operate or release doc is asked for.

| rule | severity | failures | warnings | first three |
| --- | --- | --- | --- | --- |
| R12 required docs exist | P2 | 3 | 0 | purpose, architecture, plan |
| R7 line-number citations | P2 | 1 | 0 | `evals/fixtures/README.md:26` |

1. **P2: No doc covers `purpose`.** Evidence: `README.md:1` (the front door; there is no central index to anchor to). The README says what the collection is in its first paragraph, but no doc's headings match the concern. In apply: yes — a `PRODUCT.md` skeleton, sections empty, marked `(skeleton, write me)`. Fill leaves purpose to people: intent is not in code.
2. **P2: No doc covers `architecture`.** Evidence: `README.md:1`. How the validators, the snapshot runner, the fixtures and the eight skill folders fit together is described nowhere in one place. In apply: a skeleton; fill could draft the Services and Data flow sections from `tools/`, `evals/` and `.github/workflows/ci.yml` on `apply fill`.
3. **P2: No doc covers `plan`.** Evidence: `README.md:1`. In apply: a `TASKLIST.md` skeleton with its first phase file; never drafted as checkboxes.
4. **P2: The fixture README cites a line number into a source file.** Evidence: `evals/fixtures/README.md:26` reads `src/config.js:12`. In apply: needs a human. The row is the fixture's own description of a defect it plants on purpose. Leave it, or add `"exempt": { "R7": ["evals/fixtures/README.md"] }` to the manifest.

**Checks Run**
- `python skills/docs-structure/scripts/docs_structure.py --repo . --manifest <the manifest above> --check-paths --format json`: 4 docs, 4 failures, 0 warnings, 0 split candidates, 5 concerns applied, 2 covered. R6 was on and found nothing: every backticked repo path in the four files exists.
- `python skills/docs-structure/scripts/docs_evidence.py --repo .`: 68 files, 10 code files, 0 packages, 9 CLI hints (argparse scripts, not a product command), 1 CI workflow, 0 env names, `unknown: true`.
- `python skills/docs-structure/scripts/docs_structure.py --repo .` with no manifest: discovery returned `ambiguous` with candidates `examples/` (9) and `evals/` (8), checked the root files only, proposed nothing.

**Not Checked**
- The eight `skills/*/SKILL.md` files and their `references/`: excluded by design; a directory holding a `SKILL.md` is tooling, not project docs.
- Prose accuracy — that is `docs-sync-audit`, whose report on this repo is in `examples/docs-sync-audit.md`.
- The eval fixtures' own `docs/`: intentionally defective; their findings are the snapshots under `evals/snapshots/`, not a result about this repository.
