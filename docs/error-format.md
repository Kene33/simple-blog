# API error format

Every non-2xx response uses the same top-level shape and includes a request ID
that can be found in server logs.

## Envelope

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "request_id": "req_01J2EXAMPLE",
    "fields": [
      {
        "field": "title",
        "code": "TOO_LONG",
        "message": "Must contain at most 200 characters"
      }
    ]
  }
}
```

- `code` is stable and intended for client branching.
- `message` is safe to display but is not a compatibility key.
- `request_id` is returned in the body and the `X-Request-ID` response header.
- `fields` is present only when a specific input field caused the failure.
- Sensitive values, SQL details, stack traces, and token data never appear in
  the response.

## Error codes

| HTTP | Code | Meaning |
| --- | --- | --- |
| `400` | `BAD_REQUEST` | Request shape or state is invalid outside field validation |
| `401` | `AUTH_REQUIRED` | No valid access session was provided |
| `401` | `AUTH_INVALID` | Credentials or session token are invalid |
| `403` | `FORBIDDEN` | The principal lacks the required permission |
| `403` | `CSRF_FAILED` | CSRF token is missing or invalid |
| `404` | `RESOURCE_NOT_FOUND` | Resource is unavailable to this request |
| `409` | `RESOURCE_CONFLICT` | Unique or state constraint prevents the operation |
| `413` | `MEDIA_TOO_LARGE` | Upload exceeds its configured limit |
| `415` | `MEDIA_UNSUPPORTED` | MIME type or file format is not allowed |
| `422` | `VALIDATION_ERROR` | Request fields fail schema validation |
| `429` | `RATE_LIMITED` | The caller exceeded a route limit |
| `500` | `INTERNAL_ERROR` | Unexpected server failure |
| `503` | `DEPENDENCY_UNAVAILABLE` | Required database or storage dependency is unavailable |

The API may add a more specific code only when clients need behavior different
from the category above. New codes require documentation and tests.

## Examples

### Authentication failure

```json
{
  "error": {
    "code": "AUTH_INVALID",
    "message": "Invalid credentials",
    "request_id": "req_01J2EXAMPLE"
  }
}
```

The response does not reveal whether a username or email exists.

### Ownership failure

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "You do not have permission to modify this resource",
    "request_id": "req_01J2EXAMPLE"
  }
}
```

### Unavailable dependency

```json
{
  "error": {
    "code": "DEPENDENCY_UNAVAILABLE",
    "message": "Service temporarily unavailable",
    "request_id": "req_01J2EXAMPLE"
  }
}
```

The server logs the dependency name and internal cause against the same request
ID. The client receives no internal connection details.

## Request ID rules

- Accept a valid incoming `X-Request-ID` only after applying a length and
  character validation limit.
- Generate a server-owned ID when the header is absent or invalid.
- Return the final ID on success and failure responses.
- Include it in structured logs and downstream service log context.

## FastAPI mapping

- Pydantic request errors map to `422 VALIDATION_ERROR`.
- Auth dependencies map missing/invalid sessions to `401` codes.
- Authorization policies map ownership and role failures to `403 FORBIDDEN`.
- Domain services raise typed application exceptions; routers do not assemble
  ad-hoc error JSON.
- The catch-all handler logs the exception internally and returns only
  `500 INTERNAL_ERROR`.
