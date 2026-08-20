# 006: UI redesign implementation

Status: proposed

Owner: unassigned (written for handoff to an independent implementing agent)

Created: 2026-08-19

Target branch: `arv-person-a-assessment` at `3ff1878` (verify with `git log -1 --oneline` before starting; re-ground if the head moved)

Design authority: `docs/learnlens/ui-redesign-decisions.md` (approved 2026-08-19). Where this
plan and that document disagree, the design document wins for visual decisions and this plan
wins for sequencing and scope. Read it in full before Step 1.

## Outcome

Replace the frontend's current visual system (dark violet/cyan, three incompatible stylesheets,
no shared components, no router) with the approved LearnLens design system: light "academic
instrument" identity, design tokens + CSS Modules, a shared component library with Radix-backed
interaction primitives, lucide icons, IBM Plex typography, URL routing with guards and a 404,
and the "certainty grammar" status system. All existing behaviour, data contracts, and API
calls are preserved. Outside this plan: score/leaderboard/gamification *behaviour* changes
(roadmap 005 Steps 3 and 5), provisional-result reveal (decision D-01), mounting the orphaned
analytics dashboard (roadmap Step 6), dark theme, and any backend change.

## Source evidence

| Claim or rule | Evidence | Requirement |
| --- | --- | --- |
| Navigation is a `useState<ScreenId>` string; no router, URLs, or 404 | `src-main/frontend/src/App.tsx:41`, `src/components/AppShell.tsx:7-18`, dispatch at `App.tsx:229-290` | NFR26 (consistent navigation) |
| Runtime deps are only react, react-dom, react-markdown, remark-gfm | `src-main/frontend/package.json:22-27` | — |
| Three incompatible CSS systems ship together | `src/styles.css` (3,487 lines, dark), `src/features/analytics/analytics.css` (light, orphaned), `src/features/feedback/feedback.css` (own palette; light fragment at `:50-55` patched by `styles.css:1791-1825`) | NFR26 |
| `PASS`/`INCOMPLETE` render as lowercase body text with no visual treatment | `src/features/assessment/assessmentReviewPresentation.ts:11-13`; usages `AssessorReviewPanels.tsx:161,266-269` | D2 §14.4, AT24 |
| Result and lifecycle enums are already correct and typed | `src/features/assessment/types.ts` (`assessmentResultValues`, `resultStateValues`) | AC19, D1 §3.2 |
| Focus-trap logic duplicated three times; one native `window.confirm` | `TaskView.tsx:133-163`, `AdminWorkspace.tsx:27-62`, `useReviewDialogFocus.ts`; `AdminWorkspace.tsx:148` | NFR4 |
| Seven CSS classes used in JSX are defined nowhere | `App.tsx:317` `page-actions`, `TaskView.tsx:436` `circuit-builder`, `StudentsView.tsx:139` `search-field`, `EducatorDashboard.tsx:151,158`, `CourseEditor.tsx:451,693` | — |
| `var(--accent)` is referenced but never defined, so review-list selection border is invalid | `src/features/assessment/assessment.css:135-138` | — |
| Visible product name is QuantumLearn in 7 user-facing places; e2e asserts the heading | `index.html:6-7`, `LoginScreen.tsx:43,74,99`, `App.tsx:35,220`, `AdminWorkspace.tsx:212`, `CourseEditor.tsx:493,695`, `StudentsView.tsx:89`, `e2e/person4.e2e.ts:21` | Docs name the product LearnLens; `CLAUDE.md:16` forbids mass code rename |
| Learner-visible Bloom enum prints raw (`ANALYSE (CONCEPTUAL)`) | `TaskView.tsx:319` | D2 §14.3 "plain language"; D1 §3.5 `ANALYSE` spelling |
| Evidence criteria are silently ellipsis-truncated | `styles.css:1471-1477` (`.source-list span`) | D2 §14.3 (conditions must be shown) |
| Feedback `validated` vs `safe_fallback` classes are undefined, states look identical | `FeedbackPanel.tsx:178`; no stylesheet defines either modifier | FR18, PD7 |
| Text sizes go down to `.54rem` (≈8.6px) | `styles.css:2400-2405` and ~dozens more | NFR4 (zoom, contrast), AC17 |
| Hardcoded 70% score threshold colours the submission banner | `TaskView.tsx:517-528` | Conflicts with roadmap 005 Step 3; behaviour retained this plan |
| XP leaderboard with rank colours is public ranking | `AnalyticsView.tsx:174`, `styles.css:2860-2862` | FR25 conflict; behaviour retained this plan, flagged |
| Fonts load via render-blocking Google `@import` | `styles.css:1` | NFR7 |
| Existing unit/e2e suites that must stay green | `src/test/App.test.tsx`, `src/test/CourseEditor.test.tsx`, `src/test/person4E2E.test.tsx`, `src/features/**/**.test.tsx?`, `e2e/person4.e2e.ts`, `e2e/assessment-review.e2e.ts` | CI `quality.yml` frontend job |
| Accessibility base to preserve: skip link, dialog semantics, reduced motion, semantic tables | `AppShell.tsx:84,124`, dialogs with `role="dialog" aria-modal`, `styles.css:3477-3486`, `useReducedMotion.ts` | NFR4, AC17 |

