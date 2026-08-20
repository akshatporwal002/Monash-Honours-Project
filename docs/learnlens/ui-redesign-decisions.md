# LearnLens UI redesign — decisions and system description

Status: approved design direction, not yet implemented

Owner: Arv Surana (design decisions approved in session, 2026-08-19)

Scope: visual identity, component architecture, and URL routing for `src-main/frontend`.
No behaviour, API, data, or backend change is designed here. Where a visual decision
collides with existing behaviour (scores, leaderboard, gamification defaults), the
conflict is flagged with its blocking decision or roadmap step rather than resolved
silently.

Implementation: requires a numbered plan under `docs/plans/` (via `/draft-plan`) before
any code changes. This document is the design authority that plan will cite.

---

## 1. Why a redesign

The current UI is a recognisable AI-default: violet→cyan gradients (`#8b5cf6`→`#22d3ee`)
on near-black `#070711`, animated atom and orb decorations, and glassy gradient panels.
Beyond taste, the execution is not product-grade:

- **Three incompatible visual systems ship together.** The dark app (`styles.css`, 3,487
  lines), a light-themed analytics dashboard (`features/analytics/analytics.css`) that is
  unreachable from the app, and a feedback panel (`features/feedback/feedback.css`) with
  its own hardcoded palette — including a light-mode fragment rendered inside the dark
  task modal, patched over with 35 lines of specificity overrides (`styles.css:1791-1825`).
- **No system, only values.** 86 distinct hex literals alongside 18 tokens, 23+ spacing
  values, 12+ border radii, three unrelated button systems plus native browser buttons
  in the task modal, seven CSS classes referenced in JSX that are defined nowhere, and
  one `var(--accent)` that resolves to nothing (`assessment.css:135`).
- **The most important status in the product has no design.** `PASS` and `INCOMPLETE`
  render as lowercase body text via `readable()`
  (`features/assessment/assessmentReviewPresentation.ts:11`), visually identical to each
  other and to everything around them — while spec D2 §14.4 requires text + icon +
  accessible status semantics.
- **No URLs.** Navigation is a `useState` string in `App.tsx:41`; there is no deep
  linking, no browser back/forward, no 404.

The controlling docs' only visual mandates are calm ones — NFR26 (stable layout, low
visual clutter, small steps, consistent navigation), NFR4/AC17/AT24 (WCAG 2.2 AA,
keyboard, screen reader, zoom, no colour-only meaning). The current aesthetic works
against all of them. The redesign treats those mandates as the brief, not as compliance
overhead.

## 2. Decisions taken (approved)

| # | Decision | Choice | Rationale |
| --- | --- | --- | --- |
| 1 | Product name in UI | **LearnLens** in all visible copy, titles, and wordmark | Aligns UI with every controlling doc. Code, packages, and internal identifiers stay `quantumlearn` per `CLAUDE.md` ("do not mass-rename"). The e2e assertion on the `QuantumLearn` heading (`e2e/person4.e2e.ts:21`) is updated as part of implementation. |
| 2 | Aesthetic direction | **Light-first academic instrument** | Calm, paper-adjacent, reading-first. Best fit for NFR26, long assessor/educator sessions, dense evidence tables, and AA contrast. Dark mode is deferred but the token structure permits it later (§4.8). |
| 3 | Scope | Visual system + shared component library + **URL routing** | A reskin cannot fix a product feel built on three CSS systems and zero shared components. Routing gives the product real URLs, back/forward, deep links, and a 404. |
| 4 | Styling architecture | **Design tokens + CSS Modules for all styling; Radix unstyled primitives for behaviourally hard components only** (Dialog, AlertDialog, Select, DropdownMenu, Tabs, Toast, Tooltip) | Tokens + Modules keep every visual decision ours with zero framework look. Radix supplies focus management and screen-reader behaviour that this codebase currently hand-rolls incorrectly (focus trap copy-pasted three times; `window.confirm` at `AdminWorkspace.tsx:148`; unstyled feedback buttons). WCAG 2.2 AA is a release gate — interaction correctness is bought, visual identity is owned. |

