# Architecture

> **This document owns:** the parts of this collection, how a skill is put together, and what checks each part. *(draft, review me)*

<!-- concern: architecture; fill: packages, services, env, decisions, routes, schema -->

Drafted from repo evidence by the docs-structure skill on 2026-09-16; every sentence names the file it came from. There is no application here: this repository is eight skills, three maintainer tools and the cases that hold them to their word.

## In one diagram

```
skills/<name>/SKILL.md          the instructions an agent loads
      ├─ references/*.md        detail the agent reads only when it needs it
      └─ scripts/*.py           read-only helpers the agent runs

tools/validate_skills.py   ─┐
tools/validate_evals.py    ─┼─▶  .github/workflows/ci.yml  (4 jobs)
plugin validate (upstream) ─┘

evals/<skill>.json         trigger / anti-trigger / behavior cases
evals/fixtures/            small defective repos the scripts run against
evals/snapshots/*.json     the output those runs must keep producing
```

Sources: [skills] [tools] [evals] [.github/workflows/ci.yml].

*(draft, review me)*

## Parts

| part | what it holds | file or folder |
| --- | --- | --- |
| skills | seven folders, each a `SKILL.md` with optional `references/` and `scripts/` | [skills] |
| bundled scripts | eight Python files across five skills; docs-structure carries four, four skills carry one, two carry none (scan: `ls skills/*/scripts/*.py`) | [skills/docs-structure/scripts] |
| skill validator | frontmatter, metadata and this repo's own conventions, printed as `path:line` | [tools/validate_skills.py] |
| eval validator | the eval cases, plus a snapshot run of every bundled script against a fixture | [tools/validate_evals.py] |
| social preview | generates the repository's preview image | [tools/make_social_preview.py] |
| plugin manifests | what a marketplace installs | [.claude-plugin/plugin.json] [.claude-plugin/marketplace.json] |
| examples | one verbatim run per skill, kept as evidence of what the output looks like | [examples/README.md] |

*(draft, review me)*

## How a skill is checked

Thirty-eight eval cases across seven files: 19 triggers, 12 anti-triggers and 7 behavior cases (scan: the `kind` field of every case under evals/*.json) [evals]. A trigger names a prompt that selects the skill, an anti-trigger a prompt that selects a different one, and a behavior case asserts something about a run [evals/docs-structure.json].

Bundled scripts are held by snapshot. `SNAPSHOT_SCRIPTS` maps each script to a fixture repository, runs it, and compares the JSON with the file under `evals/snapshots/` [tools/validate_evals.py]. The fixtures are small repositories with planted defects, including an env file whose value is a canary the runner asserts never appears in any output [evals/fixtures/README.md].

Continuous integration runs four jobs: `validate`, `first-party`, `evals` and `scripts` [.github/workflows/ci.yml]. The first runs this repository's own validator, the second runs the upstream plugin validator in strict mode over the marketplace and the skills, the third runs the eval and snapshot checks, and the fourth checks that every bundled script parses and that one of them leaves the repository untouched [.github/workflows/ci.yml].

*(draft, review me)*

## Conventions a skill follows

Bundled scripts use the Python standard library only and never write, so they run anywhere without setup and cannot damage the repository they are pointed at [tools/validate_skills.py]. Each takes `--format text|json` and caps its own output [skills/docs-structure/scripts/docs_structure.py]. The validators print every diagnostic as `path:line: message`, so an editor can jump to it [tools/validate_skills.py].

*(draft, review me)*

## Key decisions, and why

- The collection is installed as a plugin from a marketplace manifest rather than copied file by file [.claude-plugin/marketplace.json].
- Skill descriptions share a budget the validator enforces, so a new skill costs the others room [tools/validate_skills.py].
- Script behaviour is pinned by snapshot rather than by unit test, so a change to a heuristic shows up as a diff a maintainer reads [tools/validate_evals.py].

open question: why seven skills rather than fewer with more modes - the split is not recorded anywhere in the repository.

*(draft, review me)*

## Open questions

- Whether a ninth skill carries its own fixture or reuses an existing one [evals/fixtures/README.md].
- What happens to a snapshot when a heuristic changes deliberately; the runner regenerates on request, and nothing records which change a snapshot diff belonged to [tools/validate_evals.py].

*(draft, review me)*
