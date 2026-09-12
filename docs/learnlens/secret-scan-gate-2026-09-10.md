# Full-history secret-scan gate delivery — 10 September 2026


Tested baseline: `27a397a66b5fb6544ba08d9c8950fbbc8c6b4ca4`.

The gate now disposes of six verified synthetic findings using exact historical
fingerprints and runs a complete reachable-history scan on every configured CI
event. It rejects incomplete scans even when Gitleaks returns zero. Default
secret-detection rules remain enabled, including `generic-api-key`.

## Evidence and scope

The [baseline audit](main-audit-2026-09-10.md) records the original scan findings.
This delivery addresses NFR10's reason/owner requirement for
suppressions, NFR15's secret protection, and the work order's security gate.

The original audit and master task list are unchanged. Application code,
frontend dependencies/tests, other CI jobs, and shared runtime setup are unchanged.
No history was rewritten by this scanner change.

Changed files:

- `.gitleaksignore`: six commit/file/rule/line fingerprints, each with a reason.
- `.github/scripts/secret_scan.py`: security-only history/completion checks and an
  isolated positive control, using the Python standard library.
- `.github/workflows/quality.yml`: only the `secret-scan` job; pinned scanner
  installation, explicit full-history execution, and redacted evidence retention.
- `docs/learnlens/secret-scan-gate-2026-09-10.md`: this separate delivery note.

## Independent disposition of every historical finding

Each source blob was inspected at its reported commit, and the literal's addition
was checked against that commit's parent diff. The six findings contain three
distinct readable, numbered synthetic labels; all matched values remain redacted.
The historical assessment model declares a uniqueness constraint on
`evaluation_idempotency_key`; the evaluation service queries it to replay a
decision. The historical `db_session` fixture uses a temporary SQLite database.
These identifiers do not supply authentication to an external service.

Every row below excludes **only** `generic-api-key` at the stated historical line.
The complete commit hashes are retained in `.gitleaksignore`.

| Commit | Historical file and line | Verified context and rationale |
| --- | --- | --- |
| `681bba2583a0360f16f99b587d93689d11484402` | `src-main/backend/tests/test_assessor_review_api.py:374` | `test_review_queue_query_count_is_constant_as_records_grow` creates a second provisional `AssessmentDecision` in the test database. The matched field distinguishes that synthetic decision. |
| `681bba2583a0360f16f99b587d93689d11484402` | `src-main/backend/tests/support/assessment.py:310` | `build_provisional_decision` constructs and commits a synthetic provisional decision through the supplied test session. |
| `b85b1bdfe716a3b46bd581e62c675f1cc509c3c5` | `src-main/backend/tests/test_assessment_evaluation_api.py:131` | `test_complete_valid_evaluation_creates_one_provisional_decision` passes a replay identifier to the evaluation service using static criterion and quality ports. Assertions inspect one persisted provisional decision/evaluation. |
| `a15a497ea448eb1ccc5cc66e5aca29ce37a28c65` | `src-main/backend/tests/test_learner_model_safety.py:80` | `test_strict_contract_rejects_grade_result_and_unsafe_extra_fields` builds a synthetic learner-model payload and checks Pydantic rejection of prohibited fields. This identifier is payload metadata. |
| `d8ba5ac760ccc1815462a2e88cdb4dfb623fc380` | `src-main/backend/tests/test_assessment_attempt_models.py:91` | `_provisional_decision` seeds the original synthetic decision used by model tests. |
| `d8ba5ac760ccc1815462a2e88cdb4dfb623fc380` | `src-main/backend/tests/test_assessment_attempt_models.py:204` | `test_assessment_decision_idempotency_allows_one_record_per_evaluation` deliberately reuses the helper's identifier and asserts `IntegrityError` when inserting a duplicate. |

No additional findings appeared in the complete baseline or all-ref scans.
The fresh fingerprint sets exactly equal the original six-finding redacted report.
There are no path, directory, whole-commit, field-name, or value-wide exclusions.
The same value reintroduced at a new commit still requires review. Repository
maintainers must revalidate dispositions after scanner upgrades or new findings;
the ignore list must not be extended automatically.

## CI behavior and scanner provenance

### 11 September integration disposition

The release/reuse delivery introduced one further synthetic finding at
`5439ba77be6d070f83e83c6a03bb1ad5c8a32fc5`,
`src-main/backend/tests/test_conditional_programming.py:240`. Independent source
inspection confirmed a test-only HMAC pseudonymization setting consumed by
`HmacSha256Pseudonymizer`, with offline worker adapters, research disabled and a
temporary SQLite database. It supplies no external authentication. The existing
maintainer-owned ignore list records only this exact historical fingerprint;
all default rules and future-occurrence review remain required.

