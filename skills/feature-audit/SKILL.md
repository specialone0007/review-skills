---
name: feature-audit
description: Read-only, repository-agnostic feature readiness audit for finding bugs, launch blockers, regressions, UI/UX flow errors, accessibility issues, auth/data risks, missing critical tests/docs, and production readiness gaps in a named feature, route, URL, workflow, product surface, or PR, or across the whole repository when no scope is named. Use when the user explicitly asks for a feature/product-surface audit, scan, launch-readiness check, production-readiness review, or bug-risk report. If the primary ask is security, test coverage, docs drift, repo organization, feature ideas, or PR communication, use security-audit, test-gap-audit, docs-sync-audit, repo-health-audit, feature-brainstorm, or pr-branch-summary instead.
license: MIT
---

# Feature Audit

Run a deep readiness audit for one feature or product surface in any repository. Produce a comprehensive prioritized findings report with evidence and fix direction. Default posture for audit-only requests: stay read-only and do not edit files, reformat code, stage changes, create commits, or run destructive commands. If the user explicitly asks to find and fix bugs or remediate readiness issues in the same request, run a brief evidence-first audit pass, then switch to the normal implementation workflow for the confirmed target issues.

## Core Rules

- Stay read-only for audit-only requests. If the user explicitly asks for fixes too, audit briefly first, identify the target issues with evidence, then proceed in the same turn using the normal implementation flow.
- Default to a full-repository audit when the user does not provide a specific scope. Inventory the repo's major product surfaces, routes, and workflows, then audit the highest-risk ones for readiness and defect risk.
- Full-repo audits are breadth-first, then depth-limited. Inventory the repo, rank surfaces by risk, deep-inspect as many high-risk surfaces as the turn allows, and list the rest under **Surveyed But Not Deeply Inspected** with a pointer to run another pass on them. State the surface counts in the report header. Never present a shallow sweep as complete coverage.
- Be repository-agnostic. Do not assume framework, language, test runner, database, route style, deployment platform, or file layout.
- Prefer repo evidence over memory. Discover conventions from files, scripts, configs, tests, docs, routes, and existing patterns.
- Use fast search first when available (`rg`, `fd`, code search); fall back to native file/search tools if needed.
- Keep scope feature-focused. Report global architecture issues only when they affect this feature's user journey, launch safety, maintainability, or operations.
- Aim for exhaustive coverage inside the chosen scope. Do not stop after finding the first few issues or a representative sample; continue tracing adjacent code paths, states, and tests until the feature surface has been checked as completely as practical for the turn.
- List every distinct, actionable finding you can substantiate within the scope, including lower-severity `P3` findings when they represent real readiness, UX, maintainability, resilience, or test risk. Do not impose an arbitrary top-N cap unless the user explicitly asks for one.
- Use the specialist skills when the user's primary goal is narrower: `security-audit` for AppSec, `test-gap-audit` for coverage gaps, `docs-sync-audit` for documentation drift, `repo-health-audit` for structure/reuse, `feature-brainstorm` for improvement ideas, and `pr-branch-summary` for PR communication.
- Separate confirmed bugs from inferred risks. Label product decisions, missing context, or assumptions clearly.
- Avoid duplicate findings. When one root cause creates several symptoms, report the root cause once and list the affected symptoms or surfaces in that finding.
- Treat UI/UX flow errors as audit findings when they can confuse users, block completion, hide recovery paths, cause wrong actions, or make important states hard to understand.
- Avoid noisy style opinions. Findings should be actionable risks, not generic cleanup wishes.

## Inputs

Accept any specific surface, including:

- Feature names: `uploads`, `roles`, `billing`, `notifications`, `dashboard compose`.
- Routes or URLs: `/hub/feed`, `/settings/team`, `http://localhost:3000/admin/users`.
- Workflows: `invite teammate -> accept invite -> set role -> revoke access`.
- Pull requests or branches: audit the changed feature surface and its connected flows.
- Bug-risk themes: `audit search pagination`, `scan auth around exports`, `review mobile launch risks for checkout`.

If scope is blurry, infer a reasonable boundary from the request and state it in the report. If no scope is stated, do not ask for one; proceed with a full-repo audit. Ask a clarifying question only when multiple interpretations would lead to materially different audits.

## Discovery Workflow

1. Establish repo context.
   - Read the top-level file list and likely project manifests: package files, lockfiles, framework configs, app configs, build/test configs, Docker/compose files, CI workflows, docs, and README-like files when present.
   - Identify the stack, app entrypoints, route conventions, test conventions, local run commands, environment requirements, and whether this is a monorepo.
   - Check `git status --short` before touching verification so existing user changes are visible.

