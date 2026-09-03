---
name: feature-brainstorm
description: Brainstorm evidence-grounded product, UX, workflow, and technical improvement ideas for a clearly named feature, route, workflow, product surface, or PR. Use when the user asks what could be added, improved, simplified, expanded, polished, automated, differentiated, or made more valuable. This is not a bug audit; use feature-audit for defects, regressions, launch blockers, missing tests, or production-readiness risks.
license: MIT
---

# Feature Brainstorm

Brainstorm useful improvements for one feature or product surface. Stay grounded in the repository, product flow, UI, docs, or PR context, but use a generative posture: look for better outcomes, not defects.

## Core Rules

- Stay read-only unless the user explicitly asks to implement ideas.
- Do not present bugs, regressions, missing tests, or launch blockers as brainstorm items. If you find those, briefly label them as audit candidates and keep the main output focused on opportunities.
- Prefer evidence-grounded ideas over generic product advice. Cite files, routes, components, docs, issue text, screenshots, or observed workflow behavior when available.
- Optimize for actionable idea quality, not idea count. A short list with clear tradeoffs is better than a long wishlist.
- Separate quick wins from bigger bets.
- Include effort and confidence for each meaningful idea.
- Avoid roadmap fantasy. When repository, product, or workflow evidence is thin, either omit the idea or label it as speculative with low confidence and the evidence gap.
- Consider user value, business value, operational value, developer velocity, support load, accessibility, onboarding, retention, and differentiation.
- Avoid proposing large rewrites unless the feature already shows clear structural limits and the payoff is concrete.

## Inputs

Accept any specific surface, including:

- Feature names: `uploads`, `billing`, `dashboard compose`, `notifications`.
- Routes or URLs: `/settings/team`, `/hub/feed`, `http://localhost:3000/admin/users`.
- Workflows: `invite teammate -> accept invite -> set role -> revoke access`.
- Pull requests or branches: brainstorm improvements connected to the changed surface.
- Product prompts: `what should we add next`, `how can this be better`, `brainstorm improvements for search`, `what could make onboarding stronger`.

If scope is blurry, infer a practical boundary and state it. If no surface is named, do not ask for one and do not brainstorm the whole repo: inventory it, pick the one to three highest-leverage surfaces, say which you picked and why, then brainstorm those. A focused set of ideas beats a repo-wide dump. Ask only when multiple interpretations would produce materially different brainstorms.

## Discovery Workflow

1. Establish context.
   - Read top-level project files only as needed to understand stack and conventions.
   - Check `git status --short` before verification so user changes are visible.
   - Locate the feature's routes, pages, components, API handlers, services, schemas, tests, docs, and adjacent flows.

2. Understand current behavior.
   - Trace the main user journey and obvious alternate states.
   - Note entry points, completion points, user decisions, error/recovery moments, and repeated manual work.
   - For PRs, inspect changed files and nearby unchanged code to understand what the change enables.

3. Generate opportunity areas.
   - Product value: new capabilities, better defaults, richer comparisons, clearer decisions, integrations, collaboration, personalization, automation.
   - UX flow: fewer steps, clearer next actions, stronger empty states, better progress, clearer success/recovery, mobile ergonomics, accessibility.
   - Workflow efficiency: bulk actions, saved views, templates, shortcuts, better search/filter/sort, history, import/export, notifications.
   - Trust and confidence: previews, confirmations, audit trails, explanations, status visibility, reversible actions.
   - Technical leverage: reusable components, API affordances, instrumentation hooks, extensibility points, feature flags, lower support/debug cost.

4. Prioritize.
   - Rank by likely user impact, implementation effort, confidence, and fit with the existing product shape.
   - Mark speculative ideas as such, keep them low-confidence, and exclude them if they cannot be tied to any repo, product, workflow, or user evidence.
   - Include at least one "not pursuing" item when there are tempting ideas that do not fit.

## Idea Quality Bar

Each strong idea should answer:

- What changes for the user or team?
- Why does it matter?
- What evidence suggests it fits this feature?
- What is the likely effort?
- What would be the first implementation step?
- What risk, tradeoff, or open question should the team consider?

Do not recommend:

- Generic "add AI", "add analytics", "improve performance", or "make it nicer" ideas without feature-specific detail.
- Low-confidence roadmap bets presented as recommendations when the available evidence only supports exploration.
- Cosmetic-only polish unless the user asked for polish or the surface is visibly UI-focused.
- New settings, toggles, or configuration without a clear user decision they support.
- Abstractions that only make the code look cleaner without a product or workflow payoff.

## Report Format

Use this structure unless the user asks otherwise:

```markdown
**Feature Brainstorm: <feature/scope>**

No code changed. I reviewed <brief scope> to identify improvement opportunities, not bugs.

## Highest-Leverage Ideas

1. **<idea title>**
   - Opportunity: <what could be added, improved, simplified, or made more valuable>
   - Why it matters: <user/business/team impact>
   - Evidence: `<path>:<line>` or <observed route/workflow/docs evidence>
   - First step: <smallest concrete next action>
   - Effort: Small / Medium / Large
   - Confidence: High / Medium / Low

## Quick Wins

- **<idea>**: <why it is cheap and useful>

## Bigger Bets

- **<idea>**: <larger roadmap option and why it may be worth exploring>

## Not Pursuing

- **<tempting idea>**: <why it is not recommended now>

## Audit Candidates

- <Only include if source inspection revealed possible bugs, readiness risks, or missing tests that should be handled with feature-audit. Keep this short.>

## Assumptions

- <only include if useful>
```

If the user asks for a compact brainstorm, return the top 5 ideas with effort and confidence only.

## Post-Brainstorm Implementation

If the user asks to implement an idea after the brainstorm:

- Confirm which idea or group of ideas is being implemented when scope is ambiguous.
- Keep the implementation focused on the chosen idea.
- Preserve existing product behavior unless the idea explicitly changes it.
- Update tests, docs, fixtures, stories, or analytics only when they are part of the chosen improvement.
- Run focused verification and report what changed, what was checked, and what remains open.

## Related Skills

- Use `feature-audit` when the ask is defects, blockers, launch risks, or missing tests rather than ideas.

## Agent Portability Notes

- Use available shell, search, git, browser, GitHub, or MCP tools as appropriate.
- If browser or runtime inspection is unavailable, continue with source inspection and list that limitation.
- In hosts that support inline review comments, do not emit them for brainstorm ideas; reserve inline comments for confirmed actionable findings during audits or reviews.
