# Architecture

> **This document owns:** the map of the system - its context, the containers it runs as, the building blocks inside them, how a request moves at runtime, how it is deployed, and the qualities and risks that shaped it. Decisions live in their own records. *(skeleton, write me)*

*Read this if you need the map before you change a boundary.*

<!-- concern: architecture; fill: packages, services, env, routes, schema, decisions -->

## Context

*The system as one box, the people and external systems around it, and what crosses each edge. Names from the code and the integrations, not roles invented for the diagram.*

## Containers

*One row per deployable unit: name, language and runtime, what it owns, its port or entry point, what it must never do. A text diagram of the arrows between them, each arrow labelled with the environment name that makes it.*

## Building blocks

*Inside each container, the modules or packages that matter and what each is responsible for. From the folder tree, one level deep.*

## Runtime

*The life of one unit of work, step by step, naming the container and the table or queue at each step.*

## Deployment view

*The topology only: which container runs on which platform, from the deploy configs, one line each. The units table, the environment per unit and the steps are DEPLOYMENT's; link it, never repeat it.*

## Quality and risks

*The qualities the design pays for (latency, cost, isolation) and the known risks and debts, dated, each with an owner or an open question.*