## Current-state trace

Input: user actions inside a single-page React 19 app served by Vite; session established via
`/api` (dev proxy `vite.config.ts:9-14`). Permission checks: role gating happens client-side in
`App.tsx:229-290` for *presentation only*; services enforce scope server-side (unchanged by
this plan). State: per-screen `useEffect` fetch pairs (duplicated `load()` pattern, e.g.
`EducatorDashboard.tsx:55-89`). Output: screens listed in the design doc §6. Audit: none in the
frontend (unchanged). Failure handling: `ScreenState` error panel; feedback pipeline announces
stages via `aria-live` (`FeedbackStatus.tsx:8-14`).

Gaps: no URL state (back/forward broken); status semantics `MISSING` for results;
`analytics` feature `UNVERIFIED` against the live app (mounted only in `src/e2e/main.tsx` and
`src/test/person4E2E.test.tsx`); contrast of `--subtle #73758e` at sub-12px sizes `CONFLICTING`
with NFR4.

## Proposed design

Full rationale lives in `docs/learnlens/ui-redesign-decisions.md`. Implementation contracts an
independent agent needs:

**New directories and conventions**

```
src/styles/tokens.css        # every custom property from design doc §4; ONLY place hex is allowed
src/styles/globals.css       # reset, base type, focus ring, .sr-only, skip link, reduced motion
src/components/ui/<Name>/    # <Name>.tsx + <Name>.module.css + <Name>.test.tsx
src/routes.tsx               # route objects + guards
```

- CSS Modules everywhere new; no new selectors in `styles.css`. `styles.css` shrinks each step
  and is deleted in Step 9. Hex literals outside `tokens.css` fail review.
- Tokens: copy the exact palette, type scale, spacing (4–64), radii (4/8/12/999), two shadows,
  and motion durations from design doc §4.1–§4.3. Minimum rendered font size 12px.
- Fonts: `@fontsource/ibm-plex-sans` (400/500/600), `@fontsource/ibm-plex-serif` (400/600),
  `@fontsource/ibm-plex-mono` (400/600), imported in `main.tsx`; delete the Google `@import`.
- Icons: `lucide-react`, per-icon imports only; fixed status pairings from design doc §4.4.
- New runtime deps (exact set — do not add others without recording why):
  `react-router-dom`, `lucide-react`, `@radix-ui/react-dialog`, `@radix-ui/react-alert-dialog`,
  `@radix-ui/react-select`, `@radix-ui/react-dropdown-menu`, `@radix-ui/react-tabs`,
  `@radix-ui/react-toast`, `@radix-ui/react-tooltip`, plus the three `@fontsource` packages
  (dev-time assets).

**Component API contracts** (props may grow, not shrink; keep names exact so screen migrations
are mechanical):

- `Button`: `variant: 'primary'|'secondary'|'quiet'|'danger'`, `size?: 'sm'|'md'`,
  `loading?: boolean`, native button props. Renders `<button>`; loading sets `aria-busy` and
  disables.
- `ResultSeal`: `result: 'PASS'|'INCOMPLETE'`, `lifecycle: ResultState`, `size?: 'sm'|'lg'`.
  PASS = solid `--affirm` + `CheckCircle2`; INCOMPLETE = outlined `--attend` + `CircleDot`;
  lifecycle sub-line text per design doc §4.5; `PROVISIONAL` uses the dashed border variant.
  Never renders any other value (throw in dev on unknown input). INCOMPLETE copy never says
  "fail" (AT19).
