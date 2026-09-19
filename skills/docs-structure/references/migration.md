# Migrating a repository to the shape

Loaded on demand. What a repository laid out by an earlier version of this skill - or by hand -
needs in order to pass R15, and the exact list for the two repositories the shape was proved on.
`shape.md` is the layout; this file is the move.

## What changes for any repository on the flat shape

The checker reports every step; apply performs all of them in one run and the user commits.

1. **Moves.** Every doc that covers a concern moves to that concern's canonical path. The old
   names that changed: `RUNBOOK.md` becomes `guides/OPERATIONS.md`, `API_REFERENCE.md` becomes
   `reference/API.md`, `CLI_REFERENCE.md` becomes `reference/CLI.md`, `DESIGN_GUIDELINES.md` becomes
   `reference/DESIGN_SYSTEM.md`, `TASKLIST.md` and `tasklist/` go under `plans/`, `research/`
   goes under `history/`; every other doc keeps its name under its bucket. `docs_split.py --move`
   rebases the doc's own links, rewrites every inbound link across tracked Markdown, moves a split's
   parts folder alongside, and proves each rewritten link resolves. Owner lines, review markers and
   evidence brackets survive untouched.
2. **The index** is rewritten in the list grammar. Every row the table index had is kept under its
   old heading, converted to a line with its state; a hand-grouped topic section (43's "Forecast
   quality and settlement") sits after the five buckets and before Packages. A person then
   reclassifies those topic docs into buckets over time, or leaves them: R15 fires only on docs that
   cover a concern.
3. **Skeletons** for the concerns the repo never had. Sixteen are always on (README, AGENTS.md,
   INDEX, manifest, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT, OPERATIONS, CONTRIBUTING,
   PRODUCT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY), so a repo on the flat shape usually
   gets `SETUP.md`, `ONBOARDING.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `CONFIGURATION.md`,
   `INTEGRATIONS.md`, `SECURITY.md`, plus the earned `PIPELINES.md`, `decisions/`, `CHANGELOG.md`,
   and one `DEPLOYMENT.md` and `OPERATIONS.md` under each unit that deploys on its own.
4. **`AGENTS.md`** at the root, forty lines at most: a link to the README's Commands table,
   conventions and gotchas as open questions. A `CLAUDE.md` with content of its own stays and gets
   an R11 warning until it becomes the one line `@AGENTS.md` (move its rules into `AGENTS.md`, or
   into a doc the index lists).
5. **The README** keeps every line it has. The Start-here block is regenerated between its markers
   (README, index, AGENTS.md; first stops setup, the daily loop, the architecture), and the template
   sections it lacks - on both repositories all six: What it is, Quickstart, Repository layout,
   Commands, Configuration, Status - are appended as skeletons on `apply readme`.
6. A root `CHANGELOG.md` moves to `docs/history/CHANGELOG.md` (or `docs/CHANGELOG.md` when the
   history bucket holds one doc); the root keeps a one-line pointer so GitHub still surfaces it.

## eclipse_fm (`main`, checked 2026-09-19, read-only)

Twenty-five concerns apply (three units deploy on their own: `server`, `agents/eclipse-agentos`,
`strudel-validator`). Before: 7 failures, all R15. After the dry-run apply on a scratch copy:
0 failures, 0 moves, every concern covered; the advice warnings that remain are a `CLAUDE.md` with
content, the README's `Services` section as a second home for the architecture, and the six README
sections to append.

Moves (6):

| from | to |
| --- | --- |
| `docs/RUNBOOK.md` | `docs/guides/OPERATIONS.md` |
| `docs/TESTING.md` | `docs/guides/TESTING.md` |
| `docs/ARCHITECTURE.md` | `docs/reference/ARCHITECTURE.md` |
| `docs/DATA_MODEL.md` | `docs/reference/DATA_MODEL.md` |
| `docs/DESIGN_GUIDELINES.md` | `docs/reference/DESIGN_SYSTEM.md` |
| `docs/PRODUCT.md` | `docs/explanation/PRODUCT.md` |

New skeletons (19): `AGENTS.md`; `docs/getting-started/SETUP.md`, `ONBOARDING.md`;
`docs/guides/DEVELOPMENT.md`, `DEPLOYMENT.md` (the map variant), `CONTRIBUTING.md`;
`docs/reference/API.md`, `CONFIGURATION.md`, `INTEGRATIONS.md`, `SECURITY.md`;
`docs/explanation/PIPELINES.md`, `decisions/README.md`, `decisions/ADR-0001-first-decision.md`;
`docs/CHANGELOG.md` (earned by the one tag; alone in history, so flat); `server/docs/DEPLOYMENT.md`,
`server/docs/OPERATIONS.md`; `agents/eclipse-agentos/docs/DEPLOYMENT.md`,
`agents/eclipse-agentos/docs/OPERATIONS.md`; `strudel-validator/docs/DEPLOYMENT.md`. The index is
rewritten (53 lines); the README block is regenerated and six sections are appended.

Known before the migration PR: the drafted `DATA_MODEL.md` carries a `meaning` column that reads
"not documented" in every row of three tables (gate G12); the migration is the moment to say it
once above each table and drop the column.

## 43 (`staging`, checked 2026-09-19, read-only)

Thirty-three concerns apply (six units deploy on their own: `apps/web`, `services/ingest-bot`,
`services/notifier`, `services/podcast`, `services/prediction-engine`, `services/research`).
Before: 11 failures, all R15.

Moves (10):

| from | to |
| --- | --- |
| `docs/DEPLOYMENT.md` (+ `docs/deployment/`, its parts) | `docs/guides/DEPLOYMENT.md` (+ `docs/guides/deployment/`) |
| `docs/RUNBOOK.md` | `docs/guides/OPERATIONS.md` |
| `docs/TESTING.md` | `docs/guides/TESTING.md` |
| `docs/ARCHITECTURE.md` | `docs/reference/ARCHITECTURE.md` |
| `docs/DATA_MODEL.md` | `docs/reference/DATA_MODEL.md` |
| `docs/API_REFERENCE.md` | `docs/reference/API.md` |
| `docs/AUTH.md` | `docs/reference/SECURITY.md` |
| `docs/DESIGN_GUIDELINES.md` | `docs/reference/DESIGN_SYSTEM.md` |
| `docs/PRODUCT.md` | `docs/explanation/PRODUCT.md` |
| `docs/TASKLIST.md` (+ `docs/tasklist/`) | `docs/history/plans/TASKLIST.md` (+ `docs/history/plans/tasklist/`); the manifest's `counts` entry follows. The history bucket now holds two docs (plans and the changelog), so it gets its folder |

New skeletons (23): `AGENTS.md`; `docs/getting-started/SETUP.md`, `ONBOARDING.md`;
`docs/guides/DEVELOPMENT.md`, `CONTRIBUTING.md`; `docs/reference/CONFIGURATION.md`,
`INTEGRATIONS.md`; `docs/explanation/PIPELINES.md`, `decisions/README.md`,
`decisions/ADR-0001-first-decision.md`; `docs/history/CHANGELOG.md`; `DEPLOYMENT.md` and
`OPERATIONS.md` under each of the six units (the `apps/web` and `services/research` READMEs seed
theirs). The root `DEPLOYMENT.md` becomes the map variant once the unit guides exist; its eleven
parts are the merge candidate R3 already names. The index is rewritten (99 lines): the five
buckets, then the hand groups "Product and plan", "Build and run", "Notifications and podcasts",
"Forecast quality and settlement" and "Research" with every row they had, then Packages with the
seven unit READMEs. The twelve R14 warnings on `current` rows stay until a person dates them; the
README gets its six sections appended.

Known before the migration PR: `docs/research/` is a record folder by name and holds the research
log; `research` is not pinned in the manifest, so the shape does not move it. Pin it
(`"requiredDocs": {"research": true}`) and it moves to `docs/history/research/` with the rest.
`docs/AUTH.md` becomes `reference/SECURITY.md`: read it against the template's five sections
(authentication, authorisation and roles, secrets handling, data classes, known gaps) and add what
it lacks as advice says, never by rewriting what is there.

## How to run the migration on a repository

1. Plan: `docs_structure.py --repo . --format json`; read `init.moves` and `init.files`.
2. Apply, on a clean working tree, in the order SKILL.md gives: moves first (each through
   `docs_split.py --move <from> <to>`, written only on `proof.ok`), then skeletons, the index, the
   agent file, the README block; gate the scratch tree; run the checker again and expect 0 moves.
3. Commit as one change; the diff is renames plus new files, and the index.
