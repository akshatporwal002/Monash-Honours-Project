# Course recovery and material quarantine

FR4 course metadata changes now append immutable `course_revisions`. A revision records code, title, description, state, enrolment-open setting, time zone, actor, time, action and restoration provenance. It also preserves the module, enrolment and source context at that change. Migration 0051 snapshots existing courses with an unknown original actor; its timestamp is the snapshot time, not an invented original edit time.

Course owners and administrators may inspect history and restore metadata through `/courses/{course_id}/revisions` and `/courses/{course_id}/revisions/{revision_id}/restore`. Restoration requires the latest history version and a reason. It appends a revision, retains intermediate edits, and leaves modules, enrolments, assessment evidence, source revisions, approvals and citations intact. Restoring a published state reruns current publication checks in the same transaction. The educator course editor exposes the historical context and restore action. Student and foreign-owner access is denied.

FR5 uploads and downloaded HTTPS resources start quarantined. Stored originals remain private and content-addressed; quarantine is an enforced database state, not a claim that filename/signature validation detects malware. Both offline and semantic processors scan before extraction. They extract the exact scanned bytes and require a clean receipt for the same content hash, processing revision, policy and live claim before publication. Replacement files reset current scan state without rewriting old originals, extracted passages or citations.

## Operator configuration

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `MATERIAL_SCAN_POLICY` | `disabled` | `disabled` blocks processing; `required` enables the configured scanner. No allow-unscanned mode exists. |
| `MATERIAL_SCAN_POLICY_VERSION` | empty | Required nonempty reference to the operator's actual approved policy/version. Change it when policy or approved scanner configuration changes. |
| `MATERIAL_CLAMSCAN_PATH` | empty | Absolute path to an operator-provisioned local `clamscan` executable. |
| `MATERIAL_SCAN_TIMEOUT_SECONDS` | 60 | Per-process timeout, 1–120 seconds. |
| `MATERIAL_SCAN_DATABASE_MAX_AGE_DAYS` | 7 | Maximum signature database age, 1–30 days; operators must choose a value under their policy. |

The local adapter uses the [ClamAV command-line scanner](https://docs.clamav.net/manual/Usage/Scanning.html) and its [documented options and return codes](https://github.com/Cisco-Talos/clamav/blob/main/docs/man/clamscan.1.in). It records engine/database identity from `--version`, enables archive/document scans and limit/encryption/broken-file alerts, checks database age, and accepts only a successful, explicit `OK` result with no error output. Unsupported options, missing/stale databases, unavailable executable, timeouts, incomplete/skipped scans and adapter exceptions cannot yield a clean receipt. Scanner output and local paths are not exposed as user error messages. No documents are uploaded to a scanning service; no signatures are downloaded by the application.

The worker retains an append-only receipt in `material_scans`, exposed to authorised course managers at `/courses/{course_id}/materials/{material_id}/scans`. Material APIs include `scan_status` and `current_scan_id`. Rejection and disabled policy stop automatic retries; scanner unavailability uses the existing bounded infrastructure retry schedule. An explicit fresh processing run can retry after configuration repair. An expired worker cannot publish a receipt or extraction over a recovered worker's result.

## Existing records and consumers

- Legacy material is not marked clean by migration. General retrieval, new source/task approvals, course publication/restoration to published, and original-file delivery require current-policy clean receipts. Raw content delivery also checks the delivered bytes against the receipt's hash. HTTPS links are fetched into private storage and scanned; they no longer bypass quarantine through a redirect to changing remote content.
- Historical source/passage/citation APIs, recorded assessments and task-review history remain readable within their existing authorisation scope. Existing task approval summaries do not retrospectively revoke approval solely because scanner policy changed. New task approval and course publication explicitly rerun the scan gate. Historical extracted text is not a clean-scan claim about the original binary.
- A receipt is bound to the source revision's original content hash. Scanning replacement bytes never certifies an older passage. Rejection of replacement bytes preserves older approved passages and their exact citations. Changing the policy version requires another scan for new uses.
- Local demo authentication and source-free demonstration content can still run with the default configuration. Upload processing, source-backed generation and new sourced publication remain closed until the operator provisions a scanner and policy. A successful boot or health check does not certify scanning readiness.
- Integrated API contracts include `CourseRevisionRead`, `CourseRestoreRequest`, `MaterialScanRead`, `MaterialRead` and `LearningMaterialRead`. Migration 0051 follows 0050 in the integrated migration chain.
- Runtime vector and lexical retrieval share approved-source, course and scan eligibility. The derived vector cache rebuilds from preserved passages after loss or restore; see [local vector retrieval](local-vector-retrieval.md) for scoring and recovery semantics.

## Verification limits and test fixtures

`test_intake_controls.py` exercises restore provenance, scope denial, stale restores, SQL immutability, quarantine, scan retry boundaries, exact byte binding, source preservation, policy changes, new-publication gates, binary-delivery denial and HTTPS quarantine. Existing material-recovery and source-history tests use an explicitly injected synthetic scanner in their own fixtures. The local ClamAV adapter contract is tested with synthetic subprocess responses. These tests establish control behaviour only; they do not establish malware detection effectiveness or institutional approval.

Synthetic source builders can use `tests/support/material_scanning.py`: fixtures explicitly call `enable_synthetic_scanning(monkeypatch)`, or their test module opts into the named, non-autouse `synthetic_material_scanning` fixture. `approve_sourced_fixture_task` records a hash-bound synthetic receipt. It does not enable a policy globally. Existing sourced-fixture callers carry explicit module opt-ins; source-free import-only callers are excluded. New fixture consumers creating sourced approvals or querying operational retrieval must also opt in. Disposable browser servers use `synthetic_scanning_scope` for their app lifecycle and restore the previous settings/adapter on cleanup. Per-test disabled/rejected-policy overrides remain available. Production code does not import these helpers.

Activation still needs a real approved malware policy, provisioned supported scanner, maintained signature database and an operator verification under that actual configuration. No real scanner efficacy, institutional approval, hosted deployment or study approval is asserted by this delivery.
