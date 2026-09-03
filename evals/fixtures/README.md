# Eval fixtures

`mini-app/` is **intentionally defective**. Do not fix it, and do not copy anything from it.

It exists so the eval cases in `evals/*.json` have a target with known problems, and so the bundled scripts have a deterministic input for snapshot tests. If you "clean it up", the evals stop testing anything.

## Planted defects, and which skill should find each

| Defect | Where | Skill |
| --- | --- | --- |
| Export lookup has no ownership check — any caller can read any export by id | `mini-app/src/routes/exports.js` | `security-audit` |
| User deletion has no role check and no confirmation step | `mini-app/src/routes/admin.js` | `security-audit`, `feature-audit` |
| `exports.js` and `admin.js` have no tests at all | `mini-app/tests/` | `test-gap-audit` |
| `smoke.test.js` has a test case but no assertions | `mini-app/tests/smoke.test.js` | `test-gap-audit` |
| README documents `npm run dev`; the actual script is `dev:start` | `mini-app/README.md`, `mini-app/package.json` | `docs-sync-audit` |
| README documents `MAX_EXPORT_ROWS` and `API_TOKEN`; only one is wired to anything meaningful | `mini-app/README.md`, `mini-app/src/config.js` | `docs-sync-audit` |
| `formatDate` is duplicated verbatim in two places | `mini-app/src/lib/format-date.js`, `mini-app/src/utils/format-date.js` | `repo-health-audit` |
| `src/utils/` is a catch-all directory | `mini-app/src/utils/` | `repo-health-audit` |

## About the credential

`mini-app/.env.example` contains `API_TOKEN=not-a-real-token-eval-fixture-placeholder`.

That is not a credential. It is deliberately structurally invalid so it cannot be mistaken for one, and it is labelled in the file itself. It exists so `repo_inventory.py` has an `.env` file to report the *name* of — that script never reads env file contents, and the security-audit skill is instructed never to print a secret value.

## Regenerating script snapshots

`tools/validate_evals.py --update-snapshots` reruns the bundled scripts against `mini-app/` and rewrites the expected JSON. Do that only when a script's output format changed on purpose, and read the diff before committing it.
