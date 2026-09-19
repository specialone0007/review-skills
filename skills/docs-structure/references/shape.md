# The shape: which docs a repository gets, where each one lives, and why

Loaded on demand. `SKILL.md` says what to check and what apply may do; `structure.md` says why each
rule exists and spells out the split and the fill; this file is the layout itself - the tree, one row
per document, the scenarios that earn each one, and the grammar of the three files that hold the tree
together (the index, the agent file, a decision record).

The layout borrows from four things people already use and combines them, because none of them
alone covers a working repository: Diátaxis for the buckets (a doc is written for one of four reader
intents and never mixes them), arc42 for what an architecture doc must answer, MADR for how a decision
is recorded, and the AGENTS.md convention for what a coding agent needs at the root. The index is
shaped like an `llms.txt` file so an agent can parse it without reading the folder.

## The tree

```
README.md                       front door, fixed sections: what it is, quickstart, Start here, layout, commands, config link, status
AGENTS.md                       for coding agents: conventions, gotchas, a link to the README's commands; forty lines at most
CLAUDE.md                       one line, "@AGENTS.md", when Claude Code is in use
docs/
  INDEX.md                      the map: every doc, one line each, one section per bucket
  structure.json                the manifest
  getting-started/              LEARN   - read once, in order, to a first success
    SETUP.md
    ONBOARDING.md
  guides/                       DO      - one task per file, imperative, no theory
    DEVELOPMENT.md
    DEPLOYMENT.md
    OPERATIONS.md
    TESTING.md
    CONTRIBUTING.md
    RELEASING.md
  reference/                    LOOK UP - complete, dry, shaped like the thing it describes
    ARCHITECTURE.md
    CONFIGURATION.md
    DATA_MODEL.md
    API.md | CLI.md | PUBLIC_API.md
    INTEGRATIONS.md
    SECURITY.md
    DESIGN_SYSTEM.md
  explanation/                  UNDERSTAND - why it is the way it is
    PRODUCT.md | OVERVIEW.md
    PIPELINES.md
    decisions/
      README.md
      ADR-0001-<slug>.md
  history/                      RECORD  - what happened, dated, never edited into the present
    CHANGELOG.md
    research/LOG.md + research/log/YYYY-MM.md
    plans/ROADMAP.md
    plans/TASKLIST.md + plans/tasklist/phase-NN-<slug>.md
<unit>/                         each package or service of a monorepo
  README.md                     what this unit is and how to run it alone
  AGENTS.md                     this unit's commands and conventions; the nearest file wins
  docs/                         optional, flat (a unit earns two docs at most): only about this unit
    DEPLOYMENT.md
    OPERATIONS.md
```

### The buckets

- **getting-started** is for someone who has never run it. Sequential, one path, ends at a visible
  success. Nothing goes here that a returning reader looks up.
- **guides** are tasks. Every file answers "how do I ..." with numbered steps and the commands. A
  guide never explains why; it links to explanation for that.
- **reference** is for looking things up. Complete and boring on purpose: every variable, every route,
  every table, every third party. Its structure mirrors the thing described (the API doc is shaped like
  the API). Reference never carries a how-to.
- **explanation** is for understanding. Product intent, the pipelines and why they run that way, and
  every decision with its date and its options. Explanation carries no commands.
- **history** is the record. Changelog, research log, plans. Files here describe a moment and are dated;
  they are never edited to reflect the present (a plan that changed gets a new entry, not a rewrite).
  The checker treats `history/` as a record root: R8 skips it, R6 and R7 only warn, and nothing in it
  covers a concern except the three that live there by definition.

### The collapse rule

The tree above is the full form. A repository earns only some of the docs, and a small repository
should not carry five folders for six files:

- Fewer than **seven** earned docs in total: no bucket folders. The same file names sit directly in
  `docs/`; the index keeps the bucket headings so the reader still knows the intent of each.
- Seven or more: a bucket folder exists when it would hold **two or more** docs. A bucket with one doc
  keeps that doc flat in `docs/`.
- `decisions/`, `research/`, `plans/` and the split parts folders exist whenever they have content,
  regardless of the count; they are folders of many small files by nature.

The canonical path of a doc is therefore a function of the concern and the earned-doc count, and the
checker computes it. A doc at any other path is a `layout` finding (R15) with the path it moves to.
There is no compatibility mode: a repository on an older flat shape gets one move finding per doc and
apply's organise step does the moves and rewrites inbound links.

## One row per document

