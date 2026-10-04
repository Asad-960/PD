# PDTT Implementation Plan

> Original review-first plan. The user subsequently authorized implementation in this chat. Execution status and deviations are recorded in `docs/rebuild-progress.md`; unchecked clinical gates remain unresolved.

> 2026-10-04 update: the user narrowed the visible gender control to Male/Female and requested an immediate hackathon-ready educational demonstration. The implemented 3D scene uses HuBMAP anatomical meshes and deterministic condition-linked visual cues. The PDF now leads with four-organ rule signals. These are **not** clinical organ-safety calculations; the numerical physiology and validation gates below remain open. The backend still accepts older stored gender values for report compatibility.

**Date:** 2026-10-04

**Goal:** Build a neat patient-and-medication workflow that produces a truthful four-organ assessment, a realistic body visualization, graphs where supported, and a downloadable report explaining every conclusion.

**Architecture:** Keep the existing FastAPI backend, simulation worker, append-only run storage, and observer council. A verified numerical engine owns physiology; evidence rules interpret supported facts; the frontend visualizes stored results. Animation, graphs, and PDF all consume the same versioned assessment.

**Tech stack:** Existing Python/FastAPI/Pydantic/SQLite and Next.js/React/TypeScript. Plan Three.js for the body scene, a maintained chart library for time series, Lucide for controls, and ReportLab for backend PDF generation. Add dependencies only during the relevant implementation phase.

**Specification:** The user's workflow in this conversation, refined below using the four documents in `scenarios - conditions/`. This root document defines the proposed behavior and implementation order. Existing technical plans remain historical context; reconcile their status with current code before executing tasks.

## 1. Intended Behavior

The primary screen is a patient intake form. The user enters a list of medications to administer, problems affecting each of the four systems, age, gender, blood-pressure issues, and an optional patient name. The app requests additional measurements only when the selected calculation or evidence rule needs them.

The workflow is:

1. Enter patient information.
2. Select conditions for the heart/circulation, kidneys, liver, and lungs.
3. Add medications, their doses, routes, and administration schedules.
4. Review entered information, missing requirements, and assessment coverage.
5. Start the assessment after validation succeeds.
6. Watch the body animation synchronized with the assessment timeline.
7. Read the structured report and available graphs.
8. Download that same report as a PDF.

Starting requires an explicit command after review. Editing submitted information creates a new assessment; it does not alter the previous result. The app must never replace patient inputs with a preset without showing that change.

### Success Means

- All requested inputs exist and reach the backend without substitution.
- Conditions are selectable by system and retain their specific subtype and severity.
- The medication list supports multiple drugs and preserves each administration.
- Every result explains what was checked, what was found, why, and what could not be assessed.
- The animation feels anatomically credible and matches the available data.
- The screen, graphs, and exported PDF agree for the same run.
- Unsupported conditions, drug combinations, or measurements never become fabricated normal results.

## 2. Current State and Gaps

These are observations from reading the repository, not a fresh test certification:

| Area | Current implementation | Required change |
|---|---|---|
| Patient intake | `backend/api.py` creates a patient aged 62, female, 72 kg | Accept and persist the entered profile |
| Medication input | Presets or positional `custom_actions` lists | Typed medication rows with catalogue validation |
| Conditions | Strings and limited context | Source-linked, structured selections for all four systems |
| BP input | No complete intake workflow | Explicit BP history/status and optional measured readings |
| Physiology | `IllustrativeEngineAdapter`; most responses are unmodeled | Verify an appropriate engine and its actual scenario coverage |
| Organ findings | Existing observer council and small evidence registry | Reviewed rules with exact applicability and missing-data behavior |
| Visualization | Static body image and event workbench | Synchronized anatomical scene and useful playback controls |
| Report | Findings/events displayed separately | One canonical report with explanations, graphs, and PDF export |

The active adapter currently illustrates fluid amounts and records selected medication exposures without numerical drug-response prediction. Its capabilities must remain visible until actual coverage is demonstrated. Existing audit and progress documents describe different stages of repair; reproduce relevant checks against the current files before deciding what remains broken.

## 3. Inputs and Validation

### Patient Information

