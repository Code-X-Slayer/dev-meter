# DevMeter API reference

Base URL examples use `http://127.0.0.1:8000`. Replace IDs and credentials
with values from the current environment. Management JWTs and gateway API keys
are different credentials.

## Authentication

### `POST /v1/auth/login`

Authenticates the single administrator configured by environment variables.

Request:

```json
{
  "username": "ADMIN_USERNAME",
  "password": "ADMIN_PASSWORD"
}
```

Success: `200`, returning an `access_token`, `token_type`, and `expires_at`.

Errors: `401` invalid credentials; `422` invalid request body; `503`
authentication configuration is incomplete.

### `GET /v1/auth/me`

Returns the identity in a valid management JWT.

Header:

```text
Authorization: Bearer MANAGEMENT_TOKEN
```

Success: `200`, for example `{"username":"ADMIN_USERNAME"}`.

Errors: `401` missing, malformed, invalid, or expired token.

## Service and key management

The following endpoints require a management JWT. Ownership is derived from
the authenticated username; there is no owner-selection header.

### `POST /v1/services`

Registers an upstream service.

Request:

```json
{
  "name": "Text service",
  "upstream_base_url": "https://api.example.com/v1"
}
```

Success: `201`, returning service ID, name, validated URL, and timestamps.

Errors: `401` missing/invalid JWT; `409` duplicate service name for the
administrator; `422` invalid name or unsafe URL.

### `GET /v1/services`

Lists services owned by the authenticated administrator.

Success: `200` with an array of service objects.

Errors: `401` missing or invalid JWT.

### `POST /v1/services/{service_id}/keys`

Creates a key for an owned service.

Request:

```json
{
  "name": "Gateway key"
}
```

Success: `201`. The response includes the plaintext `secret` exactly once,
along with metadata and a non-secret `key_prefix`.

Errors: `401` missing or invalid JWT; `404` unknown or inaccessible service;
`422` invalid body.

### `GET /v1/services/{service_id}/keys`

Lists key metadata for an owned service. It never returns plaintext secrets or
stored hashes.

Success: `200` with an array of key metadata.

Errors: `401` missing or invalid JWT; `404` unknown or inaccessible service.

### `DELETE /v1/keys/{key_id}`

Revokes an active key owned through the authenticated administrator.

Success: `204`.

Errors: `401` missing or invalid JWT; `404` unknown, inaccessible, or already
revoked key.

## Gateway

### `POST /v1/gateway/{service_id}`

Forwards a JSON request to the registered upstream service. This endpoint does
not accept a management JWT. It requires the service-specific gateway key:

```text
Authorization: Bearer KEY_SECRET
Content-Type: application/json
```

The registered upstream URL cannot be overridden by request parameters or
headers. Only explicitly allowed content headers are forwarded.

Success: the upstream HTTP status and JSON response where possible.

Errors:

- `400` invalid JSON request body.
- `401` missing, malformed, unknown, revoked, or wrong-service API key.
- `429` current UTC-day per-key request limit reached.
- `502` upstream timeout or connection failure.

Authenticated forwarding attempts are recorded as usage records, including
controlled upstream failures. Unauthenticated attempts are not counted.

## Analytics

Analytics endpoints require a management JWT and only return data for services
owned by the authenticated administrator.

### `GET /v1/services/{service_id}/usage/summary`

Returns all-time service totals, successful and failed counts, success rate,
average duration, and current-day remaining capacity across active keys.

Success: `200`.

Errors: `401` missing or invalid JWT; `404` unknown or inaccessible service.

### `GET /v1/services/{service_id}/usage/daily`

Groups usage by inclusive UTC date.

Optional query parameters:

```text
?start_date=2026-10-01&end_date=2026-10-31
```

Success: `200` with an array containing date, total, successful, failed, and
average-duration values. Empty history returns an empty array.

Errors: `401` missing or invalid JWT; `404` unknown or inaccessible service;
`422` malformed dates or a start date after the end date.

## Liveness

### `GET /health`

Returns `{"status":"ok"}` with `200`. This is a liveness endpoint only; it does
not claim that the database or upstream services are healthy.
