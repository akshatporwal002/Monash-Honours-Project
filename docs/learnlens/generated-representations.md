# Generated representations and stage access

FR35 requires text, visual, worked-example, circuit and stepwise forms where the construct permits. The task review editor can now generate alternatives from the saved task and its approved, clean-scanned source passages. Generation creates a new immutable draft revision; it neither approves content nor delivers it to a learner. Existing manual alternatives survive regeneration unless they exactly match previously generated items being replaced.

## Generation, review and delivery

`POST /api/v1/practice-representations/tasks/{task_id}/generate` accepts an expected revision and a practice, supported or transfer target. It requires the course owner through the educator API, the existing mutation security guard, and current source approvals. The task revision and source approvals are checked again after generation. Concurrent edits, fabricated quotations, undeclared references, invalid circuits and instructional transfer candidates prevent saving.

The configured structured-output provider uses the existing durable provider meter. Without a configured external runtime, local extraction produces actual source excerpts and structured task/source blocks; it does not claim to generate a solved example. A labelled source example can supply a draft worked example. A circuit alternative reproduces the bounded starter circuit. Every format is either offered or accompanied by a reason it is unavailable. Brief and detailed content are separate variants. Exact quotations establish traceability, not factual correctness or semantic equivalence; reviewers must evaluate those judgments.

The provider receives target task input and declared sources, without private marking answers or the other episode stage. Transfer targets and standalone transfer tasks accept access-only variants at instructional level zero. Generated access alternatives require human review for unchanged construct and response demands, just like authored access alternatives.

Generation provenance is stored at `marking_criteria.representation_generation.{practice|supported|transfer}` with candidate quotations, installed content, source approvals, input revision, provider/model, prompt version and usage. The saved `TaskRevision.provenance` is `GENERATED`, including when alternatives are appended to an authored task. Category-quality review should also detect the retained `representation_generation` marker after subsequent manual revisions. No insertion-time approval is performed.

Reviewed ordinary variants use the existing practice catalog and explicit delivery receipt. Formal episodes use typed `access_representations` independently on supported and transfer plans, alongside existing instructional representations and legacy accessibility strings. Metadata exposes only the current stage's choices. Delivery resolves content from the frozen requested stage, so retries cannot substitute transfer content for a supported-stage receipt. Access remains level zero in formal evidence. An active course transfer or fresh check blocks instructional requests and replays across tasks while retaining reviewed access.

The episode support UI uses format and explanation-detail preferences to select an actual reviewed alternative. Formal support remains an explicit learner action, including on-request mode. Preference controls do not alter formal response requirements or establish learning outcomes.

## Integration boundaries

The task review route and UI provide a complete generate, save-draft, review and delivery path. Initial task-generation attachment is a separate integration hook for the generation owner:

- Call `attach_generated_task_representations(output, sources, provider=..., model=...)` before final generated-task validation. It copies the task, builds missing candidates locally, validates supplied candidates, and supports basic tasks and multipart plans.
- Call `bind_task_representation_sources(criteria, mapping)` when retrieval chunk IDs become stored source-passage IDs. It copies and remaps installed alternatives, candidate quotations and the duplicate multipart plan together.
- Optional configured-model candidates use `representation_candidates` and `transfer_access_candidates` inside marking criteria; their provider/model identity is required. Missing candidates are recorded with the local builder's identity.

These hooks are tested but not yet called by the shared initial generation entry points in this branch. The generation owner retains those files. Combined OpenAPI contracts and quality-review integration remain the coordinator's responsibility. This change adds no migration.

The narrow TaskReviewPanel mounts and task-review source/circuit validation additions predate the coordinator's reservation of those files for category-quality review. Preserve those additions when merging that review work; this branch does not implement or bypass category-quality decisions.

## Verification

The new representation tests and existing task-14 support/privacy lifecycle checks passed in targeted runs (17 cases before the final standalone-transfer case). The final focused run passed 13 cases: all 12 representation-generation cases plus the existing course-transfer delivery/replay regression. It covers local extraction, source-ID remapping, fabricated output, concurrent edits, draft-only API behavior, private-stage boundaries, frozen access replay and level-zero transfer evidence. A further single-case run verifies the added provider-budget failure response. Provider clients and source approvals/scanner receipts are synthetic; no paid provider call or real content approval is claimed.

Ten distinct component cases passed across the generation, task-14 support and task-review panel tests, including preferred content, transfer access, unsaved-draft blocking and stale-revision errors. TypeScript and scoped ESLint passed. Scoped Ruff and whitespace checks apply to the changed files. Broad suites, browser acceptance and human construct/accessibility review remain outside these focused checks.

## Release and reuse audit

The existing deployment package and release operations cover the same local/hosted images, readiness smoke checks, scanner mounts and policy, stopped-writer backups, retained-image migration compatibility, and rollback restoration into a fresh volume. The conditional-programming module already exercises the pathway, learner-model, adaptation and assessment interfaces. This audit found no additional concrete software gap in those mechanisms; it does not establish operational or independent reuse acceptance.

Local container execution remains unverified. The installed Docker Desktop was started, but its Linux engine reported that it could not start; `wsl --status` confirmed that Windows Subsystem for Linux is not installed. No remote engine, image pull, deployment or host-feature installation was used. An operational local engine is needed before container, scanner, backup and rollback execution can be evidenced.

Host/TLS configuration, real scanner signatures and source receipts, recovery/availability records, an approved second-subject module, and independent measured reuse acceptance still require their actual owners and environment. NFR24's 16 developer-hour gate requires measured human effort and the approved module decision; code inspection cannot supply that evidence. These are explicit remaining acceptance conditions, not claims that the overall project is complete.
