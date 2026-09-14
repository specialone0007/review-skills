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
| A `postinstall` hook runs code automatically on install | `mini-app/package.json` | `security-audit` |
| `left-pad` is pinned to `*`, accepting any published version | `mini-app/package.json` | `security-audit` |
| `local-helper` resolves via `file:`, outside any registry and outside advisory coverage | `mini-app/package.json` | `security-audit` |
| No lockfile despite declared dependencies, so installs are not reproducible | `mini-app/` | `security-audit` |
| `requirements.txt` pins every dependency with `==` but has no lockfile, so this must be reported as **low**, not medium | `mini-app/requirements.txt` | `security-audit` |
| `docs/` has no central index; the manifest names `docs/INDEX.md`, which does not exist. Must be reported as **one** finding, anchored to the manifest line | `mini-app/docs/structure.json` | `docs-structure` |
| `setup.md` links to `#configuration`; the heading is `## Config` | `mini-app/docs/setup.md` | `docs-structure` (anchors are this skill's alone; both skills flag a dead relative link) |
| `setup.md` cites `src/config.js:12`, a line number into source | `mini-app/docs/setup.md` | `docs-structure` |
| `setup.md` and `history.md` have no owner line | `mini-app/docs/` | `docs-structure` (warning) |
| `history.md` has two H1 headings, so a split must refuse it; `guide.md` is over the fixture's `splitAt` and splits cleanly into three parts | `mini-app/docs/history.md`, `mini-app/docs/guide.md` | `docs-structure` |
| `42.5%` appears in four docs | `mini-app/docs/*.md` | `docs-structure` (warning) |
| `crlf-sample.md` has Windows line endings; its `## Notes` anchor must still resolve from `limits.md` | `mini-app/docs/crlf-sample.md` | `docs-structure` |

## About the docs folder

`docs/structure.json` sets `splitAt: 20` so the oversize rule fires on 23-line files. Without
it the two-H1 refusal and the three-part split would need a 500-line fixture, and the
snapshot runner passes no `--manifest`, so the script reads this default path. It is the
only manifest in the fixture and the only thing there that is not a planted defect.

`crlf-sample.md` is pinned `-text` in `.gitattributes` on purpose: the fixture is otherwise
normalised to LF, which would erase the line-ending defect the file exists to plant.

## About the credential

`mini-app/.env.example` contains `API_TOKEN=not-a-real-token-eval-fixture-placeholder`.

That is not a credential. It is deliberately structurally invalid so it cannot be mistaken for one, and it is labelled in the file itself. It exists so `repo_inventory.py` has an `.env` file to report the *name* of — that script never reads env file contents, and the security-audit skill is instructed never to print a secret value.

## Regenerating script snapshots

`docs_drift.py` is expected to find three things here: the `npm run dev` command that does not exist, and both documented environment variables, which are read only inside `src/config.js` — a module nothing imports, so the documented settings cannot take effect. That last one is why `src/config.js` must stay unreferenced.

`requirements.txt` exists to hold the severity fix from the real-repo trial: a fully `==`-pinned manifest with no lockfile is a `low`, because calling it "not reproducible" is wrong and costs the report credibility. `package.json` covers the other branch, since a `^4.17.21` range is not a pin. Do not add a lockfile beside either one, and do not loosen the `==` pins.

The `postinstall` hook and the odd dependency specs are inert: nothing here is ever installed, and the hook only prints a line. They exist so `dependency_audit.py` has real supply-chain shapes to detect.

`tools/validate_evals.py --update-snapshots` reruns the bundled scripts against `mini-app/` and rewrites the expected JSON. Do that only when a script's output format changed on purpose, and read the diff before committing it.
