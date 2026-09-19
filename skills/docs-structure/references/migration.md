# Migrating a repository to the shape

Loaded on demand. What a repository laid out by an earlier version of this skill - or by hand -
needs in order to pass R15, and the exact list for the two repositories the shape was proved on.
`shape.md` is the layout; this file is the move.

## What changes for any repository on the flat shape

The checker reports every step; apply performs all of them in one run and the user commits.

1. **Moves.** Every doc that covers a concern moves to that concern's canonical path. The old
   names that changed: `RUNBOOK.md` becomes `guides/OPERATIONS.md`, `API_REFERENCE.md` becomes
   `reference/API.md`, `CLI_REFERENCE.md` becomes `reference/CLI.md`, `DESIGN_GUIDELINES.md` becomes
   `reference/DESIGN_SYSTEM.md`, `AUTH.md` becomes `reference/SECURITY.md`, `TASKLIST.md` and
   `tasklist/` go under `plans/`, `research/` goes under `history/`; every other doc keeps its name
   under its bucket - always the bucket folder, there is no flat form. `docs_split.py --move`
   rebases the doc's own links, rewrites every inbound link across tracked Markdown, moves a split's
   parts folder alongside, and proves each rewritten link resolves. Owner lines, review markers and
   evidence brackets survive untouched.