- `LifecycleTag`, `JudgeTag`, `SystemTag`, `StepText`: one component per namespace per design
  doc §4.5. `JudgeTag` accepts only `'APPROVED'|'REJECTED'`; `SystemTag` only
  `'SUCCEEDED'|'FAILED'`. These are separate exports, not variants of one chip — the
  type system enforces D3 §5.2 namespace separation.
- `EstimateChip`: outlined-only; requires `uncertainty: string` (non-optional) so an estimate
  can never render without its uncertainty wording (NFR27).
- `Field`: `label`, `help?`, `error?`, `required?`; wires `id`/`aria-describedby` to its child
  input; error text has `role` only via the child's `aria-invalid` + described-by (no alert
  spam).
- `Dialog`/`AlertDialog`: Radix wrappers; `AlertDialog` requires `confirmLabel`,
  `tone?: 'default'|'danger'`, and an optional `reason` textarea slot (assessor actions
  require a reason — D2 §14.2).
- `Meter`: `value`, `max`, `label` (visible), never percentage-only display; used for
  non-formal progress only.
- `Histogram`: takes counts; renders SVG bars + a visually-available `<table>` equivalent
  (D2 §8.4).
- `PageHeader`: `eyebrow?`, `title`, `description?`, `actions?`. Title is `h1`, serif.

**Routing contract** — route table exactly as design doc §5, implemented with
`createBrowserRouter`. Guards read the existing session/role state from `App.tsx`; an
unauthorised hit on a valid path renders the same 404 component as an unknown path (no
existence leak). The task workspace becomes `/student/tasks/:taskId`; leaving with an unsaved
draft intercepts via `AlertDialog`. `sessionState === 'checking'` renders the loading state at
any route. Vite dev server needs no change (SPA fallback already in `nginx.conf`; verify
`vite preview` serves fallback for e2e).

**Copy contract** — visible product name becomes "LearnLens" (title, meta description, login,
shell wordmark, empty-state copy). Internal identifiers, package names, and API strings are
untouched (`CLAUDE.md:16`). en-AU spelling; Bloom always via a plain-language map:

```ts
// src/components/ui/bloom.ts — single source for learner-facing Bloom wording (D2 §5.1)
REMEMBER: 'Remember — recall the relevant facts', UNDERSTAND: 'Understand — explain the idea',
APPLY: 'Apply — use the method in a task', ANALYSE: 'Analyse — break the material into parts
and relate them', EVALUATE: 'Evaluate — judge against the criteria', CREATE: 'Create — produce
new work from the parts'
```
(Exact descriptor wording: take from D2 §5.1 table at `docs/02-pass-incomplete-bloom-assessment-spec.md:86-93`, not from this sketch.)

**Behaviour-preservation rule** — every step's tests must show the same data, states, and
actions before and after. Three knowingly non-compliant behaviours are restyled but not
removed (their removal is roadmap work): the score submission banner (`TaskView.tsx:517-528`)
keeps its logic but loses success/failure colour coding (neutral surface, text unchanged); the
leaderboard keeps rendering but loses gold/silver/bronze celebration styling (plain table);
XP/gamification stays visible pending FR25 work. Record all three in the PR body.

## Step 1: Dependencies, tokens, fonts, global base

Files:

- `src-main/frontend/package.json`, `package-lock.json`
- `src-main/frontend/src/styles/tokens.css` (new)
- `src-main/frontend/src/styles/globals.css` (new)
- `src-main/frontend/src/main.tsx` (import fontsource + new styles before `styles.css`)
- `src-main/frontend/src/styles.css` (remove line 1 Google `@import` only)

Changes:

- [ ] Install the exact dependency set from Proposed design; commit lockfile.
- [ ] Create `tokens.css` with every token from design doc §4.1–§4.3, each colour annotated
      with its intended pairing (e.g. `/* text on --surface, AA 4.5+ */`).
- [ ] Create `globals.css`: `color-scheme: light` on `:root` is NOT yet set (the app is still
      dark until Step 9); scope new globals under a `.ll-root` class applied by new components'
      top-level containers so old and new systems co-exist during migration.
- [ ] Add a token contrast test `src/styles/tokens.test.ts`: parse `tokens.css`, compute WCAG
      contrast for the documented pairs (`--ink`/`--surface`, `--ink-muted`/`--surface`,
      `--accent`/`--surface`, each status hue on white and on its wash), assert ≥4.5:1 for
      text roles. Adjust token values until it passes; update the design doc if any value
      shifts.
