---
name: pr-branch-summary
description: Compare the current git branch against staging, production, or another release/base branch and draft PR communication. Use when the agent is asked to prepare a pull request title/message, PR description, release-target comparison, branch diff summary, team/Slack/Telegram summary, or explanation of what a PR contains based on all changes since staging or production.
license: MIT
---

# PR Branch Summary

## Overview

Create PR-ready communication from real git evidence, not from memory. Compare the current branch against the requested base (`staging`, `production`, or an explicit ref), inspect the changed code directly, then produce a clear PR title, PR description, and concrete team/Telegram summary in chat.

## Core Rules

- Do not change the user's work. Never edit, reformat, stage, commit, amend, push, create branches, create pull requests, or write report files into the target repository.
- Resolve the base from local and existing remote-tracking refs first. Fetch only when the base ref is missing, or when the user asks for fresh remote state.
- When a fetch is required, use the narrowest form: `git fetch origin <base>`. This updates one remote-tracking ref. It never touches the working tree, the index, or local branches. Say in the report that you fetched and which ref you updated.
- Do not use `git fetch --all --prune` by default. `--all` touches every configured remote and `--prune` deletes stale remote-tracking refs, neither of which this skill needs.
- Report output goes to chat. If a temporary file is unavoidable because the output is large, write it outside the repository and delete it when done.
- Be evidence-first. Describe what the diff actually contains, not what the commit messages claim.

## Workflow

1. Identify the comparison base.
   - If the user names `staging`, `production`, or a specific ref, use that.
   - If the target is ambiguous, try to resolve a base before asking: first use the upstream PR/base branch if discoverable from git or hosting context, then `origin/staging` or local `staging`, then `origin/main` or local `main`.
   - If no base is resolvable, ask one concise question. When proceeding without confirmation, state the resolved base and why it was selected.
   - Prefer remote refs such as `origin/staging`, `origin/production`, or `origin/main` when available; otherwise use the local ref.

2. Gather git evidence.
   - Run `git status --short --branch` first and note uncommitted changes separately.
   - If the base ref is missing locally or the user asked for fresh remote state, fetch just that ref with `git fetch origin <base>`. Skip the fetch when the ref already exists locally and the user did not ask for it, or when the environment cannot reach the remote.
   - Compare from the merge base: use `git merge-base HEAD <base-ref>`, then diff `<merge-base>..HEAD`. This matches what a PR introduces relative to the base branch.
   - Use the bundled `scripts/collect_pr_context.py` when available. The path is relative to this skill's own directory, which differs by host (`.claude/skills/pr-branch-summary/`, `~/.codex/skills/pr-branch-summary/`, and so on). Use `python` if `python3` is not on PATH.
   - Do not create Markdown reports inside the target repository. Prefer stdout and summarize the result directly in chat. If a temporary report is necessary because the output is large, write it outside the repository in the current scratch/workspace directory and delete it when it is no longer needed.

```bash
python <skill-dir>/scripts/collect_pr_context.py --base staging
python <skill-dir>/scripts/collect_pr_context.py --base production --fetch
```

Add `--fetch` only when the base ref is missing or the user asked for fresh remote state; it fetches that one ref from `origin`.

3. Inspect the actual changes.
   - Read the collected context from stdout, changed file list, commits, and diff stats.
   - Open the important changed files or focused diffs when the report is not enough.
   - Do not rely on commit headers alone. Inspect enough code to understand each major changed area and avoid missing quiet implementation details.
   - Cluster changed files by product/system intent before writing. Use repo-appropriate groups such as UI/UX, API contracts, backend services, background jobs, data access, permissions/auth, billing/subscription, storage/integrations, performance, responsive layout, tests, config, and deployment.
   - For large PRs, inspect at least one representative diff from every high-impact cluster and any file with backend routes, workers, migrations, payments, auth, storage, background jobs, public API contracts, or deployment configuration.
   - Check nearby tests, migrations, API contract files, configuration, and UI copy when relevant.
   - Do not describe behavior that is not present in the diff. Label uncertain inferences as assumptions.
   - Treat uncommitted working tree changes as separate from the PR unless the user explicitly wants them included.

