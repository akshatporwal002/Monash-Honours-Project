# Manual accessibility procedures

Requirements: [NFR4, FR14, AC17](../../01-implementation-requirements.md),
[AT11/24 and access equivalence](../../02-pass-incomplete-bloom-assessment-spec.md),
[work-order §15.3](../../03-codex-implementation-work-order.md).
Apply these procedures across the [role matrix](role-matrix.md), including dialogs,
loading, error, saved and empty states. Record individual findings in the blank
case record; do not reduce a whole role to one tick. Every status starts blank.

Mappings below were checked on 10 September 2026 against
[W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/). They identify relevant criteria for
these procedures, not a complete conformance audit. An accessibility reviewer must
evaluate all applicable A/AA criteria and complete pages/processes before any
WCAG 2.2 AA claim. A passing axe scan is supplementary evidence only.

## K — keyboard and focus

At 100% native zoom, set aside the mouse. From the address bar Tab into the page;
use Shift+Tab backwards, arrows for radios/selects, Enter/Space to activate, and
Escape to dismiss where offered. Exercise shell navigation/skip link, all form
controls, upload chooser, tables with links, circuit buttons and result/review
dialogs. Record a focus sequence including entry, first error, save, dialog open,
cancel and completed action. Focus must be visible and logical; each control must
work and no trap may prevent leaving. Dialog focus remains inside until closed,
then returns to a useful trigger. Name, role and selected/expanded/disabled state
must be discoverable. Check browser back/forward and narrow-screen navigation.
Applicable: 2.1.1, 2.1.2, 2.4.1, 2.4.3, 2.4.6, 2.4.7, 4.1.2.

At 200%/400% repeat opening menus/dialogs and tabbing to bottom actions. Fixed
headers/footers or author-created overlays must not entirely hide the focused
component (2.4.11); record partial obstruction too as usability evidence.
[W3C focus guidance](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html).

## S — screen reader flow and announcements

Use a human tester familiar with their screen reader. Proposed pairings: NVDA with
Firefox or Chrome on Windows, VoiceOver with native Safari on macOS. Record exact
versions, verbosity and keyboard settings; choose final combinations with the
accessibility owner. Navigate headings, landmarks, lists, forms and table headers
using the reader's own navigation commands, then use normal form interaction.
Do not use the DOM or a screenshot as evidence that words were spoken.

Listen before, during and after: invalid sign-in (G01), preference load/retry/save
(S05/E below), prediction checkpoint and simulation (C01), submission/feedback
(S02), review dialog open/cancel/confirm (A02), upload processing (E01), and report
save/status change (S10/E06). Record actual speech in order and the action timestamp.
Expected: control labels/required states, headings and table relationships convey
the same meaning as the screen; dynamic success, wait and error messages are
perceivable without searching or losing input focus. Repeated polling must not
continually interrupt reading. Announce the purpose and reason requirement of the
dialog, and distinguish pending review, formal result and Quality Judge status.
Applicable: 1.3.1, 1.3.2, 3.3.1/2, 4.1.2, 4.1.3.
[W3C status-message guidance](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html).

## V — contrast, zoom, reflow and presentation

Measure text foreground/background from computed colours using the reviewer's
contrast tool. Sample body/help/placeholder/error text, buttons, links, result
labels and selected navigation in default, focus, hover and error states. Record
the colour pair, font size/weight, exact unrounded ratio, tool/version and screenshot.
SC 1.4.3 needs 4.5:1 for ordinary text, 3:1 for large text (18pt or 14pt bold);
document any legitimate inactive/decorative/logo exception rather than silently
omitting it. [W3C contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html).

Measure essential input boundaries, selected states, chart/circuit information and
author-styled control indicators against adjacent colours. SC 1.4.11 generally
requires 3:1 for essential non-text information, with its specified exceptions.
Capture state information lost when colour is unavailable (1.4.1), including
PASS/INCOMPLETE and circuit state. Do not treat colour ratios alone as proof of
readability. [W3C non-text contrast](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html).

