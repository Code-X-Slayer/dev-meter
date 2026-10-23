# DevMeter

DevMeter is an educational FastAPI MVP for exposing registered ML, LLM, and
other HTTP services through a small managed gateway. It demonstrates service
registration, one-time API-key creation, protected forwarding, a basic daily
request quota, and usage analytics.

It is intentionally not production-ready infrastructure. The project focuses
on an explainable backend foundation rather than distributed operations,
billing, or a complete identity system.

## What problem it solves

An API platform needs a controlled boundary between callers and upstream
services. DevMeter provides that boundary in a small demonstrable workflow:

1. Register an upstream service.
2. Create an API key for that service.
3. Call the service through the protected gateway.
4. Enforce a simple per-key daily request limit.
5. Inspect aggregate and daily usage.

The gateway never exposes stored API-key hashes and does not forward the
DevMeter `Authorization` header to an upstream.

## Architecture

```mermaid
flowchart LR
    Client[API client] -->|JWT management requests| API[FastAPI routes]
    Client -->|Bearer API key + JSON| Gateway[Protected gateway]
    API --> AuthN[Admin JWT authentication]
    Gateway --> Auth[Hash and validate API key]
    Auth --> Quota[Daily per-key quota]
    Quota --> Upstream[Registered upstream URL]
    Quota --> Usage[UsageRecord]
    API --> Analytics[SQL aggregation queries]
    AuthN --> API
    Analytics --> Usage
    API --> DB[(SQLite or PostgreSQL)]
    Usage --> DB
    Auth --> DB
    Upstream --> Gateway
```

Application startup creates one SQLAlchemy engine, one session factory, and one
lifespan-owned `httpx.AsyncClient`. Each request receives a short-lived
database session. Alembic owns schema migrations.

## Tech stack

- Python 3.14+
- Poetry 2.x
- FastAPI
- Pydantic and Pydantic Settings
- SQLAlchemy 2.x
- Alembic
- HTTPX
- SQLite for isolated local tests
- PostgreSQL and `psycopg` for the intended production database
- pytest and Ruff
- React, TypeScript, Vite, Tailwind CSS, and Recharts dashboard

## Project structure

```text
.
├── alembic/                 # Database migrations
├── docs/                    # Architecture and API reference
├── frontend/                # React/Vite dashboard
│   └── src/
├── scripts/                 # Disposable local demo
├── src/dev_meter/
│   ├── api/                 # FastAPI routes and schemas
│   ├── core/                # Settings and validation
│   ├── infrastructure/      # SQLAlchemy engine, sessions, and models
│   └── services/            # Auth, registry, gateway, and analytics
├── tests/                   # Backend tests
├── pyproject.toml
├── poetry.lock
└── .github/workflows/ci.yml
```

## Local setup (Ubuntu or WSL)

Requirements:

- Python 3.14 or newer
- Poetry 2.x
- Node.js 20 or newer and npm

From an Ubuntu or WSL terminal, clone the repository, enter it, and install
the locked backend dependencies:

```bash
git clone <REPOSITORY_URL>
cd dev-meter
poetry install
```

If Poetry is not installed, install it using the official Poetry instructions
for your environment, then reopen the terminal so `poetry` is on `PATH`. Run
Python commands inside the managed environment with `poetry run`.

Install the locked dashboard dependencies separately:

```bash
cd frontend
npm ci
cd ..
```

Do not create or commit `.env` files. Export local settings in the shell or
use a local secret manager instead.

## Configuration

The application reads environment variables with the `DEVMETER_` prefix:

