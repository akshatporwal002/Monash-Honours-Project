# Audit schema and privacy controls

`audit_events` is append-only. ORM update/delete operations are rejected, and retention/deletion
is an administrative policy outside student and research request paths.

| Field | Contract |
| --- | --- |
| `id` | UUID. |
| `actor_reference` | Namespace pseudonym or fixed system actor. |
| `action` | Typed action below. |
| `outcome` | `success` or `failure`. |
| `occurred_at` | UTC timestamp. |
| `correlation_id` | Request/job UUID. |
| `resource_type`, `resource_id` | Opaque type and UUID; use workflow, feedback, report, or export UUID rather than submission ID. |
| `failure_category` | Required only on failure; sanitized bounded category. |
| `deduplication_key` | Unique operation-specific key supporting exact replay and concurrency. |

Required actions are `feedback_generation_started`, `feedback_generation_completed`,
`feedback_judged`, `feedback_regenerated`, `feedback_fallback_used`, `feedback_viewed`,
`feedback_reported`, `research_export_created`, `workflow_completed`, and `workflow_failed`.
Correlation/time, action/time, and actor/time indexes support operational review.

Student-path audit writes are transactional where practical and otherwise best effort: an audit
failure must not lose a submission or released feedback. Research export authorization/preparation
is strict and fail-closed. A generator error, cancellation, or client-closed stream appends a
sanitized failed `research_export_created` event without storing response content or an exception.

## Redaction and logging

Recursive key/value redaction is applied before bounded structured metadata reaches operational
logs. Logs use route templates, not raw sensitive URLs, and contain only correlation ID, status,
workflow stage, latency, and sanitized category.

Audit rows and logs must never contain raw answers/drafts, feedback or report text, prompts/provider
output, source chunks, names/emails/direct student IDs, API keys/access tokens/cookies/CSRF tokens,
or raw external exceptions. Tests use sentinel values and recursive key variants to enforce this
boundary across database rows, logs, API responses, and exports.
