# Testing

> **This document owns:** how this repository is tested — the runners, where tests live, how to run them, and what CI checks. *(skeleton, write me)*

*Read this if you are writing or running tests.*

<!-- concern: testing; fill: tests, ci, packages -->

## Runners and layout

*Which test runners are configured and where tests live. From config files and folder names.*

## Running tests

*The test command is AGENTS.md § Commands'; one line and a link. Here only what AGENTS does not hold: one file, one folder, watch mode, the flags - copied from the runner's own options.*

## What CI runs

*Every workflow: its event (push, pull request, schedule, manual), its jobs, and which of them gate a merge. From the workflow files. A nightly sync or deploy workflow is listed here by its event and trigger only; its steps are DEPLOYMENT § Deploy steps' (one line and a link). JOBS holds only what the repository itself schedules.*

## Coverage and gaps

*Coverage configuration if any. What is deliberately untested, and why, as open questions until a human answers. When the inventory found no runner and no tests folder, this section says so in one sentence with the scan behind it; that sentence is the doc's reason to exist.*
