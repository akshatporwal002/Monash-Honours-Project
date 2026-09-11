# Task 38 durable provider metering

This delivery implements the software budget boundary for the existing external
Responses adapter. It does not establish a provider approval, an approved monetary
amount, a paid load result, or an AUD cost per human-confirmed learning loop.

## Configuration and scope

Every API process and worker spending from the same approval must use the same
database and `LLM_BUDGET_ID`. The ID identifies one approved allocation, not a
process, restart, model, or automatically renewing period. Its stored limit,
currency and policy version cannot be silently changed by another worker.
Changing those values with the same ID fails closed. A different ID requires a
separate approved allocation; restarting or changing models does not reset spend.

External dispatch requires all of these deployment settings:

- `LLM_BUDGET_ID`, `LLM_BUDGET_POLICY_VERSION`, and `LLM_BUDGET_LIMIT`.
- `LLM_COST_CURRENCY`: the uppercase three-letter currency of that allocation.
- `LLM_PRICING_VERSION`: reference to the approved pricing/bounding record.
- `LLM_PRICING_PROVIDER`, `LLM_PRICING_MODEL`, and `LLM_PRICING_BASE_URL`, matching
  the currently selected provider, model and endpoint exactly.
- Explicit `LLM_INPUT_COST_PER_MILLION` and `LLM_OUTPUT_COST_PER_MILLION` in that
  currency. Missing prices remain missing; an explicitly approved zero is valid.
- `LLM_MAX_INPUT_TOKENS` and `LLM_MAX_OUTPUT_TOKENS`, checked against the approved
  provider/model capacity and pricing. Technical defaults are 32768 and 4096;
  those defaults do not themselves constitute provider approval.

No monetary amount, pricing approval or currency is supplied by default. Local
template mode remains usable without any external budget. Existing administrator
provider/model and timeout/retry controls remain in place. Selecting an external
model without matching pricing now stops external dispatch. Production factories
always attach the durable meter; only an explicitly supplied `httpx.MockTransport`
can construct the isolated adapter without one.

The Compose deployment forwards the same budget and pricing settings to the API
and worker. Blank monetary placeholders remain absent; they do not become approved
zero prices. An explicitly supplied zero price remains valid. Configuration
validation covers both containers' rendered settings; actual container execution
still requires the operating-environment checks.

The reservation is the maximum configured input charge plus maximum configured
output charge, rounded upwards to currency millionths. The text-only adapter
rejects requests whose serialized UTF-8 byte length plus 1024 framing allowance
exceeds the input bound, and sends `max_output_tokens` to the provider. The approval
must cover this tokenizer/framing bound, all billable output including reasoning,
and applicable rates and fees. Tools, images, audio, provider-specific extra fees,
or a provider which does not honour these bounds require a separately implemented
and approved adapter. No currency conversion is inferred. Budget limits and billed
actuals require exact precision of at most six decimal places.

## Persistence and recovery

Migration `20260911_0047`, initially following `20260910_0046`, adds
`provider_budgets` and `provider_usage` without inserting approvals or backfilling
unknown history. The integrated migration chain ends at `20260911_0051`; readiness
and the exact table assertions (`tests/test_migrations.py:EXPECTED_TABLES`) match it.
Downgrade refuses to delete a populated budget ledger; retain history and use the
verified backup/recovery procedure. The migration and exercised database are SQLite.

Short independent transactions reserve exposure before any network call. A shared
budget update serializes simultaneous workers. A conditional dispatch claim allows
each attempt key to send once. Duplicate reservations with the same fingerprint
do not charge twice; conflicting requests or already claimed keys cannot dispatch.
Callers can supply an internal `metering_key`; otherwise each logical adapter call
gets a new ID. Each connection retry has its own numbered attempt record.

The existing durable workflow owns submission replay, leases and infrastructure
retry limits. A legitimate recovery retry makes a new metered call and must obtain
new budget; prior ambiguous exposure remains counted. The ledger does not cache or
replay model output. Feedback generator/judge records carry submission/task/course
correlation in internal provenance, outside the model prompt. Task generation
retains supplied course/module IDs. Provider/model selection, endpoint fingerprint,
prompt version, token bounds, rates, pricing/policy versions, and the workflow's
timeout/retry policy are retained for each attempt.