| Variable | Default | Purpose |
| --- | --- | --- |
| `DEVMETER_APPLICATION_NAME` | `DevMeter` | FastAPI application title |
| `DEVMETER_ENVIRONMENT` | `development` | `development`, `testing`, or `production` |
| `DEVMETER_DEBUG` | `false` | FastAPI debug mode |
| `DEVMETER_DATABASE_URL` | `sqlite:///./dev_meter.db` | SQLAlchemy database URL |
| `DEVMETER_ADMIN_USERNAME` | unset | Administrator login identity |
| `DEVMETER_ADMIN_PASSWORD_HASH` | unset | Argon2 hash of the administrator password |
| `DEVMETER_JWT_SECRET` | unset | JWT signing secret; at least 32 characters in production |
| `DEVMETER_JWT_EXPIRY_MINUTES` | `30` | Access-token lifetime, from 5 to 1440 minutes |
| `DEVMETER_DEFAULT_REQUEST_LIMIT` | `100` | Requests per API key per UTC day |
| `DEVMETER_UPSTREAM_TIMEOUT` | `10.0` | Upstream timeout in seconds |

The default SQLite URL is convenient for local exploration and automated
tests. For PostgreSQL, set a URL without committing credentials:

```bash
export DEVMETER_DATABASE_URL='postgresql+psycopg://user:password@localhost/dev_meter'
```

The application does not connect to the database when its module is imported.
The engine is created at application lifespan startup and disposed at shutdown.
When `DEVMETER_ENVIRONMENT=production`, SQLite and debug mode are rejected at
startup. The production database URL must therefore be supplied explicitly.

Management authentication requires an administrator username, an Argon2
password hash, and a JWT signing secret. Generate a password hash locally
without putting the password in source control:

```bash
poetry run python -c "from argon2 import PasswordHasher; print(PasswordHasher().hash(input('Password: ')))"
```

Set the resulting value as `DEVMETER_ADMIN_PASSWORD_HASH`, and provide a
separate randomly generated value for `DEVMETER_JWT_SECRET`. Passwords,
password hashes, JWT secrets, and access tokens must be supplied through the
environment or a secret manager, never committed to the repository.

## Database migrations

Apply all migrations:

```bash
poetry run alembic upgrade head
```

Create a migration after adding reviewed ORM model changes:

```bash
poetry run alembic revision --autogenerate -m "describe the change"
```

Check that model metadata and migrations agree:

```bash
poetry run alembic check
```

Rollback all application migrations:

```bash
poetry run alembic downgrade base
```

The current schema contains services, API keys, and usage records. It does not
contain users, organizations, plans, or billing tables.

## Run the API

Start the development server:

```bash
poetry run python -m dev_meter.main
```

The server binds to `0.0.0.0` and uses the `PORT` environment variable when it
is set, defaulting to port `8000` locally. Open the interactive API
documentation at
<http://127.0.0.1:8000/docs>.

For a fully local, disposable demonstration using a mocked upstream:

```bash
poetry run python scripts/demo.py
```

The script creates a temporary SQLite database, applies migrations, registers a
service, creates a generated API key, calls the gateway through an in-process
HTTPX mock, and prints summary and daily analytics. It authenticates through
the local management login endpoint but does not print the JWT or full API-key
secret. The temporary database is removed automatically when the script exits.
It does not call an external API.

## Dashboard

The repository includes a separate Vite dashboard in [`frontend/`](./frontend/)
for the existing management and gateway APIs. It does not add backend routes
or fabricate data:

- **Overview** reads service summaries and daily usage.
- **Services** registers upstreams and composes service details from existing
  service, key, and summary endpoints.
- **API keys** creates and revokes service keys; a new secret is displayed once
  and is never written to browser storage.
- **Analytics** renders the backend's daily usage response with inclusive date
  filters.
- **API playground** sends JSON through the protected gateway using a
  service-specific API key.

Install and run it with Node.js 20 or newer:

```bash
cd frontend
npm ci
npm run dev
```

Run the FastAPI server separately with `poetry run python -m dev_meter.main`.
Vite proxies `/v1` and `/health` to `http://127.0.0.1:8000`, so local
development does not require CORS configuration. The management JWT is held in
React memory and is cleared when the page is refreshed or the user signs out.
Administrator credentials and signing secrets are entered through the login
form and are not frontend environment variables.

