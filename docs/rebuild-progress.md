# Execution ledger: implementation.md

Started 2026-10-04 after the user authorized implementation in this chat.

- Baseline: existing backend suite, 193 passed.
- Ruling: implement in the existing directory because it is not a Git checkout; preserve existing files and databases.
- Ruling: retain the existing illustrative adapter for legacy tests/presets. The new patient workflow uses an explicit evidence-and-administration timeline adapter with no invented physiological baselines.
- Ruling: no locally installed Pulse binding was found. Deliver the complete intake, source-linked assessment, animation, report, and PDF workflow while keeping patient-specific numerical physiology unavailable until engine verification; clinical accuracy cannot be established by this rebuild alone.
- Shared interfaces: catalogue -> intake/preflight -> immutable profile and schedule -> worker -> report -> scene/charts/PDF. All consumers bind to run ID and cursor.
- Delivered: 178 source-referenced condition catalogue entries; 12 medication/formulation entries; typed patient and all-four-system intake; BP history/readings; optional measurements and name; allergy/ongoing-medication histories; dose/unit/route/schedule validation; explicit scope review.
- Delivered: submitted-profile persistence instead of fixed demo demographics; repeated and infusion administration arithmetic; idempotent concurrent submission; exact applied-event timeline; partial/final status and run/cursor isolation; immutable report cache and submission-pinned catalogue/evidence/preflight metadata.
- Delivered: Three.js procedural conceptual anatomy, organ selection, generic breathing/pulse motion, administration activity, playback/seek/speed/camera reset, reduced-motion handling/static fallback; Recharts administered-amount graphs; structured report and same-cursor selectable-text PDF with inputs, reasoning, references, measurements, graphs, and limits.
- Delivered: source-linked qualitative ibuprofen/renal-vulnerability, saline/heart-failure, morphine/cirrhosis, morphine/respiratory-hazard checks; exact-ingredient allergy matching. No comprehensive interaction checker or patient-specific dose recommendation is claimed.
- Fresh read-only review found saved-case edit, measurement-review invalidation, planned-versus-applied timeline, and historical-evidence issues. All four were fixed. Additional testing reproduced and fixed concurrent retry duplication, partial-to-final autoplay, PDF history omissions, rounded measurement exports, and stale legacy disclaimers.

## Verification Evidence

- Full backend suite: 208 tests passed; `artifacts/rebuild/backend-release.xml`.
- Frontend production build: successful Next.js compilation and TypeScript check.
- Browser suite: 5 scenarios passed, covering complete intake/report/graphs/PDF, missing name, required inputs, restored editable intake, renewed review after measurement changes, repeated applied events, and mobile overflow checks.
- Scene checks: desktop, 1920px-wide, 390px and 375px-mobile canvas captures are nonblank; playback changes canvas pixels. `artifacts/rebuild/artifact-checks.json` records dimensions and pixel checks.
- PDF: text-content assertions preserve demographics, history notes, full-precision entered values and report ID. The browser-exported four-page report was rendered and visually inspected for readable tables, explanations, references, graphs, pagination, and margins. Screenshots and rendered pages are under `artifacts/rebuild`.

## Explicit Deviations and Remaining Gates

- A genuine numerical physiology engine is not installed/verified. Numerical prediction is blocked, not substituted with assumed healthy baselines or made-up injury scores. The requested perfect clinical calculations cannot be honestly certified.
- The scene is custom procedural conceptual anatomy, not a licensed photorealistic anatomical asset or patient-specific scan. Generic movement and particles do not represent measured circulation, concentrations, or therapeutic response.
- Catalogue coverage exceeds rule coverage. Four-system history is accepted but most disease/drug-specific behavior, combination interactions, pediatric/population eligibility, disease dynamics and clinical normality interpretation remain unavailable.
- Evidence sources were link-checked; independent clinical review and reference-case physiological validation have not occurred. Engineering tests do not satisfy those gates. No "fine/safe" treatment conclusion is generated from absent evidence.
- All original plan checkboxes are retained as requirements, not retrospectively marked complete where clinical or asset gates were deferred.

## Hackathon presentation update, 2026-10-04

- Replaced the procedural body with male/female aligned HuBMAP CCF 3D reference meshes (CC BY 4.0). Condition-linked motion, texture roughness, and evidence-caution glow are deterministic educational cues, not calculated organ physiology.
- The visible form now has one Male/Female gender selector; the existing backend sex parameter is populated from that selection for this constrained demo. Legacy report values remain readable.
- Added backend `visual_responses` with recorded condition mechanism, medication-event cues, and rule-based organ signals. `review_required` means a source-linked caution was found; `no_flag_in_limited_checks` is **not** a safety clearance.
- Replaced the long PDF with a two-page, summary-first organ assessment, row-specific administration amounts, one arithmetic graph per medication, and concise evidence provenance. The on-screen report also shows four organ signals near its top.
- Verification: 210 backend tests, final Next.js production build, targeted desktop and mobile Playwright flows, nonblank canvas screenshots, frame-to-frame pixel difference, and visual PDF rendering. Full clinical validation remains outstanding.

## Local Use

Running frontend: `http://localhost:3000`. API: `http://127.0.0.1:8001`. The user's pre-existing port-8000 server was not stopped. `scripts/start_app.ps1` can start both rebuild servers when their selected ports are free. Data remains in the new v3 SQLite file; original source documents and earlier databases are untouched.