States preserve the financial distinction:

- `RESERVED`: admitted but unclaimed. Recovery can release it atomically.
- `DISPATCHED`: claimed before the transport call. Process interruption here is
  ambiguous and never releases exposure on a timer or lease expiry.
- `NOT_SENT`: transport reported a connection failure before dispatch. Exposure
  is released and the bounded connection retry may seek another reservation.
- `UNKNOWN` / `OBSERVED`: dispatch finished or failed; available token counts and
  response ID are retained, including malformed output, HTTP errors and partial
  usage. Billed actual remains null. Estimates never release reserved exposure.
- `RELEASED`: cancelled before dispatch; it can never dispatch afterwards.
- `RECONCILED`: an attributable receipt supplies actual cost, matching currency,
  recording actor and timestamp. It replaces that attempt's held exposure once.
  Replaying the same receipt/amount is harmless; conflicting receipts fail and a
  unique receipt cannot be applied to a second attempt.

Actual spend can exceed the earlier reservation if the provider violates its
approved bound. It is retained honestly and blocks further admission when the
budget is exceeded. Observed token estimates above the reservation also increase
held exposure. Reconciliation and late token observations use the recorded pricing;
new deployment prices cannot rewrite older estimates. Cancellation during a slow
reservation may leave an undispatched reservation for recovery, with no network
call. Database operations run off the async event loop so contention does not
silently bypass the existing wall timeout.

## Operator interface

From the backend with authorised database access, `python -m scripts.provider_usage
list --budget-id <approved-id>` lists bounded metadata, states, estimates, nullable
actuals and provenance. `--limit` accepts 1–1000 rows. The tool does not print prompts
or credentials and never calls a provider.

`python -m scripts.provider_usage release-undispatched --usage-id <id>` releases
only a reservation that still has not claimed dispatch. This cannot erase an
ambiguous charge.

`python -m scripts.provider_usage reconcile --usage-id <id> --actual <amount>
--currency <currency> --receipt-id <unique-billing-line-reference> --actor
<authorised-operator-reference>` records supplied billing evidence. The operator
must verify attribution, currency and actual amount. A receipt reference is not
automatically proof of provider approval or reconciliation completeness. Incorrect
receipts are rejected on conflicting replay rather than overwritten.

The existing benchmark's historical feedback snapshot and currency/coverage gates
remain intact. For a future approved campaign, include this durable attempt ledger
when reconciling all spend, including failed calls and recovery retries. An unknown
token count or actual amount is not zero, and a token-based estimate is not a bill.

## Verification and remaining external evidence

Focused tests cover separate-engine concurrent admission, duplicate reservation
and dispatch, reconciliation races and conflicting receipts, undispatched recovery,
process interruption on both sides of the dispatch claim, release/dispatch races,
late observations, excess actual/estimated exposure, malformed and partial usage,
transport errors, timeout/cancellation, budget/input denial before transport,
connection retry metering, operator inspection/reconciliation and migration history.
Existing targeted runtime cases exercise the real database worker with synthetic
generator/judge responses under changed timeout/attempt policy, including the
single quality regeneration. Exact final counts are recorded in the delivery receipt.

Recorded focused execution: 56 passed in the initial 58-case run; two existing
worker fixtures needed explicit synthetic pricing/budget configuration and passed
after that correction. Seven additional cases cover process interruption, frozen
pricing/excess exposure, release races, operator tooling, partial usage and
reservation-timeout cancellation. The final affected 30-case run passed in 19.01
seconds. Across these scoped receipts, all 65 distinct cases are accounted for;
this is not a full application-suite result. Two earlier sandbox launches failed
to create temporary fixtures and supply no database behavior evidence. The first
interruption test launcher also printed a Windows multiprocessing diagnostic;
the replacement subprocess launcher passed both boundaries without that diagnostic.

Live provider/model approval, pricing and framing evidence, the real budget,
attributable invoices, an approved load campaign and human-confirmed complete-loop
cost remain external records. No live calls, deployments or study processing were
performed. PostgreSQL execution, a hosted recovery campaign and external billing
reconciliation are not claimed by the SQLite fixture results.
