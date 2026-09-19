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
README.md                       front door, fixed sections: what it is, quickstart, Start here, layout, commands link, config link, status
AGENTS.md                       for coding agents: the commands with their source, conventions, gotchas; forty lines at most
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
  plans/                        PLAN    - what is next and the living checklists, edited as work moves
    ROADMAP.md
    TASKLIST.md + tasklist/phase-NN-<slug>.md
  history/                      RECORD  - what happened, dated; only the changelog's Unreleased section moves
    CHANGELOG.md                (at the root instead, pinned, when a release tool writes it there)
    research/LOG.md + research/log/YYYY-MM.md
CONTRIBUTING.md                 one line pointing at docs/guides/CONTRIBUTING.md, so GitHub surfaces it
CHANGELOG.md                    one line pointing at docs/history/CHANGELOG.md, when the changelog lives there
<unit>/                         each package or service of a monorepo
  README.md                     what this unit is and how to run it alone
  AGENTS.md                     this unit's commands and conventions, earned by the unit's own scripts; the nearest file wins
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
- **plans** is what is next: the roadmap and the living checklists. Edited as work moves, so it is a
  live bucket, not a record - R6, R7 and R9 apply in full.
- **history** is the record. The changelog and the research log. Files here are dated and describe a
  moment; only the changelog's `Unreleased` section is edited, and a version once cut is not. The
  checker treats `history/` as a record root: R8 skips it, R6 and R7 only warn, and nothing in it
  covers a concern except the two that live there by definition.

### Fixed paths

Every doc lives in its bucket folder, always. The path of a doc is a function of its concern and
nothing else, so an agent that knows the shape hops to `docs/reference/CONFIGURATION.md` without
counting docs first. An earlier draft of this shape collapsed the folders under seven docs and kept a
lone doc flat; with sixteen docs always on that rule never fired for a repository with code, and it
made PRODUCT's path depend on whether a decisions folder existed, which is not a path anyone can
predict. The one exception is a repository whose docs live at its root (the manifest's roots are
`*.md`): those stay flat there.

`decisions/`, `research/`, `tasklist/` and a split's parts folder exist whenever they have content;
they are folders of many small files by nature.

A doc at any other path is a `layout` finding (R15) with the path it moves to. There is no
compatibility mode: a repository on an older flat shape gets one move finding per doc and apply's
organise step does the moves and rewrites inbound links.

## One row per document

Every doc keeps the template grammar: an H1, a `> **This document owns:** ...` line, a
`Read this if you ...` line, the `<!-- concern: x; fill: ... -->` comment, then H2 sections each with
one italic guidance line. "Earned by" names the inventory evidence; `always` means every repository
with code. The fill keys are the inventory keys the section drafts are allowed to cite.

### Root

