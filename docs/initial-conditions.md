# Current patient context and model coverage

Status after the 2026-10-04 engine-integrity repair: the available adapter is
**ILLUSTRATIVE**, not a verified Pulse integration or reference replay. The
machine-readable authority is `simulation/capability-manifest.json`.

The earlier condition/scenario descriptions were proposals and included invalid
mappings and unsupported outcome claims. They are preserved in the pre-repair
source ZIP, not used as current capability assertions.

| Input | Current behavior |
|---|---|
| CKD | Qualitative context; no numerical CKD model. Never mapped to renal artery stenosis. |
| Renal artery stenosis | Specific context; no numerical model in the active adapter. |
| Heart failure | Qualitative context; no computed congestion, pressure or oxygenation response. |
| Diabetes | Context only. No glucose/insulin/nephropathy trajectory; no invented eGFR. |
| COPD, hypertension, anemia | Context only; no disease-specific numerical response. |
| Hepatic impairment/cirrhosis | Qualitative context; exact rule scope and source verification remain pending. |
| Measured baselines | Retained in PatientProfile. The development adapter explicitly reports them as unused. |
| Missing baselines | Remain None/is_missing; educational constants are separate model values. |

Fixed organ quantities are educational examples with `source=pdtt_illustrative_model`
and `capability=illustrative`. They cannot be described as patient measurements,
initialization calibrated to the patient, or validated drug/disease responses.

## Executable actions

- Saline: illustrative amount bookkeeping in mL or L, intravenous route; bolus or
  a finite-duration infusion. Only illustrative total-fluid amount changes.
- Dehydration: illustrative removal in mL, L, or fraction in [0,1], environmental
  route; bolus or finite duration. No computed renal or cardiovascular response.
- Ibuprofen/High_Dose_NSAID and morphine: nonnumerical exposure records. Rule
  applicability, exact citations and evidence review require their repair gate.
- Fentanyl, generic Opioid_Bolus, ACE inhibitors, norepinephrine, oxygen, naloxone
  and unknown interventions: not executable in the current adapter.

Amount bookkeeping does not represent intravascular distribution, perfusion,
renal filtration, therapeutic benefit or patient safety. Unsupported actions
are rejected; no rescue outcome or optimal clinical dose is generated.

## Demonstration scope

Use a synthetic patient to show truthful coverage, missingness, deterministic
scheduling, evidence provenance and replay mechanics as they are implemented.
An evidence-only drug change must leave numerical quantities unchanged.

A genuine physiology demonstration requires a separately verified engine or
exact recorded traces with producing-engine/scenario provenance. Arbitrary
numerical forks cannot be computed by replay alone. No surgical outcome or
unmodeled drug combination is predicted by the current implementation.

The council/API/UI and branch comparison remain subsequent gates. Follow
`docs/gemini-handoff-2026-10-04.md` and the current implementation progress ledger.
