---
paths:
  - "**/models/**"
  - "**/models.py"
  - "**/schema.prisma"
  - "**/schema/**"
  - "**/entities/**"
  - "**/*.sql"
  - "**/queries/**"
  - "**/repository/**"
  - "**/repositories/**"
  - "**/dao/**"
  - "**/migrations/**"
  - "**/migrate/**"
  - "**/alembic/**"
  - "**/db/migrate/**"
  - "**/routes/**"
  - "**/api/**"
  - "**/controllers/**"
  - "**/endpoints/**"
  - "**/handlers/**"
---

# Backend Standards

## API contracts

Follow the existing protocol, URL conventions, response envelopes, pagination, and error format. Do not introduce REST conventions into another protocol or change a public response shape as cleanup.

Validate untrusted input and authorize each operation at the appropriate boundary. Use protocol-appropriate status/error codes. Keep stack traces, database internals, secrets, and sensitive records out of client errors and logs.

## Data integrity

Model responsibilities and naming follow the project's architecture; domain models may legitimately own business invariants. Use database constraints for integrity that must survive concurrent or external writes.

Choose native types supported by the actual database. Represent money with exact decimals or documented integer minor units; preserve timestamp/timezone semantics. Add timestamps and identifiers when the domain or established schema requires them, not mechanically to every table.

## Queries

- Parameterize untrusted values. Use allowlists or safe query-builder facilities for identifiers and sort expressions that cannot be bound as values.
- Inspect generated queries and query plans for N+1 behaviour, excessive reads, and index needs. Choose loading strategies for the ORM and workload actually in use.
- Design indexes around measured filters, joins, ordering, write cost, and database behaviour; not every foreign key or column needs a new index.
- Use transactions for atomic groups of writes and appropriate concurrency control for read-modify-write invariants. A transaction alone does not prevent every race.
- Choose timeouts, cancellation, pagination, and work limits for the request's latency and resource budget. Add caching only with a clear invalidation and isolation strategy.

## Migrations

Treat deployed migrations as immutable. Follow the project's migration tool, naming, transactional, and rollout conventions.

Plan compatibility with the code that will run during the rollout. For required columns on populated tables, use a suitable backfill/default/constraint sequence; do not invent a meaningless default solely to satisfy NOT NULL. Remove consumers before dropping data they still require.

Use online or concurrent schema operations only when supported by the database and deployment environment. Batch large backfills and make retry behaviour explicit.

Document a realistic recovery path: rollback when safe and supported, otherwise roll-forward or restoration from a verified backup. A destructive migration cannot honestly promise to recover deleted data from a schema-only downgrade. Applying migrations to a live database requires the relevant authorization.

Exercise important success, authorization, error, integrity, and migration cases using the actual database semantics where doubles are insufficient.
