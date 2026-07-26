# QuantumLearn MVP requirements traceability

This matrix audits the live implementation against the authoritative root
`Software Requirements Specification.txt`. It maps each FR1–FR28 and NFR1–NFR25 to concrete
application surfaces and verification evidence. It does not treat the existence of code as proof
that a measured target has been achieved.

## Evidence labels

- **Automated** — the requirement is directly exercised by a committed automated test.
- **Implemented — manual** — the implementation exists, but the complete acceptance condition
  still needs an integrated or human check.
- **Externally measurable** — the SRS defines a user-study, operational, load, review, or
  deployment target that cannot be established by repository inspection alone.
- **Gap** — a material part of the requirement is absent or is not connected in the live path.

All API routes below are relative to `/api/v1`.

## Audit verification snapshot

Local verification on 2026-07-26 passed all 383 backend tests with 83.29% service coverage, all
59 frontend tests across eight files, the TypeScript production build, Ruff lint/format, migration
head/check, OpenAPI and generated-contract drift checks, and 10 Playwright scenarios across Edge
Stable and WebKit. The locked CI gate remains the release authority for NFR10; native Safari and
the other external measurements identified below are not implied by these local results.

## Functional requirements

| ID | Evidence | Concrete implementation | Verification and honest scope |
| --- | --- | --- | --- |
| FR1 | **Automated** | `UserRole`, signed session cookies, `require_roles`, and the role-scoped LMS router. | `test_authentication_routes.py`, `test_session_tokens.py`, and `test_lms_core_api.py::test_role_scoping_and_explicit_bootstrap`. The unauthenticated legacy arbitrary-student router is no longer mounted. |
| FR2 | **Automated** | `POST /auth/login`, `GET /auth/me`, `GET /educator/dashboard`; `LoginScreen`, `App`, and `EducatorDashboard`. | Authentication route/service tests cover valid, invalid, inactive, and tampered sessions; LMS role tests deny non-educators. |
| FR3 | **Automated** | `GET /students/me/dashboard`, `/students/me/tasks/{task_id}`, draft/submission history routes, `Enrollment`, and course-read scoping. | LMS API tests cover authentication, enrolment-scoped task access, prerequisite access, and role denial. Student routes derive identity from the session rather than a caller-supplied student ID. |
| FR4 | **Automated** | `Course`, `CourseModule`, `Enrollment`; create/list/get/patch/publish/archive course routes plus module and enrolment routes. `CourseEditor` reloads saved courses and supports course, module, outcome, and enrolment edits. | LMS API tests cover persistence and educator scope; `CourseEditor.test.tsx` covers creation, reload, edits, and enrolment. |
| FR5 | **Automated** | Canonical upload/fetch/list and authenticated content routes, `LearningMaterial`, `LocalFileStorage`, PDF/DOCX/PPTX extractors, safe HTTPS validation, a 20 MB file limit, and a larger 21 MB request/proxy envelope. Only successfully indexed sources become usable grounding. | Storage/material lifecycle tests cover type, size, request boundaries, traversal, duplicate, fetch safety, indexing failure, and course scope. The canonical learning-loop test covers byte-for-byte educator/enrolled-student access and denial for an unenrolled student. |
| FR6 | **Automated** | `LearningOutcome` belongs to `CourseModule`; create/list/patch/delete routes and editor controls validate weekly/topic shape. | LMS tests cover all CRUD paths and ownership; Course Editor tests exercise weekly/topic creation and editing. Schema/database integrity rules enforce module association. |
| FR7 | **Automated** | Upload/fetch processing calls `index_material_offline`; generation retrieves chunk text from the selected module with a course-source fallback, binds authorised chunk IDs, and reports a typed no-result when evidence is absent. `POST /courses/{course_id}/retrieval/search` returns source-labelled passages. | RAG tests cover authorised hits, labels, no-result behavior, and privacy-safe audit. The canonical learning-loop proves upload → chunk retrieval → generated task source → grounded feedback alignment. The minimal deployment uses a deterministic SQLite-backed lexical index rather than a separate vector service. |
| FR8 | **Automated** | `POST /courses/{course_id}/tasks/generate` uses indexed passage text, the selected outcome, and the administrator-selected provider/model through one runtime factory; the offline adapter remains usable without credentials. Stored tasks include prompt, type, difficulty, answer/criteria, outcome, authorised source, generation metadata, and a prerequisite sequence. | Generation API/LMS tests assert evidence appears in the provider prompt, exact requested count, type-appropriate scaffolds, provider metadata, module/outcome ownership, and strict citation allow-listing. The Course Editor sends one explicitly selected outcome and blocks generation without an indexed source. |
| FR9 | **Automated** | Six `TaskType` values; type-specific generation/grading in `LmsService`; MCQ, multiple-answer, text, editable code, and circuit modes in `TaskView`. | `test_lms_core_api.py::test_all_six_task_types_accept_and_mark_correct_responses` and frontend `App.test.tsx` cover multiple-answer and code-completion interaction. |
| FR10 | **Automated** | `position`, difficulty, and `prerequisite_task_ids`; the live grounded generator creates beginner→intermediate→advanced scaffolding with an explicit prerequisite chain. | Generation/LMS tests and the canonical MVP loop assert three ordered tasks, stable positions, and prerequisite links. |
| FR11 | **Automated** | `_require_unlocked`, ordered task queries, and `TaskRead.access_status`; locked UI actions are disabled. | LMS API test receives 423 for a locked draft and observes the next task unlock after prerequisite completion. |
| FR12 | **Automated** | Student task GET, nullable draft GET, draft PUT, submission POST, and attempt-history GET; `SubmissionDraft` and immutable `SubmissionAttempt`. `TaskView` restores saved text, selections, code, and circuits and displays prior attempts/latest feedback when reopened. | LMS API and frontend tests cover open/save/reload/submit/resubmit, answer preservation, latest state, history count, and points awarded once. |
| FR13 | **Automated** | `starter_code`, preserved `code` text, Qiskit `<pre><code>` rendering, code explanation textarea, editable code-completion editor, and code draft/attempt restoration. | Six-type backend and frontend task tests verify code explanation/completion payloads and reload behavior; database text columns retain formatting. |
| FR14 | **Automated** | `POST /students/me/simulate`, bounded `simulate_circuit`, Qiskit `QuantumCircuit`, `transpile`, and Aer `AerSimulator`; circuit/results UI. Circuit-task grading reuses the same validation/simulation boundary. | `test_quantum_simulation.py`, student simulation tests, and the six-type LMS test cover Aer execution and controlled invalid-input errors. |
| FR15 | **Automated** | Every accepted LMS submission atomically creates/queues its feedback workflow and starts it in the interactive path; the idempotent feedback route supports recovery/replay. Attempts expose the durable feedback reference, and `TaskView` restores the latest released feedback. | Feedback pipeline/API tests prove automatic creation, persistence, recovery, and idempotency. The canonical MVP loop proves submission → validated grounded feedback without a separate manual trigger. |
| FR16 | **Automated** | Strict feedback schema, `LocalFeedbackGenerator`/`LlmFeedbackGenerator`, and rendered summary/error/explanation/actions/next step. | Feedback agent/pipeline tests cover correct, partial, incorrect, actionable, and sanitized fallback shapes. |
| FR17 | **Automated** | `LlmFeedbackJudge`, quality policy, `JudgeEvaluation`, and optional Responses structured-model adapter. | Quality-judge and persistence tests record correctness, relevance, grounding, pass/fail, and reason. Without configured credentials/model, the runnable MVP deliberately uses the deterministic local judge rather than an external LLM. |
| FR18 | **Automated** | `FeedbackPipeline` releases only accepted feedback, regenerates once, then stores/releases a safe fallback. | Pipeline scenario tests cover first-pass success, rejection→success, two failures→fallback, malformed judge output, and exact replay. |
| FR19 | **Automated** | Immutable `SubmissionAttempt` stores student/task/attempt/status/score/feedback reference/submitted timestamp; unique attempt sequence and point-award constraints. | LMS attempt-history/immutability tests and persistence constraints verify prior attempts are retained. `test_data_integrity.py` also verifies an exact `1..8` attempt sequence across concurrent database sessions. |
| FR20 | **Automated** | `LearningEvent` and typed services record task view, draft save, submission, feedback view, and completion with HMAC pseudonym, course/task/type/time/correlation. The browser opens a task through `GET /students/me/tasks/{task_id}`, so the live UI records `task_view`. | Learning-event unit/API tests, LMS event assertions, App task-open tests, feedback-view tracker tests, and privacy tests. |
| FR21 | **Automated** | Student dashboard summary/task states/scores plus per-task attempt history; all identity comes from `CurrentStudent`. | LMS tests cover private dashboard/progress/history and role scoping; `StudentDashboard` renders pathways, rings, scores, XP, and achievements, while `TaskView` renders retained attempt number/time/score/status records. |
| FR22 | **Automated** | `GET /educator/students`, `GET /educator/dashboard`, `at_risk_threshold` setting, overdue calculation, and educator-owned course filters. | LMS monitoring/admin test covers “not started” versus at-risk and threshold-backed dashboard data. |
| FR23 | **Automated** | Recommendation calculation prioritizes missing prerequisites, then the lowest-scoring outcome; `Recommendation` rows persist rank/priority/reason. | LMS prerequisite test asserts the unlock reason and persisted active recommendation. |
| FR24 | **Automated** | `Reminder`, 24-hour overdue threshold, rolling 24-hour duplicate check, dashboard display/read action, and educator bulk reminders. | LMS reminder test checks the overdue threshold path, repeat dashboard deduplication, and read state. |
| FR25 | **Automated** | `TaskPointAward`, profile points, configured points-per-level calculation, `Achievement`/`StudentAchievement`, production achievement seed migration `20260726_0013`, and XP/achievement UI. | Migration and LMS tests assert default achievements and one point award across resubmissions; dashboard tests exercise levels and achievements. |
| FR26 | **Automated** | SQLAlchemy/Alembic models persist users, courses, modules, enrolments, materials/chunks, outcomes, tasks, drafts/attempts, feedback/judging, events, recommendations, reminders, gamification, settings, and audits. | Migration round-trip, persistence-model, LMS, feedback, research, event, and audit tests. Some historical legacy tables remain for migration compatibility but are not routed. |
| FR27 | **Automated** | Admin user list/create/patch/deactivate/reactivate, course archive, and settings GET/PUT routes guarded by `CurrentAdministrator`. | LMS admin lifecycle/role tests. The local demo bootstrap is loopback-only, absent in production, and treated as a development fixture rather than an administrative operation. |
| FR28 | **Automated** | The React shell connects course authoring, indexed-source task generation, student tasks, automatic feedback, dashboards, and recommendation APIs. | `test_mvp_learning_loop.py::test_canonical_mvp_learning_loop` uses the real `/generate-tasks` path and exercises authenticated course/module/outcome/material authoring, enrolment/publish, locked→available progression, draft, submit/resubmit/history, grounded validated feedback, points, recommendations, monitoring, and role isolation without swapping APIs or database models. Frontend component tests exercise the same contracts. |