For each matrix route/state set the actual browser page zoom to **200%** using its
menu. Read and operate all fields, tables, menus, circuit controls, feedback and
dialogs; capture the zoom indicator and cropped/hidden content. Content/function
must survive enlargement. Reset to 100% between cases. CSS font-size injection is
separate supplementary testing, not native zoom evidence.
[SC 1.4.4](https://www.w3.org/WAI/WCAG22/Understanding/resize-text.html).

At a desktop content viewport equivalent to 1280 CSS pixels at 100%, set native
page zoom to **400%**, giving approximately 320 CSS pixels of layout width.
Record actual viewport width/height and native zoom; do not assume monitor pixels
equal CSS pixels. Inspect for two-direction page scrolling, clipped buttons,
overlapping text and unusable dialogs. Also test 320 CSS px at 100% as a separate
reflow case. Two-dimensional tables/diagrams can have justified local scrolling;
surrounding controls/text still reflow and equivalent circuit information remains
available. If a browser cannot set 400%, record that limitation and perform 320px
reflow separately; leave the native 400% case NOT RUN.
[SC 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html).

Additional reviewer checks: text spacing overrides (1.4.12), hover/focus popovers
(1.4.13), pointer target size/spacing (2.5.8), and password paste/autofill (3.3.8).
Use normative exceptions where relevant; unresolved applicability needs a reviewer
decision, not an automatic pass. These do not replace the full A/AA review.

## E — validation and recoverable service errors

Perform G01, E02, A01 and A02's invalid-input branches. Record whether the error
identifies the field/problem and a useful correction (3.3.1–3.3.3), retains other
input, and offers a keyboard-accessible retry. Consequential review/archive/account
changes need check/confirmation or a permitted reversal (3.3.4 where applicable).

For a reproducible service outage without modifying application code:

1. Start the chosen fixture normally; sign in; finish loading S05 preferences or
   the L task. Save one baseline draft successfully. Keep both terminals running.
2. In browser developer tools, temporarily block ONLY requests matching
   `*/api/v1/students/me/preferences*` for load/save errors, or enable Offline
   for the current tab for a save error. Record the actual injection method.
   Start blocking before opening preferences. If native tooling lacks request
   blocking, load the page first then use its network-offline facility; if neither
   exists, leave that injected scenario NOT RUN and retain native invalid-input checks.
3. Technical tester observes the error with keyboard/screen reader. Preference
   load should say “Preferences could not be loaded.” and expose “Reload learning
   preferences”. Disable blocking, return to that control and activate it: expected
   focus is Presentation pace. Change a value and save; expect “Learning preferences
   saved.” with focus remaining on Save preferences.
4. For a task save error, change a synthetic response, switch the tab offline and
   Save draft. Verify the response stays in the editor and no false success/result
   appears. Restore network, retry once, then reload to verify the saved response.
   Never reload an unsaved offline draft to make the test easier.

Do not stop/restart the standard server for error injection: it would create a new
DB and invalidate the session. A network fault cannot prove a particular HTTP 503
message or provider timeout; record the distinction. The original
[focused tests](../../../src-main/frontend/e2e/accessibility-interactions.e2e.ts)
use Playwright response interception, which native manual browsers do not inherit.
Full restart/provider-failure drills remain coordinator work.

## C — equivalent circuit and result information

These are technical tester procedures, never unaided participant answer cards.

**C01 (L supported stage; FR14, AT11, SC 1.1.1/1.3.1/2.1.1/2.5.7).** On the fresh
task activate Add H gate with Enter. Record prediction “Zero and one each have
probability one half”, enter reasoning, then Record prediction for this input.
Inspect Earlier predictions → View saved predictions and inputs: saved circuit
text should identify one qubit and H on qubit 0. Run 1,024 shots. Compare the visual
circuit, text circuit, numeric count rows and the table captioned Exact probabilities
and sampled frequencies. Read each state with its row/column headers using the
screen reader. Counts total 1,024; ideal probabilities for this fixture are half
each; counts need not be exactly 512/512. Read saved run identity and distinguish
probabilities from sampled frequencies and from formal results. Remove a gate
using its button, add it again, record a new prediction and rerun; verify preserved
earlier prediction and new circuit/output agreement. Record ambiguous gate names
or missing initial-state/measurement order information as findings.

**C02 (L separate transfer).** After Explain the result and Your reflection,
activate Start unaided fresh application. Read Fresh application is unaided;
conceptual tutor input must disappear while access support remains. Enter a fresh
response, add fresh X then H then H, enter fresh prediction/reasoning, Record fresh
prediction, Run fresh circuit. Compare Fresh application circuit text with the
saved output and shot information. Save/reload to confirm the separate transfer
history. The supported conceptual hints have no instructional count cap: request
at least three approved hints during a separate supported fixture and record the
saved help history. No help-count deduction or transfer answer leakage is allowed
(D-05, BP5/6); service protection is not an assessment penalty.

**C03 (B two-qubit circuit task, if present).** From the demo dashboard open the
assigned circuit task and record its actual task ID. Add H and CX by keyboard,
remove each by its wire button, clear and rebuild. Compare drag-to-wire capability
with button capability: can the same permitted gate be placed on every wire without
dragging? Read control/target order, input state, measurement order and outputs in
text. If the task is absent, mark NOT RUN and ask coordinator for an existing
supported two-qubit fixture; do not silently replace it with the one-qubit trial.
See the source-backed candidate in [dependencies](dependencies.md). An accessible
alternative must preserve the assessed construct and full permitted functionality.

Circuit source: [TaskView](../../../src-main/frontend/src/components/TaskView.tsx),
[EpisodeFields](../../../src-main/frontend/src/components/EpisodeFields.tsx),
[EpisodeSnapshot](../../../src-main/frontend/src/components/EpisodeSnapshot.tsx).
