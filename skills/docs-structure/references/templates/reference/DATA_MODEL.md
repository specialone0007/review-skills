# Data model

> **This document owns:** where data lives and what it means - the stores, the entities and their relationships, the conventions, and the migrations. *(skeleton, write me)*

*Read this if you touch where data lives - the database, the cache, the object store.*

<!-- concern: data; fill: schema, decisions -->

## Stores

*One H3 per place data lives - the database, a cache, an object store, a queue - from the schema and the store SDKs: what is kept there, its key or path shape, what must never be deleted from it, and a link to the CONFIGURATION row that points at it.*

## Entities and relationships

*For a store with a schema in the repo: one H3 per area, each a table with one row per table or model - name, the relations it points at, the file that defines it, and what a row means where the schema says so. When no table carries a comment, say so once with the grep behind it and leave the meaning column out. Then the foreign keys that matter, in words; a diagram if it fits on a screen. A store without a schema (Redis, S3) has its shape under Stores and nothing here.*

## Conventions

*Naming, timestamps, soft delete or not, how enums are stored.*

## Migrations

*The migration tool, the folder, how one is written and reviewed, and a dated count of migrations and tables so drift is visible.*