For a separately hosted frontend, set the non-secret
`VITE_API_BASE_URL` before building, for example
`VITE_API_BASE_URL=https://api.example.test npm run build`. Leave it unset for
the local Vite proxy. The backend must then allow the frontend origin through
its CORS policy; this repository does not enable permissive production CORS.
The frontend does not use cookies, so requests use explicit bearer headers.
Rejected or expired management tokens clear the in-memory session and return to
the login screen.

Frontend checks:

```bash
cd frontend
npm test
npm run build
```

The frontend dependencies are locked in
[`frontend/package-lock.json`](./frontend/package-lock.json). The dashboard
checks have been run locally with Node.js 20; the GitHub Actions workflow runs
the same locked install, test, and build commands.

Dependency audit status as of 2026-10-23:

- `npm audit --omit=dev`: no production vulnerabilities reported.
- `npm audit`: 13 findings remain in development-only tooling, including
  `tinypool`, nested Vite/esbuild, Vitest's mocker, and Tailwind CSS's legacy
  `braces` dependency path. npm's available fixes require breaking upgrades
  (`vitest@4.1.12`/newer and `tailwindcss@4.3.3`), so they were not applied
  blindly. These tools are used only in local development and CI builds, not
  in the deployed browser bundle. Reassess them before expanding CI trust or
  running development tooling against untrusted project input.

The liveness endpoint is:

```bash
curl http://127.0.0.1:8000/health
```

It returns:

```json
{"status":"ok"}
```

## Complete demo workflow

The examples use placeholders only. Replace `MANAGEMENT_TOKEN`, `SERVICE_ID`,
and `KEY_SECRET` with values returned by the preceding commands. Management
bearer tokens authenticate the configured administrator; gateway API keys are
separate credentials used only for forwarding.

### 1. Log in to the management API

```bash
curl -X POST http://127.0.0.1:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"ADMIN_USERNAME","password":"ADMIN_PASSWORD"}'
```

The response contains a short-lived `access_token`. Store it temporarily as
`MANAGEMENT_TOKEN`; it is not returned by any other endpoint.

To inspect the authenticated identity:

```bash
curl http://127.0.0.1:8000/v1/auth/me \
  -H 'Authorization: Bearer MANAGEMENT_TOKEN'
```

### 2. Register a service

```bash
curl -X POST http://127.0.0.1:8000/v1/services \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer MANAGEMENT_TOKEN' \
  -d '{"name":"Local text service","upstream_base_url":"https://api.example.com/v1"}'
```

The response contains a service ID and the validated upstream URL.

### 3. Create an API key

```bash
curl -X POST http://127.0.0.1:8000/v1/services/SERVICE_ID/keys \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer MANAGEMENT_TOKEN' \
  -d '{"name":"Demo gateway key"}'
```

The successful response contains `secret` exactly once. Save it temporarily as
`KEY_SECRET`; only its hash and a short prefix are persisted.

### 4. Call the protected gateway

```bash
curl -X POST http://127.0.0.1:8000/v1/gateway/SERVICE_ID \
  -H 'Authorization: Bearer KEY_SECRET' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"hello"}'
```

The gateway uses the registered upstream URL and forwards the JSON body. It
does not allow a request to override the upstream destination.

For a completely local test without an external upstream, use the mocked
transport in `tests/test_gateway.py` or point development configuration at a
safe local test service only when the URL validation policy is explicitly
adjusted for that development environment.

### 5. Inspect usage summary

```bash
curl http://127.0.0.1:8000/v1/services/SERVICE_ID/usage/summary \
  -H 'Authorization: Bearer MANAGEMENT_TOKEN'
```

The summary includes total, successful, and failed requests, percentage
success rate, average duration, the configured per-key limit, and
`requests_remaining`. The remaining value is the sum of unused daily capacity
across active API keys belonging to this service.

### 6. Inspect daily usage

