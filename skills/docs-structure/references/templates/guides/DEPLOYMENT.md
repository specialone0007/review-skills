# Deployment

> **This document owns:** how this is deployed - every deployable unit, its environment, the steps, and how to roll back. *(skeleton, write me)*

*Read this if you are about to ship it.*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Units

*A table: unit, root directory, platform, public or private, health check. One row per deployable unit, including data stores; the build and start commands are AGENTS.md's, link them. When the repository holds no deploy config, one sentence says so with the scan behind it, and an open question asks where deployment is configured.*

## Environment per unit

*Where each unit's example file lives and how values reach the unit in each environment - the platform's settings, a vault, a mounted file. The names are CONFIGURATION's: link its section for the unit, never a table here.*

## Deploy steps

*Numbered, from a clean checkout to a live URL. Include the migration step and where the domain is set.*

## Rollback

*How to get back to the previous version, and what state (database, queues) does not roll back with the code.*

## Known traps

*Dated bullets. Each one cost somebody an afternoon.*
