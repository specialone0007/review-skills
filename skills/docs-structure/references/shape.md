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
CLAUDE.md                       one line, "@AGENTS.md", written when none exists and a .claude/ folder does
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
    JOBS.md
  explanation/                  UNDERSTAND - why it is the way it is
    PRODUCT.md | OVERVIEW.md
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
  AGENTS.md                     this unit's commands and conventions, for every unit that deploys on its own; the nearest file wins
  docs/                         optional, flat (a unit earns two docs at most): only about this unit
    DEPLOYMENT.md
    OPERATIONS.md
```

### The buckets

- **getting-started** is for someone who has never run it. Sequential, one path, ends at a visible
  success. Nothing goes here that a returning reader looks up, with two exceptions a returning
  reader does reach in the same hop: the glossary at the foot of ONBOARDING, and SETUP § If it fails.
- **guides** are tasks. Every file answers "how do I ..." with numbered steps and the commands. A
  guide never explains why; it links to explanation for that.
- **reference** is for looking things up. Complete and boring on purpose: every variable, every route,
  every table, every third party. Its structure mirrors the thing described (the API doc is shaped like
  the API). Reference carries no tutorial; a checklist that is part of the thing described (a
  pre-flight list before adding a component, how a migration is written) stays with it.
- **explanation** is for understanding. Product intent and every decision with its date and its
  options. Explanation carries no commands and no tables of things (the jobs table is reference).
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
`*.md`): those stay flat there, and the manifest's roots are the source of truth for that case.

`decisions/`, `research/`, `tasklist/` and a split's parts folder exist whenever they have content;
they are folders of many small files by nature.

A doc at any other path is a `layout` finding (R15) with the path it moves to. There is no
compatibility mode: a repository on an older flat shape gets one move finding per doc and apply's
organise step does the moves and rewrites inbound links.

## One row per document

Every doc keeps the template grammar: an H1, a `> **This document owns:** ...` line, a
`Read this if you ...` line, the `<!-- concern: x; fill: ... -->` comment, then H2 sections each with
one italic guidance line. The root files, the decision record, the plans files (ROADMAP, TASKLIST), the
record files (CHANGELOG, LOG) and DESIGN_SYSTEM's golden-rule blockquote break it on purpose, as `structure.md` § Init lists. "Earned by" names the inventory evidence; `always` means every repository
with code. The fill keys are the inventory keys the section drafts are allowed to cite.

### Root

| doc | concern | read this if you | owns | earned by | sections |
| --- | --- | --- | --- | --- | --- |
| `README.md` | readme | arrived from anywhere - a person skimming, an agent parsing | what it is, the quickstart (install and run as a checked copy of AGENTS.md's commands, the one repeat the shape allows), the hand-off, the layout, the licence file by name (what it means for a contribution is CONTRIBUTING's); one line and a link for anything else a doc owns | always. Missing: written from the template with the Start-here block in its slot. Existing: fitted into the template order on apply, every line kept, sections a doc owns re-homed with a pointer left behind. Cannot be switched off | What it is · Quickstart · Start here (the block) · Repository layout (table) · Commands (one line + link to AGENTS.md) · Configuration (one line + link) · Status · fill: readme, packages, tree, services, env, ci, tests |
| `AGENTS.md` | agent | are a coding agent or a new contributor with ten minutes | the commands as the manifests name them, each with its source and with the package manager the lockfile names (pnpm, yarn, bun, npm; uv, poetry, pip); the conventions an agent cannot infer (the rules themselves are CONTRIBUTING's); the preconditions it trips on (the fix is the task's guide's); a link to the index | always, and under every unit of a monorepo that deploys on its own (the one trigger, everywhere in this file), built from that unit's manifest; a unit with no scripts gets the install command and open questions. A skeleton; the gate never judges its prose, a person finishes it. Cannot be switched off | Commands (one bullet per task, source in brackets) · Conventions · Gotchas · Docs (a link to the index) |
| `CLAUDE.md` | agent | use Claude Code | nothing; it imports AGENTS.md | written only when none exists and a `.claude/` folder does | the single line `@AGENTS.md`; an existing CLAUDE.md with content is left alone and warned |

### getting-started

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `SETUP.md` | setup | have never run it | prerequisites, install and run (a checked copy of AGENTS.md's install and run commands, the one repeat the shape allows), the first visible success, what to do when it fails | always | Prerequisites · Install · Run it · First success · If it fails · fill: packages, tree, ci, env, services |
| `ONBOARDING.md` | onboarding | joined this week | the reading order, the path per role, the vocabulary | always; the glossary is worth having at any size, and the reading order is five lines | Read in this order · By role · Glossary · fill: readme, packages, schema, routes |

### guides

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `DEVELOPMENT.md` | develop | change code here every day | the daily loop: the order of run, debug, lint, test, each step a link to AGENTS.md's command; the lint tools and their configs; the common problems (how a change gets in is CONTRIBUTING's) | always | Daily loop · Run and debug · Lint and format · Common problems · fill: packages, tree, ci, tests, env |
| `DEPLOYMENT.md` | deploy | ship it | every deployable unit with its platform, environment, URL and deploying branch; how values reach it (the names and the example file's path are CONFIGURATION's); the steps; the rollback | always; with no deploy config in the repo the doc says where deployment is configured instead (an open question until a person answers) | Units · How values reach a unit · Deploy steps · Rollback · Known traps · fill: services, env, ci, ops, decisions. Monorepo root: the map variant (Units · Order · Rollback), each unit's own guide holding the steps |
| `OPERATIONS.md` | operate | are on call or something is down | health checks, alerts, what to do when a thing breaks, who is on call (what runs unattended is JOBS's) | always; the health route or alert file found is the evidence, and a library says it is not operated | Health · Alerts · When something is wrong · On call · fill: ops, jobs, services, env, decisions |
| `TESTING.md` | testing | are writing or running tests | runners, layout, how to run one file or in watch mode (the test command itself is AGENTS.md's), what CI runs including scheduled workflows, gaps | always; with no runner or tests folder the doc says so under Coverage and gaps, which is the fact a newcomer needs most | Runners and layout · Running tests · What CI runs · Coverage and gaps · fill: tests, ci, packages |
| `CONTRIBUTING.md` | contribute | want to land a change | branch and commit rules, the pull request, review, the code conventions a linter does not enforce, the licence (what CI runs is TESTING's) | always; how a change gets in exists in every team repo, public or private - with no LICENSE the doc says the repo is private and takes no outside contributions. The root keeps a one-line `CONTRIBUTING.md` pointing here, so GitHub surfaces it | Before you start · Making a change · Code conventions · Review · fill: tree, ci, tests, packages |
| `RELEASING.md` | release | cut a version | versioning, cutting and publishing (tag, changelog entry, artifact, registry); putting an artifact into an environment is DEPLOYMENT's | any kind: a publish or release script or workflow, or a release tool's config (release-please, semantic-release, changesets, standard-version) - an application that cuts versions needs it as much as a library | Versioning · Release steps · What a release contains · Rolling back a release · fill: release, packages, ci, decisions |

### reference

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `ARCHITECTURE.md` | architecture | need the map | context, containers, building blocks, runtime, the deployment view (topology only; the units, environments and steps are DEPLOYMENT's), quality and risks (arc42, sections 3, 5, 6, 7, 10, 11) | always; a single-package library still has a context, building blocks and the qualities it pays for | Context · Containers · Building blocks · Runtime · Deployment view · Quality and risks · fill: packages, services, env, routes, schema, decisions |
| `CONFIGURATION.md` | configuration | need to know what a variable does | every environment variable and flag: name, unit that reads it, required or not, secret or not; the path of every config and example env file (Files is the one home of that path); never a value or a default in a cell | always; with nothing read, the doc says so and where it looked | Variables by unit · Files · Flags · fill: env, services, packages |
| `DATA_MODEL.md` | data | touch the database | where data lives: the stores, the entities and their relationships, conventions, the migrations | a schema or migrations, or a store SDK (Redis, S3, Mongo, Supabase, Firestore, DynamoDB, ...) - data lives somewhere; a store without a schema fills Stores and leaves Entities empty | Stores · Entities and relationships · Conventions · Migrations · fill: schema, decisions |
| `API.md` | http | call it over HTTP | how to call it (base URL, the header a call carries; the auth model is SECURITY's), endpoints, errors, one end-to-end call | HTTP routes or an OpenAPI file (a library's own examples do not count) | Calling it · Endpoints · Errors · Typical end-to-end call · Notes · fill: routes, auth, env, packages |
| `CLI.md` | commands | run it from a shell | install and invoke, commands, exit codes, the config files (the env names are CONFIGURATION's) | a CLI entry point | Install and invoke · Commands · Exit codes and output · Configuration · fill: cli, packages, readme |
| `PUBLIC_API.md` | exports | import it | install and import, the exported surface, usage, stability | library kind with a public entry | Install and import · Exported surface · Usage · Stability and versioning · fill: exports, packages, tests, decisions |
| `INTEGRATIONS.md` | integrations | need to know what talks to whom outside the repo | one section per third party: what for, which unit, what breaks when it is down (the env names are CONFIGURATION's; each section links its rows) | always; the SDKs and outward env names found are listed, and a repo that talks to nothing says so | Integrations (one H3 per third party: purpose, unit, link to its names, failure mode) · Not integrated · fill: integrations, env, services |
| `SECURITY.md` | security | handle auth, secrets or personal data | authentication, authorisation and roles, what is secret-specific (rotation, who has access, what is never committed; which names are secrets is CONFIGURATION's secret column, where values live is DEPLOYMENT's), data classes, known gaps | always; the auth library, middleware, roles and secret-shaped names found are the evidence, and a repo with no authentication says so. The name is GitHub's for a vulnerability policy only at the root or `docs/`; under `reference/` it is not surfaced, so the two do not collide | Authentication · Authorisation and roles · Secrets handling · Data classes · Known gaps · fill: auth, env, routes, schema |
| `JOBS.md` | jobs | need to know what runs when nobody clicks | every job, queue and schedule the repository itself runs (source, a CronJob manifest, a platform cron file), the data flows between them, the retry design (what a person does when a job is stuck is OPERATIONS's) - reference, looked up, not read for its why | a queue, worker or scheduler library, a cron expression in source, a CronJob manifest or a platform cron setting - a scheduled CI workflow is TESTING's and earns nothing here | Jobs · Queues · Schedules · Data flows · Failure and retry · fill: jobs, ops, services, env |
| `DESIGN_SYSTEM.md` | design | build a screen | tokens, the component library, patterns, do and do not, the pre-flight checklist | a frontend framework, OR three or more frontend signals (tokens, a `ui/` or `components/` folder, a styles setup); one vendored stylesheet alone does not count | Foundations · Components - reuse, do not rebuild · Patterns · Do and do not · Pre-flight checklist · fill: frontend, packages, tree |

Three docs share a slot: a repository gets `API.md`, `CLI.md` or `PUBLIC_API.md` for the surfaces it
has, and all of them when it has all three.

### explanation

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `PRODUCT.md` | purpose | want to know what this is and why | what it is today, who it is for, the core concept, how success is measured, principles, what was said no to (what is next is ROADMAP's) | always (application and monorepo kinds) | What it is today · Who it is for · Core concept · How success is measured · Principles · What we said no to · fill: readme, packages, routes, decisions, tree |
| `OVERVIEW.md` | purpose | evaluate whether to use it | what it does, who uses it and how, concepts, non-goals, principles | always (library, CLI or infrastructure kind, when the repo is not also an application or monorepo - those kinds win); replaces PRODUCT | What it does · Who uses it, and how · Concepts · Non-goals · Principles · fill: readme, packages, exports, cli, decisions, tree |
| `decisions/README.md` | decisions | want to know why | the list of every decision record, newest first | an existing `adr`, `adrs`, `rfcs` or `decisions` folder, or the manifest pin `requiredDocs: {"decisions": true}`. Decision-like commits (subject containing `decid`, `switch`, `migrat`, `replace`, `remov`, `adopt`, `revert`, `drop`, `deprecat`, `instead`) are advice in the inventory, never a trigger: `migrat` matches "add migration for users" | a list in the index grammar; the folder's inside index |
| `decisions/ADR-NNNN-<slug>.md` | decisions | are about to re-decide something | one decision: context, options, the decision, consequences | the same; apply writes one skeleton record (`ADR-0001-first-decision.md`), never one per commit | status and date line · Context · Options · Decision · Consequences |

### plans

| doc | concern | read this if you | owns | earned by | sections · fill |
| --- | --- | --- | --- | --- | --- |
| `ROADMAP.md` | plan | want to know what is next | the ordered list of what is planned, dated; PRODUCT and OVERVIEW link here and carry no roadmap of their own | a doc whose file name (not its path) contains the whole word plan, plans, roadmap or milestones, or a top-level `plans` or `roadmap` folder (never `docs/plans/`, which the shape itself writes) - in effect opt-in: a repository that plans in files says so by having one | Now · Next · Later · Done · never drafted as checkboxes |
| `TASKLIST.md` + `tasklist/phase-NN-<slug>.md` | tasks | are executing the plan | the phase table and the living checklists | a doc whose file name contains the whole word todo, backlog, tasklist or tasks, or a `tasklist` or `tasks` folder; its own concern, so a repository with a TODO and no roadmap gets one doc, not two | the phase table with counts (R9) and one file per phase |

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
| cron, queues, workers, schedules | `JOBS.md` | OPERATIONS has no Scheduled jobs section; its Health and Alerts link the jobs they watch |
| the units, the how values reach a unit, the deploy steps | `DEPLOYMENT.md` | ARCHITECTURE § Deployment view is the topology only, one line per container, and links |
| how a caller proves who it is, roles | `SECURITY.md` | API § Calling it says which header a call carries and links |
| environment names | `CONFIGURATION.md` | INTEGRATIONS links each third party's rows; SECURITY § Secrets handling links CONFIGURATION's secret column and holds rotation, access and never-committed |
| the reading order | `ONBOARDING.md` § Read in this order | the README's Start-here block names four files (README, index, AGENTS.md, ONBOARDING with its state) and first stops until ONBOARDING is written; the index lists, it does not order |
| what is next | `plans/ROADMAP.md` | PRODUCT and OVERVIEW have no Roadmap section; Principles links |
| the install and run commands, repeated | `AGENTS.md` § Commands | the one exception: README § Quickstart and SETUP § Install / § Run it carry a checked copy, so a reader can start without a hop; R11 diffs the copy against AGENTS.md. TESTING § Running tests, DEVELOPMENT § Daily loop and § Lint and format, DEPLOYMENT § Units link |
| environment names, in the deploy and CLI docs, and which of them are secrets | `CONFIGURATION.md` (secret column) | DEPLOYMENT § How values reach a unit says where the example file lives and how values reach the unit; CLI § Configuration names the config files; both link the names |
| a symptom and its fix | the guide of the task: SETUP § If it fails, DEVELOPMENT § Common problems, DEPLOYMENT § Known traps, OPERATIONS § When something is wrong | AGENTS.md § Gotchas holds the precondition in one line and links the fix |
| what a person does when a job is stuck | `OPERATIONS.md` § When something is wrong | JOBS § Failure and retry holds the retry design and links |
| a scheduled CI workflow | `TESTING.md` § What CI runs | JOBS § Schedules lists cron in the code only |
| why something was said no to | `decisions/` | PRODUCT § What we said no to, OVERVIEW § Non-goals and INTEGRATIONS § Not integrated hold one line and a link each |
| the licence | README § Status names the file | CONTRIBUTING § Before you start says what it means for a contribution, and where to report a vulnerability |
| the consumer's install and first call (library, CLI) | `PUBLIC_API.md` § Install and import, `CLI.md` § Install and invoke | README § Quickstart carries a checked copy for those kinds (R11 diffs it against that doc, not AGENTS.md); AGENTS.md stays the developer's commands |
| how a value reaches a unit (platform settings, vault, mounted file) | `DEPLOYMENT.md` § How values reach a unit | SECURITY § Secrets handling keeps rotation, access and never-committed, and links |
| which platform and environment a unit runs on, its URL, the branch that deploys there | `DEPLOYMENT.md` § Units | ARCHITECTURE § Deployment view is the arrows between containers and links; API § Calling it links for the base URL |
| cutting and publishing a version (tag, changelog entry, artifact) | `RELEASING.md` | DEPLOYMENT § Deploy steps links for the step that publishes; RELEASING links DEPLOYMENT for the step that puts an artifact into an environment |
| the code conventions a linter does not enforce | `CONTRIBUTING.md` § Code conventions | AGENTS.md § Conventions and DEVELOPMENT link; ARCHITECTURE § Containers keeps "what it must never do" at container level only |
| the path of a config or example env file | `CONFIGURATION.md` § Files | DEPLOYMENT § How values reach a unit holds the mechanism and links; SETUP § Install copies the file by name as a command |
| a managed store that is also a third party (S3, Redis, Supabase) | `DATA_MODEL.md` § Stores owns what is kept there and the key shape | INTEGRATIONS holds the purpose and the failure mode and links the store |
| the code layout | README § Repository layout owns the top-level table | ARCHITECTURE § Building blocks starts one level inside a container and links the README row |
| what is next, when no ROADMAP exists | nowhere, on purpose: PRODUCT and OVERVIEW never hold it | a repository that plans in files earns ROADMAP; one that plans in a tracker has no roadmap doc, and the index says so by having no plans/ group |
| the health route | `OPERATIONS.md` § Health (in a monorepo the root doc's table; a unit's doc links its row) | DEPLOYMENT § Units has no health column; DEVELOPMENT § Run and debug links |
| the port a unit listens on | `CONFIGURATION.md` (the row; stated in prose against its source) | ARCHITECTURE § Containers and DEVELOPMENT § Run and debug link |
| rolling back | `DEPLOYMENT.md` § Rollback | RELEASING § Rolling back a release says only whether a published version can be pulled |
| the vocabulary | `ONBOARDING.md` § Glossary | PRODUCT § Core concept and OVERVIEW § Concepts link the entries |
| the data stores | `DATA_MODEL.md` § Stores | DEPLOYMENT § Units lists deployable units only |

## Scenarios: what each kind of repository earns

The inventory decides the kind (`application`, `library`, `cli`, `infrastructure`, `monorepo`,
`docs-only`; a repository can be several). The rows above say what earns each doc; this table says
what a typical repository of each kind ends up with, so a reader can sanity-check a proposal.

| kind | always (every repository with code) | earned by evidence | never |
| --- | --- | --- | --- |
| application | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT, OPERATIONS, CONTRIBUTING, PRODUCT, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY (sixteen with the index and the manifest) | DATA_MODEL, API, DESIGN_SYSTEM, JOBS, RELEASING, decisions/, CHANGELOG, plans/ | OVERVIEW, PUBLIC_API, CLI (unless it also ships one) |
| library | README, AGENTS.md, SETUP, ONBOARDING, DEVELOPMENT, TESTING, DEPLOYMENT (one line: published, not deployed), OPERATIONS (one line: not operated), CONTRIBUTING, OVERVIEW, ARCHITECTURE, CONFIGURATION, INTEGRATIONS, SECURITY | RELEASING, PUBLIC_API, CHANGELOG, decisions/ | PRODUCT, DESIGN_SYSTEM, JOBS, API (its own examples and tests are not routes) |
| cli | as library, with CLI instead of PUBLIC_API; both when both entries exist | | |
| monorepo | the application set at the root as the map; per unit: its own README.md (a person's, seeds only) | per unit with a Dockerfile or deploy config: `<unit>/docs/DEPLOYMENT.md` and `<unit>/AGENTS.md`; per unit with a health route or an alert file: `<unit>/docs/OPERATIONS.md` (cron is JOBS's); the root DEPLOYMENT becomes the map variant (a table of units and links); the root OPERATIONS keeps its ordinary template and owns the table of every unit's health route, which the unit docs link | a unit never owns architecture, product, security or data; those stay at the root. A unit doc that reads like one of those (`server/docs/S3-STORAGE.md`) is never moved and never covers the root concern: it is listed in the index as unreviewed, and the root doc links it or absorbs it by hand |
| infrastructure | the same sixteen, with OVERVIEW instead of PRODUCT (it has users, not a product it is becoming); DEVELOPMENT is the loop of changing the manifests and applying them | decisions/, CHANGELOG | PRODUCT, API, DATA_MODEL, DESIGN_SYSTEM |
| docs-only | nothing - the README, index and agent file are always-on for repositories with code | only what the manifest pins | everything else |

Worked examples from real runs, so the numbers mean something:

- A three-service application with a Prisma schema, 130 routes, a React frontend, `better-auth`,
  `bullmq` and the S3, Redis, OpenAI and Resend SDKs, 25 decision-like commits and one tag: the
  sixteen, plus DATA_MODEL, API, DESIGN_SYSTEM, JOBS, RELEASING and CHANGELOG, plus a
  DEPLOYMENT and an AGENTS.md under each of three units and OPERATIONS under two. Every bucket
  folder but `plans/` exists; decisions/ waits for a folder or a pin.
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
State is one of `skeleton`, `draft`, `unreviewed`, `reviewed YYYY-MM-DD`, `none YYYY-MM-DD`, `stale YYYY-MM-DD`.

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
## Units

- [server/README.md]: the Express server - what it is and how to run it alone - unreviewed

## Root files

- [drum_reference.md]: ... - unreviewed
```