| Input | Requirement | Behavior |
|---|---|---|
| Patient name | Optional | Blank is accepted; use the generated patient identifier in the report |
| Age | Required | Explicit value and unit; numerical eligibility follows the selected engine's verified population |
| Gender | Required response | Include an option to decline disclosure; preserve the response without using it to infer physiological parameters |
| Physiological sex parameter | Conditional | Ask separately if an engine or equation requires it; disclose its use and allow missing/unknown to limit that assessment |
| Body mass | Conditional, in kg | Required for any selected model, dose expression, or urine-output calculation that uses weight |
| Current medications | Explicit list or none known/unknown | Separate ongoing medication exposure from the planned administration list |
| Allergies | Explicit list or none known/unknown | Preserve allergen and reaction; assess only documented catalogue relationships |
| Baseline measurements | Conditional | Store value, unit, observation time, source, and missingness |

Do not silently assume normal labs, average body mass, physiological sex, or absence of allergies. If an engine initializes model defaults, record those separately as model assumptions rather than patient measurements. Optional name must not affect calculations.

### Conditions for the Four Systems

Each system requires an explicit response: **no known problem**, **one or more known conditions**, or **unknown/not assessed**. No known problem is a history response, not proof that the organ is functioning normally.

For each selected condition, store a stable condition ID, system, display name, subtype, severity/stage when known, relevant history, and supplied supporting measurements. Allow multiple conditions per system. If severity is unknown, retain unknown rather than assigning a disease-wide default risk.

The supplied documents define the condition vocabulary and proposed mechanisms. They do not establish that the installed engine models every listed condition or that every proposed threshold is clinically verified.

| System | Source | Condition scope to catalogue |
|---|---|---|
| Cardiovascular | `scenarios - conditions/Document1.pdf` | Hypertension, CAD/prior MI, heart failure type/class, prior CABG/PCI/stents, arrhythmias, valvular disease, peripheral arterial disease, congenital disease; separately catalogue acute complications |
| Renal | `scenarios - conditions/Renal_Agent_Framework.docx` | All condition entries across primary renal disease and systemic contributors, including AKI categories, CKD, diabetic/hypertensive kidney disease, glomerular disease, infection, obstruction, vascular disease, and congenital conditions |
| Hepatic | `scenarios - conditions/Hepatic_Agent_Data_Report (1) (1).docx` | Drug-induced injury, viral/metabolic/alcohol-related disease, autoimmune/biliary/genetic disease, cirrhosis/portal hypertension, acute failure, congestion/ischaemia, encephalopathy, and tumours |
| Respiratory | `scenarios - conditions/Respiratory Agent Architecture.pdf` | COPD, asthma/airway obstruction, hypoxemia, hypercapnia/acidosis, pulmonary edema, and referenced systemic contributors such as sepsis |

Catalogue every source entry during Phase 1, distinguish pre-existing conditions from observed complications and systemic context, and retain document section/page references. Cross-organ context should reference one underlying condition rather than duplicate diagnoses in several systems. CKD must never be mapped to renal artery stenosis.

### Blood Pressure

Collect an explicit BP-related status: no known issue, hypertension, hypotension, another documented issue, or unknown. For hypertension, retain controlled/uncontrolled/unknown and severity when supplied. Permit dated systolic and diastolic readings in mmHg, with measurement context and source.

BP history and measured BP are different facts. A history selection does not generate a pressure value. Share the canonical hypertension condition with the cardiovascular section so the two controls cannot contradict each other. Check reading units, finite values, and systolic/diastolic consistency; source clinical interpretation separately from input plausibility checks.

### Medications to Administer

Use searchable catalogue selections, with an add/remove row workflow. Each row contains:

- Normalized active ingredient and selected product/formulation where relevant.
- Dose value and compatible unit; concentration if volume must be converted to ingredient amount.
- Route permitted for that product and supported by the assessment.
- Administration time relative to the run, and bolus or infusion duration/rate.
- Repeat schedule if applicable, expanded into explicit events with stable IDs.

At least one complete planned medication is required for this workflow. Reject unknown identifiers, blank fields, nonpositive doses, invalid units/routes, nonfinite numbers, and schedules outside the requested horizon. Do not invent therapeutic dose ceilings; reviewed catalogue constraints and engine constraints must be explicitly distinguished.

Flag accidental duplicate rows and overlapping administrations for review while allowing intentional repeats. Examine pairwise interactions where evidence exists, and disclose unassessed combinations. Independent single-drug warnings do not establish combined-drug safety or predict mixture effects.

### Before Starting

Frontend checks provide immediate field errors; the backend repeats authoritative validation. A preflight response lists errors, required missing facts, supported calculations, evidence-only checks, and unsupported requests. Block the requested numerical simulation when essential inputs or model capabilities are absent. Permit a clearly scoped partial evidence assessment only after the user explicitly chooses that mode on the review screen.

