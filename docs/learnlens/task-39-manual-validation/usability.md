# First-time human usability trials

This protocol prepares NFR1/2/3 evidence. It is not a completed participant study.
Keep technical walkthroughs, rehearsals and generated feedback separate. A person
who has used the tested workflow in a rehearsal is no longer a first-time tester
for that workflow. An AI agent is never a participant.

## Fixed targets and proposed decisions

| Measure | Required target | Proposed operational definition; owner must resolve before counted trials |
| --- | --- | --- |
| Educator setup, NFR2 | At least five first-time trials; course creation, one resource upload, one outcome and one generated task within 20 minutes | Recruit at least five distinct first-time educators; require every counted trial to finish all four milestones in ≤1,200 seconds, not an average. Start on authenticated educator dashboard; sign-in outside clock because NFR2 lists setup, not authentication. Source processing/review and required module setup are inside the clock. Generation ends when one reviewable task is visibly saved; publication is not an extra timed requirement. |
| Student learnability, NFR3 | At least 80% of first-time students sign in, open a task, submit and find feedback unaided within 15 minutes | Student sample size is unspecified; propose ten distinct first-time students (eight successes required), with five as a smaller exploratory sample only if the owner explicitly accepts it. Start on signed-out login; end when participant locates their submitted response's feedback. All four milestones and no navigational/content assistance, in ≤900 seconds, count as success. Completion need not yield formal PASS. |
| User rating, NFR1 | Average at least 7/10 in approved student and educator review | Use one identical overall ease-of-use question per participant on a 1–10 scale; arithmetic mean over available ratings, report educator/student means, pooled mean and missing counts. Proposed conservative acceptance: each role mean ≥7 as well as pooled ≥7. Requirement does not specify pooling/weighting; retain separate means until approved. This is not a SUS score. |

Other open choices: representative recruitment and accessibility needs without
diagnosis collection; exact source/task/content familiarity; allowed reference
materials; timing/assistance rules; recording consent and retention; whether a
real provider or offline fixture is appropriate for the claimed review; threshold
boundary rounding; approved instrument version; counting technical cancellations.
Document owner/date/decision in the [trial plan](result-templates.md) before runs.
Do not silently adopt these proposals as institutional policy.

For exploratory trials, record the same raw data and label the plan unapproved.
Do not claim acceptance or research approval. Fixed thresholds above are not
negotiated away by choosing a small sample or discarding difficult sessions.

## Facilitator preparation (not shown to participants)

Use [setup](setup.md). Give each participant only the appropriate card below,
synthetic credentials, resource/task brief and permitted access tools. Do not
show the role matrix, selectors, direct task URL, sample answers or facilitator
demonstration. The participant must discover navigation. The task title is an
identification cue, not an action hint. Use a new fixture/server for each session.

Practice recording on separate synthetic fixtures without participants. Test the
resource parses and one task can be generated using the real UI before scheduling,
then use a clean trial state. Record these as setup rehearsals only. The L fixture
contains a supported circuit episode and separate unaided transfer: do not reveal
its fresh answer. The learning owner should choose a task appropriate to expected
prior subject knowledge and record that knowledge as a sampling variable. If the
chosen episode cannot be completed within the target, record the result honestly;
do not change the task halfway through or replace it retrospectively.

For educator timing, required source approval through Review source is part of
the discoverable workflow. Give permission to review the supplied synthetic material
for the disposable exercise, but do not imply expert/institutional approval. The
generated task need not be published or used to assess a real learner. Record the
provider/mode and any material processing wait so local template timings are not
presented as hosted/live-provider timings.

## Shared opening script (read verbatim)

“We are checking how easy this application is to use. We are testing the application,
not you. Use the account and materials on your card. Work as you normally would.
You may stop at any time. You do not need to explain your thinking continuously;
we will ask about your experience afterwards. If you need help, tell me. I will
record the request and can help if you want, but we record assisted work separately.
Your speed, help use and feedback in this exercise do not change a course result.”

Record permission for observation and any recording under the agreed process.
Access tools such as keyboard, screen reader, magnification or an agreed equivalent
response mode are access support, not task assistance. Record functional setup,
not disability/medical details. Do not remove access tools to improve a timing.

## Educator participant card

