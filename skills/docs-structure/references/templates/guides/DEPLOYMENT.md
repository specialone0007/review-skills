# Deployment

> **This document owns:** how this is deployed - every deployable unit, its environment, the steps, and how to roll back. *(skeleton, write me)*

*Read this if you are about to ship it.*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Units

*A table: unit, root directory, platform, environment (production, staging), its URL, public or private, which branch deploys there. One row per deployable unit and environment; the data stores are DATA_MODEL's, the health route OPERATIONS's, the build and start commands AGENTS.md's - link, never repeat. This is the one home of the environments and their URLs; API § Calling it links here. When the repository holds no deploy config, one sentence says so with the scan behind it, and an open question asks where deployment is configured. A library or CLI says in one sentence that it is published, not deployed, links RELEASING, and the doc ends there.*

## How values reach a unit

*How values reach the unit in each environment - the platform's settings, a vault, a mounted file. The names and the example file's path are CONFIGURATION's: link its section for the unit, never a table here.*

## Deploy steps

*Numbered, from a clean checkout to a live URL, each command step a link to AGENTS.md § Commands. Say where the migration step sits and where the domain is set.*

## Rollback

*How to get back to the previous deployed version, and what state (database, queues) does not roll back with the code. In a unit's own guide: this unit's rollback; rolling the whole back is the root map's. RELEASING says only whether a published version can be pulled.*

## Known traps

*Dated bullets. Each one cost somebody an afternoon.*
