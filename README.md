# Review Skills

Portable `SKILL.md` workflows for AI coding agents to review, improve, and communicate code changes.

This repository contains focused review skills for agents that support the Agent Skills / `SKILL.md` format, including Codex, Claude Code, Cursor, GitHub Copilot CLI, and other compatible tools.

## Skills

| Skill | Use For |
| --- | --- |
| `pr-branch-summary` | Compare a branch against staging, production, or another base and draft PR communication. |
| `feature-audit` | Run a broad feature readiness audit for bugs, regressions, UX flow errors, and launch risks. |
| `repo-organization-audit` | Review repository structure, naming, module boundaries, dead code, duplication, and reuse opportunities. |
| `feature-brainstorm` | Brainstorm evidence-grounded product, UX, workflow, and technical improvement ideas. |
| `security-audit` | Run a focused AppSec review for auth, authorization, injection, secrets, data exposure, and abuse paths. |
| `docs-sync-audit` | Find stale or missing documentation after code, API, config, workflow, or release changes. |
| `test-gap-audit` | Find missing, weak, stale, or mis-scoped regression coverage and recommend concrete tests. |

## Choose The Right Skill

| Skill | Use This When | Do Not Use This When |
| --- | --- | --- |
| `feature-audit` | You need a launch-readiness or bug-risk review for a specific feature, route, workflow, or PR. | The primary goal is only security, test coverage, docs drift, repo structure, ideation, or PR copy. |
| `security-audit` | You need an AppSec review for auth, authorization, injection, secrets, data exposure, dependencies, or abuse paths. | You want broad product readiness or non-security bug finding. |
| `test-gap-audit` | You need to know which tests are missing, weak, stale, or insufficient for a feature, PR, bug fix, or repo. | You want the agent to find product bugs rather than evaluate regression coverage. |
| `docs-sync-audit` | You need to compare code, APIs, config, commands, workflows, or examples against documentation. | You want implementation review, UX critique, or general code quality feedback. |
| `repo-organization-audit` | You need structure, naming, dead-code, duplication, reuse, or module-boundary feedback. | You want runtime behavior, product readiness, security, or coverage findings. |
| `feature-brainstorm` | You want evidence-grounded product, UX, workflow, or technical improvement ideas. | You need defects, blockers, missing tests, or launch risks reported as findings. |
| `pr-branch-summary` | You need PR titles, descriptions, release comparisons, or team summaries from branch diffs. | You need code review findings or implementation changes. |

## Install

Install all skills with the `skills` CLI:

```bash
npx skills add specialone0007/review-skills --skill '*'
```

Install one skill:

```bash
npx skills add specialone0007/review-skills --skill feature-audit
```

Or copy a skill folder manually into your agent's skills directory, for example:

```text
.claude/skills/<skill-name>/
.agents/skills/<skill-name>/
.github/skills/<skill-name>/
.cursor/skills/<skill-name>/
~/.codex/skills/<skill-name>/
~/.cursor/skills/<skill-name>/
```

Each skill folder contains a `SKILL.md` file, and some skills may include supporting scripts or metadata.

## Recommended Workflow

Use the most specific skill for the job:

- Use `feature-audit` for broad readiness and defect risk.
- Use `security-audit` when the primary question is security.
- Use `test-gap-audit` when the primary question is coverage.
- Use `docs-sync-audit` when the primary question is documentation drift.
- Use `repo-organization-audit` when the primary question is structure or maintainability.
- Use `feature-brainstorm` when you want improvement ideas rather than findings.
- Use `pr-branch-summary` when you need PR or team communication.

## Compact Output Examples

These examples show the expected shape, not full reports.

```markdown
**Feature Audit: checkout**
No code changed. I checked the checkout flow and related API handlers. No P0s found.
1. **P1: Guest checkout can submit without server-side email validation.**
   Evidence: `src/checkout/api.ts:42`. Suggested fix direction: validate on the server and add a regression test.
```

```markdown
**Security Audit: exports**
1. **P1: Team members can request another team's export by ID.**
   Abuse path: an authenticated user guesses an export ID. Evidence: `app/api/exports.ts:88`.
```

```markdown
**Test Gap Audit: invitations**
1. **P2: Expired invite acceptance has no regression test.**
   Suggested test: API test for expired token response and unchanged membership state.
```

```markdown
**Docs Sync Audit: CLI setup**
1. **P2: README still documents `npm run dev`, but the package script is `pnpm dev`.**
   Evidence: source `package.json:8`; docs `README.md:24`.
```

```markdown
**Repo Health Audit: src/features**
1. **P2: Billing permission checks are duplicated across three modules.**
   Suggested cleanup direction: centralize the shared rule behind one helper.
```

```markdown
**Feature Brainstorm: search**
1. **Saved filters**
   Opportunity: let frequent users reuse common searches. Effort: Medium. Confidence: High.
```

```markdown
**PR Title**
feat(exports): add CSV export status tracking

**Team Summary**
This branch adds export status visibility and updates the API response shape. Reviewers should focus on status transitions and rollback behavior.
```

## Safety

Most skills are read-only by default. They instruct the agent not to edit files unless you explicitly ask for fixes or implementation.

Audit and brainstorm skills should not change files during the review phase. To authorize implementation, ask explicitly with wording like "fix these findings", "add the suggested tests", or "update the stale docs".

As with any third-party agent skill, review the skill contents before enabling it in a trusted environment.

## License

MIT
