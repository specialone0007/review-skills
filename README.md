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

## Safety

Most skills are read-only by default. They instruct the agent not to edit files unless you explicitly ask for fixes or implementation.

As with any third-party agent skill, review the skill contents before enabling it in a trusted environment.

## License

MIT
