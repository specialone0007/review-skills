# API reference

> **This document owns:** the endpoints — path, method, auth, request and response shape, errors. The API is the contract; nobody reimplements it. *(skeleton, write me)*

*Read this if you call it over HTTP.*

<!-- concern: http; fill: routes, auth, env, packages -->

## Authentication

*How a caller proves who it is, and which endpoints need it.*

## Endpoints

*One H3 per path prefix, each a table with one row per endpoint: method, path, handler file, the auth guard it uses. Request and response shapes from the handler types; copy real payloads, not invented ones.*

## Errors

*The error envelope and the codes, once, so every endpoint can point here.*

## Typical end-to-end call

*The sequence a real client makes, in order, with the code file that does it.*

## Notes

*Rate limits, pagination, versioning, anything a caller learns the hard way.*
