# Review Skills

[![CI](https://github.com/specialone0007/review-skills/actions/workflows/ci.yml/badge.svg)](https://github.com/specialone0007/review-skills/actions/workflows/ci.yml)
[![skills.sh](https://skills.sh/b/specialone0007/review-skills)](https://skills.sh/specialone0007/review-skills)

Seven review skills that make any `SKILL.md`-compatible agent file the same report every time: findings ranked P0–P3, each one anchored to a `path:line` you can open.

Claude Code already ships strong first-party review — a built-in `/security-review`, an official `code-review` plugin, and a security-review GitHub Action — and this does not try to out-detect any of them. What it adds is the shape around them: one consistent, evidence-first output format across seven distinct review dimensions, five of which no first-party review tool covers at all. The same seven skills run unchanged in Codex, Cursor, and Copilot CLI, where the Claude-only tooling does not run, and each ships an `agents/openai.yaml` so it appears as a properly named action in Codex rather than an untitled prompt.

Every audit skill is read-only by default. It reports; it does not edit, until you explicitly ask for fixes.

```bash
npx skills add specialone0007/review-skills --skill '*'
```

Then just ask:

```text
audit my repo for launch risks
security audit this repo
what tests am I missing
```

Given no scope, every audit surveys the whole repository, ranks surfaces by risk, inspects the riskiest in depth, and tells you what it only skimmed. Name a feature, route, PR, or branch and it narrows to that instead.

## Example output

```markdown
**Security Audit: exports**

No code changed. I reviewed the export API and its permission checks. P0s found: 0.

1. **P1: Team members can request another team's export by ID.**
   Abuse path: an authenticated user guesses or increments an export ID.
   Impact: cross-tenant data disclosure.
   Evidence: `app/api/exports.ts:88`.
   Suggested mitigation: scope the lookup by the caller's team before returning the row.
```

A complete run is in [examples/](examples/).

## Skills

| Skill | Use it when | Not for |
| --- | --- | --- |
| `feature-audit` | Launch-readiness or bug-risk review of a feature, route, workflow, PR — or the whole repo. | Narrower asks that a specialist below covers. |
| `security-audit` | AppSec review: auth, authorization, injection, secrets, data exposure, dependencies, abuse paths. | Broad product readiness or non-security defects. |
| `test-gap-audit` | Which tests are missing, weak, stale, or insufficient. | Finding product bugs rather than evaluating coverage. |
| `docs-sync-audit` | Comparing code, APIs, config, commands, or examples against the docs. | Implementation review or code-quality feedback. |
| `repo-health-audit` | Structure, naming, dead code, duplication, reuse, module boundaries. | Runtime behavior, readiness, security, or coverage. |
| `feature-brainstorm` | Evidence-grounded product, UX, workflow, or technical improvement ideas. | Defects, blockers, or launch risks reported as findings. |
| `pr-branch-summary` | PR titles, descriptions, release comparisons, team summaries from branch diffs. | Review findings or implementation changes. |

Each skill names its nearest neighbours in its own `## Related Skills` section, so the agent can route itself if you pick the wrong one.

## Compared to first-party tooling

| | First-party (Claude Code) | Review Skills |
| --- | --- | --- |
| Bug and security detection | `/security-review`, the official `code-review` plugin, security-review Action. Use them. | Not a replacement. Same class of finding. |
| Report shape | Varies by tool and run | One contract: P0–P3 severity plus `path:line` evidence, no finding without both |
| Dimensions covered | Security, correctness, performance, maintainability | Those, plus test-coverage gaps, documentation drift, repo structure and duplication, improvement ideation, and PR communication |
| Runs in Codex, Cursor, Copilot CLI | No | Yes, unchanged, with Codex interface metadata |
| Cost | Built in on paid plans | MIT, no server, no account |

If you only use Claude Code and only want security and correctness findings, use the first-party tools. This exists for the other five dimensions, and for teams whose agents are not all Claude Code.

## Install

With the `skills` CLI:

```bash
npx skills add specialone0007/review-skills --skill '*'          # all seven
npx skills add specialone0007/review-skills --skill feature-audit # just one
```

As a Claude Code plugin:

```text
/plugin marketplace add specialone0007/review-skills
/plugin install review-skills@review-skills
```

Or copy a skill folder into your agent's skills directory:

```text
.claude/skills/<skill-name>/
.agents/skills/<skill-name>/
.github/skills/<skill-name>/
.cursor/skills/<skill-name>/
~/.codex/skills/<skill-name>/
~/.cursor/skills/<skill-name>/
```

Each folder holds a `SKILL.md`, an `agents/openai.yaml` with Codex interface metadata, and — for some skills — a bundled read-only Python script that uses only the standard library. Scripts are accelerators; every skill still works without them.

## Safety

All seven skills are read-only on your files by default. They instruct the agent not to edit, stage, or commit anything unless you explicitly ask for fixes or implementation.

One precise exception: `pr-branch-summary` may run `git fetch origin <base>` when the base branch you asked to compare against is missing locally. That updates a single remote-tracking ref and never touches your working tree, index, or local branches. It is skipped when the ref already exists.

To authorize implementation, ask explicitly — "fix these findings", "add the suggested tests", "update the stale docs".

As with any third-party agent skill, read the skill contents before enabling it in a trusted environment. Everything here is plain Markdown plus one small Python script, so it is quick to audit.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run `python tools/validate_skills.py` before opening a PR; CI runs the same checks.

## License

MIT — see [LICENSE](LICENSE).
