# Role-by-role execution matrix

Use [setup state codes](setup.md) and a fresh fixture for each destructive branch.
`WEB` is the recorded frontend origin; replace `{task_id}` etc. with your receipt
or a link actually returned by the UI. Every row has a blank result and evidence
field. Enter `PASS`, `FAIL` or `NOT RUN` only after a tester records what happened;
for NOT RUN give the missing dependency. Test status never changes a learner result.

Repeat each row in each required native browser and with the applicable K/S/V/E/C
procedures in [accessibility](accessibility.md). Expand one row per browser, mode
and branch in the [case record](result-templates.md). An expected outcome is a
test oracle grounded in source/requirements, not a claim it passed. Severity is
the proposed impact if the expectation fails: Critical = blocked key journey
without equivalent access, disclosed protected records or invalid consequential
result; High = major impediment/work loss with workaround; Medium = recoverable
confusion; Low = minor friction. These are triage proposals, not D-09 staffing promises.
Evidence convention: `<run>/<case>/<browser>-<mode>/` with screenshots, speech
transcript, timings or redacted request receipt as appropriate.

## Entry and student

| ID; requirements; modes | Starting state and exact actions | Expected result | Severity | Result | Evidence location |
| --- | --- | --- | --- | --- | --- |
| G01; FR2/3, AC1; K/S/E/V | B, signed out at `/login`. Tab through role radios (arrows change role), Email address, Password, Sign in. Submit empty; enter `invalid@example.test` and an incorrect password; retry with receipt credentials and matching role. | Required email receives focus; invalid login is announced; retry opens correct workspace. Paste/password manager works. No account or password leaked in errors. | Critical | | |
| G02; FR1, AC1; K/S/V | L student authenticated. Open `/admin/users`, `/assessor/review` and `/this-route-does-not-exist`. Activate Go to your workspace, then sign out. | All unavailable paths show the same non-disclosing not-found page with usable return link. Protected page returns to login after sign-out. This checks UI behaviour, not API security certification. | Critical | | |
| S01; FR3/12, AC5; K/S/V | B Student, `/student`. Read heading, navigation, Continue learning; activate it. Read task heading, instructions and response choices. Use keyboard to select an option; Save draft; reload. | Assigned task opens, typed/selected draft restores, focus and reading order remain usable. | Critical | | |
| S02; FR12/15/28, AC8; K/S/E/V | Fresh L student, `/student/tasks/{task_id}`. Perform C01 supported prediction/simulation, fill Explain the result and Your reflection; perform C02 transfer, Save draft, reload, then Submit activity. | Draft survives reload. Accepted response appears in Attempt history; Your feedback becomes available after worker processing. Pending formal result remains Awaiting assessor review; no provisional PASS/INCOMPLETE is exposed. | Critical | | |
| S03; FR19/31, BP8; K/S/V | L after S02. Mark feedback reviewed using the button containing “reviewed this feedback”. Choose Revise an earlier response, fill Reason for your revision, change reflection and Submit activity. Reload and inspect history. | Feedback review acknowledged, revision creates another response linked to the original; both responses/predictions remain inspectable. No replacement of old evidence. | High | | |
| S04; FR23/37, AC12/14; K/S/V | L after worker suggestion. Read reason; on separate fresh L journeys choose Accept suggestion, Defer suggestion, or Replace suggestion using displayed choices. After acceptance follow Open chosen activity. | Choice and explanation are readable and persist. Approved next activity opens. Non-essential choices do not alter formal standard/results. Record actual labels for replacement alternatives. | High | | |
| S05; FR35/37, AT11/12; K/S/E/V | R student, `/student/preferences`. Change Presentation pace and Preferred format; Save preferences; reload. Toggle non-essential personalisation and optional points in their own sections; save each. Reopen assigned task. | Saved values persist; Learning preferences saved is announced without focus theft. Optional rewards disappear when off; task access and assessment standard remain. | High | | |
| S06; FR19/21/30/39, AC15; K/S/V | L after S03, `/student/progress` → Course → fixture course. Follow a recorded count to `/student/progress/records`, then an evidence link to `/student/evidence/{evidenceId}` and Inspect estimate and correction history to `/student/learner-model`. Preserve all generated query parameters. | Observations, help, uncertain model estimates and released formal results are separate. Evidence has provenance/history. No invented grade percentage; empty sections explain absence. Record timezone discrepancy separately (T39-D1). | High | | |
| S07; BP7, AC22; K/S/E/V | R after A02 confirm or override; student `/student/tasks/{task_id}`, Assessment result and review. Read result, reasons and permitted next action; fill What would you like your assessor to review? → Request assessor review. Reload. | Confirmed PASS or INCOMPLETE and human status are readable without colour. Request and history persist; private assessor reasons remain private. | Critical | | |
| S08; FR12, AT17; K/S/V | H after A04 authorises a new form. Student task → Current outcome and reassessment → Open fresh reassessment; enter Your response and Submit activity; reload. | Fresh task opens; new response does not overwrite earlier INCOMPLETE/current outcome while pending. Preserved original and reassessment history remain readable. | High | | |
| S09; FR34, AC13; K/S/E/V | M student `/student/misconceptions`; Learning checks → hypothesis link. Fill Your answer, Explain your reasoning, Instructional help used; Save response. Read Alternate explanation; save revision using Save revision and start fresh check; answer fresh check using visible controls. | Staged prompts and help attribution are clear; fresh question is not exposed early. History and uncertainty remain; a hypothesis is not a diagnosis or formal grade. | High | | |
| S10; PD7/BP7; K/S/E/V | H student at task: Work through your reasoning → Your reasoning or question → Send to tutor → Report this reply → Describe the concern → Send reply report. Reload, read Report updates. | Saved report and assessor review status are announced; history retains notices, without private staff notes. | High | | |