2. Map the feature surface.
   - Find routes/pages/controllers/API handlers/jobs/commands related to the feature.
   - Find UI components, templates, state modules, styles, client-side services, form handlers, and shared helpers.
   - Find backend services, models, schemas, repositories, migrations, queues, permissions, and integrations if relevant.
   - Find tests, docs, fixtures, seed data, storybook/examples, analytics events, and API contracts.
   - For PR audits, compare changed files with adjacent unchanged files so regressions outside the diff are visible when they affect the feature.

3. Trace user journeys.
   - Happy path: create, view, update, delete, submit, publish, export, invite, purchase, or whatever the feature's core action is.
   - Alternate states: empty, loading, error, validation failure, permission denied, unauthenticated, expired session, disabled feature flag, offline/slow network where applicable.
   - UI/UX flow: entry points, clear next actions, action labels, hierarchy, confirmation/cancel paths, success states, recovery routes, multi-step progress, and whether the interface preserves user context.
   - Data boundaries: pagination, filtering, sorting, ownership, tenant/org boundaries, time zones, localization, file size/type limits, rate limits, retries, idempotency.
   - Navigation boundaries: deep links, browser back/forward, refresh, direct URL access, mobile layout, keyboard access, screen reader labels, focus management.

4. Verify safely.
   - Run only low-risk commands that fit repo conventions: lint/typecheck/unit tests for relevant areas, syntax checks, focused test files, or build checks when reasonably quick.
   - Prefer existing scripts from manifests or docs. Do not invent install steps unless dependencies are already present or the user asked.
   - Use local smoke checks only when a server is already running or the repo has an obvious safe dev command and the audit needs runtime behavior. Do not leave long-running processes orphaned.
   - Never use production credentials, mutate production data, run migrations against shared databases, or execute destructive cleanup commands.
   - Record every check run and any checks skipped because services, credentials, browsers, dependencies, or time were unavailable.

5. Run a second-pass completeness sweep.
   - Re-scan the mapped feature files, adjacent tests, route handlers, shared helpers, docs/contracts, and state/error boundaries for issue categories not covered in the first pass.
   - Specifically look for missed alternate states, negative paths, authorization/data-boundary edges, stale UI states, mobile/accessibility issues, and missing regression tests.
   - De-duplicate root causes, but preserve separate findings when the cause, affected user journey, owner, or fix direction is meaningfully different.
   - If time, tooling, credentials, or repo setup prevents a full second pass, say what was not exhaustively checked under `Not Tested` or `Residual Risk`.

## What To Look For

Audit across the layers that exist in the repository:

- Routing/navigation: broken links, unreachable states, missing redirects, bad route params, deep-link failures, incorrect HTTP methods/status codes.
- Data correctness: missing joins/includes, stale caches, race conditions, duplicate submissions, bad sorting/filtering, pagination gaps, time zone mistakes, null/empty handling.
- Validation: client/server drift, missing server-side validation, weak error messages, unsafe defaults, file/input edge cases, inconsistent required fields.
- Auth and authorization: tenant leaks, owner checks, role mismatches, unauthenticated access, privilege escalation, insecure object references.
- Reliability: unhandled exceptions, retry/idempotency gaps, loading spinners that never resolve, background job failures, flaky external integrations.
- UI/UX flow integrity: unclear next step, dead ends, navigation loops, mismatched labels and outcomes, duplicated or conflicting actions, stale status copy, lost context after submit/back/refresh, weak success or recovery paths, risky destructive actions, and multi-step flows without progress or escape.
- UX readiness: confusing flows, missing empty/error/loading states, inaccessible controls, focus traps, poor keyboard support, mobile/responsive breakage.
- Visual interaction coherence: disabled/enabled states, hover/focus/pressed feedback, selected/current state clarity, modal/drawer behavior, responsive layout shifts, text overflow, touch target size, and important content hidden below folds or behind overlays.
- Accessibility basics: semantic labels, form labels, alt text, focus order, color contrast risks, keyboard operability, announced errors.
- Performance: avoidable N+1 queries, overfetching, large bundles/assets, blocking render gates, slow search/filter paths, expensive re-renders.
- Observability and operations: missing logs/metrics for critical failures, unclear error boundaries, risky feature flags, missing rollback or migration notes.
- SEO/share where relevant: titles, metadata, canonical URLs, public indexing expectations, Open Graph/social previews.
- Tests and docs: missing regression coverage for the audited journeys, stale docs/API contracts, absent fixtures for important states.

