# Medication Report Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every medication administration, organ association, reviewed caution, chart value, and scene cue internally consistent, while showing numerical organ responses only when an independently checked model supports them.

**Architecture:** Keep the administration ledger as the authoritative calculated quantity in the current patient workflow. Build a per-medicine/per-organ coverage map from the assessment basis pinned to each run, then derive timed scene and text events from committed administrations and findings. Isolate illustrative PK behind a verified calculation/label contract; do not treat it as an organ-response model.

**Tech Stack:** Python/FastAPI/Pydantic/SQLite/pytest; Next.js/React/TypeScript/Three.js/Recharts/Playwright.

**Spec:** `docs/superpowers/specs/physiological-twin-design.md` (especially sections 5–7); audit: `artifacts/backend-calculation-audit-2026-10-05.md` and `artifacts/backend-organ-visual-audit-2026-10-05.json`.

## Global Constraints

- Synthetic patient inputs only; no EHR integration.
- Current patient workflow is evidence-only and `numerical_effect=False` for all 12 catalogue medicines.
- The four visible organs are cardiovascular, respiratory, renal, and hepatic. A catalogue target is not proof of an effect.
- Each numerical quantity has one model owner, units, parameter provenance, scenario coverage, and validation status. Unsupported quantities remain unavailable.
- Preserve the pinned assessment basis so old reports do not silently change when the live catalogue changes.
- On the target laptop, benchmark a stable 30 FPS before claiming smooth scene performance; respect reduced-motion preference.
- Do not interpret catalogue order as physiology; an exact medication allergy is a patient-level safety alert.

## Review Focus

1. A drug with three catalogue targets but one reviewed rule must show three **associations/exposures** and at most one **reviewed caution** for that case. Task 1 tests this.
2. A warning evaluated at the first snapshot must never appear on the body before its finding exists. Task 2 tests this at 0 and 1 seconds.
3. Repeated doses, two active medicines, and a partial/cancelled report must not create future cues or merge distinct event identities. Task 2 tests this.
4. Small-unit doses and very short infusions must retain nonzero values and the correct peak time; saline must not be called a plasma-volume prediction. Task 3 tests these.
5. Seeking, playback, and reduced-motion must keep the scene, text, and chart at the same selected simulation time. Task 4 tests these.

## File responsibility map

| File | Responsibility |
| --- | --- |
| `backend/reports/coverage.py` (new) | Derive per-drug/per-organ association, reviewed-rule, and numerical-model coverage from pinned basis. |
| `backend/reports/safety.py` (new) | Derive exact-allergy patient-level alerts from committed administrations and the entered allergy list. |
| `backend/reports/visual_response.py` | Emit separate exposure and caution events at their actual committed times. |
| `backend/reports/service.py` | Assemble report from pinned basis and cursor-bounded events; call coverage and PK modules. |
| `backend/reports/pk.py` (new) | Own unit-safe illustrative PK math, event-aware samples, and finite-window maximum metadata. |
| `backend/evidence/patient_registry.py` | Keep exact-allergy findings outside organ routing. |
| `backend/reports/pdf.py` | Use the same coverage/timeline/PK facts as the interactive report. |
| `frontend/lib/contracts.ts` | Type the new coverage, safety-alert, and timed cue contracts. |
| `frontend/lib/reportTimeline.ts` (new) | Pure projection of report state at a selected time. |
| `frontend/components/report/ReportView.tsx` | Render coverage, current findings, ledger, and chart values from that projection. |
| `frontend/components/simulation/BodyScene.tsx` | Smoothly render visual cue changes without inventing physiological movement. |
| `tests/test_report_coverage.py`, `tests/test_report_timing.py`, `tests/test_report_pk.py` (new) | Pin backend behavior and calculation regressions. |
| `frontend/tests/workflow.spec.ts` | Exercise synchronized playback, multi-organ coverage, and reduced motion. |

---

### Task 1: Explicit per-organ coverage and patient-level allergies

**Interfaces:** `build_organ_coverage(drugs: dict, rules: dict, capabilities: dict) -> dict[str, dict[str, dict]]`; report field `organ_coverage[drug_id][organ] = {associated, reviewed_rule_ids, numerical_model_id, numerical_status}`. `numerical_status` is `unsupported` for the current assessment adapter. `build_safety_alerts(intake, administrations, drugs) -> list[dict]` returns patient-level exact-ingredient alerts with `event_id`, `time`, `ingredient_id`, and `reported_allergy`; these do not use the organ-only `AgentFinding` schema.