The previous `gitleaks/gitleaks-action@v2` selects short event ranges for push/PR
runs despite `fetch-depth: 0`. The replacement explicitly uses
`--all --full-history` on every configured event, from the repository root.
The [upstream action implementation](https://github.com/gitleaks/gitleaks-action/blob/v2/src/gitleaks.js)
documents the previous range selection.

Gitleaks is pinned to **8.28.0**. The Linux x64 archive SHA-256 is
`a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb`.
This was checked against the public
[release checksum manifest](https://github.com/gitleaks/gitleaks/releases/download/v8.28.0/gitleaks_8.28.0_checksums.txt).
The local Windows x64 archive also matched that manifest
(`da6458e8864af553807de1c46a7a8eac0880bd6b99ba56288e87e86a45af884f`),
and the executed binary matched the archive member byte for byte.

No replacement ruleset is added: Gitleaks uses its built-in default configuration.
The history and control scans share the explicit repository ignore file and any
future repository configuration. Ambient configuration environment overrides are
removed for reproducibility. Git text-conversion/external-diff helpers are disabled
for consistent raw patch input; both complete converted and raw scans found the
same six fingerprints here. See the
[Gitleaks 8.28.0 fingerprint documentation](https://github.com/gitleaks/gitleaks/blob/v8.28.0/README.md#gitleaksignore).

The gate checks an unshallow checkout, exact scanner version, an independent Git
text-patch commit inventory, matching scanner commit count, nonzero processed bytes,
absence of error/unexpected warning diagnostics, a freshly written JSON array,
zero findings, and scanner exit zero. It repeats the Git inventory to catch ref
changes during the scan. Reports include the head and expected commit identities.

The isolated positive control constructs a nonfunctional balanced hex value at
`src-main/backend/tests/support/assessment.py:310`, the same path/line as an
exclusion. With the repository exclusions loaded, `generic-api-key` must still
report exactly that finding, return exit one, and redact the value. The temporary
fixture is removed; only redacted reports are retained. This runs in CI as well.

## Commands and results

Run from the repository root with Python 3.11+ and Gitleaks 8.28.0 on `PATH`:

```powershell
python .github/scripts/secret_scan.py --gitleaks (Get-Command gitleaks).Source --report-dir .tmp-security-evidence
```

The gate invokes the equivalent of the commands below, where `GITLEAKS_FIXTURE_DIR`
identifies the isolated positive-control directory:

```sh
gitleaks git . --log-opts="--all --full-history --no-ext-diff --no-textconv" --redact=100 --no-banner --no-color --log-level=info --gitleaks-ignore-path=.gitleaksignore --report-format=json --report-path=history.json
gitleaks dir "$GITLEAKS_FIXTURE_DIR" --redact=100 --no-banner --no-color --log-level=info --gitleaks-ignore-path="$PWD/.gitleaksignore" --report-format=json --report-path=positive-control.json
```

Local execution used the existing backend Python environment and the verified
Gitleaks binary. Git version: `2.55.0.windows.4`.

| Verification | Result |
| --- | --- |
| Original sandbox failure reproduced, before exclusions | Exit **0**, Git `ERR` diagnostics, only **112** commits; rejected as incomplete. The original audit's **116**-commit/exit-zero failure was also replayed through the new guard and rejected. |
| Complete fixed-baseline scan before exclusions (`--full-history 27a397a...`) | Exit **1**, **176** text-bearing commits, **16,313,297** bytes, exactly the six audited fingerprints; no error diagnostics. |
| Complete all-ref scan before exclusions | Exit **1**, initially **182** text-bearing commits; later raw-patch run **183**, **16,365,840** bytes; the same six findings and no additional findings. |
| Gate with exclusions before delivery commit | Exit **0**, **183** text-bearing commits out of **229** reachable commits, **16,365,840** bytes, JSON `[]`, no error/warning diagnostics. Independent Git inventory agrees. |
| Isolated positive control | Scanner exit **1**, exactly **one** `generic-api-key` finding at the intended path/line; matched value redacted in JSON/log; gate accepts this expected detection. |
| Security guard regression probes | Rejected the retained zero-exit truncated scan, absent completion summary, wrong commit count, malformed report, missing report despite a stale clean report, and unexpected warning. |
| CI scope and syntax | YAML parsed; Bash installation/run snippets passed `bash -n`; all non-security jobs and workflow-level settings structurally identical to the starting commit. |
| Scanner helper lint/format; patch whitespace | `ruff check --isolated`, `ruff format --isolated --check`, and `git diff --check` passed. |

The audit's **181** is a Gitleaks text-fragment count, not the baseline's total
Git commit count (**222**). Scans of all local refs can include work on other
branches, and those refs advanced during this task. The original audit did not
retain a ref inventory, so its exact extra-ref set cannot be reconstructed from
the report alone. This delivery does not use 181 as an artificial success threshold:
the new gate independently inventories the actual refs and checks the count.

CI uploads only the report files as `secret-scan-evidence`.

## 2026-09-11 CI follow-up

The secret-scan job for commit `f8b7d13a854550b3b1044e516f5f63b69c6ba794`
(run `34555972980`, job `103128629314`) reported one `generic-api-key`
finding. Local execution of the unchanged pinned gate reproduced it. The exact
historical fingerprint is:

```text
c71e9bff6bcaf0dbb0c2f0357aaaa9c524d784ae:docs/learnlens/task-38-local-capacity-20260911.md:generic-api-key:133
```

The match is ordinary future cost-evidence documentation: three slash-separated
lower-case nouns following the words “token bounds”. The line lists required
records; it contains no credential assignment, issued credential or test key.
The inspected scan JSON redacted the matched value. Only this exact historical
fingerprint was added; all seven previous exclusions and every default rule remain
unchanged. The current sentence now separates the same nouns with ordinary prose
punctuation, and an isolated scan of that revised document reports zero findings.

At the same head, the complete local gate passed over **297 text-bearing commits**
out of **396 reachable commits**, with **21,019,366 bytes** processed, zero history
findings, and the unchanged positive control detecting and redacting exactly one
synthetic finding. CI's earlier 291 text commits reflect its smaller fetched ref
inventory. The local inventory and scanner count agree; no fixed count was used
to bypass coverage. Evidence is retained in ignored scratch reports. This verifies
the local correction; a subsequent hosted CI result is separate evidence.

## 2026-09-11 positive-control stability repair

CI run `34558650591`, job `103136623973`, at commit
`5a57b666a1e7a50a249fcf6436f65b3dfd79f5c9` completed its history scan with
zero findings but found nothing in the random positive control. Its redacted
artifact retains no fixture value, so the exact cause cannot be established.
The pinned generic rule requires entropy above 3.5 and ignores certain substrings,
including hexadecimal words `dead` and `feed`; either can affect random hex data.

The control now deterministically constructs 48 hexadecimal characters, with each
symbol occurring three times (entropy exactly 4), in an order avoiding the pinned
rule's hexadecimal stopwords. This is never-issued detection data. The path, line
310, scanner/configuration, expected rule/count/exit, redaction assertions and
complete-history checks are unchanged; no exclusions were added.

Two regression checks passed for stable entropy and stopword avoidance. One full
local gate run at that head passed over **298 text-bearing commits** out of
**397 reachable commits**, processing **21,118,949 bytes** with zero history
findings. The control produced exactly one redacted `generic-api-key` finding at
the required path and line. Reports remain private in ignored evidence storage.
This is local validation of the pending script change, not a new hosted CI result.

## Remaining limits

This is Gitleaks' default text-patch history coverage: binary contents, recursive
archive/encoding inspection, unreachable objects, unfetched refs, and changes
introduced only in merge resolutions are not separately scanned. A clean heuristic
scan does not establish that every possible credential format is absent.
Fingerprint semantics and commit counting must be rechecked when upgrading the
pinned scanner. The hosted Ubuntu job itself has not been run in this local task.

## 2026-09-12 export-document prose finding

CI run `34687133232`, secret-scan job `103535963552`, at source
`67b6c92166793f96b56ef364c89b08bd483e2030` scanned 299 text-bearing commits and
reported exactly one finding. Redacted artifact `10296092405` has SHA-256
`d16516d4e1aaa790bee5e65e157df5eda74b43259636b981918ddd174bb55aff`.
The finding is `generic-api-key` at line 88 of
`src-main/docs/research-export-schema.md`. That line lists export categories and
slash-separated cost-field names following token-count wording. It contains no
credential assignment, issued secret or authentication value.

Only that exact commit/path/rule/line fingerprint is excluded after source review.
The current sentence uses ordinary prose punctuation while preserving every
export category. Rewording alone cannot clear the already-reachable historical
finding. Default rules, full-history traversal, commit-count verification and
the positive-control detection/redaction checks remain unchanged. The failed CI
receipt remains historical evidence; the corrected local gate is a separate
verification, avoiding another application suite for a documentation-only change.

With the reviewed exception in the working tree at `67b6c92`, the local pinned
gate passed over **305 text-bearing commits** out of **404 reachable commits**,
processing **21,886,879 bytes**, with zero history findings. The unchanged
positive control produced exactly one expected redacted finding. The local
scanner count matches its independently enumerated Git history; CI fetched a
smaller ref inventory. This local correction does not rewrite the failed hosted
job as a pass. Its redacted reports remain in ignored scratch storage.