## Educator

| ID; requirements; modes | Starting state and exact actions | Expected result | Severity | Result | Evidence location |
| --- | --- | --- | --- | --- | --- |
| E01; FR4/5/6/8, AC2/3; K/S/E/V | B Educator `/educator` → create-course action → `/educator/courses`. Enter unique Course code, Course title, Description, Course time zone. Save and add materials → Choose file → select prepared resource → Upload → Refresh status. Review source; enter Source review reason; Approve source revision. Define outcomes → Module title, Module description, Learning outcomes · one per line → Save and generate → Outcome, Tasks=1 → Generate tasks. | Course, processed source, module/outcome and one generated reviewable task persist. Processing and success are announced. No claim that generation is publication. This is the facilitator's checklist, not participant instructions. | Critical | | |
| E02; FR5/18, AC2; K/S/E/V | B Educator at Learning materials. Try HTTPS address `http://example.test/resource`; attempt add-link action. Choose invalid `.txt` if chooser permits all files; otherwise note native filter and use a harmless malformed `.pdf`. Correct to the valid supplied resource. | Clear validation/processing fault; no misleading indexed/success state. Refresh/retry actions usable, previous valid resource retained; errors not stack traces. Network URL checks on this fake address are negative tests only. | High | | |
| E03; PD9, FR4/8, AC16; K/S/E/V | E01 course: Review saved tasks (via course review toggle) → Task to review. Inspect title, prompt, expected evidence and sources. Enter Review reason → Submit for review; enter reason → Approve task; Publish course. Reopen course. Edit task prompt, Save task revision and inspect Saved content and review history. | Review/publish errors explain unmet requirements; valid synthetic approval persists. Content edits require renewed review; prior source/task versions remain. Stop and record unmet formal/publication prerequisites rather than bypassing them. | High | | |
| E04; FR22/38/39, AC6/15; K/S/V | L educator `/educator/students`, then `/educator/analytics` → Course → fixture course. Follow count/evidence/history links into `/educator/progress/records`, `/educator/evidence/{evidenceId}` and `/educator/learner-model`, retaining query parameters. | Course-scoped learner evidence and cohort trends are readable; no fake pass average or fixed learner label. Model corrections preserve original records. Record empty-state coverage separately from populated coverage. | High | | |
| E05; D-02, FR1; K/S/E/V | B course lead `/educator/courses` → choose course → Manage assessor eligibility. Select a synthetic Teaching account; enter Access change reason → Approve teaching eligibility; reload. | Eligibility approval and history appear, with separate admin grant requirement. No implicit assessor access from educator status. | High | | |
| E06; PD7, FR38; K/S/E/V | H educator `/escalations`. Choose Course and review queue; select returned owner/backup, enter acknowledgement schedule, resolution rules and Configuration reason → Save queue configuration. Inspect retained output; complete Respond to report with synthetic dates/reason/learner notice → Record human response. | Assessor/technical queues remain distinct; status, private reason and public notice are distinguishable. Student Refresh reports sees notice, not private reason; history persists. Synthetic schedule does not activate service promises. | High | | |
| E07; FR4, AC2; K/S/E/V | B disposable created course at `/educator/courses`. Open Archive, cancel; reopen and confirm Archive course in the dialog. | Initial safe focus, trapped modal focus, cancellation returns to trigger; confirmed archive removes active availability while preserving protected history. | High | | |

## Assessor (sign in as Educator with the receipt's scoped assignment)

