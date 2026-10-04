# Engine integrity repair implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task. Execution is native in the current session, as requested by the user.

**Goal:** Repair misleading engine output and capability drift before adding the organ council.

**Architecture:** Preserve the engine/worker/evidence boundaries. The available adapter becomes explicitly illustrative, with a conservative fluid bookkeeping demonstration and no disease/drug response prediction. Capability reporting and feasibility use the same strict manifest; genuine Pulse/replay feasibility remains unverified.

**Tech stack:** Python 3.12, Pydantic 2, pytest, SQLite; existing local environment and isolated audit dependencies.

**Spec:** `docs/superpowers/specs/2026-10-03-physiological-twin-design.md`, clarified by `docs/audit-2026-10-04.md` and repairs R0–R1 in `docs/gemini-handoff-2026-10-04.md`.

## Global constraints

- Research/education sandbox; no clinical prediction or medical clearance claim.
- Only the engine owns numerical state; no paid API dependency.
- Missing measurements remain missing; ignored inputs and illustrative constants are disclosed separately.
- Generic CKD/diabetes cannot enable renal artery stenosis or manufacture measured labs.
- Evidence-only medication does not change numerical quantities.
- Current development output is illustrative, never Pulse-derived or a verified trace.
- Preserve original audit evidence; record new results separately.

## Review focus

- Reinitialization after a different patient must clear every prior action/state.
- Unrecognized names containing a known drug substring must remain unsupported.
- Zero dose, wrong route/unit and nonfinite time cannot create or corrupt a numerical action.
- Splitting time advancement and restoring a mid-infusion state must not change fluid bookkeeping.
- A successful illustrative lifecycle or importable unrelated `pulse` module must not pass genuine physiology feasibility.

## Task 1: baseline and regressions

**Files:** `artifacts/audit/pre-repair-source.zip`, `tests/test_illustrative_engine.py`, `artifacts/implementation/engine-integrity-progress.md`.

**Interfaces:** Existing adapter/worker constructors remain callable; tests pin observable behavior, not private formula constants.

- [x] Preserve the current source snapshot and existing XML/hash evidence.
- [x] Add regressions including: zero-dose saline leaves all quantities unchanged; 500 mL bolus adds exactly 0.5 L only to illustrative total fluid; 600 mL infusion over 60 seconds adds 0.3 L in 30 seconds and stops at completion; CKD and diabetes never manufacture disease-specific vitals; unknown drug substrings cannot be accepted; invalid route/unit/time rejected.
- [x] Run tests explicitly with the bundled interpreter and `.audit-deps`, storing RED results in `artifacts/implementation/engine-integrity-red.xml`.

```python
engine.initialize({"conditions": ["CKD"], "context": {"diabetes": True}})
before = engine.snapshot()["quantities"]
engine.apply_event({"ingredient_id": "saline", "dose": 0, "unit": "mL",
                    "route": "intravenous", "simulation_time": 0})
engine.advance(60)
assert engine.snapshot()["quantities"] == before
```

## Task 2: truthful adapter and strict shared capabilities

**Files:** `simulation/adapter.py`, `simulation/capabilities.py`, `simulation/capability-manifest.json`, `simulation/coverage.py`.

**Consumes:** Existing `initialize`, `apply_event`, `advance`, `snapshot`, `serialize`, `restore` signatures.

**Produces:** `IllustrativeEngineAdapter`, `load_manifest() -> CapabilityManifest`; snapshot quantities all tagged illustrative; exact canonical action aliases; illustrative/evidence/unsupported scenario report. Legacy class import is a compatibility alias with no reference provenance claim.

- [x] Make the manifest strict and retain engine/version/mode/provenance fields across JSON round trips.
- [x] Remove drug/disease response formulas. Reset baseline state every initialization; expose ignored inputs and explicit model assumptions.
- [x] Implement bolus and finite-duration fluid add/remove bookkeeping, only changing total fluid. Validate action unit/route/time/dose; reject insufficient removal volume rather than silently clamp. All medication handling is nonnumerical and exact-ID based.
- [x] Make advancement a pure function of initial volume and admitted fluid schedules at absolute time. Invalid operations do not partially mutate state.
- [x] Use versioned canonical checkpoint envelope with digest; validate content, mode/version and event schedules before mutation.
- [x] Coverage consumes the strict active manifest, preserves CKD as CKD context, separately lists illustrative aspects, and blocks unsupported executable interventions.

```python
assert engine.snapshot()["quantities"]["heart_rate"]["capability"] == "illustrative"
assert CoverageGate().evaluate_intervention("norepinephrine")["numerical_effect"] is False
assert CoverageGate.CONDITION_ALIASES["ckd"] == "CKD"
```

## Task 3: integrate honest worker/feasibility semantics

**Files:** `simulation/worker.py`, `simulation/feasibility_check.py`, `backend/schemas/domain.py`, existing feasibility/coverage tests.

**Consumes:** Task 2 manifest and adapter.

**Produces:** Worker uses truthful active adapter; config persisted with actual adapter identity; failed engine returns cannot emit applied-action success. Feasibility separates illustrative lifecycle pass from genuine engine gate failure.

- [x] Ensure worker/config engine identity comes from the actual adapter; record model assumptions rather than accepting default Pulse claims.
- [x] Honor coverage rejection and false initialization/advance/action returns; use existing failure event path. Do not assert that this resolves the later atomicity/concurrency defects.
- [x] Adapter outputs schema-aligned `is_valid` and `numerical_error_code`; update domain metadata defaults so bare quantities/configuration cannot accidentally claim Pulse.
- [x] Rewrite feasibility to test actual evidence-only numerical isolation, exact restore and provenance; `gate1_passed` remains false for the illustrative adapter.
- [x] Update old tests whose expectations asserted false Pulse/CKD capabilities; preserve/strengthen their intent. Record the corrected acceptance expectation.

```python
result = run_feasibility()
assert result["illustrative_lifecycle_passed"] is True
assert result["physiology_engine_verified"] is False
assert result["gate1_passed"] is False
```

## Task 4: verification and handoff ledger

**Files:** `artifacts/implementation/engine-integrity-*.xml`, `docs/implementation-progress.md`, `docs/initial-conditions.md`, `docs/architecture-explanation.md`.

**Consumes:** Tasks 1–3 public contracts.

**Produces:** Tested first repair tranche with accurate remaining-blocker list.

- [x] Run all existing/new default-collected tests, plus relevant independent audit probes A01–A08/A13 and controls with interface-equivalent updates where required.
- [x] Run real feasibility CLI; record expected exit 1 for unverified physiology and successful illustrative lifecycle separately.
- [x] Review all changed files against five review-focus cases. Resolve relevant regressions before marking this tranche complete.
- [x] Document real-engine integration, full snapshot immutability/strict domain validation, persistence, worker concurrency, checkpoint worker schedule and evidence review as remaining work.

No publishing, deployment or external messaging is included. Work happens in the existing user-selected directory; a recoverable source ZIP replaces git/worktree operations because this directory has no repository.

