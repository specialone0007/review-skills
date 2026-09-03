---
name: repo-health-audit
description: Read-only repository health and organization audit for finding naming drift, unclear file or folder placement, weak module boundaries, dead code, duplicate code, repeated patterns that should become shared helpers, duplicate concepts, inconsistent conventions, oversized files, circular dependencies, and structural issues that make a codebase harder to navigate or more likely to become spaghetti over time. Use when the user asks to review repo organization, folder structure, naming, architecture hygiene, codebase structure, module layout, dead code, duplicate code, reuse opportunities, or whether a repository is getting messy.
license: MIT
---

# Repo Health Audit

Run a read-only audit of repository structure, naming hygiene, reuse health, and long-term maintainability. Produce a prioritized report of organization problems with evidence and practical fix direction. Default posture: do not edit, move, rename, reformat, stage, or delete files unless the user explicitly asks for cleanup after the audit.

## Core Rules

- Stay read-only during the audit. If the user asks for fixes too, audit first, then switch to normal implementation only after the target changes are clear.
- Default to a full-repository audit when the user does not provide a specific scope. Inventory the repo's top-level structure, modules, and packages, then inspect the areas with the most naming drift, duplication, dead code, or boundary confusion.
- Full-repo audits are breadth-first, then depth-limited. Inventory the repo, rank surfaces by risk, deep-inspect as many high-risk surfaces as the turn allows, and list the rest under **Surveyed But Not Deeply Inspected** with a pointer to run another pass on them. State the surface counts in the report header. Never present a shallow sweep as complete coverage.
- Focus on organization, discoverability, naming, boundaries, dead code, duplication, reuse opportunities, and long-term maintainability. Do not report ordinary implementation bugs unless they are caused by structural confusion or repeated code.
- Infer conventions from the repo before judging. Existing patterns, framework defaults, monorepo layout, package boundaries, and local naming style matter more than generic preferences.
- Separate confirmed structure problems from subjective preferences. Label judgment calls clearly.
- Prefer actionable findings over broad advice. Every finding should point to concrete files, folders, names, imports, scripts, repeated code, or duplicated concepts.
- Avoid aesthetic nitpicks. A name or folder is a problem only when it creates ambiguity, inconsistency, duplication, poor discoverability, or maintenance risk.
- Respect generated, vendored, build output, migration, lockfile, and third-party directories unless the issue is that they are incorrectly committed or mixed with source.

## Inputs

Accept any organization target, including:

- Whole repository: `audit repo organization`, `is this codebase getting messy?`
- Specific area: `review app folder structure`, `audit naming in src/features`, `check API module organization`
- Monorepo/package layout: `scan packages for boundary drift`, `review workspace organization`
- Naming consistency: `find confusing names`, `check file and folder naming`
- Dead code and reuse: `find unused code`, `scan duplicate code`, `find helper extraction opportunities`
- Architectural hygiene: `find spaghetti structure`, `report module boundary problems`

If scope is unclear, choose the smallest useful boundary that covers the user's request and state it in the report. If no scope is stated, do not ask for one; proceed with a full-repo audit.
For scoped audits, inspect neighboring/shared code only as needed to validate convention, reuse, and import boundaries, but keep findings focused on the requested scope.

## Scope Boundaries

This skill should stay focused on repo health issues that affect navigation, reuse, boundaries, and safe growth.

### In Scope

- Dead code: unused files, exports, components, routes, scripts, configs, assets, feature flags, stale types, and old fixtures.
- Duplicate code: copied helpers, repeated validation, repeated API clients, repeated formatting logic, repeated permission checks, duplicated UI/state patterns, and repeated data transforms.
- Helper or component extraction opportunities when repeated behavior appears in several places, is likely to evolve together, or divergence would cause bugs.
- Naming consistency across files, folders, modules, functions, components, hooks, services, routes, environment variables, scripts, and tests.
- Folder and file placement, including feature code in random shared folders, shared code hidden inside one feature, and tests/docs/assets placed against repo convention.
- Module boundaries, including UI importing server-only code, features reaching into other feature internals, domain logic leaking into route handlers/components, and packages crossing ownership boundaries.
- Import health: circular dependencies, deep relative imports, inconsistent path aliases, barrel files hiding dependencies, and imports from private internals.
- Oversized files and folders, catch-all `utils`, `helpers`, `common`, `misc`, or `lib` areas, and flat directories with too many unrelated peers.
- Duplicate concepts, including multiple sources of truth for constants, enums, schemas, clients, stores, permission rules, and config values.
- Stale structure docs: README files, docs, comments, scripts, or metadata that describe old folders, commands, feature names, or ownership.
- Generated, vendor, and build-output hygiene when generated files are mixed with source, build artifacts are committed unexpectedly, or ignored files do not match repo reality.
- Test organization, including inconsistent placement, duplicated fixtures, old snapshots, and test names that no longer match behavior.
- Config and script organization, including repeated script logic, stale paths in scripts, duplicated config files, and unclear environment/config boundaries.
- Monorepo and package hygiene, including package boundaries, shared package creep, dependency direction, duplicated package responsibilities, and unclear ownership.