- [ ] Self-host fonts; delete the Google Fonts `@import` (`styles.css:1`). Old UI falls back
      to its stacks — acceptable for the migration window; note any visual diff in the PR.

Edge and failure cases:

- Fontsource import order must precede any CSS using the families, else FOUT in dev only —
  not a failure, but keep imports at the top of `main.tsx`.
- If a token cannot reach AA at its role, darken the token, never shrink its role.

**Acceptance:** `npm run lint`, `npm test` (including new `tokens.test.ts`), and
`npm run build` pass; `rg "fonts.googleapis" src` returns nothing.

## Step 2: Static UI primitives

Files (each `src/components/ui/<Name>/<Name>.tsx` + `.module.css` + `.test.tsx`):

- `Button`, `IconButton`, `TextLink`, `Tag`, `Card`, `PageHeader`, `DescriptionList`,
  `Field`, `Input`, `Textarea`, `Checkbox`, `RadioGroup`, `SearchInput`, `Skeleton`,
  `EmptyState`, `ErrorState`, `Meter`, `Stepper`, `Prose`, `CodeBlock`
- `src/components/ui/index.ts` barrel

Changes:

- [ ] Implement each to the API contracts above, styled only from tokens.
- [ ] Tests per component: renders accessible name; variants apply the right class; `Field`
      wires `label[for]`/`aria-describedby`; `Meter` exposes `role="meter"` (or
      progressbar with `aria-valuetext`) and its visible label; disabled/loading states set
      the right ARIA.
- [ ] `Meter` and `Tag` must not accept or render percentage-formatted formal-result data —
      no special code needed, but add a test asserting `ResultSeal` (Step 3) is the only
      component that accepts `AssessmentResult` (type-level: no other component imports it).

Edge and failure cases:

- Long labels wrap, never truncate (the `.source-list` truncation bug class must not recur);
  add a wrap test for `DescriptionList` with a 300-char value.

**Acceptance:** `npm test` green with new component tests; `npm run build` passes;
no component's module.css contains a hex literal (`rg -n "#[0-9a-fA-F]{3,8}" src/components/ui --glob '*.css'` → empty).

## Step 3: Status system components

Files:

- `src/components/ui/ResultSeal/`, `LifecycleTag/`, `JudgeTag/`, `SystemTag/`, `StepText/`,
  `EstimateChip/` (same triplet layout)
- `src/components/ui/bloom.ts` (+ `bloom.test.ts`)

Changes:

- [ ] Implement the six status components per the API contracts and design doc §4.5, importing
      result/lifecycle types from `src/features/assessment/types.ts` (do not redeclare enums).
- [ ] `ResultSeal` tests: PASS renders solid affirm treatment with icon + visible text "Pass";
      INCOMPLETE renders outlined attend treatment, icon, text "Incomplete", and copy contains
      no "fail" substring (AT19); `PROVISIONAL` renders dashed variant and the sub-line
      "Provisional — awaiting assessor review"; `CONFIRMED` renders "Confirmed by assessor";
      information is conveyed by text+icon (assert both present), not colour alone (AT24).
- [ ] `JudgeTag` test: renders only in-namespace values; TypeScript rejects `PASS` (compile
      test via `// @ts-expect-error`).
- [ ] `EstimateChip` test: refuses to render without `uncertainty` (required prop, compile
      test) and always shows it.
- [ ] `bloom.ts`: map every Bloom process to the D2 §5.1 plain-language descriptor; test
      asserts en-AU `Analyse` spelling and full coverage of the enum.

Edge and failure cases:

- Unknown/legacy result value (e.g. old `FAIL` from a stale payload): `ResultSeal` renders
  nothing and logs a dev-only warning — it must never invent a third visual state (AC19).

**Acceptance:** named tests `ResultSeal.test.tsx`, `JudgeTag.test.tsx`,
`EstimateChip.test.tsx`, `bloom.test.ts` pass in `npm test`.

## Step 4: Radix interaction primitives

Files:

- `src/components/ui/Dialog/`, `AlertDialog/`, `Select/`, `DropdownMenu/`, `Tabs/`,
  `Toast/`, `Tooltip/`

Changes:

- [ ] Wrap each Radix primitive with system styling; `AlertDialog` supports `tone="danger"`
      and an optional required-reason textarea slot (validation: confirm disabled until
      non-empty when the slot is marked required).