Supporting dependency decisions (owned here, revisitable at plan time):

- **react-router** for routing (decision 3 requires a router; it is the boring, correct
  choice).
- **lucide-react** for icons, imported per-icon. The current 17 hand-drawn paths in
  `ScreenPrimitives.tsx` are inconsistent in optical weight and cannot grow to the set
  the status system needs. Lucide is stroke-based, tree-shakeable, and visually neutral.
- **Self-hosted fonts via `@fontsource`** packages, replacing the render-blocking Google
  Fonts `@import` at `styles.css:1`. No network dependency, stable rendering, better
  first paint.

## 3. Design concept: the instrument, not the poster

**Subject grounding.** LearnLens teaches quantum computing and assesses it through
evidence against Bloom targets. Its intellectual centre is *measurement*: a learner's
state is genuinely uncertain — held as estimates with explicit uncertainty — until a
formal assessment measures it and collapses it to a definite `PASS` or `INCOMPLETE`.
The product spec is unusually explicit that users must always be able to tell
**evidence from inference** (NFR27) and **provisional from confirmed** (D2 §14.4).

**The signature: a certainty grammar.** The one memorable, load-bearing idea of this
design is that *visual certainty encodes epistemic certainty*, everywhere, without
exception:

- **Solid** treatment (filled chips, solid borders, full-strength ink) = observed facts
  and confirmed results. A confirmed `PASS` seal is solid. A recorded submission is solid.
- **Outlined** treatment (transparent fill, 1.5px border) = system inference and
  provisional states. A provisional result seal is outlined. A learner-model estimate is
  always outlined and always carries its uncertainty text.
- **Dashed** treatment = absent or awaited: missing evidence, pending review, empty
  states. The "under review — result withheld" state (D-01 pending) is a dashed outline.

This grammar is not decoration; it is the spec's separation rules (NFR27, D2 §14.5,
D3 §5.2) made visible. It gives the product a distinctive look no template produces,
and every application of it is checkable against a rule.

**Everything else stays quiet.** One accent. No gradients anywhere. No ambient
animation. Hairline borders instead of shadows for structure; shadows only for true
elevation (dialogs, toasts, menus). The current decorative motifs — `.quantum-backdrop`,
`.circuit-line`, `.orb`, `.hero-atom`, the electron-orbit brand mark — are removed
entirely, not restyled. The subject shows up where it is real: circuit diagrams, Dirac
notation in task content, measurement histograms with their data-table equivalents.

**Calibration note.** Current AI-generated design clusters around three defaults: warm
cream + high-contrast serif + terracotta; near-black + single acid accent; and hairline
broadsheet. This design is deliberately none of them: the ground is a near-neutral
bright paper (not cream), the accent is a cyanotype blue (not terracotta), display type
is a technical superfamily (not a fashion serif), and the structural device (certainty
grammar) is derived from the product's own rules rather than applied styling.

## 4. Visual system

### 4.1 Colour tokens

All values are AA-checked intents; exact values are verified against WCAG 2.2 AA
contrast during implementation and may shift by small amounts to pass. No raw hex is
permitted outside the token file.

Verified in implementation by `src/styles/tokens.test.ts`, which computes the contrast
ratio of every documented pairing from the token file itself. One value shifted during
Step 10: `--ink-muted` moved from `#6E7580` to `#626A75` after the axe-per-route scan
found it failing against `--paper` and `--surface-sunken` (it had only been checked
against `--surface`). Those two pairings are now asserted.

**Ground and ink**

| Token | Value | Use |
| --- | --- | --- |
| `--paper` | `#FAF9F7` | Page background |
| `--surface` | `#FFFFFF` | Cards, panels, table bodies |
| `--surface-sunken` | `#F1F0EC` | Wells, code-adjacent areas, table headers |
| `--line` | `#E4E2DC` | Hairline borders, dividers |
| `--line-strong` | `#C8C6BF` | Input borders, emphasised structure |
| `--ink` | `#20242B` | Primary text (blue-black, not pure black) |
| `--ink-soft` | `#4E555F` | Secondary text |
| `--ink-muted` | `#626A75` | Metadata, captions (minimum 12px, AA-checked) |

