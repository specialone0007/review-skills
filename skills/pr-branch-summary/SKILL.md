---
name: pr-branch-summary
description: Compare the current git branch against staging, production, or another release/base branch and draft PR communication. Use when the agent is asked to prepare a pull request title/message, PR description, release-target comparison, branch diff summary, team/Slack summary, or explanation of what a PR contains based on all changes since staging or production.
---

# PR Branch Summary

## Overview

Create PR-ready communication from real git evidence, not from memory. Compare the current branch against the requested base (`staging`, `production`, or an explicit ref), inspect the changed code, then produce a clear PR title, PR description, and concrete team summary in chat.

## Workflow

1. Identify the comparison base.
   - If the user names `staging`, `production`, or a specific ref, use that.
   - If the target is ambiguous, try to resolve a base before asking: first use the upstream PR/base branch if discoverable from git or hosting context, then `origin/staging` or local `staging`, then `origin/main` or local `main`.
   - If no base is resolvable, ask one concise question. When proceeding without confirmation, state the resolved base and why it was selected.
   - Prefer remote refs such as `origin/staging`, `origin/production`, or `origin/main` when available; otherwise use the local ref.

2. Gather git evidence.
   - Run `git status --short --branch` first and note uncommitted changes separately.
   - Fetch remote refs with `git fetch --all --prune` unless the user asked not to fetch or the environment cannot reach the remote.
   - Compare from the merge base: use `git merge-base HEAD <base-ref>`, then diff `<merge-base>..HEAD`. This matches what a PR introduces relative to the base branch.
   - Use `scripts/collect_pr_context.py` when available.
   - Do not create Markdown reports inside the target repository. Prefer stdout and summarize the result directly in chat. If a temporary report is necessary because the output is large, write it outside the repository in the current scratch/workspace directory and delete it when it is no longer needed.

```bash
python /path/to/pr-branch-summary/scripts/collect_pr_context.py --base staging --fetch
python /path/to/pr-branch-summary/scripts/collect_pr_context.py --base production --fetch
```

3. Inspect the actual changes.
   - Read the collected context from stdout, changed file list, commits, and diff stats.
   - Open the important changed files or focused diffs when the report is not enough.
   - Check nearby tests, migrations, API contract files, configuration, and UI copy when relevant.
   - Do not describe behavior that is not present in the diff. Label uncertain inferences as assumptions.
   - Treat uncommitted working tree changes as separate from the PR unless the user explicitly wants them included.

4. Draft the communication.
   - Use the repository's PR style if it has one. Look for pull request templates, recent PRs, or existing contribution docs when available.
   - If no convention is visible, use a Conventional Commits-style PR title: `<type>(<scope>): <imperative summary>`.
   - Keep the title specific and outcome-oriented.
   - Mention the comparison target in the description when it matters, especially for staging/production deltas.

## Required Output

Return these sections in the chat unless the user asks for a different shape. Do not create a PR description Markdown file in the repository unless the user explicitly requests a file artifact. If using `collect_pr_context.py` for an explicitly requested repo-local artifact, pass `--allow-repo-output` with `--output`.

```markdown
**PR Title**
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

**Team Summary**
<2-5 sentence update suitable for Slack/Teams. Explain what the PR changes, why it matters, expected impact, and anything reviewers or release owners should watch. Avoid internal diff jargon unless the team needs it.>
```

## Quality Bar

- Ground every claim in a commit, file diff, test, or explicit user context.
- Group changes by product/system intent instead of listing files mechanically.
- Call out database migrations, feature flags, env vars, permissions, background jobs, billing/payment paths, authentication, observability, and deployment risks when present.
- Include verification honestly. If tests were not run, say so.
- Make the team summary concrete enough that someone who never opens the PR understands the change and review focus.
- Keep summaries concise, but do not omit risky or release-relevant details.

## Manual Git Fallback

If the script is unavailable, collect the same evidence manually:

```bash
git status --short --branch
git fetch --all --prune
git rev-parse --abbrev-ref HEAD
git rev-parse --verify origin/staging
git merge-base HEAD origin/staging
git log --date=short --pretty=format:'%h %ad %s' <merge-base>..HEAD
git diff --stat <merge-base>..HEAD
git diff --name-status <merge-base>..HEAD
git diff --find-renames <merge-base>..HEAD
```