## 4. Calculation and Evidence Requirements

"Perfect calculations" must become an evidence-based release standard: documented formulas and units, verified implementation, reference comparisons, numerical tolerances, traceable inputs, and independently reviewed scope. Passing software tests alone does not establish patient-specific clinical accuracy.

### One Owner of Physiology

- One numerical engine owns the shared state and advances time.
- Cardiovascular, renal, hepatic, and respiratory observers read immutable snapshots.
- Observers explain cross-organ relationships without changing physiological values.
- Every quantity identifies its unit, source, coverage, and simulation time.
- Every finding records its observed inputs, predicate outcomes, rule/model version, source references, missing information, and limitations.

Retain the existing coverage categories: `engine_simulated`, `evidence_only`, `illustrative`, and `unsupported`. Identify exact recorded replay as an execution mode with trace provenance; do not treat replay as a computation for arbitrary new inputs.

### Numerical Engine Gate

Verify the actual installed engine/version with initialization, condition mapping, drug administration, time advancement, and repeatable output. Establish a per-scenario matrix of supported ingredients, formulations, routes, doses, populations, conditions, measured inputs, outputs, and combinations. Verify baseline stabilization and model limitations before accepting a scenario.

Pulse is a candidate, not a guarantee of coverage. Its published patient methodology describes population and initialization restrictions, and its drug methodology documents model assumptions. Confirm the installed version against these sources rather than assuming age, BP, or every drug/condition can be simulated: [Pulse patient methodology](https://pulse.kitware.com/_patient_methodology.html), [Pulse drug methodology](https://pulse.kitware.com/_drugs_methodology.html).

If no suitable numerical engine is available, the initial assessment can report reviewed evidence and explicit gaps. Keep the requested numerical simulation as an unmet capability; changing labels or adding moving curves does not complete that requirement.

### Verification Standard

- Check dose, concentration, amount, and infusion-rate conversions with dimensional tests.
- Compare calculations against independently derived reference cases and reviewed sources.
- Define output-specific tolerances and solver convergence checks before accepting numerical comparisons.
- Confirm identical inputs, engine version, configuration, and seed reproduce results within declared tolerances.
- Test same-time administrations, repeated doses, schedule boundaries, interruption, invalid snapshots, and stale data.
- Audit that each patient input is used by the relevant model/rule or explicitly reported as unused.
- Evaluate evidence only after the relevant exposure occurs; future doses cannot trigger current exposure findings.
- Keep qualitative warnings available when their own premises are sufficient, while marking missing quantitative personalization separately.
- Do not convert missing evidence, no matching rule, or unsupported coverage into a normal assessment.

Reference ranges and clinical thresholds require source verification, population applicability, timing, and qualified domain review. The supplied documents contain proposals and potentially inconsistent thresholds; resolve them before enabling affected rules. A short run cannot imply long-term kidney or liver outcomes unless that timescale is actually modeled.

## 5. Body Animation and Graphs

After successful preflight, show preparation progress followed by the body scene as authoritative snapshots become available. The animation must explain drug administration, circulation, and the involvement of the four systems without presenting conceptual mechanisms as measured events.

Use an anatomically credible, licensed body/organ asset in a full-width Three.js scene. Show the heart, lungs, liver, and kidneys in recognizable positions, with restrained organ selection/highlights and route-specific administration markers. General circulation or breathing can be explanatory animation; patient-specific rate, flow, clearance, injury, or concentration changes require corresponding supported data.

Provide play/pause, replay, seek, speed, camera reset, and organ selection. Playback speed changes viewing speed only. Tie labels, highlights, charts, and displayed findings to one selected simulation timestamp. Distinguish playback pause from pausing a live backend run. For incomplete/stale data, stop extrapolating and show the last valid time.

Provide a static view for reduced motion, WebGL failure, and limited devices. Check desktop/mobile framing, text fit, contrast, keyboard access, meaningful accessible labels, and nonblank canvas rendering. The scene must leave room for report data and controls without overlap.

Graphs use stored series, with time and unit axes, medication markers, data-source labels, and valid reference bands where verified. Potential panels include BP/heart rate, oxygen saturation/respiratory rate, renal variables, hepatic markers, and drug concentration only when modeled. Missing or unsupported series display an explicit unavailable state. Never draw a flat normal line or invented concentration curve to fill space.

## 6. Report and PDF

Use the familiar structure of a laboratory report while titling it **Medication and Multi-Organ Simulation Report**. Identify actual entered measurements separately from model outputs; simulated values must not appear to be laboratory test results.

The report contains:

1. Patient identifier, optional name, demographics as entered, run ID, date/time, and completion status.
2. Submitted medications with doses, units, routes, and schedule.
3. Conditions, BP history/readings, supporting measurements, and unknown information.
4. Assessment scope and numerical/evidence coverage.
5. Summary findings for all four systems and reviewed medication interactions.
6. Per-finding explanation: observed facts, rule/model, result, reasoning, references, and missing facts/limitations.
7. Available measurement/model tables with values, units, time, provenance, and applicable ranges.
8. Supported graphs and event timeline.
9. Explicit assumptions, unsupported checks, uncertainty where quantified, and engine/rule/data versions.

Use outcomes such as **concern identified**, **no concern identified within assessed scope**, and **unable to assess**. Severity and confidence/coverage are separate attributes. Explain favorable findings only for checks actually performed; never force the report to say the regimen is fine.

Generate a versioned `AssessmentReport` from the persisted run and a fixed event cursor. Both the screen and PDF use it. Completed runs have final reports; cancelled, failed, or still-running runs may export clearly marked partial reports describing the available time interval. Store report identity/version so later evidence updates cannot silently rewrite old conclusions.

Render a real PDF on the backend with selectable text, repeated table headings, readable chart labels, page numbers, consistent margins, and working source links. Download with a safe filename and `application/pdf`. Confirm PDF content and numbers match the canonical report and inspect rendered pages for clipping, missing graphs, and blank pages. An omitted name must not break rendering.

Keep identifiable information local in the current deployment, exclude it from routine logs and URL parameters, and sanitize user text in the UI/PDF. Decide retention and deletion behavior before enabling use with real patient records.

## 7. File and Interface Plan

Paths below are proposed implementation locations, not files created by this planning task. Extend existing contracts and services before adding parallel systems. Follow `frontend/AGENTS.md` and the installed Next.js documentation during frontend work.

| Files | Responsibility |
|---|---|
| `backend/schemas/domain.py` | Extend profile/condition contracts while preserving strictness, missingness, and immutable run inputs |
| `backend/schemas/intake.py` (new) | Typed intake, medication plan, and preflight results |
| `backend/catalogue/conditions.json`, `drugs.json`, `registry.py` (new) | Source-linked selections, product/unit/route metadata, and support mappings |
| `backend/intake.py` (new) | Normalize intake, expand schedules, validate requirements, and map to existing contracts |
| `backend/api.py` | Catalogue/preflight endpoints and submitted-profile run creation |
| `simulation/adapter.py`, `capabilities.py`, `capability-manifest.json`, `coverage.py`, `feasibility_check.py` | Explicit capabilities and verification of each active adapter |
| `simulation/pulse_adapter.py` (conditional new file) | Real Pulse bridge only if the feasibility gate selects and verifies Pulse |
| `simulation/worker.py`, `backend/database/writer.py`, `schema.py`, `backend/events/types.py` | Persist complete inputs, schedule, snapshots, findings, and lifecycle history |
| `backend/evidence/models.py`, `registry.py`, `rules.json`, `sources.json`, `backend/council.py` | Reviewed evidence evaluation and organ interpretation |
| `backend/reports/models.py`, `service.py`, `pdf.py` (new) | Canonical report model, stored-run assembly, and PDF rendering |
| `frontend/lib/contracts.ts`, `api.ts` (new) | Typed server contracts and request/error handling |
| `frontend/components/intake/` (new) | Patient fields, organ conditions, BP, medication rows, and preflight review |
| `frontend/components/simulation/` (new) | Body scene, timeline, and controls driven by backend results |
| `frontend/components/report/` (new) | Report sections, charts, and PDF download |
| `frontend/app/page.tsx`, `globals.css`, `frontend/public/models/` | Workflow composition, responsive styling, and licensed anatomy assets |
| `tests/`, `frontend/tests/` (new where needed) | Intake, coverage, numerical/reference, evidence, report, and browser acceptance checks |

Proposed API boundaries:

```text
GET  /api/catalogue/conditions -> versioned condition catalogue
GET  /api/catalogue/drugs      -> versioned medication catalogue
POST /api/preflight           -> errors, missing inputs, eligible modes, coverage
POST /api/runs                -> accepts typed submitted intake; returns run_id
GET  /api/runs/{run_id}/report -> canonical AssessmentReport
GET  /api/runs/{run_id}/report.pdf -> PDF for the same report version
```

Retain the existing run, findings, events, stream, and control endpoints. Preflight does not start a worker. Run creation repeats validation and binds catalogue/model/evidence versions; it cannot trust a prior browser approval against changed data. Unknown preset IDs should produce an error rather than silently selecting another scenario.

## 8. Implementation Order and Gates

### Phase 1: Establish the Catalogue and Verified Scope

**Files:** source documents, new `backend/catalogue/`, existing capability files, new `docs/condition-coverage.md` and `docs/calculation-validation.md`.

- [ ] Inventory every condition, scenario, proposed mechanism, required input, and threshold in the four source documents with section/page references.
- [ ] Assign stable IDs, aliases, system relationships, subtype fields, and unknown-state behavior; reconcile duplicate BP/condition entries.
- [ ] Mark source proposals separately from verified evidence and installed numerical capabilities.
- [ ] Verify the candidate engine's deployment feasibility and actual supported population/scenario matrix.
- [ ] Define an initial verified drug/scenario set while retaining unsupported catalogue entries as explicit gaps.
- [ ] Record reference cases, tolerance rationale, and evidence-review requirements before numerical claims are enabled.

**Gate:** Every source entry is accounted for; each selected assessment has a documented supported mode. No assumption of universal drug or disease support.

### Phase 2: Fix the Submitted-Patient Backend Path

**Files:** domain/intake contracts, `backend/intake.py`, catalogue registry, API, persistence contracts, `tests/test_intake.py` and `tests/test_intake_api.py`.

- [ ] Add focused contract checks before changing parsing: age/gender/name persistence, unknown organ/BP states, multi-condition selections, and malformed drug rows.
- [ ] Replace positional action arrays with typed rows and explicit schedule expansion.
- [ ] Add unit-aware, route-aware validation and conditional measurement requirements.
- [ ] Add preflight, and remove the fixed 62/female/72 kg substitution from submitted runs.
- [ ] Persist the exact normalized profile, medication plan, catalogue versions, and coverage decision.
- [ ] Verify API validation, retry idempotency, and rejection before run creation for missing numerical prerequisites.

**Gate:** Submitted facts survive request-to-storage round trips, errors identify the specific field, and invalid/unsupported numerical requests cannot start workers.

### Phase 3: Verify Calculations and Organ Findings

**Files:** selected adapter, capability files, worker, evidence registry/models/sources/rules, council, existing simulation/evidence/persistence tests plus reference fixtures.

- [ ] Re-run the existing suite and relevant audit probes against current code; classify current failures before repairing them.
- [ ] Implement only verified adapter mappings and preserve explicit ignored/missing-input reporting.
- [ ] Verify reference calculations, conversion invariants, solver tolerances, timing, stable initialization, reproducibility, and conservation where applicable.
- [ ] Review each enabled rule's exact source, applicability, units, missing facts, exposure timing, and severity language.
- [ ] Add source-backed interaction checks and cross-organ explanations without giving observers ownership of numerical state.
- [ ] Confirm unsupported/future exposures do not change physiology or produce false favorable findings.
- [ ] Verify worker lifecycle, immutable history, event order, and failure/stale-data handling before downstream consumers rely on results.

**Gate:** Enabled numerical outputs meet documented reference tolerances; evidence conclusions are traceable and reviewed. Any outstanding capability stays explicit.

### Phase 4: Build the Intake and Review Experience

**Files:** frontend contracts/API helpers, intake components, page and styles, browser acceptance checks.

- [ ] Build the requested patient, organ, BP, and multi-medication sections with precise controls and clear error states.
- [ ] Add conditional fields from catalogue requirements; preserve entered values across validation errors.
- [ ] Build the review screen with normalized schedule, missing information, supported scope, and explicit partial-assessment selection.
- [ ] Connect real catalogue/preflight/run endpoints, prevent duplicate submissions, and handle connection or backend errors.
- [ ] Verify keyboard use, mobile layout, long names, multiple drug rows, and that changed input requires a new run.

**Gate:** A user can enter and review a complete case without hidden defaults or raw technical action arrays.

### Phase 5: Build the Report and Graphs

**Files:** report models/service, API report endpoint, report/chart components, `tests/test_reports.py`.

- [ ] Define and assemble the versioned report from a persisted run/cursor, including final or partial status.
- [ ] Add organ and medication findings with reasoning, observed values, references, and coverage.
- [ ] Add available charts with shared time selection, units, administration markers, and missing-data states.
- [ ] Verify input/run isolation, report repeatability, unsupported-combination disclosure, and correct handling of failed/cancelled runs.

**Gate:** Every displayed assertion traces to recorded inputs, results, or reviewed evidence. No unsupported series is plotted as a prediction.

### Phase 6: Build the Realistic Body Scene

**Files:** simulation components, anatomy assets, page/styles, browser visual checks.

- [ ] Integrate and record the licence for an anatomical model with recognizable four-system positioning.
- [ ] Add route markers, organ selection, readable labels, playback controls, and snapshot-driven effects.
- [ ] Link scene, charts, and findings to one timestamp; keep conceptual animation visibly distinct from computed response.
- [ ] Add reduced-motion/static fallback and reliable disconnected/stale states.
- [ ] Verify desktop/mobile screenshots, canvas pixels, asset loading, motion, seeking, camera framing, and control interactions.

**Gate:** The scene is nonblank, usable, anatomically credible, synchronized, and truthful about the available calculations.

### Phase 7: Add and Verify PDF Download

**Files:** backend PDF renderer, PDF endpoint, frontend download control, `tests/test_report_pdf.py` and rendered report fixtures.

- [ ] Generate PDFs from the same `AssessmentReport` used by the UI.
- [ ] Include readable tables, explanations, sources, graphs where available, and clear partial/coverage labels.
- [ ] Verify PDF values/version against report JSON and correct headers/filename on download.
- [ ] Render and inspect short/long reports, absent name, many medications, unknown fields, unavailable charts, and multipage tables.

**Gate:** A downloaded PDF faithfully contains the current report, with no clipped content or fabricated lab results.

### Phase 8: End-to-End Acceptance

**Files:** integration/browser tests, validation fixtures, relevant project documentation.

- [ ] Complete cases with no known organ problems, multiple conditions, BP issues, multiple medications, missing optional name, and missing essential model inputs.
- [ ] Exercise catalogue drugs/conditions lacking numerical support and combinations without interaction evidence.
- [ ] Test disconnect/reconnect, pause/resume/cancel, failed calculation, replay, new input after completion, and PDF download.
- [ ] Confirm the same run/time/version is used throughout body animation, graphs, findings, and export.
- [ ] Review documented clinical/model scope independently of engineering test results; record unresolved coverage and evidence gaps.

**Gate:** The complete requested workflow passes reproducible engineering checks, and the release description states exactly which assessments have been validated.

## 9. Review Focus

| Failure mode | Required behavior | Owning phases |
|---|---|---|
| mg versus mcg, dose versus rate, volume without concentration | Reject incompatible inputs or perform a tested, explicit conversion | 2, 3 |
| Age/sex/BP outside numerical model eligibility | Retain entered information; refuse unsupported prediction and explain available scope | 1, 2, 3 |
| Unknown organ state or missing labs | Preserve missingness; allow only independently supported findings | 2, 3, 5 |
| Drug combination with two individual rules but no interaction model | Report individual checks and unassessed combination; no combined safety claim | 3, 5, 8 |
| Animation or PDF using another run or stale cursor | Bind every view/export to run ID, timestamp/cursor, and report version | 5, 6, 7, 8 |

## 10. Verification Commands and Evidence

During implementation, use the existing Windows test runner and frontend build:

```powershell
.\scripts\run_tests.ps1
npm --prefix frontend run build
```

Run adapter feasibility using the project interpreter selected by the test runner. The illustrative probe and genuine-physiology probe must remain distinct:

```powershell
python -m simulation.feasibility_check --illustrative-only
python -m simulation.feasibility_check
```

Before claiming a phase complete, retain relevant test results, model/reference comparisons, evidence-review records, browser screenshots, and PDF render checks. Browser and PDF tooling are added in their own implementation phases. No application tests, numerical validation, or clinical review were performed as part of creating this document.

## 11. Planning Assumptions and Next Review

This is a proposed redesign for review, with the current research/education scope retained until patient-specific validity is established. The core clinical eligibility and model coverage must be settled before promises of numerical outcomes. The intended presentation is a quiet medical workbench with realistic anatomy and a structured report.

The next discussion should settle the initial drug/scenario set, intended users and use, supported age/population range, and acceptable evidence-only behavior when numerical simulation is unavailable. These decisions affect implementation scope; they do not prevent documenting the requested workflow now.

**Original stop point (superseded):** The first request asked for this plan only. The user's subsequent request authorized implementation and starting the app. Engineering delivery does not establish clinical validation or numerical model coverage.
