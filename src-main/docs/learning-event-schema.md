# Learning-event schema

Learning events are append-only behavioral measurements. Server code derives the pseudonymous
actor, course, task scope, and UTC occurrence time. The browser can ingest only `task_view` and
`draft_save`; submission, feedback-view, and completion events originate from trusted backend
hooks.

## Common fields

| Field | Contract |
| --- | --- |
| `id` | Server-generated UUID. |
| `pseudonymous_user_id` | Namespace-separated HMAC-SHA256 `v1` pseudonym. |
| `course_id`, `task_id` | Canonical server-resolved opaque scope. |
| `event_type` | One of the five types below. |
| `client_event_id` | Caller UUID used for idempotency; browser supplies this for its two allowed types. |
| `occurred_at` | Server-generated UTC timestamp. |
| `correlation_id` | Request/job UUID. |
| `workflow_reference` | Nullable server-only workflow UUID used to measure an exact first terminal feedback view; browser ingestion cannot set it. |
| `metadata` | Strict type-specific JSON, maximum 1,024 encoded bytes. |
| `deduplication_key` | Unique pseudonymous actor + event type + caller UUID key. |

Exact replays return the existing event. Reuse of a caller UUID with different event type, scope,
or metadata is a conflict. Event recording uses an independent transaction; best-effort hooks
cannot roll back feedback or submission persistence.

## Metadata allow-list

| Event type | Origin | Metadata |
| --- | --- | --- |
| `task_view` | Browser | Optional `source` slug, maximum 100 characters. |
| `draft_save` | Browser | Optional `duration_ms`, integer from 0 through 86,400,000. Draft content is forbidden. |
| `submission` | Trusted backend | Positive `attempt_number` up to 10,000; optional numeric `score` from 0 through 100. |
| `feedback_view` | Trusted first-terminal-read hook | `feedback_status`: `validated` or `fallback`. |
| `completion` | Trusted backend | `completion_status`: `completed`, `passed`, or `failed`; optional numeric `score` from 0 through 100. |

Metadata is flat and rejects unknown fields, nested structures, sensitive-key variants, non-finite
numbers, and oversized strings. It never contains answers, drafts, names, emails, credentials,
tokens, feedback text, prompts, or source chunks.