4. Draft the communication.
   - Use the repository's PR style if it has one. Look for pull request templates, recent PRs, or existing contribution docs when available.
   - If no convention is visible, use a Conventional Commits-style PR title: `<type>(<scope>): <imperative summary>`.
   - For PR titles and commit headers, prefer a clear Conventional Commit scope when one exists, such as `docs(pr-summary): improve PR summary guidance`.
   - Keep the title specific and outcome-oriented.
   - Mention the comparison target in the description when it matters, especially for staging/production deltas.
   - When the user asks for a Telegram/team message, write it in first person if the user is reporting their own work. Prefer "I added/addressed/improved" over passive phrasing.
   - Telegram/team messages should be organic and readable, not a giant bullet dump. Use compact paragraphs that cover all major change clusters without exposing unnecessary implementation trivia.

## Required Output

Return these sections in the chat unless the user asks for a different shape. Do not create a PR description Markdown file in the repository unless the user explicitly requests a file artifact. If using `collect_pr_context.py` for an explicitly requested repo-local artifact, pass `--allow-repo-output` with `--output`.

```markdown
**PR Title**
<type>(<scope>): <short imperative summary>

**Squash Commit Header**
<type>(<scope>): <short imperative summary>

**PR Description**
## Summary
- <what changed, grouped by user-visible or system behavior>

## Why
- <problem, context, or release reason>

## Changes
- <concrete implementation bullets>

## Testing
- <commands run, checks performed, or "Not run" with reason>

## Risk / Rollback
- <main risks, migration/config concerns, and rollback notes>

**Telegram Message**
<A concise, organic update suitable for Telegram or a team chat. Use first person when the user wants to send it as their own update. Cover every major change cluster from the code inspection, but compress details into readable paragraphs. Avoid file names, commit hashes, and low-level bug trivia unless release owners need it.>
```

If the user only asks for a Telegram/team message, return just `**Telegram Message**` unless they also asked for PR title, PR description, or commit header.

## Quality Bar

- Ground every claim in a commit, file diff, test, or explicit user context.
- Group changes by product/system intent instead of listing files mechanically.
- Include small backend/runtime changes when they materially affect behavior, performance, reliability, deployment, or data shape. Generic examples include persisted computed fields, chunked/streamed transfer, retry behavior, cache behavior, lighter hydration endpoints, access predicates, queue/background-job persistence, and integration fallback handling.
- Call out database migrations, feature flags, env vars, permissions, background jobs, billing/payment paths, authentication, observability, and deployment risks when present.
- Include verification honestly. If tests were not run, say so.
- Make the Telegram/team summary concrete enough that someone who never opens the PR understands what was added, what was fixed, and what changed operationally.
- Keep summaries concise, but do not omit risky, release-relevant, or behavior-changing details.
- Avoid over-explaining transient local/deploy fixes in Telegram messages unless the user specifically asks for build/deploy details.
- Verify every commit you cite as evidence. Before naming a commit as a revert, a churn hotspot, or proof that a subsystem is risky, run `git show --stat <hash>` and confirm its diff actually touches that subsystem. Never assemble a revert or churn list from `git log --grep` alone; the message and the diff disagree often enough to matter.
- State real counts. If you write "four reverts", list exactly four. A hedge like "at least four" followed by six hashes tells the reader the list was grepped rather than checked.

## Manual Git Fallback

If the script is unavailable, collect the same evidence manually:

```bash
git status --short --branch
git fetch origin staging   # only if the base ref is missing or stale
git rev-parse --abbrev-ref HEAD
git rev-parse --verify origin/staging
git merge-base HEAD origin/staging
git log --date=short --pretty=format:'%h %ad %s' <merge-base>..HEAD
git diff --stat <merge-base>..HEAD
git diff --name-status <merge-base>..HEAD
git diff --find-renames <merge-base>..HEAD
```

## Related Skills

- Use `feature-audit` when the ask is to review the branch for defects before writing the PR.
- Use `test-gap-audit` when the ask is which tests the branch still needs.

## Agent Portability Notes

- Use available shell, search, git, GitHub, or MCP tools as appropriate. The evidence you gather matters more than the tool names used to gather it.
- If the remote is unreachable, compare against the local base ref, and label the base as possibly stale in the report.
- In hosts that support inline review comments, do not emit them from this skill; it drafts communication rather than review findings. Use `feature-audit` or `security-audit` when inline findings are wanted.
