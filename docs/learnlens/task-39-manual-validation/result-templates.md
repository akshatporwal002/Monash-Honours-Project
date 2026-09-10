# Blank records — copy for each real run

All observation/result fields below are deliberately empty. Allowed test statuses
are PASS, FAIL and NOT RUN; add the blocker for NOT RUN. No blank implies a pass.
Use the [matrix](role-matrix.md) and [trial protocol](usability.md) as instructions.
Store completed participant records outside the source repository in the approved
evidence location. Keep credentials out of screenshots and shared records.

## Trial plan and authority

| Field | Value |
| --- | --- |
| Plan ID/version, decision date, review owner | |
| Research/operational classification and applicable approval reference | |
| Facilitator, accessibility reviewer, evidence custodian | |
| Recruitment/sampling, student N, educator N (at least five) | |
| First-time eligibility rule and verification | |
| Exact task, source digest and outcome; content reviewer | |
| Environment/provider mode and acceptance-claim scope | |
| Approved timing, assistance, pause and exclusion rules | |
| Rating question/scale, role pooling/weighting decision | |
| Does fallback feedback count? Why? | |
| Recording permission, storage/retention reference | |
| Approved access arrangements (functional only) | |
| Outstanding decisions/blockers | |

## Browser / OS / version record

Duplicate one row per browser/assistive-technology configuration. Include native
Safari version and macOS build, not a WebKit project name.

| Run ID | Test date/timezone | App commit/dirty state | Profile, fixture IDs, origin | Browser/version/channel | OS/build, hardware | Viewport CSS px / screen px / OS scaling | Native zoom | AT/version/settings | Tester ID | Evidence root |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | | | |

| Runtime field | Value |
| --- | --- |
| Python path/version; Node path/version; dependency lock revision | |
| API/web ports, setup command, startup log | |
| Fresh database and upload directory; fixture creation receipt (private) | |
| Browser update availability check/date; extensions/privacy settings | |
| Safari keyboard navigation, VoiceOver Quick Nav/verbosity | |
| Release-build versus fixture limitations | |

## Individual technical case

| Field | Value |
| --- | --- |
| Run, matrix case/subcase and procedure K/S/V/E/C | |
| Role, native browser, fixture receipt/starting state | |
| Requirement/WCAG criterion | |
| Steps actually executed (including deviations) | |
| Expected result (copy relevant oracle) | |
| Actual result | |
| PASS / FAIL / NOT RUN | |
| Severity; blocker or defect ID | |
| Focus before/during/after, or actual spoken announcement | |
| Measurement: colours/font/ratio/tool, zoom/viewport, or circuit/run comparison | |
| Evidence file/location and timestamp | |
| Tester, date, reviewer and review decision | |

## Coverage ledger

One row per matrix case × browser × applicable procedure/branch. C01–C03 also
receive their own rows. Expand rows rather than combining untested states.

| Case | Role | Browser | Procedure/state | Result | Defect/blocker | Evidence | Tester/date |
| --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | |

## First-time session

| Field | Value |
| --- | --- |
| Participant pseudonym; role; plan ID | |
| First-time eligibility checked; relevant prior content familiarity | |
| Environment record ID, fixture/task/source | |
| Observation/recording permission reference | |
| Start screen verified; permitted resources/access tools | |
| Wall-clock start/end with timezone; stopwatch duration seconds | |
| End reason (completed/limit/withdrew/technical fault) | |
| All required milestones completed? | |
| Unaided or assisted, with rule reference | |
| Within required limit? | |
| Counted/excluded/deferred; pre-specified reason | |
| Overall ease rating 1–10 (blank if missing); missing reason | |
| Verbatim participant comment (or labelled paraphrase) | |
| Post-timer persistence verification and evidence | |
| Observer and review date | |

Educator milestones:

| Course saved at seconds | Upload/processing complete at seconds | Outcome saved at seconds | Generated task visible at seconds | Total seconds | Within 1,200 seconds | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

Student milestones:

| Signed in at seconds | Correct task opened at seconds | Submission accepted at seconds | Feedback found at seconds | Total seconds | Unaided and ≤900 seconds | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

Assistance, interruption and deviation log (repeat rows):

| Elapsed seconds | Event/request | Exact facilitator words/action | In-app support versus outside assistance | Start/end/duration if interrupted | Effect on classification | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |

## Blank scoring ledger

Five educator slots are a scheduling minimum, not evidence of recruitment.

| Slot | Participant ID | First-time | Four milestones complete | Raw seconds | Within 1,200 | Assistance/deviation | Rating /10 | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | | | | | | | | |
| E2 | | | | | | | | |
| E3 | | | | | | | | |
| E4 | | | | | | | | |
| E5 | | | | | | | | |

Student sample size awaits the plan; duplicate rows to the approved N.

| Participant ID | First-time | All four milestones | Raw seconds | Outside assistance | Unaided and ≤900 success | Counted/excluded reason | Rating /10 | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| | | | | | | | | |

| Aggregate | Value | Numerator / denominator or calculation | Reviewer decision/evidence |
| --- | --- | --- | --- |
| Educator started / completed within limit | | | |
| Student started / counted / excluded | | | |
| Student unaided within-limit completion percentage | | | |
| Educator rating mean; supplied / missing ratings | | | |
| Student rating mean; supplied / missing ratings | | | |
| Pooled rating mean under approved rule | | | |
| NFR1 / NFR2 / NFR3 decision separately | | | |
| Native-browser and manual-accessibility remaining cases | | | |

## Actionable defect record

| Field | Value |
| --- | --- |
| Defect ID, concise title, observed versus source-only candidate | |
| App commit; case; browser/OS/AT; run ID | |
| Synthetic starting state, IDs and exact minimal steps | |
| Expected requirement and actual result | |
| Reproduction count / attempts; repeat-fixture outcome | |
| Impact, severity and accessible workaround if any | |
| Screenshot/video/speech/error log (redacted); timestamp | |
| Relevant source file/line; proposed owner/dependency | |
| Fix reference; retest commit/result/evidence | |

Record security/data-scope findings privately under the approved incident process.
Do not attach authentication cookies, tokens, passwords or real learner records.
