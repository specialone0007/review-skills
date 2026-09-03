# Contributing

Thanks for helping out. This repo ships prompt artifacts that other people's agents execute, so the bar is "would a stranger's agent do the right thing with this?" rather than "does it read nicely".

## Before you open a PR

Run the validator. CI runs the same thing, so this is the fastest way to avoid a red build:

```bash
python tools/validate_skills.py
```

It needs no dependencies. Every diagnostic is `path:line: message`.

## What the validator enforces

| Rule | Why |
| --- | --- |
| Frontmatter contains exactly `name` and `description` | Those are the only two fields in the Agent Skills spec. Extra keys such as `version:` risk host validation failures. |
| `name` matches the folder, lowercase and hyphens, ≤64 chars | Spec requirement, and the install path is the folder name. |
| `description` ≤1024 chars | Spec requirement. |
| All descriptions together ≤5000 chars | Descriptions sit in the system prompt on **every** request, whether a skill fires or not. This is the one budget that is always being paid. |
| Body ≤500 lines (warning at 400) | Spec guidance. Past that, split detail into a `references/` file loaded on demand. |
| `agents/openai.yaml` has all three `interface.*` keys, and `display_name` is the title-case of the folder | Keeps the Codex-facing name, the folder, and the report header from drifting apart. They have drifted before. |
| The `**<Name>: <scope>**` report header matches `display_name` | Same reason. A skill whose report calls itself something else is confusing to users and to search. |
| `default_prompt` references `$<skill-name>` | It is how Codex invokes the skill. |
| Referenced `scripts/`, `references/`, `assets/` paths exist | A SKILL.md pointing at a missing file sends the agent down a dead end. |
| `## Agent Portability Notes` present, plus `## Report Format` or `## Required Output` | Portability and a defined output contract are the point of this collection. |
| `## Related Skills` entries name real skills | Stops dangling pointers after a rename. |
| README skill table matches the `skills/` directories | The README is how people choose a skill; it must not drift. |
| No machine-specific absolute paths; relative links resolve | Skills run on other people's machines. |

## Conventions the validator cannot check

Please hold these by hand.

- **Read-only by default.** Audit and brainstorm skills must not edit, stage, or commit anything during the review phase. If a skill needs to run something that changes state, say exactly what changes and use the narrowest possible command. `pr-branch-summary` is the one skill that touches git state, and it is limited to fetching a single remote-tracking ref.
- **Evidence or it does not ship.** Every finding needs a severity and a `path:line`. That contract is the product.
- **Repository-agnostic.** Do not assume a framework, language, test runner, package manager, or file layout. Discover conventions from the repo.
- **Be concise.** Assume the model is capable. Do not explain what a PR is, or what pagination means. If a paragraph does not change what the agent does, cut it.
- **Scripts are accelerators, never requirements.** Every skill that bundles a script must keep working when the script cannot run. Always leave the manual fallback commands in place.

## Adding a new skill

1. `skills/<name>/SKILL.md` with the two frontmatter fields.
2. `skills/<name>/agents/openai.yaml` with `display_name`, `short_description`, `default_prompt`.
3. Sections: `## Core Rules`, `## Inputs`, a discovery or workflow section, an output contract, `## Related Skills`, `## Agent Portability Notes`.
4. Add a row to the README skill table.
5. Point at most three nearest-confusion neighbours from `## Related Skills`. Do not cross-reference all of them; that bloats every request.
6. Run the validator.

Before proposing a new skill, check whether it overlaps an existing one. Seven overlapping review skills already make routing hard; an eighth needs to earn its place by covering something none of the others do.

## Bundled scripts

Scripts must:

- use the Python 3 standard library only, and install nothing;
- be self-contained inside their own skill, since people install skills individually;
- be read-only on the target repo by default, following the `--allow-repo-output` pattern in `skills/pr-branch-summary/scripts/collect_pr_context.py`;
- support `--format text|json` and cap their output, printing a truncation notice when they do;
- call `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` before printing, or stay strictly ASCII. A single non-ASCII character crashes a default Windows console;
- never use `shell=True`, and resolve executables with `shutil.which`.