## Severity Rubric

- `P0`: Feature cannot work, data loss/corruption, serious security/privacy leak, production outage risk, or destructive behavior.
- `P1`: Launch blocker or high user impact; common journey fails, content/data unreachable, severe auth/validation/reliability/performance issue.
- `P2`: Important pre-launch fix; confusing or incomplete behavior, edge-case failure likely to affect users, stale contract/docs, weak regression coverage for critical paths.
- `P3`: Lower-risk polish, maintainability, resilience, or test gap worth queueing but not blocking launch.

## Evidence Standards

- Include file and line references whenever possible. Use the path format natural to the host agent; prefer absolute paths when the environment supports clickable absolute paths, otherwise use repo-relative paths.
- Cite command results concisely: command, pass/fail, and the important failure line or summary.
- If browser/API/manual verification is unavailable, say so instead of implying it was tested.
- Phrase inferred risks as inference: `Likely`, `May`, `Decision needed`, or `Could be intended`. Add compact confidence for inferred risks only: `Confidence: high`, `Confidence: medium`, or `Confidence: low`.
- Do not claim a finding is confirmed unless it is backed by code, tests, docs, runtime behavior, or command output.

## Report Format

Use this structure unless the user asks otherwise:

```markdown
**Feature Audit: <feature/scope>**

No code changed. I checked <brief scope>, including functionality and UI/UX flow. <verification summary>. No P0s found / P0s found: <count>.

1. **P1: <finding title>.**
   What is wrong and why it matters.
   Evidence: `<path>:<line>`.
   Suggested fix direction: <smallest safe change>.

2. **P2: <finding title>.**
   What is wrong and why it matters.
   Evidence: `<path>:<line>`.
   Confidence: <high/medium/low, for inferred risks>.
   Suggested fix direction: <smallest safe change>.

**Surveyed But Not Deeply Inspected**
- <For full-repo audits only: surfaces that were inventoried but not inspected deeply this pass, and which to run next. Omit this section entirely for scoped audits.>

**Checks Run**
- `<command>`: <result>

**Not Tested**
- <browser/auth/service/manual gaps and why>

**Assumptions**
- <only include if useful>
```

Keep findings ordered by severity and impact, and include all distinct actionable findings discovered rather than only the highest-impact examples. If no findings exist, say that explicitly, then list residual risks and test gaps.

## Post-Audit Fix Workflow

Use this after the audit phase is complete and the user has explicitly asked to fix findings, apply the audit, remediate issues, or find and fix bugs in the audited surface. This can happen in a follow-up request or in the same original request. Do not edit files during the evidence-gathering audit phase itself.

- Treat the audit findings as the source of truth. If later code inspection contradicts a finding, state the correction and adjust the fix plan.
- If the user names specific findings, fix only those findings. If the user broadly asks to apply the audit, fix P0/P1 findings first, then P2 findings when they are clearly safe and scoped.
- Ask a clarifying question only when the requested fix scope is ambiguous enough that reasonable choices would lead to materially different code changes.
- Keep fixes focused on the audited feature surface. Do not bundle unrelated cleanup, formatting churn, opportunistic refactors, or neighboring issues unless required for the fix.
- Prefer small, behavior-preserving changes. Preserve public APIs, data contracts, migrations, routes, and user-visible behavior unless the finding requires changing them.
- Update tests, fixtures, docs, generated types, API contracts, or stories when they are part of the broken behavior or verification surface.
- For risky fixes involving auth, data ownership, destructive actions, payments, migrations, or production integrations, explain the risk and choose the smallest safe change.
- Run focused verification after each fix group when practical: relevant unit tests, typecheck/lint, focused integration tests, build checks, or manual/browser checks.
- If a finding cannot be fixed safely in the current context, leave it open and explain the blocker, missing context, or follow-up needed.
- Final response should map audit findings to outcomes: fixed, partially fixed, not fixed, and not tested. Include checks run and remaining risk.

## Agent Portability Notes

- Use available shell, file search, browser, GitHub, or MCP tools as appropriate, while respecting read-only mode.
- Use equivalent project search, file-read, terminal, browser, and repository tools when tool names differ across hosts. The workflow matters more than tool names.
- If the host supports inline review comments, emit them only for confirmed actionable findings and keep ranges tight. Otherwise, use the Markdown report.
- If a required tool is unavailable, continue with source inspection and clearly list the limitation.