| ID; requirements; modes | Starting state and exact actions | Expected result | Severity | Result | Evidence location |
| --- | --- | --- | --- | --- | --- |
| A01; AT4/5/6, AC16; K/S/E/V | A `/assessor/setup`; choose Assigned course from receipt. Complete fields using the facilitator data card below. Choose Remember and Phrase rules for recall. Save without phrases, then with All required phrases=Hadamard and Excluded phrases=Hadamard; correct Excluded phrases=Pauli. Save assessment draft; Approval reason → Approve and publish. | Missing/contradictory rule errors are announced, editable values retained. Corrected draft/publication succeeds and repeat publish is disabled. This isolated recall fixture does not replace selected APPLY policy. | Critical | | |
| A02; AT15/16/20/24; K/S/E/V | New R for EACH Confirm result, Override result (choose INCOMPLETE), Withhold result, Return for review and Void result. `/assessor/review` → read Response and evidence, criterion reason, provenance and quality review → action. In alertdialog test empty/space-only Reason (required); cancel/Escape then reopen, enter reason and confirm. Reload; sign in separately as associated student. | Cancel initially focused; blank reason prevents confirmation; dialog announces purpose, traps focus and returns it. Action recorded status heard; history retains action/reason. Learner sees only permitted released result/lifecycle. Quality Judge rejection is not a learner result. Void has no usable formal result. | Critical | | |
| A03; AT15, BP8; K/S/E/V | L after S02. `/assessor/review` → Inspect attempt matching response. Read all three criteria and saved evidence; choose criterion decisions, enter individual reasons and check relevant Whole immutable learner response references. Enter Formal confirmation reason → Apply frozen pass rule and confirm result. | Decisions require human evidence/reasons; frozen rule produces binary formal result with retained history. Do not mark every criterion MET unless the synthetic response supports it. AI assessment release is not asserted. | Critical | | |
| A04; AT17, AC21; K/S/E/V | H `/assessor/review` → Reassessment and outcome rule. Policy approval reason → Publish outcome rule. Fresh equivalent form → Fresh interference explanation; Private reassessment reason and Reassessment notice to learner → Authorise reassessment; reload. | Authorisation persists with whole-evidence outcome rule, no averaging. Learner gets separate fresh form (S08) and permitted notice only. | High | | |

A01 facilitator data card, adapted from the existing
[setup browser test](../../../src-main/frontend/e2e/assessment-setup.e2e.ts):
Outcome ID=`outcome_id`, Task form ID=`task_id`; Outcome wording=“Recall the
Hadamard gate name.”; Source=“Approved gate glossary”; Source version=`v1`;
Source digest=`sha256:glossary` (synthetic fixture label); Claim=“Recall a gate
name.”; Required evidence=“The gate name is present.”; Mandatory criterion=“Name
the Hadamard gate.”; Task family=`recall`; Permitted tools=`None`; Instructional
support=`None`; Access conditions=`Text`; Transfer rule=“No transfer required for
this recall criterion.” Inspect then check both Bloom/process and access-mode
verification boxes. For a separate validation branch change Bloom to Understand
with phrase rules: expect human-assessment guidance, then choose Human assessment.
This data card is not a policy change or expert approval.

## Administrator

| ID; requirements; modes | Starting state and exact actions | Expected result | Severity | Result | Evidence location |
| --- | --- | --- | --- | --- | --- |
| D01; FR27, AC7; K/S/V | B Admin `/admin`, `/admin/users`, `/admin/courses`, `/admin/settings`; navigate by sidebar and back/forward. | System overview, Users, Courses and Settings headings/landmarks expose usable navigation, tables and empty/loading/error states. | High | | |
| D02; FR1/27; K/S/E/V | B `/admin/users` → Add user. Enter Full name=Task39 disposable, unique Email address at example.test, Role=Student, a synthetic Temporary password meeting displayed rules → Create account. Change Role for that user. Open deactivate dialog, cancel, then confirm; reactivate. | Required fields/errors announced; new row and changed state persist. Confirmation protects consequential changes; no use of an existing learner account. | Critical | | |
| D03; FR1, D-02; K/S/E/V | After E05, B Admin `/admin/courses` → Manage assessors for the chosen course. In Manage assessor grants select approved Teaching account, enter Access change reason, Grant assessor access; reload. Add reason and revoke that exact synthetic grant. | Eligibility required before grant. Active/inactive history and reasons readable; revoked educator loses assessor workspace on refresh. Other course grants/history untouched. | Critical | | |
| D04; FR27, AC7; K/S/E/V | B `/admin/settings`. Read Provider/Model controls; change only Automatic overdue reminders, Save settings, reload, restore original synthetic value. | Save/persistence/status usable; failed save does not announce success. Do not select a live provider or claim runtime-provider validation from this test. | High | | |

For direct history entry (when testing the input form itself), use the receipt's
Course ID and Outcome ID and select Load history; educator also supplies the
receipt's `student_id` in Learner ID and selects Load learner history. Bare
`/progress/records` and `/evidence/...` are not complete populated test URLs:
follow the application's links to retain `course`, filter and outcome scope.
For a correction subcase, student chooses an actual Evidence ID from the linked
record, enters Context and Add context. Educator opens that learner history,
Review learner note → Reason → Add review; reload both histories. Expect both
the original observation and the learner note/review to remain.

Source route authority: [App.tsx](../../../src-main/frontend/src/App.tsx).
Action authorities: [CourseEditor](../../../src-main/frontend/src/components/CourseEditor.tsx),
[TaskView](../../../src-main/frontend/src/components/TaskView.tsx),
[AdminWorkspace](../../../src-main/frontend/src/components/AdminWorkspace.tsx),
[assessor review tests](../../../src-main/frontend/e2e/assessment-review.e2e.ts),
[human workflows](../../../src-main/frontend/e2e/human-workflows.e2e.ts),
[learning loop](../../../src-main/frontend/e2e/learning-loop.e2e.ts).