- [ ] Write failing tests in `tests/test_report_coverage.py` for all 12 × 4 drug/organ cells. Pin the current facts: ibuprofen targets renal/cardiovascular/hepatic, but only renal has a reviewed rule; morphine has hepatic and respiratory rules; saline has a cardiovascular rule; amlodipine has one association and zero reviewed rules. Assert all 48 numerical statuses are `unsupported`.
- [ ] Add an allergy regression: changing the order of `target_organs` must not change the location/identity of an exact-ingredient allergy alert. Assert it appears once in `safety_alerts`, remains linked to the administered event, and is absent from organ-response counts.
- [ ] Run `pytest tests/test_report_coverage.py -q` and confirm the new assertions fail against the current contract.
- [ ] Implement `backend/reports/coverage.py`, using only the run's pinned drug/rule maps and adapter capabilities. Move the exact-allergy text match out of `patient_registry.py` and into `backend/reports/safety.py`, using only committed administrations and entered allergies. Update `service.py`, `frontend/lib/contracts.ts`, and intake/report labels so “association”, “reviewed caution”, and “numerical response” are visibly distinct. Do not copy `evidence_available` to every organ.
- [ ] Rerun the focused test and existing patient-workflow tests; update only assertions superseded by the corrected contract. Commit this independently reviewable coverage change.

Example assertion shape:

```python
assert coverage["ibuprofen"]["renal"]["reviewed_rule_ids"] == ["RULE_NSAID_RENAL_HEMODYNAMIC"]
assert coverage["ibuprofen"]["cardiovascular"]["reviewed_rule_ids"] == []
assert coverage["amlodipine"]["cardiovascular"]["numerical_status"] == "unsupported"
```

### Task 2: One clock and causal event identity for report cues

**Interfaces:** `build_visual_responses(..., administrations, findings_timeline)` returns cue records with `time`, `event_id`, `kind`, and `finding_id` (`null` for exposure). An exposure cue is created at administration time for each associated organ. A caution cue is a *separate* record at the earliest committed finding time for each `(event_id, rule_id)`; it is never backdated to the dose. The report includes only events at or before its cursor.

- [ ] Write failing tests in `tests/test_report_timing.py` for CKD + ibuprofen at 0 s: at 0 s the kidney has exposure only; at 1 s it has the source-linked caution and matching finding. Add a second dose at 20 s, another medicine, and a partial/cancelled cursor; assert unique causal event IDs and no future warning, administration, or concentration projection masquerading as recorded state.
- [ ] Run the focused test and confirm the timing and event-identity assertions fail.
- [ ] Change `visual_response.py` to emit exposure and caution records separately. Deduplicate repeated snapshot findings by `(event_id, rule_id)` while retaining the first committed `simulation_time`; do not deduplicate distinct administrations by `rule_id`. Add `causal_event_ids` and `finding_id` to the relevant `frontend/lib/contracts.ts` types. Update `service.py` report assembly and `ReportView.tsx` rendering to use the new cue identity.
- [ ] Re-run focused and patient-workflow tests. Check a report built at an earlier cursor is immutable after later snapshots arrive. Commit the timing change.

Core invariant:

```python
assert caution["time"] == min(f["simulation_time"] for f in findings
                              if caution["event_id"] in f["causal_event_ids"]
                              and caution["rule_id"] == f["rule_id"])
assert caution["time"] >= exposure["time"]
```

### Task 3: Correct or quarantine illustrative PK; retain the ledger

**Interfaces:** `build_illustrative_pk(administrations, drugs, horizon_seconds, cursor_time) -> list[dict]`. Only return a series for a drug/route with a dimensionally valid, documented parameter set; return no saline plasma-volume series. Every series carries `model_id`, `status="illustrative"`, `parameter_source`, `window_start`, `window_end`, `peak_kind="within_window"`, and unrounded internal values. The administration ledger remains available for every medicine.

- [ ] Write failing tests in `tests/test_report_pk.py` using the audited fixtures: morphine 20 mg IV / 250 L displays 80 mcg/L, fentanyl 100 mcg IV stays nonzero, morphine bolus at 30 s peaks at 30 s under the implemented formula, furosemide 10–11 s infusion includes 11 s, ibuprofen's 300 s maximum is labeled “within window”, partial reports stop at their recorded cursor, and saline has no fictitious plasma-volume series.
- [ ] Run focused tests and confirm each old behavior fails. Add explicit dimensional checks (`mg/L` to `mcg/L` multiplies by 1000) and a source/parameter review gate before enabling any illustrative curve in the UI or PDF. If no acceptable parameter source is available, hide that drug's PK curve and show its ledger with “concentration unavailable”.
- [ ] Move the formula from `service.py` into `pk.py`; insert administration times and infusion-end times in the sample grid, use precision until formatting, and calculate the peak from the actual evaluated samples or analytic extremum as appropriate. Define whether a partial view contains recorded values only; never silently project beyond `last_time`.
- [ ] Update `pdf.py` to locate its peak marker by the returned peak index/time, not rounded-value equality. Run focused tests, PDF assertion, and the full backend suite. Commit the calculation change.

Acceptance example:

