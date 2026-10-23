# DevMeter architecture

DevMeter is a small FastAPI backend that demonstrates the control-plane and
data-flow concerns of an API gateway without pretending to be production
infrastructure. The application is intentionally layered so a learner can
trace a request from the route to the database or upstream call.

## Application construction and lifespan

[`src/dev_meter/app.py`](../src/dev_meter/app.py) exposes `create_app(settings)`
and a module-level `app` for Uvicorn. The factory creates the FastAPI instance,
registers route modules, and configures the liveness endpoint.

The lifespan creates one SQLAlchemy engine, one session factory, and one shared
HTTPX client. These resources are stored on application state and closed or
disposed during shutdown. Importing the application does not connect to the
database.

[`src/dev_meter/main.py`](../src/dev_meter/main.py) starts Uvicorn, binds to
`0.0.0.0`, and reads `PORT` when supplied by a hosting platform.

## Route layer

HTTP responsibilities are split across:

- [`auth_routes.py`](../src/dev_meter/api/auth_routes.py) — administrator login
  and identity lookup.
- [`routes.py`](../src/dev_meter/api/routes.py) — service and API-key
  management.
- [`gateway_routes.py`](../src/dev_meter/api/gateway_routes.py) — gateway
  authentication, request parsing, forwarding, and response translation.
- [`analytics_routes.py`](../src/dev_meter/api/analytics_routes.py) — owned
  summary and daily usage queries.

Route handlers validate HTTP input, resolve dependencies, translate domain
failures into HTTP responses, and delegate persistence or gateway behavior to
service modules.

## Management authentication and ownership

[`dependencies.py`](../src/dev_meter/api/dependencies.py) supplies
`get_current_identity`. It validates an HTTP Bearer JWT using the configured
signing secret and returns the token subject. Invalid, missing, or expired
tokens receive `401`.

[`services/auth.py`](../src/dev_meter/services/auth.py) verifies the configured
administrator password with Argon2 and creates or decodes HS256 JWTs. The
administrator account is configuration-based; there is no user table or
registration flow.

The authenticated username is passed as the existing `Service.owner_id`
string. This avoided a schema migration in this increment and preserves old
rows, but existing rows retain their previous owner string. A deliberate data
migration is required if old development-owned rows must be reassigned.

Management JWTs and gateway API keys are separate credential types. A
management token does not authenticate gateway requests.

## Service and API-key logic

[`services/registry.py`](../src/dev_meter/services/registry.py) creates and
lists services, creates one-time API-key secrets, stores SHA-256 API-key
hashes, and records revocation timestamps. API-key metadata endpoints return
only the non-secret prefix and metadata. The plaintext key is returned only
from successful creation.

Service ownership is included in every management lookup. A service or key
belonging to another identity is treated as unavailable.

## Database and migrations

The SQLAlchemy declarative models live in
[`infrastructure/database/models.py`](../src/dev_meter/infrastructure/database/models.py):

- `Service` — registered upstream and owner string.
- `ApiKey` — service relationship, secret hash, prefix, and revocation state.
- `UsageRecord` — authenticated forwarding attempt, status, duration, and
  success flag.

[`infrastructure/database/session.py`](../src/dev_meter/infrastructure/database/session.py)
provides request-scoped sessions. The dependency closes each session in a
`finally` block. Alembic migrations in
[`alembic/versions/`](../alembic/versions) create and evolve the schema.
Migration configuration reads `DEVMETER_DATABASE_URL`.

## Gateway request flow

1. `POST /v1/gateway/{service_id}` parses the `Authorization: Bearer` API key.
2. [`services/gateway.py`](../src/dev_meter/services/gateway.py) hashes the
   presented secret and finds an active key for the requested service.
3. The current UTC-day usage count is compared with the configured per-key
   limit.
4. The JSON body is forwarded to the registered upstream URL.
5. Only explicitly allowed headers are forwarded; the DevMeter authorization
   header is excluded and redirects are disabled.
6. A `UsageRecord` is committed for successful responses and controlled
   upstream failures.
7. The upstream status and JSON response are returned where possible.

Unauthenticated requests do not consume quota or create usage records.
Timeouts and connection failures return a controlled `502`.

## Quota and analytics

The quota is a UTC calendar-day count of usage records for one API key. It is
implemented as a database count and is intentionally not a distributed or
concurrency-safe rate limiter.

[`services/analytics.py`](../src/dev_meter/services/analytics.py) uses SQL
aggregation for totals, successful/failed counts, averages, daily grouping,
and current-day remaining capacity. Daily filters are inclusive and interpreted
as UTC dates.

## Error handling

The route layer returns predictable status codes for invalid credentials,
missing resources, invalid request bodies, quota exhaustion, and upstream
failures. Error responses do not include passwords, tokens, API-key hashes,
request bodies, or internal exception details. Database integrity failures are
rolled back before a conflict response.

## Security boundaries

This is an educational MVP:

- There is one configured administrator account.
- No registration, roles, organizations, password reset, lockout, login rate
  limiting, brute-force protection, token revocation, or JWT rotation exists.
- JWT and Argon2 use maintained primitives but do not make the service
  production-ready.
- API-key hashing is SHA-256 and secrets cannot be recovered after creation.
- The quota is not distributed or concurrency-safe.
- PostgreSQL deployment and external upstream behavior require manual
  verification.
- Render configuration is preparation only; this repository has not been
  deployed publicly.