**Accent — "cyanotype"**

The single interactive hue. Cyanotype is the blueprint blue of scientific documentation
— subject-appropriate, calm, and nowhere near the violet/cyan the app is escaping.

| Token | Value | Use |
| --- | --- | --- |
| `--accent` | `#1A5687` | Links, primary buttons, focus rings, active nav |
| `--accent-strong` | `#134369` | Hover/pressed |
| `--accent-wash` | `#EAF1F7` | Selected rows, active-state backgrounds |
| `--accent-line` | `#B7CEE2` | Selected borders, quiet emphasis |

**Status hues** (always paired with text + icon; never meaning-bearing alone, per D2
§14.4 / AT24)

| Token | Value | Use |
| --- | --- | --- |
| `--affirm` / `--affirm-wash` | `#1D6B4C` / `#E8F3ED` | Confirmed PASS, success confirmations |
| `--attend` / `--attend-wash` | `#7A5200` / `#FBF3E0` | INCOMPLETE, attention, caution notices |
| `--fault` / `--fault-wash` | `#9E2B3E` / `#F9ECEE` | System faults and destructive actions **only** — never a learner result |

Two deliberate rules: **INCOMPLETE is never red.** It is an amber "open" state — the
spec defines it as *not yet complete*, and the feedback rules (D2 §10.2) forbid failure
framing. **Red belongs to the system, not the learner**: request `FAILED`, destructive
dialogs, error states. This enforces the status-namespace separation of D3 §5.2 at the
palette level.

### 4.2 Typography

**IBM Plex superfamily** — Sans (UI and body), Serif (reading prose and outcome
statements), Mono (code, circuits, identifiers, versions). Chosen because it is one
designed system across all three roles, and because its technical heritage is literally
the subject's: Qiskit — which the app teaches — is IBM Quantum's framework. This is a
grounded pairing, not a default (current: Inter + Outfit + JetBrains Mono + a stray
"Cascadia Code" in `feedback.css:28`).

Roles:

- **Plex Sans** — everything interactive and structural: nav, buttons, labels, tables,
  forms, headings at h2 and below.
- **Plex Serif** — where a person reads or is addressed formally: outcome wording, task
  prompts, feedback prose, result explanations, page h1s. The serif marks "this is the
  substance", the sans marks "this is the instrument".
- **Plex Mono** — code, circuit text equivalents, `|00⟩` notation, attempt numbers,
  version and provenance strings, reason codes.

**Scale** (rem, base 16px): `0.75` caption · `0.8125` meta · `0.875` ui · `0.9375` body
· `1.0625` lead · `1.25` h3 · `1.5` h2 · `1.875` h1 · `2.5` display (login only).
**Floor: 12px.** The current stylesheet sets text as small as `.54rem` (≈8.6px); nothing
below 12px survives, which also resolves the zoom/reflow risk flagged against NFR4.

### 4.3 Space, radius, elevation, motion

- **Spacing scale**: 4px base — `4 · 8 · 12 · 16 · 20 · 24 · 32 · 40 · 48 · 64`. These
  ten values replace the 23+ currently in use. No off-scale value without a written
  comment in the token file.
- **Radius scale**: `4px` (chips, tags, inline code) · `8px` (buttons, inputs) ·
  `12px` (cards, panels, dialogs) · `999px` (pills, avatars). Four values replace twelve.
- **Elevation**: structure comes from `--line` hairlines on `--surface`, not shadows.
  Exactly two shadow tokens: `--raise` (menus, popovers) and `--float` (dialogs,
  toasts). The six unrelated shadows and all glow effects are removed.
- **Motion**: 120–160ms ease-out on interactive state changes; 200ms for dialog/toast
  entry. No ambient or looping animation anywhere (removes `circuit-shift`,
  `slow-spin`, `atom-spin`). `prefers-reduced-motion` support is kept and extended.

### 4.4 Iconography

