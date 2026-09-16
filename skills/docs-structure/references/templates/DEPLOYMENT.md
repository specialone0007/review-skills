# Deployment

> **This document owns:** how the system is deployed — every service, its environment, the steps, and how to roll back. *(skeleton, write me)*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Services

*A table: service, root directory, build and start command, public or private, health check. One row per deployable unit, including data stores.*

## Environment per service

*Which variables each service reads, where the example file lives, which ones are secrets. Names only, never values.*

## Deploy steps

*Numbered, from a clean checkout to a live URL. Include the migration step and where the domain is set.*

## Rollback

*How to get back to the previous version, and what state (database, queues) does not roll back with the code.*

## Known traps

*Dated bullets. Each one cost somebody an afternoon.*