## Non-functional requirements

| ID | Evidence | Concrete implementation | Verification and honest scope |
| --- | --- | --- | --- |
| NFR1 | **Externally measurable** | Minimal role-specific UI, empty/error/loading states, and a four-step educator wizard. | No educator/student review dataset currently proves an average usability score ≥7/10. |
| NFR2 | **Externally measurable** | `CourseEditor` joins details, material, outcome, generation, review, and publish actions. | Five first-time educator timed trials are still required to prove ≤20 minutes. |
| NFR3 | **Externally measurable** | Login, dashboard, task dialog, submit, and feedback polling are connected in the role app. | A first-time student study is required to prove ≥80% complete the workflow unaided within 15 minutes. |
| NFR4 | **Implemented — manual** | Semantic controls, focus styles, skip link, keyboard alternatives to drag/drop, reduced-motion CSS, and accessible feedback/analytics components. | Axe tests cover login plus feedback/analytics, and component tests exercise keyboard-operable controls. A manual complete-workflow assistive-technology pass is still appropriate before claiming no critical barriers across every role. |
| NFR5 | **Implemented — manual** | Transactions, uniqueness/idempotency, immutable attempts/audits, leased workflow recovery, migrations, and durable worker heartbeat. | Recovery/concurrency tests cover feedback/workers, but a forced full-application restart script proving zero lost/duplicate accepted LMS records is not committed. |
| NFR6 | **Externally measurable** | Health/readiness endpoints support monitoring. | No hosted monthly telemetry proves 99.5% availability. |
| NFR7 | **Externally measurable** | Provider timeouts, indexed queries, pagination/limits, and bounded circuit execution exist. | No 50-user load result proves the three p95 thresholds and <1% error rate. |
| NFR8 | **Externally measurable** | Stateless API services plus SQLite’s documented single-worker boundary. | No 5→100-user comparative load test proves the required scaling curve; SQLite may be the limiting architecture. |
| NFR9 | **Automated** | Retrieval, task generation, feedback, judging, gamification, and analytics have separate services/contracts; `GamificationService` owns the completion-to-reward policy. | Independent RAG, feedback, judge, analytics, and `test_gamification.py` tests exercise these boundaries. Architecture/runbook documents describe the major interfaces. |
| NFR10 | **Automated** | Locked Python/npm dependencies and CI gates for Ruff, pytest service coverage ≥80%, migration checks, OpenAPI drift, TypeScript lint/unit/build/E2E, audits, and secret scan. | `.github/workflows/quality.yml` is the release evidence; this row is complete only when the current full gate is green. |
| NFR11 | **Automated** | `TaskTypeRegistry` dispatches scaffolding and grading through independent handlers for all six production task types; `LmsService` has no task-specific generation or grading branches and accepts an injected registry. | `test_task_type_registry.py` registers and executes a demonstration `true_false` handler without changing any existing handler. `task-type-extension.md` documents registration plus the explicit API/persistence/UI allow-list work needed to expose a new production identifier. |
| NFR12 | **Externally measurable** | Research schemas, paired agentic/baseline records, correctness/grounding metrics, and exports exist. | A dataset of ≥100 educator-approved cases is required to prove ≥80% factual correctness and ≤5% hallucination. |
| NFR13 | **Externally measurable** | Incorrect-feedback schema requires an identified error and action; tests enforce actionable shapes. | Educator review is still required to prove ≥4/5 and the 80% sampled rate. |
| NFR14 | **Externally measurable** | Judge thresholds and deliberately flawed unit/scenario cases are automated. | The approved validation dataset is required to establish ≥80% flawed rejection and ≤20% false rejection. |
| NFR15 | **Externally measurable** | Argon2id passwords, signed/expiring cookies, role guards, CSRF/rate-limit policies, secure-cookie production guard, CORS, security headers, dependency audits, and secret scan. | Authorization/hashing controls are automated. Hosted TLS and a release-time report with zero unresolved critical/high findings remain external evidence. |
| NFR16 | **Automated** | Route-template logging and recursive redaction; HMAC-separated pseudonyms; allow-listed event/export schemas; no answer text in learning events. | Privacy/security, learning-event, audit, analytics, and export sentinel tests. |
| NFR17 | **Automated** | Foreign keys/checks/unique constraints, immutable attempts, one released feedback record, fenced worker claims, serialized attempt allocation, and verified SQLite backup restoration. Migration `20260726_0014` adds database insert/update triggers that reject missing or cross-course task/module/outcome/material relationships even outside service code. | Migration tests execute invalid direct SQL and prove all four scope triggers reject it. Concurrency tests prove the stored attempt sequence is exactly `1..8`; the backup verifier restores a separate candidate, runs integrity/FK checks, and matches every table by row count and content digest. |
| NFR18 | **Implemented — manual** | Playwright defines Chrome Stable, Edge Stable, Firefox, and WebKit projects over five critical cross-role scenarios; CI installs and runs all four projects. | Local Edge Stable and WebKit runs passed 5/5 each. Native latest Safari still requires macOS release evidence; local Chrome installation lacked machine installer privileges, and the local Firefox binary hit a Windows headless compositor failure. Those environment limitations are not recorded as application passes. |
| NFR19 | **Implemented — manual** | A Compose package runs nginx/React, FastAPI, and a recovery worker with one persistent data volume; a hosted overlay changes environment configuration only. It includes hardened containers, readiness, migration startup, first-admin provisioning, and a smoke script. | Local and hosted Compose configurations validate and deployment-runtime tests pass. An actual Docker-engine local run plus a hosted DNS/TLS deployment running the same suite remain release-environment evidence. |
| NFR20 | **Automated** | Append-only `AuditEvent` covers feedback/research; correlated `PlatformAuditEvent` covers successful/failed login, logout, course/module/outcome/task/submission/progress/admin actions. Unknown login subjects are hashed rather than stored directly. | Authentication, LMS, feedback audit mapping, append-only, privacy, and research-export audit tests. |
| NFR21 | **Automated** | Feedback UI displays the AI notice, source labels, simulation references, and an accessible reporting control; safe fallback is fixed content. | Feedback UI/API/pipeline, report, safety-policy, and accessibility tests. |
| NFR22 | **Externally measurable** | Token/cost metadata, configurable per-token rates, and administrator-managed provider/model values are resolved by both live feedback and task-generation factories without source edits. | Runtime-selection and metadata tests exist. A measured AUD-denominated completed-loop average is still required to prove ≤AUD 0.10. |
| NFR23 | **Automated** | Typed/sanitized failures, timeouts, rollback, retries, fallback, bounded input, readiness against Alembic head `20260726_0014`, and built-in offline worker recovery. | Invalid input, missing retrieval, provider timeout/error, malformed response, simulation failure, storage failure, migration readiness, and stale-worker tests. |
| NFR24 | **Externally measurable** | Course/module/outcome/task domain and most RAG/feedback services are subject-neutral at their boundaries. | No documented second-subject demonstration and elapsed implementation evidence proves the “within a few days” target. |
| NFR25 | **Automated** | Versioned CSV/JSON research export includes case/condition/input references/sources/outputs/judge results/latency/tokens/cost. The live feedback factory wires `DurableTerminalIntegrationPlanner`, HMAC pseudonymisation, configured eligibility, and provider/model metadata into the durable outbox. | Terminal-outbox eligibility/integration tests cover the handoff; research repository/export golden-file and privacy tests cover the exact export schema. The canonical learning-loop test also exercises this live feedback factory rather than a test-only pipeline. |