“You are preparing a new introductory quantum lesson. Using the supplied resource,
create a new course with the supplied unique code and a title/description of your
choice. Add the resource, define one learning outcome about the topic, and obtain
one generated task that you could review for use in that course. Tell me when
you believe those items are ready. You have up to 20 minutes. This is a disposable
exercise; you may review its synthetic content, but no real course publication
or assessment is required.”

Account card: educator email/password; unique course code; resource filename and
location; topic brief. Start at the authenticated educator dashboard. The card must
not list menu/button names or the sequence of UI screens.

Facilitator milestones (record clock readings, not just yes/no): course saved;
resource uploaded/processed; module and outcome saved; one generated task visible.
After stopping the timer, verify persistence in a separate facilitator session and
record any discrepancy. Participant saying “done” without all four observable
milestones is not complete. Do not extend the threshold to finish verification.

## Student participant card

“Use your supplied account to sign in. Find the activity named on your card,
complete and submit your response, then find the feedback on that response.
Tell me when you have found it. You have up to 15 minutes. You may use the access
tools and support that the activity permits. Follow any separate unaided-stage
instructions shown by the activity.”

Account card: student email/password; assigned task title; permitted subject
reference materials and access tools. Start on login with empty fields. Do not
include a direct task URL or explain dashboard navigation.

Facilitator milestones: successful sign-in; correct assigned task opened; response
accepted; participant locates feedback for that response. A formal result is not
required. Pending assessment is distinct from learning feedback. If only a safe
fallback/unavailable message appears, record exactly that; whether it satisfies
“find feedback” must be decided in the trial plan. Proposal: count substantive
permitted feedback only, reporting fallback completions separately.

## Timing, assistance and deviations

Use one monotonic stopwatch plus wall-clock start/end timestamps with timezone.
Start when the card is handed over and the facilitator says “begin” at the defined
starting screen. Count reading, navigation, upload, processing, simulation and
feedback waiting. Do not require concurrent think-aloud: it can change timing.
Stop at the last completed milestone, the limit, or participant withdrawal. Record
raw seconds; compare without rounding down. At the limit record “not completed
within target”; any continuation becomes a separate assisted/over-time exploration.

Default proposal: do not pause the primary elapsed clock. Record interruptions,
breaks, network/server faults and access setup changes with start/end/duration.
Report an adjusted time only as a labelled secondary measure. If the environment
fails before the clock starts, mark setup NOT RUN. After start, keep the attempt
in the started-trial log; proposed conservative student denominator includes all
started eligible trials, with technical-fault and withdrawal counts reported
separately. Any approved exclusion requires a pre-specified rule and reason; no
silent replacement. A repeat is not a first-time trial.

Do not point, name a button, give a route, enter content, or operate the screen
without recording assistance. On a help request say: “What would you try next?”
once; record this prompt too. If the participant requests direct help, give it,
record the exact words/action/time and mark the run assisted. Proposal: a neutral
clarification repeating the goal verbatim is recorded but does not itself fail
unaided status; a navigational or subject answer does. The review owner must
approve this classification before runs.

Approved in-app conceptual hints are part of supported work and are recorded
separately from facilitator help. They have no count-based assessment penalty.
The unaided transfer stage forbids conceptual help but preserves access support.
Unaided usability completion means no outside task/navigation assistance, not
denial of the application's permitted features. Record any unclear boundary.

## Post-task questions (read identically to both roles)

“Overall, how easy was LearnLens to use for the task you just attempted? Give a
rating from 1, very difficult, to 10, very easy.”

Then ask: “What, if anything, made the task difficult?” and “What would you change
first?” Accept “nothing” and missing ratings without prompting for a higher score.
Capture the participant's actual words, labelled quotation or paraphrase. No
invented feedback or AI-generated participant quote may enter the result sheet.

Use [blank scoring and session sheets](result-templates.md). Compute:
student completion = unaided within-limit successes / all counted first-time
started students ×100; report numerator, denominator and exclusions. Educator
report = every trial's raw seconds and milestones, with count at/below 1,200;
five averaged durations below 20 minutes do not establish five successful trials.
Rating mean = sum of supplied ratings / number supplied, separately by role and
pooled; report missingness and sample size. No participants means no computed
percentage, mean or acceptance decision.
