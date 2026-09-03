---
name: security-audit
description: Run a read-only, evidence-grounded security audit of a named feature, route, workflow, PR, branch, service, API, or code path, or of the whole repository when no scope is named. Use when the user asks for security risks, AppSec review, auth/authorization review, secrets exposure, injection risks, data leakage, abuse paths, unsafe dependencies, secure-by-default gaps, or security launch readiness. This is not a general bug audit; use feature-audit for broad product readiness and defects.
---

# Security Audit

Run a focused security review of one feature, PR, workflow, or code area. Prioritize exploitable risks, privacy/data exposure, unsafe trust boundaries, and missing defense-in-depth over generic hardening advice.

## Core Rules

- Stay read-only unless the user explicitly asks to fix findings.
- Default to a full-repository audit when the user does not provide a specific scope. Inventory the repo's auth boundaries, entry points, data access paths, and trust boundaries, then review the highest-risk ones deeply.
- Full-repo audits are breadth-first, then depth-limited. Inventory the repo, rank surfaces by risk, deep-inspect as many high-risk surfaces as the turn allows, and list the rest under **Surveyed But Not Deeply Inspected** with a pointer to run another pass on them. State the surface counts in the report header. Never present a shallow sweep as complete coverage.
- Ground every finding in source code, configuration, dependency metadata, runtime behavior, docs, or explicit user context.
- Separate confirmed vulnerabilities from inferred risks. Label inferred risks with confidence.
- Avoid noisy best-practice checklists. Report issues that are actionable and relevant to the audited surface.
- Prefer small, concrete mitigations over broad rewrites.
- Do not test against production systems, use real credentials, mutate data, fuzz live services, run exploit tooling against third-party targets, or disclose secrets.
- If you encounter secrets or sensitive data, do not repeat the secret value. Refer to the path and type only.
- Note when a risk needs product/legal/privacy input rather than a code-only fix.

## Inputs

Accept any specific security scope, including:

- Feature names: `exports`, `uploads`, `billing`, `team invites`, `admin users`.
- Routes or APIs: `/api/files`, `/settings/security`, `POST /orders`.
- Workflows: `invite teammate -> accept invite -> set role -> revoke access`.
- Pull requests or branches: audit the security impact of the change.
- Themes: `review auth around exports`, `scan for tenant leaks`, `audit file upload security`.

If scope is blurry, infer the smallest useful boundary and state it. If no scope is stated, do not ask for one; proceed with a full-repo audit. Ask only when different interpretations would require materially different security reviews.

## Discovery Workflow

1. Establish repo context.
   - Check `git status --short`.
   - Identify stack, auth/session model, routing, data access, validation patterns, dependency manager, env/config style, and test conventions.
   - For PRs, compare changed files with adjacent unchanged code and relevant contracts.

2. Map trust boundaries.
   - Identify users, roles, tenants/orgs, admins, service accounts, external integrations, webhooks, background jobs, file/storage systems, databases, caches, queues, and third-party APIs.
   - Identify untrusted inputs: request params, body fields, headers, cookies, uploaded files, URLs, webhook payloads, CLI args, env vars, user-generated content, and imported data.
   - Identify sensitive assets: credentials, tokens, PII, payment data, private files, internal metadata, audit logs, billing records, admin actions, and cross-tenant data.

3. Trace security-sensitive paths.
   - Authentication: session checks, token validation, expiry, refresh, logout, callback flows.
   - Authorization: role checks, ownership checks, tenant/org boundaries, admin-only paths, object-level access.
   - Validation: server-side validation, schema drift, file type/size checks, URL validation, rate limits, replay/idempotency.
   - Data exposure: response shape, logs, error messages, exports, search results, pagination, cache keys, metadata leakage.
   - Injection: SQL/NoSQL, command, template, path traversal, SSRF, XSS, unsafe redirects, unsafe deserialization.
   - Secrets/config: committed secrets, permissive defaults, missing required env docs, overly broad tokens, client-exposed server secrets.
   - Dependencies: newly added packages, abandoned packages, risky transitive use, vulnerable versions when lockfile/tooling reveals it.
   - Operations: audit logs for sensitive actions, alertable failures, rollback/feature flag behavior, secure migration/deploy ordering.