### Out Of Scope

- General bug finding, launch readiness, broken product flows, validation bugs, auth behavior bugs, and user-facing regressions. Use `feature-audit` for those.
- Security review or threat modeling unless a structural boundary issue creates an obvious security risk.
- Frontend visual/design critique, UI aesthetics, typography, spacing, motion, or polish.
- Broad performance audits such as rendering performance, query performance, caching, image optimization, or bundle tuning unless the performance risk comes directly from repo structure.
- Broad test coverage audits. This skill may report test organization problems, but not general missing behavioral coverage.
- Refactoring implementation. This skill reports and recommends; moves, renames, deletions, helper extraction, and import updates happen only after the audit.
- Style-only formatting such as semicolons, quote style, whitespace, import sorting, or Prettier/ESLint churn unless it hides a structural problem.
- Framework preference or rewrite recommendations. Judge against the repo's existing conventions and avoid broad architecture rewrites.
- Business or product logic review unless duplicated business rules create structural risk.

## Discovery Workflow

1. Establish repository shape.
   - Run the bundled `scripts/repo_inventory.py` first when it is available. One call returns detected stacks, available commands, per-directory file and line counts, the extension mix, largest files, where tests/CI/docs/lockfiles live, and structural smells such as flat directories and catch-all folders. The path is relative to this skill's own directory, which varies by host. Use `python` if `python3` is not on PATH.
   - `python <skill-dir>/scripts/repo_inventory.py --top 25`, or `--format json` when you want to filter the results yourself.
   - The script is read-only and never reads the contents of `.env` files; it reports their names only.
   - If the script is unavailable, gather the same picture manually: read top-level files and directories, manifests, workspace configs, framework configs, package manager files, build/test configs, docs, and README-like files.
   - Either way, identify stack, app/package boundaries, source roots, generated/build directories, test locations, routing conventions, feature/module conventions, and naming style.
   - Treat the inventory as a survey, not as findings. Confirm anything you intend to report by opening the files.
   - Check `git status --short` so user changes are visible before interpreting structure.

2. Map organization conventions.
   - Identify how features, shared components, services, API handlers, models, schemas, utilities, tests, assets, docs, scripts, and config are organized.
   - Compare neighboring modules to find intended patterns and exceptions.
   - Note framework-required layout separately from project-chosen layout.

3. Map usage and reuse signals.
   - Trace exports, imports, routes, commands, scripts, config references, tests, and framework entrypoints before calling code unused.
   - Search for repeated code shapes: similar functions, hooks, components, validators, request clients, formatting logic, permission checks, data transforms, constants, and error handling.
   - Distinguish harmful duplication from acceptable local duplication. Do not recommend abstraction for two small copies unless the behavior is likely to evolve together or divergence would create bugs.
   - Check whether a shared helper already exists before recommending a new one.

4. Look for structural drift.
   - Naming drift: inconsistent casing, vague names, synonyms for the same concept, misleading names, old names after product/domain changes.
   - Placement drift: files in catch-all folders, unrelated code in shared areas, feature code split across surprising locations, tests far from the code style used elsewhere.
   - Boundary drift: imports crossing package/layer boundaries, feature modules reaching into other feature internals, UI importing server-only code, domain logic leaking into routes/components.
   - Duplicate concepts: multiple helpers, constants, schemas, clients, hooks, stores, or components that appear to solve the same problem.
   - Dead code: unreferenced files, exports, components, routes, scripts, feature flags, configs, types, fixtures, or assets that appear unreachable from known entrypoints.
   - Duplicate code: copied logic, repeated UI/state patterns, repeated validation rules, repeated data mapping, duplicated API clients, or repeated conditionals that should share one implementation.
   - Missing helper opportunities: repeated code used in three or more places, business rules that must stay consistent, or copy-pasted logic that already shows small divergent changes.
   - Scale problems: oversized files/folders, flat directories with too many unrelated peers, index/barrel files hiding dependencies, unclear public/private APIs.
   - Dependency problems: circular dependencies, inconsistent import aliases, deep relative imports, duplicated config, scripts that encode stale paths.
   - Documentation mismatch: README, docs, comments, or generated metadata that describe an older structure.