Every doc keeps the template grammar: an H1, a `> **This document owns:** ...` line, a
`Read this if you ...` line, the `<!-- concern: x; fill: ... -->` comment, then H2 sections each with
one italic guidance line. "Earned by" names the inventory evidence; `always` means every repository
with code. The fill keys are the inventory keys the section drafts are allowed to cite.

### Root

| doc | concern | read this if you | owns | earned by | sections |
| --- | --- | --- | --- | --- | --- |
| `README.md` | readme | arrived from anywhere - a person skimming, an agent parsing | what it is, the quickstart, the hand-off, the layout, the commands, the licence; one line and a link for anything a doc owns | always. Missing: written from the template with the Start-here block in its slot. Existing: never rewritten; the sections it lacks are advice, and `apply readme` appends them as skeletons after the text | What it is · Quickstart · Start here (the block) · Repository layout (table) · Commands (table: task, command, source) · Configuration (one line + link) · Status · fill: readme, packages, tree, services, env, ci, tests |
| `AGENTS.md` | agent | are a coding agent or a new contributor with ten minutes | the conventions an agent cannot infer; the gotchas; links to the README's commands and the index | always. A skeleton; the gate never judges it, a person finishes it | Commands (a link to README § Commands, nothing repeated) · Conventions · Gotchas · Docs (a link to the index) |
| `CLAUDE.md` | agent | use Claude Code | nothing; it imports AGENTS.md | a `.claude/` folder or an existing CLAUDE.md | the single line `@AGENTS.md`; an existing CLAUDE.md with content is left alone and warned |

### getting-started

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `SETUP.md` | setup | have never run it | prerequisites, install, run, the first visible success, what to do when it fails | always | Prerequisites · Install · Run it · First success · If it fails · fill: packages, tree, ci, env, services |
| `ONBOARDING.md` | onboarding | joined this week | the reading order, the path per role, the vocabulary | always; the glossary is worth having at any size, and the reading order is five lines | Read in this order · By role · Glossary · fill: readme, packages, schema, routes |

### guides

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `DEVELOPMENT.md` | develop | change code here every day | the daily loop: branch, run, debug, lint, test, open a PR | always | Daily loop · Branch and PR · Run and debug · Lint and format · Common problems · fill: packages, tree, ci, tests, env |
| `DEPLOYMENT.md` | deploy | ship it | every deployable unit, its environment, the steps, the rollback | always; with no deploy config in the repo the doc says where deployment is configured instead (an open question until a person answers) | Units · Environment per unit · Deploy steps · Rollback · Known traps · fill: services, env, ci, ops, decisions. Monorepo root: the map variant (Units · Order · Rollback), each unit's own guide holding the steps |
| `OPERATIONS.md` | operate | are on call or something is down | health checks, scheduled jobs, alerts, what to do when a thing breaks | a health route, cron, alert rules, or a platform healthcheck | Health · Scheduled jobs · Alerts · When something is wrong · On call · fill: ops, jobs, services, env, decisions |
| `TESTING.md` | testing | are writing or running tests | runners, layout, how to run, what CI runs, gaps | always; with no runner or tests folder the doc says so under Coverage and gaps, which is the fact a newcomer needs most | Runners and layout · Running tests · What CI runs · Coverage and gaps · fill: tests, ci, packages |
| `CONTRIBUTING.md` | contribute | want to land a change | branch and commit rules, checks that must pass, review | LICENSE, CONTRIBUTING, CODE_OF_CONDUCT, a `.github` PR template, or a github.com/gitlab.com remote | Before you start · Making a change · Checks that must pass · Review · fill: tree, ci, tests, packages |
| `RELEASING.md` | release | cut a version | versioning, the release steps, what a release contains, rolling one back | library or CLI kind with a version or publish script | Versioning · Release steps · What a release contains · Rolling back a release · fill: release, packages, ci, decisions |

