# Data model

> **This document owns:** the tables and their meaning — what each one stores, what is append-only, and the conventions every migration follows. *(skeleton, write me)*

*Read this if you touch the database.*

<!-- concern: data; fill: schema, decisions -->

## Tables by area

*When the data lives in a store without a schema in the repo (Redis, S3, Mongo, ...), one H3 per store: what is kept there, its key or path shape, the env name that points at it. Otherwise one H3 per area, each a table with one row per table or model: name, the relations it points at, the file that defines it, and what a row means where the schema says so. When no table carries a comment, say so once with the grep behind it and leave the meaning column out. Say what must never be deleted from it.*

## Relationships

*The foreign keys that matter, in words. A diagram if it fits on a screen.*

## Conventions

*Naming, timestamps, soft delete or not, how enums are stored, how a migration is written and reviewed.*

## Inventory

*Dated count of tables and migrations, so drift is visible.*