- [ ] Tests: open/close via keyboard (Escape), focus moves into dialog on open and returns to
      trigger on close (Radix behaviour — assert it, don't reimplement it), `Select` is
      operable with arrow keys and exposes `aria-expanded`.
- [ ] Do not delete the legacy focus-trap code yet — old dialogs still use it until their
      screens migrate.

Edge and failure cases:

- Nested dialog (task exit-intercept over task page) must restore focus correctly — covered
  by an integration test in Step 6.

**Acceptance:** new primitive tests pass; `npm run build` passes; bundle still builds with
tree-shaken Radix (spot-check `dist` for absence of unused Radix packages is not required —
per-package installs make this structural).

## Step 5: Routing and shell

Files:

- `src/routes.tsx` (new), `src/main.tsx`, `src/App.tsx`
- `src/components/AppShell.tsx` + new `AppShell.module.css`
- `src/components/NotFound.tsx` (new)
- `src/test/App.test.tsx` (update), new `src/test/routing.test.tsx`
- `index.html` (title/meta → LearnLens)

Changes:

- [ ] Introduce `createBrowserRouter` with the exact route table from design doc §5. Keep
      `App.tsx`'s session and data logic; replace the `ScreenId` dispatch (`App.tsx:229-290`)
      and the `ScreenId` union (`AppShell.tsx:7-18`) with routes. Navigation callbacks become
      `<NavLink>`s.
- [ ] Guards: anonymous → redirect to `/login`; authenticated on `/login` → role home;
      role/assignment mismatch on a valid path → render `NotFound` (no redirect, no leak);
      unknown path → `NotFound` with a "Go to your workspace" action.
- [ ] Redesign `AppShell` per design doc §4.7 on the new tokens (this shell is `.ll-root`;
      the page canvas inside becomes light from this step onward — screens migrate one by one
      but share the light shell; verify each unmigrated screen remains readable on the light
      canvas and record any interim visual debt in the PR).
- [ ] Shell a11y: `header` landmark at all widths, sidebar toggle gains
      `aria-expanded`/`aria-controls`, scrim is `aria-hidden` and out of tab order (close via
      Escape and toggle), keep skip link and `main` landmark, `aria-current="page"` via
      `NavLink`.
- [ ] Wordmark: lens glyph + "LearnLens" in Plex Serif; brand element is a link to the role
      home (real navigation now, not a hash trick — replaces `AppShell.tsx:86`).
- [ ] Update `index.html:6-7` title and meta description to LearnLens.
- [ ] `routing.test.tsx`: student cannot reach `/admin` (sees not-found), deep link to
      `/assessor/review` works with assignment, unknown URL 404s, back/forward moves between
      screens.

Edge and failure cases:

- Session check in flight: any route renders the loading state, then resolves to guard result.
- `vite preview` / e2e static serving must fall back to `index.html` for deep links — verify
  `npm run e2e:build && npm run e2e:serve` serves `/student` (the e2e harness config
  `vite.e2e.config.ts` may need `appType: 'spa'` confirmation).

**Acceptance:** `routing.test.tsx` and updated `App.test.tsx` pass; manually: `npm run dev`,
sign in, use browser back/forward across three screens, refresh a deep link — all land
correctly (record as a checked manual step in the PR).

## Step 6: Student surface — login, overview, task workspace, feedback

Files:

- `src/components/LoginScreen.tsx` + new module css
- `src/components/StudentDashboard.tsx` + module css
- `src/components/TaskView.tsx` → `src/routes` page at `/student/tasks/:taskId` + module css
- `src/features/feedback/*` (`FeedbackPanel.tsx`, `FeedbackStatus.tsx`, children) + new
  `feedback.module.css`; delete `src/features/feedback/feedback.css`
- Delete from `styles.css`: login/backdrop/orb/atom sections, task-modal styles, the
  feedback override block (`styles.css:1791-1825`)
- `src/test/App.test.tsx`, `src/features/feedback/FeedbackPanel.test.tsx` (update)

Changes:

- [ ] Login per design doc §6: single card, LearnLens wordmark, remove fake stats
      (`LoginScreen.tsx:62-66`), backdrop animation, and role-selector visual noise (keep the
      demo-workspace action as a quiet secondary button; keep any role selection the backend
      demo flow actually requires — verify against the sign-in API call before removing
      controls, and keep whatever the request needs).
- [ ] Student overview: continue-card hero, pathway list in certainty grammar (solid ✓ /
      outlined available / dashed + lock icon locked — no opacity fade), estimates via
      `EstimateChip`, XP module visually demoted (plain Card at the bottom, no hero
      placement), fixed achievement icon set keyed by type (replaces server-string glyph at
      `StudentDashboard.tsx:142`).
- [ ] Task workspace becomes a routed page: three-region layout per design doc §6; pre-attempt
      disclosure as `DescriptionList` (D2 §14.3 fields); Bloom via `bloom.ts` (fixes raw enum
      at `TaskView.tsx:319`); criteria wrap fully (kills `.source-list` truncation);
      submission banner keeps logic but neutral styling (see Behaviour-preservation rule);
      unsaved-draft exit intercept via `AlertDialog`; delete the modal focus-trap copy
      (`TaskView.tsx:133-163`) — page navigation replaces it.
- [ ] Feedback rebuild on tokens: distinct `validated` (Card + "AI-generated" Tag + sources)
      vs `safe_fallback` (attend-wash notice, "Feedback unavailable") states; system Buttons
      replace unstyled natives (`FeedbackPanel.tsx:141,161`, `FeedbackReportButton.tsx:65,86`);
      keep `aria-live` stage narration exactly as-is.

Edge and failure cases:

- Refresh mid-task must reload the task from `:taskId` (existing fetch logic reused).
- Feedback fallback state keeps the submission visible and offers next steps (FR18).
- A task with no assessment block renders without the disclosure panel (existing optionality).

**Acceptance:** updated `App.test.tsx` and `FeedbackPanel.test.tsx` pass; new test asserts the
two feedback states render visibly differently (distinct accessible labels); manual keyboard
run-through of open task → respond → submit → feedback recorded in the PR (AT24 path).

## Step 7: Assessor surface — setup and review queue

Files:

- `src/features/assessment/AssessorSetup.tsx`, `AssessorSetupPanels.tsx`,
  `AssessorReviewQueue.tsx`, `AssessorReviewPanels.tsx` + new module css per component;
  delete `src/features/assessment/assessment.css`
- `src/features/assessment/assessmentReviewPresentation.ts` (presentation mapping)
- Tests: `AssessorSetup.test.tsx`, `AssessorReviewQueue.test.tsx` (update),
  `e2e/assessment-review.e2e.ts` (update selectors only if markup changed them)

Changes:

- [ ] Setup: Fieldset grouping per D2 §14.1, system `Select` for Bloom process/knowledge/
      purpose with plain-language option labels (values unchanged on the wire), "Bloom is not
      a score" as a system Notice, pass-rule preview in serif, self-attestation via system
      `Checkbox` inside a proper label layout.
- [ ] Review queue master-detail per design doc §6: filters as system Selects; rows carry
      `LifecycleTag` + small `ResultSeal`; selection state uses accent-wash (fixes dead
      `var(--accent)` at `assessment.css:135-138`); criterion decisions as MET (solid) /
      NOT MET (outlined attend) / NOT EVALUABLE (dashed) chips; evidence sections as Cards;
      formatted `DescriptionList` with a mono "view raw" disclosure replaces
      `JSON.stringify` (`AssessorReviewPanels.tsx:32-36`).
- [ ] Actions differentiated: Confirm primary, Return/Override/Withhold secondary, Void
      danger; all via `AlertDialog` with required reason (replaces bespoke dialog +
      `useReviewDialogFocus.ts`, which is deleted here).
- [ ] Replace `readable()`-as-presentation for results with the status components
      (`readable()` may remain for non-status strings).

Edge and failure cases:

- Empty queue and filtered-to-empty render `EmptyState` with the active filters named.
- Override dialog: confirm stays disabled until reason text present (existing rule, now
  enforced by `AlertDialog` slot).

**Acceptance:** both assessment unit suites pass updated; `npm run test:e2e` passes
`assessment-review.e2e.ts`; screenshot of the review detail pane attached to the PR showing
ResultSeal + criterion chips.

## Step 8: Educator and admin surfaces

Files:

- `src/components/EducatorDashboard.tsx`, `CourseEditor.tsx`, `StudentsView.tsx`,
  `AnalyticsView.tsx`, `AdminWorkspace.tsx` + module css each
- New `src/components/ui/LineChart/` and `BarList/` (shared, replace the two hand-rolled SVG
  charts at `EducatorDashboard.tsx:16-44` and `AnalyticsView.tsx:6-28`)
- Tests: `CourseEditor.test.tsx` (update), new chart component tests

Changes:

- [ ] Educator overview: metric Cards, `LineChart` with table equivalent, at-risk list via
      `EstimateChip` (inference framing), activity feed as quiet timeline; define real
      containers for the undefined `engagement-panel`/`risk-panel` classes.
- [ ] Course editor: `Stepper`, `Field`s, upload cards with processing state; version history
      visible; fix undefined `field--short`/`hero-atom--small` usages; LearnLens copy at
      `CourseEditor.tsx:493,695`.
- [ ] Students: system `Table`, `SearchInput` (defines the missing `search-field`), risk as
      outlined chips, bulk-select with system `Checkbox`; LearnLens copy at
      `StudentsView.tsx:89`.
- [ ] Analytics: `LineChart`/`BarList`; radar chart removed, replaced by per-concept evidence
      list with `EstimateChip`s (same data, list presentation); leaderboard kept but as a
      plain system Table without rank celebration styling (see Behaviour-preservation rule).
- [ ] Admin: system Tables/Cards/Fields across the four sections; `AlertDialog` replaces the
      three bespoke dialogs and `window.confirm` (`AdminWorkspace.tsx:148`); delete the
      `AdminWorkspace` focus-trap copy (`AdminWorkspace.tsx:27-62`); labelled system range
      controls; LearnLens copy at `AdminWorkspace.tsx:212`.

Edge and failure cases:

- Charts with a single data point or all-zero series render axes + table without NaN layout.
- Bulk-select none → notify action disabled with visible reason.

**Acceptance:** `CourseEditor.test.tsx` updated and passing; new `LineChart.test.tsx` asserts
the table equivalent renders the same series values; `rg "window.confirm" src` → empty.

## Step 9: Consolidation, deletion, and light cutover

Files:

- Delete `src/styles.css` (all remaining sections migrated or dead by now)
- `src/styles/globals.css` (promote to unscoped; set `color-scheme: light`)
- `src/components/ScreenPrimitives.tsx` (delete `Icon` sprite + `ProgressRing`; keep or
  migrate `ScreenState` into `ui/`)
- `src/features/analytics/analytics.css` → retokenised `analytics.module.css` (dashboard
  stays unmounted; `AnalyticsDashboard.test.tsx` and `person4E2E.test.tsx` keep passing)

Changes:

- [ ] Migrate any remaining `styles.css` consumers found by
      `rg -n "className=\"" src | grep -v module` sweep; then delete the file.
- [ ] Retokenise the orphaned analytics feature (third palette dies) without mounting it.
- [ ] Repo-wide guards: `rg -n "#[0-9a-fA-F]{6}" src --glob '*.css' --glob '!*tokens.css'` →
      empty; `rg -n "font-size: 0?\.[0-6]" src --glob '*.css'` → empty (12px floor);
      `rg "QuantumLearn" src index.html` → empty (code/package identifiers like
      `quantumlearn-web` in `package.json` are intentionally untouched).
- [ ] Delete `useReducedMotion` only if unused after migration; otherwise keep (verify).

Edge and failure cases:

- Any orphan selector discovered in the sweep gets migrated or proven dead (component search)
  before deletion — no "probably unused" deletions.

**Acceptance:** `npm run lint`, `npm test`, `npm run build` all pass with `styles.css`
deleted; the three `rg` guard commands return empty; app boots visually complete in light
theme (screenshot set in PR: login, student overview, task, review queue, admin).

## Step 10: End-to-end, accessibility evidence, and naming assertion

Files:

- `e2e/person4.e2e.ts` (heading assertion `:21` → LearnLens; selectors for routed nav)
- `e2e/assessment-review.e2e.ts` (selector updates if needed)
- New `e2e/a11y-routes.e2e.ts`: axe scan per route in the table (login, student, task,
  progress, educator, courses, students, analytics, assessor setup, review, admin ×4, 404)

Changes:

- [ ] Update e2e flows for routed navigation (URLs instead of nav-click state).
- [ ] Axe-per-route spec: fail on any serious/critical violation; record the report artefact.
- [ ] Keyboard-only e2e for the result path: open task → submit → reach result/feedback →
      activate review control, all via keyboard (AT24 automated portion).
- [ ] Run the full frontend suite from `.github/workflows/quality.yml` and record results.

Edge and failure cases:

- Axe on the unmounted analytics dashboard stays covered by the existing
  `person4E2E` harness, not the route spec.

**Acceptance:** `npm run lint`, `npm test`, `npm run build`, `npm run test:e2e` all pass
locally with output recorded; manual keyboard + zoom (400%) pass on login, task, result, and
review screens recorded as checked items with findings; anything not run is written `NOT RUN`.

## Full verification

Per step: the named tests in each acceptance line. Release: the frontend job commands from
`.github/workflows/quality.yml` (re-read it before claiming a run):
`npm run lint` · `npm test` · `npm run build` · `npm run test:e2e`, all from
`src-main/frontend`. Manual checks that automation cannot prove (record individually, mark
`NOT RUN` until done): keyboard-only full task loop; 400% zoom reflow on task and review
screens; screen-reader pass on ResultSeal and feedback stages; cross-browser spot check
(latest Chrome, Edge, Firefox, Safari — NFR18). Backend checks are unaffected but run the
backend job once at the end to prove no contract drift (`uv run --frozen ruff check .` etc.
per `quality.yml`) — expected no-op.

## Migration and rollback

Not applicable — no stored data, API contract, or migration changes. UI-only. Rollback is
`git revert` of the PR; no compatibility window needed. The one persisted-state consideration:
bookmarked deep links only exist after this ships, so there are no legacy URLs to honour.

## Risks and controls

| Risk | Impact | Control and proof |
| --- | --- | --- |
| Mixed old/new styling during Steps 5–8 looks broken | Confusing interim UI on the branch | `.ll-root` scoping; per-step screenshots; branch not merged until Step 9 cutover completes |
| Routing change breaks e2e selectors en masse | CI red, slow reviews | Step 5 lands routing + updated `App.test.tsx` together; e2e updated in Step 10 before merge; run `npm run test:e2e` locally at Steps 5, 7, 10 |
| Restyling accidentally changes behaviour (score banner, leaderboard, gamification) | Smuggled product-rule change without approval | Behaviour-preservation rule; tests assert same data/actions; the three retained conflicts named in the PR body with their roadmap owners |
| Token values fail AA in practice | NFR4 gate failure | `tokens.test.ts` contrast assertions + axe-per-route in Step 10 |
| `ResultSeal` shown for a value outside PASS/INCOMPLETE | AC19 violation | Dev-throw + render-nothing behaviour with test; type-level restriction |
| Radix版本 API drift vs wrappers | Build breakage later | Pin exact versions in package.json; wrappers isolate Radix imports to `ui/` |
| Deleting `styles.css` orphans a selector still in use | Broken screen post-cutover | Step 9 sweep command + per-screen screenshots before deletion |
| Serif/sans/mono roles applied inconsistently by the implementing agent | Identity dilution | Design doc §4.2 role table is normative; reviewer checks headings=serif h1/prose, sans UI, mono provenance |

## Missing-data report

| Gap | Owner | Blocking effect |
| --- | --- | --- |
| D-01 provisional-result visibility (`docs/learnlens/known-limits-and-deferred-decisions.md`) | Product owner + assessors | None on this plan: the no-value "Under review" state is the shipped default; the reveal variant is designed but must not be enabled here |
| FR25 gamification/leaderboard removal policy (roadmap 005 Steps 3/5) | Product owner | Leaderboard/XP/score banner are restyled-not-removed in this plan; their removal needs its own plan step |
| Exact final token hex values | Implementing agent via `tokens.test.ts` | Values in design doc §4.1 are AA-checked intents; small shifts to pass contrast are authorised and must be written back to the design doc |
| Demo role-selector backend dependency | Verify at Step 6 against the sign-in request | If the demo flow requires an explicit role field, keep a minimal control; do not guess |
| Manual screen-reader/browser evidence environments (D-12) | Accessibility/ops owners | Step 10 manual checks recorded locally; formal NFR evidence remains `NOT RUN` for release claims |

## PR mapping

Implementation PRs must mirror the step checklists and acceptance lines above, name the three
retained behaviour conflicts (score banner, leaderboard, gamification default) with their
roadmap owners, attach the screenshot set, and record every command result verbatim including
`NOT RUN` items. Recommended split: PR A = Steps 1–4 (system, no visible change), PR B =
Steps 5–8 (shell + screens), PR C = Steps 9–10 (cutover + evidence); a single PR is
acceptable if reviewers prefer one pass. Test-judge and both reviewer verdicts are required
before any ready-for-review claim, per `.agents/workflows/change-delivery.md`.