### reference

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `ARCHITECTURE.md` | architecture | need the map | context, containers, building blocks, runtime, the deployment view, quality and risks (arc42, sections 3, 5, 6, 7, 10, 11) | always; a single-package library still has a context, building blocks and the qualities it pays for | Context · Containers · Building blocks · Runtime · Deployment view · Quality and risks · fill: packages, services, env, routes, schema, decisions |
| `CONFIGURATION.md` | configuration | need to know what a variable does | every environment variable and flag: name, unit that reads it, required or not, where its example lives | always; with nothing read, the doc says so and where it looked | Variables by unit · Files · Flags · fill: env, services, packages |
| `DATA_MODEL.md` | data | touch the database | tables by area, relationships, conventions, the migration inventory | a schema or migrations | Tables by area · Relationships · Conventions · Inventory · fill: schema, decisions |
| `API.md` | http | call it over HTTP | authentication, endpoints, errors, one end-to-end call | HTTP routes or an OpenAPI file (a library's own examples do not count) | Authentication · Endpoints · Errors · Typical end-to-end call · Notes · fill: routes, auth, env, packages |
| `CLI.md` | commands | run it from a shell | install and invoke, commands, exit codes, configuration | a CLI entry point | Install and invoke · Commands · Exit codes and output · Configuration · fill: cli, packages, readme |
| `PUBLIC_API.md` | exports | import it | install and import, the exported surface, usage, stability | library kind with a public entry | Install and import · Exported surface · Usage · Stability and versioning · fill: exports, packages, tests, decisions |
| `INTEGRATIONS.md` | integrations | need to know what talks to whom outside the repo | one section per third party: what for, which unit, the env names, what breaks when it is down | always; the SDKs and outward env names found are listed, and a repo that talks to nothing says so | one H2 per integration, each: purpose, unit, env names, failure mode · fill: integrations, env, services |
| `SECURITY.md` | security | handle auth, secrets or personal data | authentication, authorisation and roles, secrets handling, data classes, known gaps | always; the auth library, middleware, roles and secret-shaped names found are the evidence, and a repo with no authentication says so | Authentication · Authorisation and roles · Secrets handling · Data classes · Known gaps · fill: auth, env, routes, schema |
| `DESIGN_SYSTEM.md` | design | build a screen | tokens, the component library, patterns, do and do not, the pre-flight checklist | a frontend framework plus tokens, a `ui/` or `components/` folder | Foundations · Components - reuse, do not rebuild · Patterns · Do and do not · Pre-flight checklist · fill: frontend, packages, tree |

Three docs share a slot: a repository gets `API.md`, `CLI.md` or `PUBLIC_API.md` for the surfaces it
has, and all of them when it has all three.

### explanation

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `PRODUCT.md` | purpose | want to know what this is becoming | what it is becoming, who it is for, the core concept, how success is measured, principles, what was said no to | always (application, infrastructure, monorepo kinds) | What it is becoming · Who it is for · Core concept · How success is measured · Principles · What we said no to · fill: readme, packages, routes, decisions, tree |
| `OVERVIEW.md` | purpose | evaluate whether to use it | what it does, who uses it and how, concepts, non-goals | always (library or CLI kind); replaces PRODUCT | What it does · Who uses it, and how · Concepts · Non-goals · Roadmap and principles · fill: readme, packages, exports, cli, decisions, tree |
| `PIPELINES.md` | pipelines | need to know what runs when nobody clicks | jobs, queues, schedules, the data flows between them, failure and retry | a queue, worker or scheduler library, cron, or a scheduled CI workflow | Jobs · Queues · Schedules · Data flows · Failure and retry · fill: jobs, ops, services, env |
| `decisions/README.md` | decisions | want to know why | the list of every decision record, newest first | decision-like commits, an existing adr/rfcs folder, or a "we chose" line in a doc | a list in the index grammar; the folder's inside index |
| `decisions/ADR-NNNN-<slug>.md` | decisions | are about to re-decide something | one decision: context, options, the decision, consequences | the same; the first record is a skeleton the user fills | status and date line · Context · Options · Decision · Consequences |

### history

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `CHANGELOG.md` | changelog | want to know what changed for a user | user-visible changes by version, Keep-a-Changelog headings | an existing CHANGELOG at the root (moved here, its root copy becomes a link) or three or more tags | Unreleased · one H2 per version · Added, Changed, Fixed, Removed · never drafted; the skeleton carries the headings only |
| `research/LOG.md` + `research/log/YYYY-MM.md` | research | run experiments | dated entries, one file per month | manifest opt-in only | Entries; never drafted |
| `plans/ROADMAP.md` | plan | want to know what is next | the ordered list of what is planned, dated | plan-like docs, or a `plans`, `roadmap`, `tasklist` or `tasks` folder | Now · Next · Later · Done · never drafted as checkboxes |
| `plans/TASKLIST.md` + `plans/tasklist/phase-NN-<slug>.md` | plan | are executing the plan | the phase table and the living checklists | the same | the phase table with counts (R9) and one file per phase |

## Scenarios: what each kind of repository earns

The inventory decides the kind (`application`, `library`, `cli`, `infrastructure`, `monorepo`,
`docs-only`; a repository can be several). The rows above say what earns each doc; this table says
what a typical repository of each kind ends up with, so a reader can sanity-check a proposal.

| kind | always | earned by evidence | never |
| --- | --- | --- | --- |
| application | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT, PRODUCT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY | OPERATIONS, CONTRIBUTING, DATA_MODEL, API, DESIGN_SYSTEM, PIPELINES, decisions/, CHANGELOG, plans/ | OVERVIEW, RELEASING, PUBLIC_API, CLI (unless it also ships one) |
| library | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT (one line: published, not deployed), OVERVIEW, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY | CONTRIBUTING, RELEASING, PUBLIC_API, CHANGELOG, decisions/ | PRODUCT, OPERATIONS, DESIGN_SYSTEM, PIPELINES, API (its own examples and tests are not routes) |
| cli | as library, with CLI instead of PUBLIC_API; both when both entries exist | | |
| monorepo | the application set at the root as the map; per unit: README.md and AGENTS.md | per unit with a Dockerfile or deploy config: `<unit>/docs/DEPLOYMENT.md`; per unit with health or cron: `<unit>/docs/OPERATIONS.md`; the root DEPLOYMENT and OPERATIONS become the map variant (a table of units and links) | a unit never owns architecture, product, security or data; those stay at the root |
| infrastructure | README, AGENTS.md, SETUP, ONBOARDING, TESTING, ARCHITECTURE, DEPLOYMENT, OPERATIONS, CONFIGURATION, INTEGRATIONS, SECURITY | decisions/, CHANGELOG | PRODUCT, API, DATA_MODEL, DESIGN_SYSTEM |
| docs-only | nothing | only what the manifest pins | everything else |

Worked examples from real runs, so the numbers mean something:

- A three-service application with a Prisma schema, 130 routes, a React frontend, `better-auth`, a
  cron job and OpenAI, Railway and Zep SDKs: sixteen docs plus the index, AGENTS.md and two unit
  deployment guides. Every bucket folder exists.
- A two-route Python service with alembic and a CLI entry: PRODUCT, SETUP, ONBOARDING, DEVELOPMENT,
  TESTING, DEPLOYMENT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY, DATA_MODEL, API, CLI. Thirteen docs, so buckets exist; `guides/` holds only DEVELOPMENT and
  `explanation/` only PRODUCT, so those two stay flat: `docs/DEVELOPMENT.md`, `docs/PRODUCT.md`,
  `docs/getting-started/{SETUP,ONBOARDING}.md`, `docs/reference/{ARCHITECTURE,DATA_MODEL,API,CLI}.md`.
- A single-package library with tests and a publish script: OVERVIEW, SETUP, ONBOARDING, DEVELOPMENT,
  TESTING, DEPLOYMENT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY, RELEASING, PUBLIC_API. Twelve docs, so buckets exist; `explanation/` holds only
  OVERVIEW and stays flat.

## The index grammar

`docs/INDEX.md` is shaped like an `llms.txt` file so that an agent can parse it and a human can scan
it:

```markdown
# <project> docs

> <one sentence: what the project is, taken from the README's first paragraph>

Pick the one file you need here; do not read the folder. Every doc says what it owns under its title.
State is one of `skeleton`, `draft`, `unreviewed`, `reviewed YYYY-MM-DD`, `stale YYYY-MM-DD`.

## Getting started

- [Setup]: prerequisites, install, run, the first success - reviewed 2026-09-01
- [Onboarding]: the reading order per role, the glossary - draft

## Guides
...
## Reference
...
## Explanation
...
## History
...
## Packages

- [server/README.md]: the Express server - what it is and how to run it alone - unreviewed

## Root files

- [drum_reference.md]: ... - unreviewed
```

Rules the checker reads from it: one line per doc, a dash, the doc as a Markdown link to its relative path, a colon, the owner text, a dash and the state (the example above abbreviates the links to their titles);
the bucket H2s in this fixed order, a bucket omitted when empty; `Packages` for unit READMEs, unit
AGENTS.md files and unit docs; `Root files` for Markdown at the repository root that is not a
community file. R1 counts a doc reachable when the index lists it or the inside index of `decisions/`,
`research/` or a split parts folder does. R14 reads the trailing state. A table-shaped index is an R15
finding with the rewrite as the fix.

## The agent file grammar

`AGENTS.md` at the root, forty lines at most, hand-maintained after the skeleton:

```markdown
# <project> - for agents

<one line: what it is and the one thing an agent gets wrong without being told>

## Commands

- install: `npm ci`                       [package.json]
- run: `npm run dev`                      [package.json: scripts.dev]
- test: `npm test`                        [package.json: scripts.test]
- lint: `npm run lint`                    [package.json: scripts.lint]

## Conventions

- <branch, commit, PR rules an agent cannot infer>

## Gotchas

- <the thing that costs an afternoon>

## Docs

- docs/INDEX.md - the map, as a link; read it before the folder.
```

Evidence for the skeleton: task-runner targets, package scripts, CI job commands, the test runner. Each
command carries its source bracket like any draft. The checker (R11) warns when the file is missing,
over `agentFileMaxLines` (default 40), or repeats a README paragraph verbatim; in a monorepo each unit
may carry its own, and the nearest one wins. `CLAUDE.md` is written only when none exists and is the
single line `@AGENTS.md`; an existing one with content is left alone and gets a warning that it should
import the agent file rather than duplicate it.

## The decision record grammar

`docs/explanation/decisions/ADR-NNNN-<slug>.md`, numbered from 0001 in order of creation, MADR-lite:

```markdown
# ADR-0007: Postgres for the event store

> **Status:** accepted · **Date:** 2026-08-10 · **Supersedes:** ADR-0003

## Context

<what forced a decision>

## Options

<two or more, each with the one reason for and against>

## Decision

<what was chosen, in one paragraph>

## Consequences

<what becomes easier, what becomes harder, what is now owed>
```

`decisions/README.md` lists every record newest first in the index grammar. The inventory's
decision-like commits and any "we chose X" line the fill finds become one record each, drafted with the
commit as the source; the record is a draft until a person confirms it. The fill gate checks the status
line and the four sections (G13). `decisions/` is a live folder, not a record folder: its files are
edited (status changes), so R6 and R7 apply in full.

## The README

One file, two readers. A person skims the headings; an agent jumps to a heading by name and reads a
table. So the README has fixed H2s in a fixed order, facts in tables rather than prose, every
command verbatim with its source, and one line plus a link for anything a doc owns:

```markdown
# <project>
<one sentence - the index reuses it>

## What it is            three sentences; PRODUCT has the long form
## Quickstart            numbered: prerequisites, install, run, the URL or command that proves it
## Start here            the block between the markers: this file, docs/INDEX.md, AGENTS.md, first stops
## Repository layout     table: folder | what lives there | its README
## Commands              table: task | command | source - install, run, test, lint, build, deploy
## Configuration         one line and a link to CONFIGURATION.md; never an env table
## Status                version, licence file, CI workflow
```

A README that does not exist is written from the template, filled from the manifests, marked a
draft. A README that exists is never rewritten: R11 lists the template sections it lacks as advice,
and `apply readme` appends those as skeleton sections after the existing text, nothing else moved
or changed. A README that has the information under other headings is left alone. The template's own
headings are never a second home, whatever they contain; any other README H2 that matches a concern
a doc owns still gets the R11 warning. `AGENTS.md` links the README's Commands table and repeats
none of it.

## Migration from the flat shape

A repository laid out by an earlier version of this skill has `docs/PRODUCT.md`, `docs/ARCHITECTURE.md`
and the rest directly in `docs/`, a table-shaped index, and no AGENTS.md. The checker reports, per doc,
one R15 finding with the move, and one for the index. Apply's organise step performs the moves in the
working tree, rewrites every inbound relative link across tracked Markdown, rewrites the index in the
list grammar, and writes the AGENTS.md skeleton; the user reviews the diff and commits. Renames:

| flat | new |
| --- | --- |
| `docs/RUNBOOK.md` | `docs/guides/OPERATIONS.md` |
| `docs/API_REFERENCE.md` | `docs/reference/API.md` |
| `docs/CLI_REFERENCE.md` | `docs/reference/CLI.md` |
| `docs/DESIGN_GUIDELINES.md` | `docs/reference/DESIGN_SYSTEM.md` |
| `docs/TASKLIST.md` + `docs/tasklist/` | `docs/history/plans/TASKLIST.md` + `docs/history/plans/tasklist/` |
| `docs/research/` | `docs/history/research/` |
| `CHANGELOG.md` at the root | `docs/history/CHANGELOG.md`, the root file becomes a one-line pointer (GitHub still surfaces it) |
| every other doc | the same name under its bucket |

Owner lines, review markers and source brackets survive a move untouched. Split parts folders move
with their doc. Nothing is deleted.

## What this shape refuses

- A doc that mixes intents: a reference with a tutorial in it, a guide that explains. The checker
  cannot read intent, so this is advice in the report and a review question, never a finding.
- More than one home for a fact. The owner line says which doc has it; the others link.
- A bucket folder for one file, or five folders for six files (the collapse rule).
- A second index in the README, a routing block in the agent file, or any list of docs outside
  `docs/INDEX.md` and the inside indexes of `decisions/`, `research/` and split folders.
- Editing history. A changed plan is a new dated entry.
