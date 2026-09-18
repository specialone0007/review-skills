# Operations

> **This document owns:** how this is run in production - health checks, scheduled jobs, alerts, what to do when each one fires, and who is on call. *(skeleton, write me)*

*Read this if you are on call or something is down.*

<!-- concern: operate; fill: ops, jobs, services, env, decisions -->

## Health

*Every health or readiness endpoint and what it checks. From the configs and route files.*

## Scheduled jobs

*Every cron or scheduler entry: schedule, what it runs, what happens if it is missed.*

## Alerts

*Alert rules or the absence of them. Each rule with its file.*

## When something is wrong

*One subsection per known failure: symptom, where to look, what to do. Until a person who has run it writes one, a single open question; a list of fix commits is not a runbook.*

## On call

*Who, how they are reached, and what they are expected to do first. Facts outside the repo carry a verified-against line with a date.*
