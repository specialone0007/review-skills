# Deployment

> **This document owns:** the map of every deployable unit in this repository, the order they go out in, and how the whole is rolled back; each unit's own deployment guide holds its steps. *(skeleton, write me)*

*Read this if you are about to ship one unit or all of them.*

<!-- concern: deploy; fill: services, env, ci, ops, decisions -->

## Units

*A table: unit, root directory, platform, environment, its URL, which branch deploys there, public or private, its own deployment guide as a link. One row per deployable unit and environment; the data stores are DATA_MODEL's. Deploys on its own means the unit folder holds a Dockerfile or platform config; a unit deployed from a dashboard with no config in the repository (the root app, a worker service) is a row here and earns no guide or agent file of its own: its steps go here under an H3, with one line on how its values reach it and an open question on where its config lives.*

## Order

*Which units must go out before which, and why. Migrations first, consumers before producers, whatever the code requires.*

## Rollback

*How the whole is rolled back, and what state (database, queues) does not roll back with the code.*
