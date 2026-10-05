# Backend calculation audit — 2026-10-05

Verdict: administration arithmetic passed the checked cases; the PK/reporting layer has reproducible implementation errors. Passing the existing suite does not establish that all calculations are correct.

## Evidence and scope

- Fresh existing suite: **210 passed in 16.17 seconds**, exit code 0. XML: `backend-audit-2026-10-05-unsandboxed.xml`.
- The restricted-runtime test client hung in Windows asyncio socket-pair creation before API assertions. Retrying outside that restriction completed the full suite. The two stalled attempts were stopped.
- Focused script: `backend-calculation-audit-2026-10-05.py`; output: `backend-calculation-audit-2026-10-05.json`.
- Focused probes call production intake, adapter and report functions with fictional fixtures. A writer stub supplies normalized recorded-event fixtures; the full suite separately covers worker/database integration.
- PDF rendering was executed with a captured `Circle` constructor to inspect the actual peak-marker location; output: `backend-pdf-calculation-audit-2026-10-05.json`.
- No application source was changed. Audit files and test outputs were added.

## Checked arithmetic that passed

1. Equivalent input doses: 400 mg = 0.4 g = 400000 mcg, with identical normalized ledger and PK inputs.
2. Three 400 mg administrations at 0, 20 and 40 seconds total 1200 mg.
3. A 500 mL infusion over 60 seconds records 250 mL at 30 seconds.
4. Two 500 mL infusions over 40 seconds, starting at 0 and 20 seconds, record 750 mL at 40 seconds.
5. Report and administration adapter agree on the partial-infusion amount.

These checks establish behavior for the exercised cases, not universal proof.

## Reproduced issues

### 1. PK output concentration unit conversion — confirmed defect

`backend/reports/service.py:163` computes normalized mg dose divided by the fixed distribution-volume parameter. Several drug records label the resulting number `mcg/L` without multiplying by 1000 (`:91`, `:94-95`, `:97-100`, `:182`).

Using the code's own morphine parameters, 20 mg IV / 250 L = 0.08 mg/L = 80 mcg/L. The report gives 0.08 mcg/L. This is an implementation/unit-contract error, independent of whether the chosen physiological parameter is appropriate.

### 2. Early rounding erases nonzero concentrations — confirmed defect

`service.py:177` rounds curve points to three decimals and `:183` rounds the peak to two decimals before returning data. In combination with the output-unit defect, 100 mcg fentanyl IV produces a zero reported peak and zero first curve point. Under the implemented 300 L distribution-volume parameter, its initial value is 0.333333... mcg/L, not zero.

### 3. Uniform sampling misses administration and infusion peaks — confirmed numerical-resolution defect

`service.py:135-142` uses 60 uniformly spaced samples without inserting event times or infusion-end times. For a 3600-second horizon, a morphine bolus at 30 seconds is reported as peaking at 61 seconds. A furosemide infusion from 10 to 11 seconds is also reported as peaking at 61 seconds, at 2.61 mg/L instead of the implemented formula's 2.666066... mg/L at 11 seconds.

### 4. The reported Cmax can mean only the peak inside the selected window — reporting qualification required

`service.py:174-185` returns the largest sampled value within the horizon without qualifying it as a window maximum. With 400 mg oral ibuprofen and a 300-second horizon, it reports a peak of 24.46 mg/L at 300 seconds. The analytic peak of the same implemented formula is about 30.9705 mg/L at 730.9794 seconds. The arithmetic at 300 seconds is not itself wrong; presenting it as the overall dose peak is misleading.

### 5. Partial report PK extends beyond the recorded cursor — consistency issue

`service.py:86` uses the full intake horizon for PK even when the last recorded event is earlier. A partial report at 30 seconds includes a 60-second PK curve for an infusion still underway. The ledger correctly shows 250 mL delivered, while the PK curve projects later delivery. Such extrapolation must be explicitly distinguished from recorded results, especially for cancelled or failed runs.

### 6. Saline plasma-volume output uses a concentration formula — dimensional/model-contract defect

`service.py:101` gives saline a distribution parameter of 5000 and labels its output `mL (plasma volume)`. The generic bolus formula produces 0.1 from a 500 mL administration. Dividing fluid volume by a distribution-volume parameter is not a calculation of plasma-volume change; the code supplies no dimensional conversion or fluid-distribution model supporting the stated output.

### 7. PDF peak marker can be drawn at the origin — confirmed rendering defect

`backend/reports/pdf.py:286-298` initializes the marker at the origin and moves it only if a three-decimal point equals the two-decimal Cmax exactly. For the 300-second ibuprofen fixture, maximum point concentration is 24.462 and reported Cmax is 24.46, so no match exists. The actual marker is drawn at (48, 26), the graph origin, instead of the peak at the right-hand end.

## Model scope, separate from implementation defects

- Patient mass 61 kg versus 120 kg produced identical PK series. The fixed PK parameters do not personalize clearance/distribution using age, weight, renal function or hepatic history.
- Hardcoded target ranges and model constants have no attached parameter-specific sources or validation evidence in the report calculation.
- Oral/non-IV calculations assume the generic absorption formula without explicit bioavailability or route-specific parameter selection. These are model assumptions, not automatically algebra errors.
- Organ damage, drug-drug response and rescue/reversal outcomes are not numerically calculated in the patient workflow. Qualitative source-linked findings and educational animation must not be mistaken for those missing calculations.
- The existing tests contain no direct PK concentration/Cmax/Tmax assertions. They can pass while these issues remain.

## Root causes and next repair scope