4. Verify safely.
   - Use repo-native static checks, lint/typecheck, focused tests, dependency audit commands, or framework analyzers when available and safe.
   - Prefer source inspection when dependency install, services, credentials, browsers, or network are unavailable.
   - Record checks run and checks skipped.

## Severity Rubric

- `P0`: Active critical vulnerability, likely credential compromise, serious tenant/privacy leak, auth bypass, data destruction, payment/security control bypass, or production exploit path.
- `P1`: High-impact security issue or launch blocker; common path exposes sensitive data, permits privilege escalation, allows injection, or weakens core auth/authorization.
- `P2`: Meaningful security gap likely to matter in realistic use; weak validation, missing object checks in edge cases, excessive logging, unsafe defaults, missing rate limits, risky dependency.
- `P3`: Defense-in-depth, hardening, auditability, documentation, or test gap worth fixing but not a blocker by itself.

## Evidence Standards

- Include tight file and line references whenever possible.
- Explain attacker capability, affected asset, abuse path, and impact.
- State why existing controls do not mitigate the issue, or what you could not verify.
- For inferred risks, include `Confidence: high/medium/low`.
- Do not include exploit payloads beyond minimal safe examples needed to explain the issue.
- Do not quote secret values, tokens, private keys, or personal data.

## Report Format

Use this structure unless the user asks otherwise:

Never print secret values, tokens, keys, credentials, or sensitive personal data in the report. Refer only to the path, setting name, secret type, or data category.

```markdown
**Security Audit: <scope>**

No code changed. I reviewed <brief scope>, focusing on auth, authorization, input validation, data exposure, injection, secrets/config, dependencies, and operational security. <verification summary>. No P0s found / P0s found: <count>.

1. **P1: <finding title>.**
   Abuse path: <who can do what>.
   Impact: <asset/user/system impact>.
   Evidence: `<path>:<line>`.
   Suggested mitigation: <smallest safe fix direction>.

2. **P2: <finding title>.**
   Abuse path: <who can do what>.
   Impact: <asset/user/system impact>.
   Evidence: `<path>:<line>`.
   Confidence: <high/medium/low if inferred>.
   Suggested mitigation: <fix direction>.

**Positive Controls Observed**
- <Only include useful existing controls that reduce risk.>

**Surveyed But Not Deeply Inspected**
- <For full-repo audits only: surfaces that were inventoried but not inspected deeply this pass, and which to run next. Omit this section entirely for scoped audits.>

**Checks Run**
- `<command>`: <result>

**Not Tested**
- <runtime/auth/service/dependency audit gaps and why>

**Assumptions**
- <only include if useful>
```

If no findings exist, say that clearly and list residual risks or untested surfaces.

## Post-Audit Fix Workflow

When the user asks to fix findings:

- Fix P0/P1 findings first, then P2 findings when safe and scoped.
- Preserve public contracts unless the security issue requires a breaking change.
- Add or update regression tests for auth, authorization, validation, and data exposure fixes.
- Avoid broad hardening sweeps unrelated to the audited scope.
- Run focused verification and report fixed, partially fixed, not fixed, and not tested.

## Related Skills

- Use `feature-audit` when the ask is broad product readiness or non-security defects.
- Use `test-gap-audit` when the ask is which tests would prove a security fix holds.

## Agent Portability Notes

- Use available shell, search, git, browser, GitHub, dependency, or MCP tools as appropriate.
- If security scanners are unavailable, continue with source inspection and state the limitation.
- If the host supports inline review comments, emit them only for confirmed actionable security findings and keep ranges tight.