```python
assert morphine["unit"] == "mcg/L"
assert morphine["points"][0]["concentration"] == 80  # 20 mg / 250 L
assert all(point["time"] <= partial_report["last_time"] for point in partial_pk["points"])
assert not any(row["drug_id"] == "saline" for row in pk_series)
```

### Task 4: Synchronize and smooth the interactive timeline

**Interfaces:** `projectReportAt(report: TimelineReport, time: number): TimelineFrame` in `frontend/lib/reportTimeline.ts`; `TimelineFrame` contains visible administrations with delivered amounts, visible findings, visible cues, and chart values at `time`. All components consume this single projection. For numerical plots, use interpolation only between valid consecutive samples within the modeled window; do not interpolate across a bolus jump or beyond the last recorded point.

- [ ] Add a failing Playwright scenario at `time=0`, `0.5`, `1`, and just before/after a second dose. Assert the body cue label, organ panel, and chart all use the selected time, including seek backward. Add an exact-unit chart-value check so no future sample is shown. Set reduced-motion preference and assert critical information remains available as text.
- [ ] Add pure TypeScript tests or testable functions for ledger interpolation: infusion at 0–60 s is 250 mL at 30 s; bolus is a step at the administration time; values cannot cross a missing interval or cursor. Remove `pk.points.find(p => p.time >= time)` from `ReportView.tsx`.
- [ ] Implement `projectReportAt` and route scene/text/chart props through it. In `BodyScene.tsx`, ease colour and opacity toward the current cue state over a short fixed visual interval, including after seeking or organ selection. Keep condition motion explicitly schematic and preserve the reduced-motion path; no dose-to-damage animation is allowed without a numerical model.
- [ ] Run Playwright on desktop and narrow/mobile viewports, then measure frame intervals on the target laptop. Record measured FPS and dropped-frame distribution in an artifact; target stable 30 FPS. If below target, simplify materials/pixel ratio before adding effects. Commit the synchronized presentation change.

Projection rule:

```ts
const visibleCues = response.cues.filter(cue => cue.time <= time);
const visibleFindings = report.findings_timeline.filter(finding => finding.simulation_time <= time);
// Never derive a red caution from a finding that is still in the future.
```

### Task 5: End-to-end truthfulness and model admission gate

**Interfaces:** A model capability manifest must enumerate exact `(ingredient, route, organ, quantity, patient-input domain)` combinations; each supported combination identifies code version, parameter source, units, validation reference cases, uncertainty, and a single state owner. The report displays a numerical organ response only when this manifest and the actual run both mark that quantity supported.

- [ ] Add a golden-case integration test for no condition + amlodipine (exposure only), CKD + ibuprofen (renal caution after the first finding), cirrhosis + morphine (hepatic plus respiratory rules), heart failure + saline (cardiovascular caution, no plasma-volume prediction), two medicines, repeat doses, and a cancelled partial run. Assert API report, scene, graph, and PDF tell the same story.
- [ ] Run the complete backend suite, Next.js build/typecheck, and Playwright workflow. Preserve test output and compare report IDs/cursors before and after replay. Any disagreement in units, cue onset, coverage, or recorded-vs-projected state blocks release.
- [ ] For a future numerical organ model, make a separate evidence/feasibility deliverable: check model/SDK availability on the actual laptop, document supported drugs/routes/organs and required patient inputs, reproduce one reference trace, verify conservation/dimensions, and compare against an independent reference. Admit only the combinations that pass. Do not enable a new numerical badge merely because the medicine appears in the catalogue. FDA's [PBPK format/content guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/physiologically-based-pharmacokinetic-analyses-format-and-content-guidance-industry) and [computational-model credibility guidance](https://www.fda.gov/regulatory-information/search-fda-guidance-documents/assessing-credibility-computational-modeling-and-simulation-medical-device-submissions) are useful review frameworks, not proof that this app is validated.
- [ ] Commit the final cross-surface contract tests and coverage documentation. Keep unsupported cells explicit in the UI.

## Completion gate and limits

The release is ready only when the focused regressions, full backend suite, frontend build, and Playwright cases pass; the 12 × 4 coverage matrix is explainable; source-linked cautions never precede findings; small units and event peaks are correct; and the PDF matches the interactive report. A smooth visual transition is a presentation property. It must never be described as a calculated pharmacological or organ response unless the separate model admission gate passes for that exact scenario.

## Self-review against the spec

- Sections 5–7 require explicit capability labels, one numerical owner, pinned inputs, and no invented drug effect; Tasks 1, 3, and 5 enforce these.
- Timeline causality and immutable report cursor are handled by Task 2; accessibility and measured performance by Task 4.
- This plan deliberately does not implement a universal medicine-to-organ physiological engine. Such a claim cannot be made from the current catalogue or four qualitative rules. It establishes a truthful, testable base and a gate for later supported numerical scenarios.