| doc | concern | read this if you | owns | earned by | sections |
| --- | --- | --- | --- | --- | --- |
| `README.md` | readme | arrived from anywhere - a person skimming, an agent parsing | what it is, the quickstart, the hand-off, the layout, the licence; one line and a link for anything a doc owns (the commands are AGENTS.md's) | always. Missing: written from the template with the Start-here block in its slot. Existing: fitted into the template order on apply, every line kept, sections a doc owns re-homed with a pointer left behind. Cannot be switched off | What it is · Quickstart · Start here (the block) · Repository layout (table) · Commands (one line + link to AGENTS.md) · Configuration (one line + link) · Status · fill: readme, packages, tree, services, env, ci, tests |
| `AGENTS.md` | agent | are a coding agent or a new contributor with ten minutes | the commands as the manifests name them, each with its source; the conventions an agent cannot infer; the gotchas; a link to the index | always, and per unit of a monorepo whose manifest has scripts of its own. A skeleton; the gate never judges its prose, a person finishes it. Cannot be switched off | Commands (one bullet per task, source in brackets) · Conventions · Gotchas · Docs (a link to the index) |
| `CLAUDE.md` | agent | use Claude Code | nothing; it imports AGENTS.md | a `.claude/` folder or an existing CLAUDE.md | the single line `@AGENTS.md`; an existing CLAUDE.md with content is left alone and warned |

### getting-started

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `SETUP.md` | setup | have never run it | prerequisites, install, run, the first visible success, what to do when it fails | always | Prerequisites · Install · Run it · First success · If it fails · fill: packages, tree, ci, env, services |
| `ONBOARDING.md` | onboarding | joined this week | the reading order, the path per role, the vocabulary | always; the glossary is worth having at any size, and the reading order is five lines | Read in this order · By role · Glossary · fill: readme, packages, schema, routes |

### guides

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `DEVELOPMENT.md` | develop | change code here every day | the daily loop: run, debug, lint, test (how a change gets in is CONTRIBUTING's) | always | Daily loop · Run and debug · Lint and format · Common problems · fill: packages, tree, ci, tests, env |
| `DEPLOYMENT.md` | deploy | ship it | every deployable unit, its environment, the steps, the rollback | always; with no deploy config in the repo the doc says where deployment is configured instead (an open question until a person answers) | Units · Environment per unit · Deploy steps · Rollback · Known traps · fill: services, env, ci, ops, decisions. Monorepo root: the map variant (Units · Order · Rollback), each unit's own guide holding the steps |
| `OPERATIONS.md` | operate | are on call or something is down | health checks, alerts, what to do when a thing breaks, who is on call (what runs unattended is PIPELINES's) | always; the health route or alert file found is the evidence, and a library says it is not operated | Health · Alerts · When something is wrong · On call · fill: ops, jobs, services, env, decisions |
| `TESTING.md` | testing | are writing or running tests | runners, layout, how to run, what CI runs, gaps | always; with no runner or tests folder the doc says so under Coverage and gaps, which is the fact a newcomer needs most | Runners and layout · Running tests · What CI runs · Coverage and gaps · fill: tests, ci, packages |
| `CONTRIBUTING.md` | contribute | want to land a change | branch and commit rules, the pull request, review, the licence (what CI runs is TESTING's) | always; how a change gets in exists in every team repo, public or private - with no LICENSE the doc says the repo is private and takes no outside contributions. The root keeps a one-line `CONTRIBUTING.md` pointing here, so GitHub surfaces it | Before you start · Making a change · Review · fill: tree, ci, tests, packages |
| `RELEASING.md` | release | cut a version | versioning, the release steps, what a release contains, rolling one back | library or CLI kind with a version or publish script | Versioning · Release steps · What a release contains · Rolling back a release · fill: release, packages, ci, decisions |

### reference

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `ARCHITECTURE.md` | architecture | need the map | context, containers, building blocks, runtime, the deployment view (topology only; the units, environments and steps are DEPLOYMENT's), quality and risks (arc42, sections 3, 5, 6, 7, 10, 11) | always; a single-package library still has a context, building blocks and the qualities it pays for | Context · Containers · Building blocks · Runtime · Deployment view · Quality and risks · fill: packages, services, env, routes, schema, decisions |
| `CONFIGURATION.md` | configuration | need to know what a variable does | every environment variable and flag: name, unit that reads it, required or not, where its example lives | always; with nothing read, the doc says so and where it looked | Variables by unit · Files · Flags · fill: env, services, packages |
| `DATA_MODEL.md` | data | touch the database | where data lives: the stores, the entities and their relationships, conventions, the migrations | a schema or migrations, or a store SDK (Redis, S3, Mongo, Supabase, Firestore, DynamoDB, ...) - data lives somewhere; a store without a schema fills Stores and leaves Entities empty | Stores · Entities and relationships · Conventions · Migrations · fill: schema, decisions |
| `API.md` | http | call it over HTTP | how to call it (base URL, the header a call carries; the auth model is SECURITY's), endpoints, errors, one end-to-end call | HTTP routes or an OpenAPI file (a library's own examples do not count) | Calling it · Endpoints · Errors · Typical end-to-end call · Notes · fill: routes, auth, env, packages |
| `CLI.md` | commands | run it from a shell | install and invoke, commands, exit codes, configuration | a CLI entry point | Install and invoke · Commands · Exit codes and output · Configuration · fill: cli, packages, readme |
| `PUBLIC_API.md` | exports | import it | install and import, the exported surface, usage, stability | library kind with a public entry | Install and import · Exported surface · Usage · Stability and versioning · fill: exports, packages, tests, decisions |
| `INTEGRATIONS.md` | integrations | need to know what talks to whom outside the repo | one section per third party: what for, which unit, what breaks when it is down (the env names are CONFIGURATION's; each section links its rows) | always; the SDKs and outward env names found are listed, and a repo that talks to nothing says so | Integrations (one H3 per third party: purpose, unit, link to its names, failure mode) · Not integrated · fill: integrations, env, services |
| `SECURITY.md` | security | handle auth, secrets or personal data | authentication, authorisation and roles, where secrets live and how they reach a unit (which names exist is CONFIGURATION's), data classes, known gaps | always; the auth library, middleware, roles and secret-shaped names found are the evidence, and a repo with no authentication says so. The name is GitHub's for a vulnerability policy only at the root or `docs/`; under `reference/` it is not surfaced, so the two do not collide | Authentication · Authorisation and roles · Secrets handling · Data classes · Known gaps · fill: auth, env, routes, schema |
| `DESIGN_SYSTEM.md` | design | build a screen | tokens, the component library, patterns, do and do not, the pre-flight checklist | a frontend framework, OR three or more frontend signals (tokens, a `ui/` or `components/` folder, a styles setup); one vendored stylesheet alone does not count | Foundations · Components - reuse, do not rebuild · Patterns · Do and do not · Pre-flight checklist · fill: frontend, packages, tree |

Three docs share a slot: a repository gets `API.md`, `CLI.md` or `PUBLIC_API.md` for the surfaces it
has, and all of them when it has all three.

### explanation

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `PRODUCT.md` | purpose | want to know what this is becoming | what it is becoming, who it is for, the core concept, how success is measured, principles, what was said no to (what is next is ROADMAP's) | always (application and monorepo kinds) | What it is becoming · Who it is for · Core concept · How success is measured · Principles · What we said no to · fill: readme, packages, routes, decisions, tree |
| `OVERVIEW.md` | purpose | evaluate whether to use it | what it does, who uses it and how, concepts, non-goals, principles | always (library, CLI or infrastructure kind); replaces PRODUCT | What it does · Who uses it, and how · Concepts · Non-goals · Principles · fill: readme, packages, exports, cli, decisions, tree |
| `PIPELINES.md` | pipelines | need to know what runs when nobody clicks | jobs, queues, schedules, the data flows between them, failure and retry | a queue, worker or scheduler library, cron, or a scheduled CI workflow | Jobs · Queues · Schedules · Data flows · Failure and retry · fill: jobs, ops, services, env |
| `decisions/README.md` | decisions | want to know why | the list of every decision record, newest first | an existing `adr`, `adrs`, `rfcs` or `decisions` folder, or three or more decision-like commits - a commit whose subject contains one of `decid`, `switch`, `migrat`, `replace`, `remov`, `adopt`, `revert`, `drop`, `deprecat`, `instead` (the inventory's `DECISION_RE`) | a list in the index grammar; the folder's inside index |
| `decisions/ADR-NNNN-<slug>.md` | decisions | are about to re-decide something | one decision: context, options, the decision, consequences | the same; the first record is a skeleton the user fills | status and date line · Context · Options · Decision · Consequences |

### plans

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `ROADMAP.md` | plan | want to know what is next | the ordered list of what is planned, dated; PRODUCT and OVERVIEW link here and carry no roadmap of their own | plan-like docs (plan, roadmap, todo, backlog, tasklist in the name), or a `plans`, `roadmap`, `tasklist` or `tasks` folder | Now · Next · Later · Done · never drafted as checkboxes |
| `TASKLIST.md` + `tasklist/phase-NN-<slug>.md` | plan | are executing the plan | the phase table and the living checklists | the same | the phase table with counts (R9) and one file per phase |

### history

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `CHANGELOG.md` | changelog | want to know what changed for a user | user-visible changes by version, Keep-a-Changelog headings | an existing CHANGELOG (at the root it is moved here and the root keeps a one-line pointer) or any git tag - a version somebody named. Deploy config alone earns nothing. When a release tool writes the root file (release-please, semantic-release, changesets, standard-version: its config file is the evidence) the canonical path is the root `CHANGELOG.md`, pinned, and nothing moves | Unreleased · one H2 per version · Added, Changed, Fixed, Removed · never drafted; the skeleton carries the headings only |
| `research/LOG.md` + `research/log/YYYY-MM.md` | research | run experiments | dated entries, one file per month | manifest opt-in only | Entries; never drafted |

## One home per fact

The headings are where two docs used to hold the same fact. This table is the owner-versus-link rule
the templates are written to; the doc that links keeps one line and a link and never the content.

| fact | owner | who links, and what its section is for instead |
| --- | --- | --- |
| the commands (install, run, test, lint, build) | `AGENTS.md` § Commands | README § Commands is one line and a link; DEVELOPMENT § Daily loop names the order of a working day and links |
| branch, commit and PR rules; review | `CONTRIBUTING.md` | DEVELOPMENT has no Branch and PR section; AGENTS.md § Conventions holds only what an agent gets wrong without being told |
| what CI runs, the checks a PR must pass | `TESTING.md` § What CI runs | CONTRIBUTING § Making a change links it; there is no Checks section |
| cron, queues, workers, schedules | `PIPELINES.md` | OPERATIONS has no Scheduled jobs section; its Health and Alerts link the jobs they watch |
| the units, the environment per unit, the deploy steps | `DEPLOYMENT.md` | ARCHITECTURE § Deployment view is the topology only, one line per container, and links |
| how a caller proves who it is, roles | `SECURITY.md` | API § Calling it says which header a call carries and links |
| environment names | `CONFIGURATION.md` | INTEGRATIONS links each third party's rows; SECURITY § Secrets handling says where secrets live, not which names exist |
| the reading order | `ONBOARDING.md` § Read in this order | the README's Start-here block names three files and hands off; the index lists, it does not order |
| what is next | `plans/ROADMAP.md` | PRODUCT and OVERVIEW have no Roadmap section; Principles links |

## Scenarios: what each kind of repository earns

The inventory decides the kind (`application`, `library`, `cli`, `infrastructure`, `monorepo`,
`docs-only`; a repository can be several). The rows above say what earns each doc; this table says
what a typical repository of each kind ends up with, so a reader can sanity-check a proposal.

| kind | always | earned by evidence | never |
| --- | --- | --- | --- |
| application | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT, OPERATIONS, CONTRIBUTING, PRODUCT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY (sixteen with the index and the manifest) | DATA_MODEL, API, DESIGN_SYSTEM, PIPELINES, decisions/, CHANGELOG, plans/ | OVERVIEW, RELEASING, PUBLIC_API, CLI (unless it also ships one) |
| library | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT (one line: published, not deployed), OPERATIONS (one line: not operated), CONTRIBUTING, OVERVIEW, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY | RELEASING, PUBLIC_API, CHANGELOG, decisions/ | PRODUCT, DESIGN_SYSTEM, PIPELINES, API (its own examples and tests are not routes) |
| cli | as library, with CLI instead of PUBLIC_API; both when both entries exist | | |
| monorepo | the application set at the root as the map; per unit: its own README.md (a person's, seeds only) | per unit whose manifest has scripts: `<unit>/AGENTS.md`; per unit with a Dockerfile or deploy config: `<unit>/docs/DEPLOYMENT.md`; per unit with health or cron: `<unit>/docs/OPERATIONS.md`; the root DEPLOYMENT and OPERATIONS become the map variant (a table of units and links) | a unit never owns architecture, product, security or data; those stay at the root |
| infrastructure | the same sixteen, with OVERVIEW instead of PRODUCT (it has users, not a product it is becoming); DEVELOPMENT is the loop of changing the manifests and applying them | decisions/, CHANGELOG | PRODUCT, API, DATA_MODEL, DESIGN_SYSTEM |
| docs-only | nothing | only what the manifest pins | everything else |

Worked examples from real runs, so the numbers mean something:

- A three-service application with a Prisma schema, 130 routes, a React frontend, `better-auth`,
  `bullmq` and the S3, Redis, OpenAI and Resend SDKs, 25 decision-like commits and one tag: the
  sixteen, plus DATA_MODEL, API, DESIGN_SYSTEM, PIPELINES, decisions/ and CHANGELOG, plus a
  DEPLOYMENT under each of three units, OPERATIONS under two, and an AGENTS.md under each unit with
  scripts. Every bucket folder but `plans/` exists.
- A two-route Python service with alembic and a CLI entry: the sixteen plus DATA_MODEL, API and
  CLI, each in its bucket: `docs/explanation/PRODUCT.md`, `docs/guides/DEVELOPMENT.md`,
  `docs/getting-started/{SETUP,ONBOARDING}.md`, `docs/reference/{ARCHITECTURE,DATA_MODEL,API,CLI}.md`.
- A single-package library with tests and a publish script: the sixteen with OVERVIEW for PRODUCT,
  DEPLOYMENT and OPERATIONS one line each, plus RELEASING and PUBLIC_API.

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
## Plans
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

> **This document owns:** the commands, the conventions an agent cannot infer, the gotchas. *(skeleton, write me)*

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

The agent file owns the commands: it is the first file an agent reads, and a command with two
homes drifts, so the README's Commands section is one line and a link here. Evidence for the
skeleton: task-runner targets, package scripts, CI job commands, the test runner. Each command
carries its source bracket like any draft. The checker (R11) warns when the file is missing, over
`agentFileMaxLines` (default 40), or repeats a README paragraph verbatim. In a monorepo a unit whose
manifest has scripts of its own earns `<unit>/AGENTS.md`, built from that manifest alone with the
commands as run from the unit, and the nearest file wins. `CLAUDE.md` is written only when none
exists and `.claude/` does, as the single line `@AGENTS.md`; an existing one with content is left
alone and gets a warning that it should import the agent file rather than duplicate it.

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

`decisions/README.md` lists every record newest first in the index grammar. A decision-like commit
is one whose subject contains `decid`, `switch`, `migrat`, `replace`, `remov`, `adopt`, `revert`,
`drop`, `deprecat` or `instead` (the inventory's `DECISION_RE`); three of them, or an existing
`adr`, `adrs`, `rfcs` or `decisions` folder, earn the bucket. Each such commit becomes one record
skeleton with the commit as its source; the record is a draft until a person confirms it. The fill gate checks the status
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
## Start here            the block between the markers: this file, docs/INDEX.md, AGENTS.md; ONBOARDING owns the reading order
## Repository layout     table: folder | what lives there | its README
## Commands              one line and a link to AGENTS.md § Commands, which owns them
## Configuration         one line and a link to CONFIGURATION.md; never an env table
## Status                version, licence file, CI workflow
```

A README that does not exist is written from the template, filled from the manifests, marked a
draft. A README that exists is fitted into the template on apply: its sections land under the
template headings they match (a `## Setup` under Quickstart, a `## Project structure` under
Repository layout), text verbatim; template sections it lacks get their guidance line; sections
that match nothing stay after, in their order; the Start-here block moves whole into its slot; and
a section that a doc owns - an env table, deploy steps - is pasted into that doc and replaced by
one line and a link. Nothing is deleted or reworded, and the proof says so line by line. R11 lists
the lacking sections as advice in plan mode. The template's own headings are never a second home,
whatever they contain. The README links `AGENTS.md` for the commands and repeats none of them; the
Start-here block names three files and hands the reading order to ONBOARDING, so it never depends
on which docs are still skeletons when it is written.

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
| `docs/AUTH.md` | `docs/reference/SECURITY.md` |
| `docs/TASKLIST.md` + `docs/tasklist/` | `docs/plans/TASKLIST.md` + `docs/plans/tasklist/` |
| `docs/research/` | `docs/history/research/` |
| `CHANGELOG.md` at the root | `docs/history/CHANGELOG.md`, the root file becomes a one-line pointer (GitHub still surfaces it) - unless a release tool writes it, in which case it stays and is pinned |
| `CONTRIBUTING.md` at the root | `docs/guides/CONTRIBUTING.md`, the root file becomes a one-line pointer |
| every other doc | the same name under its bucket |

Owner lines, review markers and source brackets survive a move untouched. Split parts folders move
with their doc. Nothing is deleted.

Every doc that covers a concern is also fitted into its template's section order by
`docs_restructure.py` (existing headings mapped to template headings, text verbatim, unmatched
sections kept after, ambiguous mappings marked for review), and the README gives away what other
docs own. The proof is line-for-line: what went in comes out, plus only the pointer, owner and
guidance lines the restructure itself adds.

## What this shape refuses

- A doc that mixes intents: a reference with a tutorial in it, a guide that explains. The checker
  cannot read intent, so this is advice in the report and a review question, never a finding.
- Deleting or rewording a person's sentence. The shape reorders and re-homes; it never edits. A
  restructure that would lose a line refuses instead.
- More than one home for a fact. The owner line says which doc has it; the others link, and the
  table above says who owns each fact two docs used to share.
- A path that depends on anything but the concern: every doc sits in its bucket folder, always.
- A second index in the README, a routing block in the agent file, or any list of docs outside
  `docs/INDEX.md` and the inside indexes of `decisions/`, `research/` and split folders.
- Editing history. A version once cut in the changelog is not rewritten; a plan lives in `plans/`,
  where it is edited as work moves.