2. **The index** is rewritten in the list grammar. Every row the table index had is kept under its
   old heading, converted to a line with its state; a hand-grouped topic section (43's "Forecast
   quality and settlement") sits after the six buckets and before Units. A person then
   reclassifies those topic docs into buckets over time, or leaves them: R15 fires only on docs that
   cover a concern.
3. **Skeletons** for the concerns the repo never had. Sixteen are always on (README, AGENTS.md,
   INDEX, manifest, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT, OPERATIONS, CONTRIBUTING,
   PRODUCT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY), so a repo on the flat shape usually
   gets `SETUP.md`, `ONBOARDING.md`, `DEVELOPMENT.md`, `CONTRIBUTING.md`, `CONFIGURATION.md`,
   `INTEGRATIONS.md`, `SECURITY.md`, plus the earned `PIPELINES.md`, `decisions/`, `CHANGELOG.md`,
   one `DEPLOYMENT.md` and `OPERATIONS.md` under each unit that deploys on its own, and an
   `AGENTS.md` under each such unit whose manifest has scripts. The root gets a one-line
   `CONTRIBUTING.md` (and `CHANGELOG.md`, when the changelog lives under history) so GitHub
   surfaces them.
4. **`AGENTS.md`** at the root, forty lines at most: the commands as the manifests name them,
   each with its source (the agent file owns them; the README's Commands section is a link),
   conventions and gotchas as open questions. A `CLAUDE.md` with content of its own stays and gets
   an R11 warning until it becomes the one line `@AGENTS.md` (move its rules into `AGENTS.md`, or
   into a doc the index lists).
5. **The README** keeps every line it has. The Start-here block is regenerated between its markers
   (three files: README, index, AGENTS.md; then a hand-off to ONBOARDING, which owns the reading
   order), and the restructure fits the README into the template order: the six sections it lacks
   on both repositories - What it is, Quickstart, Repository layout, Commands, Configuration,
   Status - get their guidance line, and a section a doc owns (43's env table, eclipse's Services
   table) is pasted into that doc and replaced by one line and a link.
6. A root `CHANGELOG.md` moves to `docs/history/CHANGELOG.md`; the root keeps a one-line pointer
   so GitHub still surfaces it. When a release tool writes the root file (release-please,
   semantic-release, changesets, standard-version) it stays there, pinned.

## eclipse_fm (`main`, checked 2026-09-19, read-only)

Twenty-seven concerns apply (three units deploy on their own: `server`, `agents/eclipse-agentos`,
`strudel-validator`; `server` and `strudel-validator` have scripts and earn an agent file). Before:
7 failures, all R15. After the dry-run apply and restructure on a scratch copy: proof ok (344
content lines in, 344 out), 0 failures, 0 moves, every concern covered; the one warning left is a
`CLAUDE.md` with content. The README's `Services` table lands in `ARCHITECTURE.md` § Containers
and its `Deployment & Database Migrations` section in `DATA_MODEL.md` § Migrations, each replaced
by a line and a link.

Moves (6):

| from | to |
| --- | --- |
| `docs/RUNBOOK.md` | `docs/guides/OPERATIONS.md` |
| `docs/TESTING.md` | `docs/guides/TESTING.md` |
| `docs/ARCHITECTURE.md` | `docs/reference/ARCHITECTURE.md` |
| `docs/DATA_MODEL.md` | `docs/reference/DATA_MODEL.md` |
| `docs/DESIGN_GUIDELINES.md` | `docs/reference/DESIGN_SYSTEM.md` |
| `docs/PRODUCT.md` | `docs/explanation/PRODUCT.md` |

New skeletons (21): `AGENTS.md`; `docs/getting-started/SETUP.md`, `ONBOARDING.md`;
`docs/guides/DEVELOPMENT.md`, `DEPLOYMENT.md` (the map variant), `CONTRIBUTING.md`;
`docs/reference/API.md`, `CONFIGURATION.md`, `INTEGRATIONS.md`, `SECURITY.md`;
`docs/explanation/PIPELINES.md`, `decisions/README.md`, `decisions/ADR-0001-first-decision.md`;
`docs/history/CHANGELOG.md` (earned by the one tag); `server/AGENTS.md`, `server/docs/DEPLOYMENT.md`,
`server/docs/OPERATIONS.md`; `agents/eclipse-agentos/docs/DEPLOYMENT.md`,
`agents/eclipse-agentos/docs/OPERATIONS.md`; `strudel-validator/AGENTS.md`,
`strudel-validator/docs/DEPLOYMENT.md`. Plus the root `CONTRIBUTING.md` and `CHANGELOG.md`
pointers. The index is rewritten (52 lines); the README block is regenerated and the README is
fitted into the template.

Known before the migration PR: the drafted `DATA_MODEL.md` carries a `meaning` column that reads
"not documented" in every row of three tables (gate G12); the migration is the moment to say it
once above each table and drop the column.

## 43 (`staging`, checked 2026-09-19, read-only)

Thirty-eight concerns apply (six units deploy on their own: `apps/web`, `services/ingest-bot`,
`services/notifier`, `services/podcast`, `services/prediction-engine`, `services/research`; the
five with scripts earn an agent file). Before: 11 failures, all R15.

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
| `docs/TASKLIST.md` (+ `docs/tasklist/`) | `docs/plans/TASKLIST.md` (+ `docs/plans/tasklist/`); the manifest's `counts` entry follows |

New skeletons (27): `AGENTS.md`; `docs/getting-started/SETUP.md`, `ONBOARDING.md`;
`docs/guides/DEVELOPMENT.md`, `CONTRIBUTING.md`; `docs/reference/CONFIGURATION.md`,
`INTEGRATIONS.md`; `docs/explanation/PIPELINES.md`, `decisions/README.md`,
`decisions/ADR-0001-first-decision.md`; `docs/history/CHANGELOG.md`; `DEPLOYMENT.md` and
`OPERATIONS.md` under each of the six units (the `apps/web` and `services/research` READMEs seed
theirs); `AGENTS.md` under `apps/web`, `services/ingest-bot`, `services/notifier`,
`services/podcast` and `services/prediction-engine`. Plus the root `CONTRIBUTING.md` and
`CHANGELOG.md` pointers. The root `DEPLOYMENT.md` becomes the map variant once the unit guides exist; its eleven
parts are the merge candidate R3 already names. The index is rewritten (102 lines): the
buckets, then the hand groups "Product and plan", "Build and run", "Notifications and podcasts",
"Forecast quality and settlement" and "Research" with every row they had, then Units with the
seven unit READMEs. The twelve R14 warnings on `current` rows stay until a person dates them; the
README is fitted into the template, its env table pasted into `CONFIGURATION.md`.

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