Lucide, 1.75 stroke, sized 16/20/24 via tokens, always `aria-hidden` beside visible
text or labelled when standalone. Status icons are fixed pairings (never improvised):
`check-circle` PASS/confirmed · `circle-dashed` provisional/under review ·
`circle-dot` INCOMPLETE (open, not failed) · `alert-triangle` system fault ·
`eye` observed evidence · `sparkle-off`→ none: AI-generated content is marked with a
text badge ("AI-generated"), not an icon alone (NFR21). Emoji and server-supplied
glyph strings (`StudentDashboard.tsx:142`) are removed; achievements get a fixed icon
set keyed by achievement type.

### 4.5 The status taxonomy (the five namespaces)

D3 §5.2 forbids these five concepts from sharing one status field or visual treatment.
Each gets a visually distinct component; they are never interchangeable:

| Namespace | Values | Component and look |
| --- | --- | --- |
| **Formal result** | `PASS` / `INCOMPLETE` | **ResultSeal** — the largest status element in the system. Sans-serif label + icon inside a sealed rectangle: PASS solid `--affirm`; INCOMPLETE outlined `--attend` with open-dot icon. Lifecycle rendered as a sub-line ("Provisional — awaiting assessor review" with dashed border variant; "Confirmed by assessor" solid), per D2 §14.4. |
| **Result lifecycle** | `NOT_ASSESSED / PROVISIONAL / CONFIRMED / OVERRIDDEN / VOID` | Sub-line of ResultSeal (above); standalone **LifecycleTag** (outlined, ink) in assessor tables. |
| **Quality Judge** | `APPROVED / REJECTED` | **JudgeTag** — small square-cornered mono-font tag, ink on `--surface-sunken`. Appears only in educator/assessor views; visually unrelated to ResultSeal so it can never be read as a learner result (AT20). |
| **Request execution** | `SUCCEEDED / FAILED` | **SystemTag** — mono, `--fault` for failures, confined to technical/admin surfaces. |
| **Submission state** | `NOT_STARTED / DRAFT / SUBMITTED / UNDER_REVIEW / RETURNED / COMPLETED` | **StepText** — plain ink text with a small leading icon, styled as workflow narration, never as an outcome. |
| **Model estimates** | e.g. `DEVELOPING`, uncertainty levels | Always outlined (certainty grammar), always accompanied by uncertainty wording and evidence links; never chip-shaped like a result (D1 §12.3, NFR27). |

### 4.6 Component library

Shared components live in `src/components/ui/` (one folder per component:
`Component.tsx` + `Component.module.css`). Radix-backed where marked.

