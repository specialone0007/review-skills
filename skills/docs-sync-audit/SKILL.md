---
name: docs-sync-audit
description: Run a read-only documentation drift audit for a feature, PR, branch, release, API, configuration change, workflow, CLI, package, or repository area. Use when the user asks whether docs are stale, missing, inconsistent with code, or need updates after code changes. Checks README files, setup guides, API docs, env docs, changelogs, examples, comments, generated docs, and user-facing instructions. This is not a general code review; use feature-audit for product bugs and readiness risks.
---

# Docs Sync Audit

Check whether documentation still matches the code, configuration, API behavior, commands, examples, and user workflows. Report stale or missing docs with concrete evidence and update direction.

## Core Rules

- Stay read-only unless the user explicitly asks to update docs.
- Ground every finding in both sides of the mismatch: the code/config/source of truth and the stale or missing documentation.
- Separate confirmed drift from inferred doc gaps.
- Prefer user-impacting docs drift over cosmetic wording issues.
- Do not report style preferences unless they make instructions misleading, incomplete, or hard to follow.
- Treat generated docs carefully: identify the generation source before recommending direct edits.
- Avoid creating docs during the audit phase.

## Inputs

Accept any docs-sync target, including:

- PRs or branches: `audit docs for this PR`, `what docs need updating before release`.
- Features: `docs sync for uploads`, `check billing docs after this change`.
- APIs: `audit OpenAPI docs against handlers`, `check SDK examples for the new endpoint`.
- Config/setup: `env docs drift`, `README setup audit`, `Docker docs sync`.
- CLI/workflows: `check command docs`, `does onboarding match the current flow`.
- Whole repo docs hygiene when explicitly requested.

If scope is unclear, infer the smallest useful boundary and state it. Ask only when different scopes would produce materially different doc checks.

## Discovery Workflow

1. Establish source of truth.
   - Check `git status --short`.
   - For PR/branch audits, identify the base and changed files when possible.
   - Locate manifests, scripts, routes, configs, schema files, migrations, API handlers, CLI entrypoints, env validation, generated-doc sources, and tests that reveal expected behavior.

2. Locate related documentation.
   - Search README files, docs folders, API docs, OpenAPI/Swagger specs, changelogs, setup guides, deployment docs, env examples, examples, fixtures, comments, storybook/docs pages, package docs, and runbooks.
   - Include docs near the feature and docs users would reasonably consult first.
   - For generated docs, locate the source file or generator command.

3. Compare code and docs.
   - Commands/scripts: names, arguments, package manager, working directory, prerequisites, outputs.
   - APIs: routes, methods, auth requirements, request/response shape, status codes, errors, pagination, webhooks, versioning.
   - Config/env: required vars, defaults, examples, secrets, feature flags, deployment settings.
   - UI/workflows: screens, labels, steps, permissions, roles, states, screenshots, examples.
   - Data/schema: fields, migrations, enums, limits, constraints, seed data, import/export formats.
   - Tests/examples: sample code, fixtures, SDK usage, curl examples, screenshots, expected outputs.

4. Verify safely.
   - Run low-risk commands that reveal docs/source mismatch when available: docs build, link check, typecheck examples, OpenAPI generation, CLI help, package scripts, or focused tests.
   - Do not install dependencies or regenerate large docs unless the user asks or the repo clearly expects it.
   - Record checks run and checks skipped.

## What To Look For

- README setup instructions that no longer work.
- Missing docs for new routes, commands, env vars, permissions, flags, migrations, webhooks, or user workflows.
- Old names, paths, screenshots, labels, examples, or config keys after a rename.
- API docs that disagree with handlers, schemas, validation, auth, errors, or status codes.
- Changelog/release notes missing user-visible or operational changes.
- `.env.example`, deployment docs, or runbooks missing required configuration.
- Example code that imports old paths, calls old APIs, uses stale package names, or omits required setup.
- Generated docs committed but stale relative to source.
- Comments or architecture docs that describe an older module boundary or behavior.

## Severity Rubric

- `P0`: Docs drift could cause production outage, data loss, security exposure, broken deploy, credential mishandling, or critical operational failure.
- `P1`: High-impact docs drift that blocks setup, release, API integration, migration, support, or a common user/admin workflow.
- `P2`: Meaningful stale or missing docs likely to confuse users, reviewers, operators, SDK consumers, or contributors.
- `P3`: Lower-risk docs cleanup, naming drift, examples, comments, or polish that should be queued.

## Evidence Standards

- Cite the source of truth and the stale/missing documentation.
- For missing docs, cite the code/config/change that should be documented and the doc area where users would expect it.
- Include exact paths and line references whenever possible.
- State whether the docs are confirmed stale, likely stale, or missing based on inference.
- Do not claim docs are safe to delete unless references, links, generated sources, and navigation were checked.

## Report Format

Use this structure unless the user asks otherwise:

```markdown
**Docs Sync Audit: <scope>**

No code changed. I compared <source/code/change scope> against <docs checked>. <verification summary>. No P0s found / P0s found: <count>.

1. **P1: <finding title>.**
   Drift: <what docs say or omit vs what code/config does>.
   Impact: <who is misled or blocked>.
   Evidence: source `<path>:<line>`; docs `<path>:<line>`.
   Suggested update: <specific docs change direction>.

2. **P2: <finding title>.**
   Drift: <what is stale/missing>.
   Impact: <why it matters>.
   Evidence: source `<path>:<line>`; docs `<path>:<line>` or expected docs area.
   Suggested update: <specific direction>.

**Likely Docs To Update**
- `<path>`: <why>

**Checks Run**
- `<command>`: <result>

**Not Tested**
- <docs build/link check/generated docs gaps and why>

**Assumptions**
- <only include if useful>
```

If no drift is found, say that clearly and list residual risks such as generated docs not rebuilt or external docs not accessible.

## Post-Audit Update Workflow

When the user asks to update docs:

- Update only docs related to confirmed drift or explicitly selected inferred gaps.
- Preserve the repo's documentation style, structure, and terminology.
- Update generated docs from the source/generator when practical instead of editing generated output directly.
- Update examples, screenshots, changelogs, env examples, API specs, and runbooks together when they describe the same behavior.
- Run docs build, link check, example typecheck, or focused verification when available.
- Final response should map findings to updated files and list checks run.

## Agent Portability Notes

- Use available shell, search, git, browser, GitHub, docs, or MCP tools as appropriate.
- If web docs, private docs, rendered docs, or external API docs are unavailable, continue with local source inspection and state the limitation.
- If the host supports inline review comments, emit them only for confirmed actionable docs drift and keep ranges tight.
