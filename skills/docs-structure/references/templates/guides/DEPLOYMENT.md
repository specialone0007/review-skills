# Deployment

> **This document owns:** how this is deployed - every deployable unit, its environment, the steps, and how to roll back. *(skeleton, write me)*

*Read this if you are about to ship it.*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Units

*A table: unit, root directory, build and start command, public or private, health check. One row per deployable unit, including data stores.*

## Environment per unit

*Which variables each unit reads and where its example file lives. Names only, never values; the full reference is CONFIGURATION's.*

## Deploy steps

*Numbered, from a clean checkout to a live URL. Include the migration step and where the domain is set.*

## Rollback

*How to get back to the previous version, and what state (database, queues) does not roll back with the code.*

## Known traps

*Dated bullets. Each one cost somebody an afternoon.*