5. Verify safely.
   - Use low-risk commands that fit the repo: `rg`, file listings, dependency graph tools, dead-code tools, duplicate-code tools, lint rules, typecheck, or existing architecture checks.
   - Do not install dependencies, run migrations, mutate generated files, or start long-running services unless the user explicitly asks.
   - Record checks run and checks skipped.

## Severity Rubric

- `P0`: Structure actively breaks builds, imports, packaging, generated output, or production/runtime boundaries.
- `P1`: High-risk organization issue that repeatedly causes wrong imports, duplicated implementations, feature bugs, ownership confusion, or unsafe layer crossing.
- `P2`: Meaningful maintainability issue likely to worsen as the repo grows, such as inconsistent placement, vague naming, oversized modules, dead code, duplicated concepts, or repeated code that should become shared.
- `P3`: Lower-risk cleanup, naming polish, documentation mismatch, or convention improvement worth queueing.

## Evidence Standards

- Include file and line references whenever possible. For folder-level findings, cite representative paths and counts.
- Show the convention and the exception. Example: most features use `src/features/<name>`, but billing files live under `src/utils/billing`.
- State whether a finding is confirmed by code evidence, inferred from pattern mismatch, or a judgment call.
- For dead code, identify the entrypoints and searches/tools used. Mark as `likely unused` unless references were exhaustively checked across code, config, routes, docs, tests, and dynamic loading patterns.
- For duplicate code, cite at least two representative copies and explain why shared behavior would reduce risk. Do not recommend abstraction when duplication is clearer and unlikely to diverge.
- Avoid claiming a move or rename is safe unless imports, routes, tests, and external references were checked.

## Report Format

Use this structure unless the user asks otherwise:

```markdown
**Repo Health Audit: <scope>**

No code changed. I checked <brief scope>, including naming, file/folder placement, module boundaries, dead code, duplicate code, helper extraction opportunities, and convention drift. <verification summary>. No P0s found / P0s found: <count>.

1. **P1: <finding title>.**
   What is structurally wrong and why it will make the repo harder to maintain.
   Evidence: `<path>:<line>`, or representative paths when the pattern repeats.
   Suggested cleanup direction: <smallest behavior-preserving change>.

2. **P2: <finding title>.**
   What is structurally wrong and why it matters.
   Evidence: `<path>:<line>`, or representative paths when the pattern repeats.
   Suggested cleanup direction: <smallest behavior-preserving change>.

**Reuse Opportunities**
- <Only include when useful: repeated code/patterns that are not severe findings but are good helper/component extraction candidates.>

**Surveyed But Not Deeply Inspected**
- <For full-repo audits only: surfaces that were inventoried but not inspected deeply this pass, and which to run next. Omit this section entirely for scoped audits.>

**Checks Run**
- `<command>`: <result>

**Not Tested**
- <dependency graph, lint, typecheck, or runtime gaps and why>

**Assumptions**
- <only include if useful>
```

If no organization problems are found, say that clearly, then list residual risks and any conventions worth documenting.

## Cleanup Guidance

When the user asks to fix findings after the audit:

- Prefer small, behavior-preserving moves and renames.
- Delete dead code only after checking imports, routes, scripts, configs, tests, dynamic references, docs, and generated references.
- Extract helpers/components only when shared behavior is stable enough to justify coupling. Keep feature-specific variation local.
- Update imports, route references, tests, docs, build config, and scripts together.
- Preserve public APIs unless the user accepts a breaking cleanup.
- Add or update architecture lint rules only when the repo already has a place for them or the repeated problem justifies it.
- Avoid large reorganizations in one patch unless the repo is small or the user explicitly asks for a broad restructuring.

## Related Skills

- Use `docs-sync-audit` when the ask is whether docs match the code.
- Use `test-gap-audit` when the ask is missing or weak test coverage.
- Use `feature-audit` when the ask is runtime behavior, product readiness, or user-facing regressions.

## Agent Portability Notes

- Use available shell, search, git, GitHub, or MCP tools as appropriate. The evidence you gather matters more than the tool names used to gather it.
- If dependency-graph, dead-code, or duplicate-code tooling is unavailable, continue with search and import tracing, and list that limitation in the report.
- In hosts that support inline review comments, reserve them for confirmed actionable findings; do not attach them to survey-level structural observations.
