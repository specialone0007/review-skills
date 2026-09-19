# Configuration

> **This document owns:** every environment variable and flag this repository reads - its name, which unit reads it, whether it is required, and where its example lives. Names only, never a value. *(skeleton, write me)*

*Read this if you need to know what a variable does or where it is read.*

<!-- concern: configuration; fill: env, services, packages -->

## Variables by unit

*One H3 per unit, each a table: name, required or optional, read by (file), secret (yes or no, from the name pattern - _SECRET, _TOKEN, _PASSWORD, _KEY, _DSN, except a name containing PUBLIC or PUBLISHABLE - or an example-file comment). The example file's path is Files', once. Names only: no value and no default in a cell, secret or not - the gate reads any value beside a name as a leak, and the example env file is the home of defaults (link it). The port a unit listens on is one sentence under the table citing its source (a Dockerfile EXPOSE, a compose ports entry), so it is never a value in a row. When the inventory found no environment name, this section is one sentence saying so with the scan behind it.*

## Files

*Every config file the code reads that is not an env file, and every example env file: its path, what it configures, which unit reads it. This is the one home of where an example env file lives; SETUP copies it by name and DEPLOYMENT links here.*

## Flags

*Feature flags and toggles: name, where it is read, what turns on. Never a default in a cell; when the default matters it is one sentence citing its source, like the port.*