**Primitives**: Button (primary / secondary / quiet / danger; sm / md; loading state) ·
IconButton · TextLink · Field (label + help + error, wired ids) · Input · Textarea ·
Select ⟨Radix⟩ · Checkbox · RadioGroup · Switch · SearchInput · Tag · StatusChip
(namespaced variants of §4.5) · ResultSeal · Card · PageHeader (eyebrow + h1 + actions)
· DescriptionList · Table (semantic, `scope` attrs, sticky header option) · Tabs ⟨Radix⟩
· Dialog ⟨Radix⟩ · AlertDialog ⟨Radix⟩ (replaces all seven bespoke dialogs and
`window.confirm`) · DropdownMenu ⟨Radix⟩ · Toast ⟨Radix⟩ · Tooltip ⟨Radix⟩ · Skeleton ·
EmptyState · ErrorState · Stepper (wizard) · Meter (labelled, non-score progress) ·
Prose (markdown container) · CodeBlock · CircuitDiagram · Histogram (SVG + mandatory
data-table equivalent, per D2 §8.4's "data table for a histogram").

**Charts**: no chart library. One shared `LineChart` and one `BarList` replace the two
near-duplicate hand-rolled SVG charts; every chart renders an accessible table
equivalent (the pattern `EngagementFunnel.tsx` already gets right). The concept-mastery
**radar chart is removed** — it implies numeric mastery geometry the product forbids
conceptually; it is replaced by a per-concept evidence list with outlined estimate
chips. **No chart may aggregate PASS/INCOMPLETE into an average** (D2 §14.5) — the
design provides count-based alternatives (n confirmed, n provisional, n awaiting).

**Deletions**: ProgressRing conic gradient (replaced by labelled Meter), the
violet→cyan bar gradient in its four duplicated forms, `.quantum-backdrop`, `.orb`,
`.hero-atom`, `.brand-mark` orbit animation, login vanity stats (`LoginScreen.tsx:62-66`).

### 4.7 Layout and shell

The sidebar shell survives, redesigned: `--paper` ground, `--surface` sidebar with a
hairline, 15rem fixed width tokenised once (currently a magic number in four places).
Wordmark top-left: **LearnLens** in Plex Serif semibold, preceded by a small lens glyph
— a circle with a vertical chord, a quiet nod to the ket `|⟩` without literalism. Nav
items are real links (routing, §5) with `aria-current="page"`, icon + label, accent
wash for the active item. User block bottom with role shown as a Tag. Skip link, `main`
landmark, and mobile drawer behaviour are kept; the mobile toggle gains
`aria-expanded`/`aria-controls`, and a proper `header` landmark exists at all widths.

Page anatomy is fixed across every screen (NFR26 "stable layout, consistent
navigation"): PageHeader (eyebrow = section, h1 = page, actions right) → content on a
12-column grid, cards on `--surface`. Density is calm for learner surfaces, compact for
assessor/educator tables.

### 4.8 Theming posture

Light is the only shipped theme. All colour usage routes through the tokens in §4.1 so
a dark theme is a future token swap, not a rewrite. `color-scheme: light` is set
explicitly; no `prefers-color-scheme` behaviour ships until a dark palette passes its
own AA audit.

## 5. Information architecture and routing

react-router replaces the `ScreenId` string state. URL map:

| Route | Screen | Guard |
| --- | --- | --- |
| `/login` | Login | anonymous only |
| `/student` | Student overview | role student |
| `/student/tasks/:taskId` | Task workspace (**route, not modal**) | role student |
| `/student/progress` | Four-area progress view | role student |
| `/educator` | Educator overview | role educator |
| `/educator/courses/new`, `/educator/courses/:courseId` | Course editor wizard | role educator |
| `/educator/students` | Students | role educator |
| `/educator/analytics` | Analytics | role educator |
| `/assessor/setup` | Assessment definition authoring | active assessor assignment |
| `/assessor/review`, `/assessor/review/:recordId` | Review queue / record detail | active assessor assignment |
| `/admin`, `/admin/users`, `/admin/courses`, `/admin/settings` | Admin sections | role admin |
| `*` | 404 with role-aware "go to your workspace" action | — |

Rules: unauthorised access to a valid route renders the same not-found treatment as an
unknown route (no existence leaking, consistent with D2 §13.3's 404 posture); guards
enforce presentation only — authorisation stays server-side (course/learner scope is
enforced in services, per product constraints). The task workspace becomes a page
because it is the product's core activity: it deserves a URL, browser back must not
destroy work (exit intercepts with an AlertDialog when a draft is unsaved), and
full-page focus management is simpler and more robust than a giant modal.

## 6. Screen-by-screen intent

Each redesign below keeps existing behaviour and data unless a conflict is flagged.

**Login** — Split layout retired. One centred `--surface` card on `--paper`: wordmark,
"Sign in to LearnLens", email + password Fields, primary Button, quiet "Load demo
workspace" secondary action. The fake stats block, animated quantum backdrop, and
three-way role selector visual noise are removed (role comes from the account; the demo
affordance remains, styled quietly). Display type: Plex Serif at `2.5rem` maximum.

**Student overview** — The hero is the learner's actual next step: "Continue" card
(serif task title, task-type Tag, submission StepText) leading a pathway list with the
certainty grammar (completed = solid check, available = outlined, locked = dashed +
lock icon, no opacity-fade). Concept estimates render as outlined chips with
uncertainty wording — explicitly *not* rings or percentages. Gamification (XP/level
card) is visually demoted to an optional, collapsed module pending the FR25 conflict
(§8). Notifications become a quiet list; reminder rules unchanged (FR24).

**Task workspace** — Now a route. Three-region page: task brief (serif prompt; the
pre-attempt disclosure panel of D2 §14.3 as a DescriptionList — outcome wording, Bloom
target *in plain language with its descriptor*, required evidence, permitted tools and
support, purpose Tag from BP1, review rule); response area (per task type — MCQ
fieldsets keep their letter chips in mono; code editor keeps the minimal tokenizer,
restyled; circuit builder redrawn in system colours with its text-equivalent panel
promoted, not hidden); and status column (submission StepText, attempt history in mono,
FeedbackPanel). The `.source-list` ellipsis truncation of evidence criteria is removed
— criteria wrap fully; truncating assessment conditions is a correctness bug, not a
style choice. Bloom enums are never shown raw (`TaskView.tsx:319` currently prints
`ANALYSE (CONCEPTUAL)`): always plain-language ("Analyse — break material into parts
and see how the parts relate").

**Feedback panel** — Rebuilt on system tokens (deletes `feedback.css`'s parallel
palette and the specificity-war overrides). `validated` vs `safe_fallback` become
visually distinct: validated = standard Card with "AI-generated" Tag and sources;
fallback = `--attend-wash` notice, "Feedback unavailable", next-step guidance. The two
currently-undefined modifier classes get real definitions. Unstyled native buttons
("Try again", "Report a concern") become system Buttons. The processing stages keep
their `aria-live` narration.

**Result presentation** — The ResultSeal (§4.5) leads; below it, in serif, the D2
§10.1/10.2 structure verbatim: what is shown / what is still needed (dashed-outline
list items — missing evidence is the canonical dashed element) / next step / review
control. Reason codes surface only from the learner-safe list (D2 §9.3). Until D-01 is
approved, the pre-confirmation state is the dashed "Under review — your result will
appear here once reviewed" card and **no result value renders** (Plan 005 Step 2 gate);
both variants are designed so approval is a flag flip, not a redesign.

**Educator overview** — Four metric Cards (counts, not scores), engagement LineChart
with table equivalent, at-risk list using outlined estimate chips (inference, not
fact — NFR27), activity feed as a quiet timeline. The undefined `engagement-panel` /
`risk-panel` classes are replaced by real Card usage.

**Course editor** — The 4-step wizard keeps its structure (it maps to NFR2's 20-minute
setup target) restyled with Stepper, Fields, and file-upload cards showing processing
state (FR5). Version history visible per FR4/D3 §8.4.

**Students / Analytics (educator)** — System Table with sticky header, SearchInput,
risk shown as outlined chips. The **XP leaderboard is removed from the design** — FR25
forbids public learner ranking (§8). Radar chart replaced per §4.6.

**Assessor setup** — The most form-dense screen; compact density, Plex Sans, generous
Fieldset grouping following D2 §14.1's field list. The "Bloom is not a score" notice
becomes a designed system Notice (attend-wash), not a bespoke amber box. Pass-rule
preview renders in serif as learner-visible language. Validation faults block approval
inline (AT4–AT6 patterning). The broken `var(--accent)` selection state is replaced by
the system's accent-wash selected-row treatment.

**Assessor review queue** — Master-detail: filter rail (system Selects), record list
(rows carry LifecycleTag + ResultSeal-small), detail pane with evidence sections as
Cards. Criterion decisions get MET (solid) / NOT MET (outlined attend) / NOT EVALUABLE
(dashed) chips — the certainty grammar doing assessor work. Raw `JSON.stringify` output
(`AssessorReviewPanels.tsx:32-36`) is replaced by a formatted DescriptionList with a
mono "view raw" disclosure. The five actions stop looking identical: Confirm = primary,
Return/Override/Withhold = secondary, **Void = danger**, all through AlertDialog with
the required reason field.

**Admin** — System Tables, Cards, and Fields; `window.confirm` replaced by AlertDialog;
the settings form's range sliders become labelled system controls. (The "Passing score"
setting itself is a Step 3 removal — flagged in §8, not silently deleted by design.)

**Orphaned analytics dashboard** (`features/analytics/`) — Its careful patterns
("Not available" over fake zeros, table equivalents, pseudonymous IDs) are adopted into
the system. The dashboard itself is restyled onto system tokens (deleting the third
palette) but **stays unmounted**; wiring it to a route belongs to roadmap Step 6
(research/analytics governance), not to a visual redesign.

## 7. Voice and copy

Sentence case everywhere. Active voice; buttons name their outcome ("Save changes",
"Publish assessment", "Request review") and keep that name through the flow. en-AU
spelling in all UI copy — `Analyse`, never `Analyze` (D1 §3.5). Learner results speak
the spec's language exactly: "Incomplete — evidence still needed", never fail-framing
(AT19). Errors say what happened and what to do next, without apology or vagueness;
empty states invite the next action. AI content is always labelled "AI-generated" with
its report control adjacent (NFR21). No exclamation marks in system copy.

## 8. Conflicts surfaced (not resolved by this design)

These are behaviour changes the redesign deliberately does **not** smuggle in. Each is
flagged to its owner/gate; the visual system is designed so their later resolution
drops in cleanly.

| Conflict | Current code | Blocking authority |
| --- | --- | --- |
| XP leaderboard with gold/silver/bronze ranks is public learner ranking | `AnalyticsView.tsx:174`, `styles.css:2860-2862` | FR25 forbids it; removal is roadmap Step 3/5 behaviour work. Design contains no leaderboard pattern. |
| Hardcoded 70% score threshold drives a green success banner | `TaskView.tsx:517-528` | Score semantics retire in roadmap Step 3. Design's submission states carry no score colouring; assessed responses show "response saved for assessment". |
| Gamification is on by default | `StudentDashboard.tsx:39-44` | FR25 says optional, off by user choice. Design demotes it visually; the default flip is a behaviour change with its own plan step. |
| Client-side risk cutoffs ignore admin settings | `StudentsView.tsx:8-12` hardcodes `<50%` | Behaviour bug; out of scope here, noted for the implementation plan. |
| Provisional-result visibility | — | **D-01 `PENDING`** (`docs/learnlens/known-limits-and-deferred-decisions.md`). Design ships the no-value "under review" state as default; the reveal variant activates only on recorded approval. |
| `QuantumLearn` e2e heading assertion | `e2e/person4.e2e.ts:21` | Updated alongside the wordmark change in the implementation plan. |

## 9. Accessibility commitments

The design's floor, mapped to gates: WCAG 2.2 AA contrast for every token pairing at
its permitted sizes, verified in the token file itself (NFR4); 12px minimum text and
reflow-safe layouts at 400% zoom; no colour-only meaning — every status element is
text + icon + shape (D2 §14.4, AT24); visible focus ring (`--accent`, 2px, 2px offset)
on all interactive elements; Radix-backed dialogs, selects, and menus for focus and
screen-reader behaviour; the existing skip link, landmarks, `aria-live` feedback
narration, semantic tables, and reduced-motion support are retained and extended
(scrim leaves the tab order, sidebar toggle gains `aria-expanded`). Manual keyboard and
screen-reader checks remain required and separately recorded per D3 §15.3 — this
document claims design intent, not test evidence.

## 10. What implementation will need (for the coming plan)

Sequencing sketch for `/draft-plan` — not a plan itself: (1) tokens + fonts + global
reset; (2) `ui/` primitives with tests; (3) shell + routing; (4) screen migrations in
risk order (login → student → task → assessor → educator → admin); (5) CSS-system
consolidation and deletion of `styles.css` decorative sections; (6) e2e updates
(heading assertion, route-based navigation, axe runs per route). Every step must keep
`npm run lint`, `npm test`, `npm run build`, and `npm run test:e2e` green per
`.github/workflows/quality.yml`. Verification of visual claims: axe per route, contrast
assertions on tokens, and screenshot review; NOT RUN until run.
