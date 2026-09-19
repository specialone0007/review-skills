# Deployment

> **This document owns:** the map of every deployable unit in this repository, the order they go out in, and how the whole is rolled back; each unit's own deployment guide holds its steps. *(skeleton, write me)*

*Read this if you are about to ship one unit or all of them.*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Units

*A table: unit, root directory, public or private, its own deployment guide as a link. One row per deployable unit; the data stores are DATA_MODEL's.*

## Order

*Which units must go out before which, and why. Migrations first, consumers before producers, whatever the code requires.*

## Rollback

*How the whole is rolled back, and what state (database, queues) does not roll back with the code.*