Normalize output units before rounding; retain numerical precision until display; evaluate peaks at event/infusion boundaries and qualify finite-window maxima; separate model extrapolation from recorded cursors; remove or replace the unsupported saline volume output; use the actual maximum-point index for PDF markers. Each repair needs a focused regression. Parameter sourcing/personalization is a separate modeling task.

## Addendum: medication-to-organ coverage and playback — 2026-10-05

**Verdict:** The user's observation is real, but it combines limited intentional coverage with two implementation/presentation defects. The current patient workflow records administration amounts; it does **not** calculate a medicine's change to any organ. The organ animation is an educational cue layer. It cannot presently show a computed response across all four organs.

### Reproduction and coverage matrix

The focused production-code probe is `backend-organ-visual-audit-2026-10-05.py`; its full matrix and fictional-case output are in `backend-organ-visual-audit-2026-10-05.json`. It ran through `DemoService`, the worker, and `build_report`, with no application-source edits. The catalogue contains 12 medicines; three have `evidence_available=true`; the patient evidence registry has four medication rules (ibuprofen/renal, morphine/hepatic, morphine/respiratory, saline/cardiovascular). Nine catalogue entries list more than one `target_organs` organ and three list one. A target list is routing metadata, not evidence that every listed organ has a calculated response or reviewed caution.

| Medicine | Catalogue routing | Reviewed caution rule coverage |
| --- | --- | --- |
| Ibuprofen | Renal, cardiovascular, hepatic | Renal, conditional on recorded vulnerability |
| Morphine | Hepatic, respiratory, renal | Hepatic with recorded cirrhosis; respiratory label hazard |
| Saline | Cardiovascular, renal, respiratory | Cardiovascular with recorded heart failure |
| Acetaminophen, naproxen, lisinopril, losartan, furosemide, fentanyl, naloxone, metformin, amlodipine | One or two catalogue organs each | No drug-specific patient rule |

For fictional CKD + 400 mg ibuprofen at 0 s, the report returned an immediate renal `source_linked_caution` cue and cardiovascular/hepatic `exposure_only` cues; respiratory had no cue. For fictional 5 mg amlodipine at 0 s, it returned cardiovascular `exposure_only` only and no findings. Those results explain why one organ may become prominent even when multiple organs are listed: a colour cue and a reviewed caution are not the same thing.

### Confirmed presentation and logic gaps

1. **No numerical organ effect (capability limit, not a hidden calculation).** `simulation/assessment_adapter.py` declares `numerical_effect=False` for every intervention and emits only `administered_*` amounts. `backend/reports/visual_response.py` derives medicine cues by membership in `target_organs`; the condition animation pattern comes from condition text, not drug response. There is no dose-dependent organ function, cross-organ feedback, interaction, or recovery trajectory in this patient workflow. The adapter's `administered_*` metric assigns its `domain` to the first target organ, though administered amount is not an organ measurement; this can mislead downstream consumers.
2. **Caution shown before its finding exists (confirmed timing defect).** `build_visual_responses` gives a `source_linked_caution` cue the administration time whenever any later matching finding exists. In the CKD/ibuprofen probe, the cue is timestamped **0 s**; the first renal finding is **1 s**. `BodyScene` turns the organ red as soon as the cue time is reached, while `ReportView` hides the finding until 1 s. At time 0, the scene and explanation disagree. A cue needs distinct administration and finding times, or the caution must start at the finding's committed time.
3. **Coverage label conflates levels of support.** `backend/intake.py` and `backend/reports/service.py` call a medicine `evidence_only` when any reviewed rule exists. For example, ibuprofen's whole medication row is marked covered even though this registry has only the renal rule. The intake says “Primary systems” from `target_organs`, and the report supplies exposure cues for all those organs. The UI does say exposure-only is not a predicted effect, but it does not show per-organ rule coverage explicitly. This can look like missing effects or imply a broader assessment than exists.
4. **Allergy routed to an arbitrary organ (confirmed classification defect).** `backend/evidence/patient_registry.py` assigns an exact-ingredient allergy match to `target_organs[0]`. The allergy alert is a medication/patient safety finding, not a calculated effect on whichever organ happens to be first in catalogue order. Changing catalogue order can move the alert between organs without changing the case.
5. **Playback and chart values are not temporally smooth or always aligned.** `BodyScene.tsx` updates colour, emissive intensity, and opacity by immediate assignment on each frame when cue state or selection changes; only the resting/pattern pulsation uses a sinusoid. `ReportView.tsx` uses the first PK sample at or **after** the selected time for “Level @”, so the displayed value can come from the future and jump between sparse samples. The prior audit found a fixed 60-point PK grid that misses short-event peaks. These are visible discontinuities and temporal errors, not evidence of a smoothly calculated organ response. Actual frame rate on the user's hardware was not measured in this audit.
6. **Repeat-event explanations can lose identity.** The backend emits the same rule at successive snapshots and links it to all active matching administrations. `ReportView.tsx` collapses visible findings by `rule_id`, leaving only the latest. The UI therefore cannot distinguish which repeated dose first triggered or continued the caution. This matters for a multi-dose timeline; it requires an event-aware display contract, not merely more animation frames.

### Required outcome before describing the display as calculated

Separate `recorded administration`, `catalogue association`, `reviewed qualitative caution`, `illustrative PK`, and `validated numerical organ response` in the data contract and UI. Any organ response curve must have a named model owner, input domain, units, parameters, provenance, and reference-case verification; otherwise display it as unavailable. The accompanying implementation plan defines regression gates for unit arithmetic, timing, organ coverage, partial reports, repeated events, and smooth presentation. It does not promise numerical effects for unsupported medicine–organ pairs.
