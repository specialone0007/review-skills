# Security

> **This document owns:** how a caller proves who it is, what a role may do, how secrets are handled, which data is sensitive, and the gaps known today. *(skeleton, write me)*

*Read this if you handle auth, secrets or personal data.*

<!-- concern: security; fill: auth, env, routes, schema -->

## Authentication

*The library or scheme, the middleware file, which routes require it. From the dependencies and the route files. When the inventory found no auth library, middleware or roles, one sentence says so with the scan behind it - public by design is a fact worth writing down.*

## Authorisation and roles

*The roles or permissions the schema or code defines, and what each may do. Names from the code.*

## Secrets handling

*What is secret-specific: rotation, who has access, what is never committed. Which names are secrets is CONFIGURATION's secret column (link its rows) and how values reach a unit is DEPLOYMENT's (link How values reach a unit); never a value or a location that holds one.*

## Data classes

*Which tables or fields hold personal or sensitive data, and what that implies for logs, exports and deletion.*

## Known gaps

*Dated bullets with an owner or an open question. A gap written down is one somebody can close.*
