# API Guide

Base path: **`/api/v1`**. All responses are JSON.

## Authentication

Every protected endpoint requires a Supabase-issued JWT:

```
Authorization: Bearer <supabase_access_token>
```

The backend verifies the token (JWKS-preferred, HS256 legacy fallback),
pinning algorithms and enforcing the `authenticated` audience. The backend
**never** trusts a `user_id` from the client; identity is derived from the
verified token, and every row access is additionally guarded by Postgres RLS.

Each response carries an `X-Request-ID` correlation header (echoed from the
request if a safe one was supplied, otherwise generated).

## Error model

All errors share one envelope, with a stable machine-readable `code`:

```json
{ "error": { "code": "not_found", "message": "…", "details": {} } }
```

| HTTP | `code` | Meaning |
|---|---|---|
| 401 | `authentication_required` | Missing/invalid token. |
| 403 | `authorization_failed` | Authenticated but not permitted. |
| 404 | `not_found` | Resource does not exist or isn't yours. |
| 422 | `validation_failed` | Request failed validation. |
| 429 | `rate_limited` | Per-user rate limit exceeded. |
| 503 | `upstream_unavailable` | A dependency (DB/AI/storage) is unavailable. |
| 500 | `internal_error` | Unexpected error (details not leaked). |

## Endpoint overview

### System
- `GET /health` — liveness (no dependencies); returns app name, environment, version.
- `GET /health/ready` — readiness (verifies database reachability).

### Profile
- `GET /profiles/me` — the authenticated user's profile.

### Resumes & analysis
- `POST /resumes` — upload a PDF (multipart).
- `GET /resumes` · `GET /resumes/{id}` · `DELETE /resumes/{id}`
- `GET /resumes/{id}/extraction` · `POST /resumes/{id}/extraction/retry`
- `GET /resumes/{id}/download` — short-lived signed URL.
- `POST /resumes/{id}/analyses` · `GET /resumes/{id}/analyses` · `GET /resume-analyses/{id}`

### Job contexts
- `POST /job-contexts` · `GET /job-contexts` · `GET /job-contexts/{id}` · `DELETE /job-contexts/{id}`

### Resume builder & generation
- `GET/POST /resume-builder/projects` · `GET/PATCH/DELETE /resume-builder/projects/{id}`
- `PUT/DELETE /resume-builder/projects/{id}/sections/{section_type}`
- `POST /resume-builder/projects/{id}/assist` — persistence-free AI assist.
- `GET /resume-templates`
- `POST/GET /resume-builder/projects/{id}/generations`
- `GET /resume-generations/{id}` · `GET /resume-generations/{id}/download`

### Interviews
- `POST /interviews` · `GET /interviews` · `GET /interviews/{id}`
- `POST /interviews/{id}/start` · `/pause` · `/resume` · `/cancel`
- `POST /interviews/{id}/answers` — multipart; exactly one of a text answer or an audio file; `?include_audio=true` returns TTS.
- `GET /interviews/{id}/report`

## Interactive reference

In development and staging the full OpenAPI UI is served at
`/api/v1/docs`, and the schema at `/api/v1/openapi.json`. Both are
**disabled in production** by design.