## Written frontend brief

The frontend was implemented from the user’s written QuantumLearn description. **Figma was not
used, inspected, copied, or treated as a design source.**

| Brief item | Coverage | Primary files |
| --- | --- | --- |
| Role-selecting login, animated circuit background, statistics | Implemented | `components/LoginScreen.tsx`, `styles.css` |
| Educator engagement, at-risk alerts, activity, course progress | Implemented | `components/EducatorDashboard.tsx`, `services/lms.py::educator_dashboard` |
| Four-step course editor, indexed-source validation, selected outcome, and grounded scaffold preview | Implemented | `components/CourseEditor.tsx`, `app/api.ts`, LMS course/material/outcome/task routes |
| Student pathway states, XP, achievements, rings, recommendations | Implemented | `components/StudentDashboard.tsx`, student dashboard service/routes |
| MCQ/multiple-answer, Qiskit code explanation/completion, drag/drop circuit and validated feedback | Implemented | `components/TaskView.tsx`, `features/feedback`, quantum/feedback services |
| Search/filter students, progress/risk, bulk notification, distribution | Implemented | `components/StudentsView.tsx`, educator student/notification routes |
| Cohort trends, task performance, mastery radar, leaderboard | Implemented | `components/AnalyticsView.tsx`, `components/EducatorDashboard.tsx`, educator dashboard service |
| Deep-space kinetic-minimal style; Outfit/Inter/JetBrains Mono; violet/cyan | Implemented | `styles.css` |
| Administrator users/courses/settings workspace | Implemented to satisfy SRS role requirements | `components/AdminWorkspace.tsx`, admin routes |

## Release interpretation

“Automated” means a directly relevant test exists; it does not waive a stricter external
measurement stated by another NFR. The repository has no known functional **Gap** row, but a
complete release claim still requires:

1. a green locked backend/frontend/contract/audit CI gate;
2. completing the usability, timing, availability, load, review-dataset, hosted-security,
   native-browser, deployment, restart-recovery, and reusability measurements labelled
   **Externally measurable** or identified as remaining manual evidence.