The index lists every Markdown file the repository tracks outside dependencies, dot-folders, build output, skill trees and fixtures: a doc the shape placed by its concern, a unit's own docs (`server/docs/S3-STORAGE.md`), a README beside a service, a doc under `ops/` - each unclaimed one as `unreviewed` under Units, Root files or Notes beside code (a file inside a source tree: `src/`, `prompts/`, `migrations/`, `tests/`), so "one hop from the index" holds for all of them; files under an inside-indexed folder (decisions/, research/, tasklist/, a split's parts) are reached through that index instead. The proposed manifest adds each unit's own docs folder to the roots, so the next run checks them too.

`none YYYY-MM-DD` is the state of an always-on doc a person confirmed says nothing applies here (a library's DEPLOYMENT, a repo with no third party), so an agent knows there is nothing to read without the hop. A changelog pinned at the root lists under History with a root link. Rules the checker reads from it: one line per doc, a dash, the doc as a Markdown link to its relative path, a colon, the owner text, a dash and the state (the example above abbreviates the links to their titles);
the bucket H2s in this fixed order, a bucket omitted when empty; `Units` for unit READMEs, unit
AGENTS.md files and unit docs; `Notes beside code` for Markdown inside a source tree; the front door, the agent file, CLAUDE.md and the root pointers (LICENSE, CONTRIBUTING, CHANGELOG, CODE_OF_CONDUCT, SECURITY and the other files GitHub surfaces by name) are not listed - they are reached from the Start-here block or by GitHub itself; `Root files` for Markdown at the repository root that is not a
community file. R1 counts a doc reachable when the index lists it or the inside index of `decisions/`,
`research/`, `tasklist/` (its sibling `TASKLIST.md`) or a split parts folder does. R9 checks the
tasklist counts through the manifest's `counts` entry, which the proposed manifest carries. R14 reads the trailing state. A table-shaped index is an R15
finding with the rewrite as the fix.

## The agent file grammar

`AGENTS.md` at the root, forty lines at most, hand-maintained after the skeleton:

```markdown
# <project> - for agents

> **This document owns:** the commands, the conventions an agent cannot infer, the gotchas. *(skeleton, write me)*

## Commands

- install: `pnpm install`                 [package.json]
- run: `pnpm run dev`                     [package.json: scripts.dev]
- build: `pnpm run build`                 [package.json: scripts.build]
- test: `pnpm run test`                   [package.json: scripts.test]
- lint: `pnpm run lint`                   [package.json: scripts.lint]
- typecheck, check, migrate               when the manifest has them

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
`agentFileMaxLines` (default 40), or repeats a README paragraph verbatim. In a monorepo every unit
that deploys on its own earns `<unit>/AGENTS.md`, built from that unit's manifest alone with the
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

`decisions/README.md` lists every record newest first in the index grammar. An existing `adr`,
`adrs`, `rfcs` or `decisions` folder, or a manifest pin, earns the bucket; the inventory's
decision-like commits (subject containing `decid`, `switch`, `migrat`, `replace`, `remov`,
`adopt`, `revert`, `drop`, `deprecat` or `instead`) are advice for the person who fills the first
record, never a trigger. Apply writes one skeleton record; the fill step may draft one record per
commit a person picks, each a draft until confirmed. The fill gate checks the status
line and the four sections (G13). `decisions/` is a live folder, not a record folder: its files are
edited (status changes), so R6 and R7 apply in full.

## The README

One file, two readers. A person skims the headings; an agent jumps to a heading by name and reads a
table. So the README has fixed H2 names - in a fixed order when written whole; an existing README keeps
its own order and gets the lacking ones after its text - facts in tables rather than prose, the
install and run commands as a checked copy of AGENTS.md's, and one line plus a link for anything
a doc owns:

```markdown
# <project>
<one sentence - the index reuses it>

## What it is            three sentences; PRODUCT has the long form
## Quickstart            numbered: prerequisites, install, run, the URL or command that proves it
## Start here            the block between the markers carries this H2: this file, docs/INDEX.md, AGENTS.md, ONBOARDING (which owns the reading order)
## Repository layout     table: folder | what lives there | its README
## Commands              one line and a link to AGENTS.md § Commands, which owns them
## Configuration         one line and a link to CONFIGURATION.md; never an env table
## Status                version, licence file, CI workflow
```

A README that does not exist is written from the template, filled from the manifests, marked a
draft. A README that exists is fitted into the template on apply: its sections land under the
template headings they match (a `## Setup` under Quickstart, a `## Project structure` under
Repository layout), text verbatim; sections that match nothing stay after, in their order;
template sections it lacks get their guidance line after all of that, never before it - the
front door opens with the person's text, not with six guidance lines; the Start-here block moves
whole into its slot, or right under the intro when that slot is still empty; and a section that a
doc owns - an env table, deploy steps - is pasted into that doc (homed by what its body holds as
much as by its heading: three environment names make it configuration) and replaced by one line
and a link to the pasted heading itself. A bracket elsewhere that cited the README section now
cites its new home. A section that lands under a template heading beside others keeps its own
heading as an H3 and its sub-headings one level down, so the outline stays a tree. Nothing is deleted or reworded, and the proof says so line by line. R11 lists
the lacking sections as advice in plan mode. The template's own headings are never a second home,
whatever they contain. The README links `AGENTS.md` for the commands and repeats none of them; the
Start-here block names four files - this README, the index, AGENTS.md, ONBOARDING labelled by its
state - and, until ONBOARDING is written, the first stops that already have content.

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
| `docs/explanation/PIPELINES.md` | `docs/reference/JOBS.md` |
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
  `docs/INDEX.md` and the inside indexes of `decisions/`, `research/`, `tasklist/` and split folders.
- Editing history. A version once cut in the changelog is not rewritten; a plan lives in `plans/`,
  where it is edited as work moves.