```bash
curl 'http://127.0.0.1:8000/v1/services/SERVICE_ID/usage/daily?start_date=2026-10-01&end_date=2026-10-31' \
  -H 'Authorization: Bearer MANAGEMENT_TOKEN'
```

`start_date` and `end_date` are optional ISO dates. Both endpoints are
inclusive, and all grouping and filtering use UTC calendar dates. An empty
history returns an empty daily list and zero-valued summary metrics.

## Endpoint overview

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Liveness |
| `POST` | `/v1/auth/login` | Authenticate the configured administrator |
| `GET` | `/v1/auth/me` | Return the authenticated administrator |
| `POST` | `/v1/services` | Register a service |
| `GET` | `/v1/services` | List owned services |
| `POST` | `/v1/services/{service_id}/keys` | Create a one-time API key |
| `GET` | `/v1/services/{service_id}/keys` | List key metadata |
| `DELETE` | `/v1/keys/{key_id}` | Revoke a key |
| `POST` | `/v1/gateway/{service_id}` | Authenticate and forward JSON |
| `GET` | `/v1/services/{service_id}/usage/summary` | Aggregate usage |
| `GET` | `/v1/services/{service_id}/usage/daily` | UTC daily usage |

See the complete [architecture document](./docs/architecture.md) and
[API reference](./docs/api-reference.md) for request shapes, authentication
requirements, and error behavior.

## Development checks

Run the complete test suite:

```bash
poetry run pytest
```

Check formatting and linting:

```bash
poetry run ruff format --check .
poetry run ruff check .
```

Validate migrations against an isolated SQLite database:

```bash
rm -f /tmp/dev-meter-check.db
DEVMETER_DATABASE_URL=sqlite:////tmp/dev-meter-check.db poetry run alembic upgrade head
DEVMETER_DATABASE_URL=sqlite:////tmp/dev-meter-check.db poetry run alembic check
DEVMETER_DATABASE_URL=sqlite:////tmp/dev-meter-check.db poetry run alembic downgrade base
```

The automated suite uses isolated SQLite databases and mocked upstream HTTP
transports. No external paid API or live upstream is required.

The repository `.gitignore` excludes virtual environments, `.env` files,
SQLite databases, caches, coverage output, and build artifacts. No real
credentials are stored in the project.

## Continuous integration

GitHub Actions configuration is defined in
[`.github/workflows/ci.yml`](./.github/workflows/ci.yml). It runs on pushes and
pull requests using Ubuntu 24.04 and Python 3.14, matching the project's
`requires-python` constraint. The backend job installs Poetry 2.5.1 and the
locked Python dependencies, then runs:

```bash
poetry run ruff format --check .
poetry run ruff check .
poetry run pytest
poetry run alembic upgrade head
poetry run alembic check
poetry run alembic downgrade base
```

Migration validation uses a temporary SQLite database and removes it even when
a migration command fails. The workflow requires no production credentials,
PostgreSQL server, or external upstream service. This repository documents the
workflow configuration. A second job installs the locked frontend dependencies
with Node.js 20, runs the Vitest client checks, and builds the dashboard. Local
validation of the current working tree has passed; the current unpushed changes
have not been run remotely. Check GitHub Actions after pushing this reviewed
change set.

## Deployment status and future Render option

[`render.yaml`](./render.yaml) defines a minimal Python web service. It installs
the locked Poetry dependencies, applies `alembic upgrade head` during the build
before the web process starts, and uses `/health` as the Render health check.
It does not create a database or contain credentials.

DevMeter is not deployed and this repository does not publish an application
URL. Render and PostgreSQL remain optional future work. If deployment is
attempted later, the blueprint expects these environment values:

