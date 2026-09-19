# Pipelines

> **This document owns:** what runs when nobody clicks - the background jobs, the queues, the schedules, the data flows between them, and how each one fails and retries. *(skeleton, write me)*

*Read this if you need to know what runs when nobody clicks. Every cron, queue and worker has its home here; OPERATIONS links, never lists.*

<!-- concern: pipelines; fill: jobs, ops, services, env -->

## Jobs

*One H3 per job or worker, from the worker files and the queue library: what it does, what triggers it, what it writes.*

## Queues

*Every queue or topic: name, producer, consumer, the environment name that points at the broker.*

## Schedules

*Every cron or scheduler entry in the code: schedule, what it runs, what happens if it is missed. A scheduled CI workflow is TESTING's (What CI runs), not a pipeline.*

## Data flows

*The path of one unit of work through the jobs above, step by step, naming the table or queue at each step.*

## Failure and retry

*Retry policy, dead letters, idempotency - the design, from the code where it says so, an open question where it does not. What a person does when a job is stuck is OPERATIONS's (When something is wrong); link it.*