| Variable | Render setup |
| --- | --- |
| `PYTHON_VERSION` | `3.14.4` in the blueprint |
| `POETRY_VERSION` | `2.5.1` to match local verification |
| `DEVMETER_ENVIRONMENT` | `production` |
| `DEVMETER_DEBUG` | `false` |
| `DEVMETER_DATABASE_URL` | Required secret containing a PostgreSQL SQLAlchemy URL |
| `DEVMETER_ADMIN_USERNAME` | Required administrator username |
| `DEVMETER_ADMIN_PASSWORD_HASH` | Required Argon2 password hash secret |
| `DEVMETER_JWT_SECRET` | Required JWT signing secret, at least 32 characters |
| `DEVMETER_JWT_EXPIRY_MINUTES` | Optional token lifetime, default `30` |

### Manual Render steps

1. Push this repository to GitHub and create a Render Blueprint from the
   repository, or create a Web Service using the commands in
   [`render.yaml`](./render.yaml).
2. Provision PostgreSQL separately through Render or another PostgreSQL
   provider. Plan, network access, backups, and cost are provider decisions
   that cannot be safely encoded here.
3. Set `DEVMETER_DATABASE_URL` in Render as a secret environment variable.
   Never put the URL in `render.yaml`, Git, or the README.
4. Set the administrator username, Argon2 password hash, and JWT secret as
   Render environment secrets/values. Do not set a plaintext password variable.
5. Deploy and confirm the build log shows migrations completing before the
   service starts. Then check `/health` and `/docs`.
6. Review the service logs and database provider status manually. This project
   has not been tested against a live PostgreSQL connection in this
   environment, so a successful local check is not a deployment guarantee.

The free or ephemeral web filesystem must not be used for durable SQLite data.
If PostgreSQL is unavailable on the chosen plan, use a private local/demo
deployment instead of deploying with SQLite. The blueprint does not perform
resets or destructive migrations; `alembic upgrade head` only applies pending
migrations.

### Public deployment warning

The management API now requires a signed bearer token for the configured
administrator. This is a minimal single-account MVP mechanism, not a complete
identity or tenant platform. Do not expose it as a production multi-user
service. There is no registration, role model, password reset, account
lockout, login rate limiting, brute-force protection, token revocation, or key
rotation mechanism.

The gateway requires a registered API key, but gateway API keys and management
bearer tokens are separate credentials. A management token cannot call the
gateway, and a gateway key cannot access management endpoints.

To remove the deployment, delete the Render web service and separately remove
the PostgreSQL database only after confirming that its data is no longer
needed. Render resource deletion is manual and potentially destructive, so it
is intentionally not automated by this repository.

## Implemented features

- Typed environment configuration
- FastAPI application factory and lifecycle management
- SQLAlchemy 2.x engine, sessions, typed models, and Alembic migrations
- Service registration and administrator-scoped listing
- One-time API-key creation with stored SHA-256 hashes
- API-key revocation
- Protected gateway forwarding
- URL validation and restricted forwarded headers
- Basic per-key UTC daily request quota
- Usage records for successful and failed authenticated forwarding attempts
- SQL aggregation-based summary and daily usage analytics
- OpenAPI documentation through FastAPI

## Known limitations and security boundaries

This is an educational MVP, not production-ready infrastructure.

- There is one configured administrator account; user registration, roles,
  organizations, and multi-tenant identity management are not implemented.
- Existing rows retain their string `owner_id`. Rows created before JWT
  management authentication are accessible only if the administrator username
  is configured to the same value, or after an explicit data migration.
- JWT signing-key rotation, token revocation, and refresh tokens are not implemented.
- Login rate limiting, account lockout, and brute-force protection are not implemented.
- The quota is a database count and is not a concurrency-safe distributed rate limiter.
- There is no Redis, billing, background processing, retry policy, or circuit breaker.
- API-key secrets are shown once, but key rotation and stronger password-style hashing are not implemented.
- Upstream response handling is intentionally minimal.
- No live PostgreSQL or external upstream validation is performed by the automated tests.
- No token accounting or model-specific metering is implemented.
- Upstream policy, observability, audit logging, and operational hardening are incomplete.
- JWT and Argon2 provide standard primitives, but their use here does not make
  this application production-ready.
