# Implementation progress — 2026-10-04

## Latest: atomic persistence repair

Plan and evidence: `docs/superpowers/plans/2026-10-04-atomic-persistence.md`
and `artifacts/implementation/atomic-persistence-progress.md`.

The worker now commits related rows together; a late write failure rolls back
snapshots and findings. Existing run/profile/schedule identities cannot be
rewritten by changed retries. Events retain their schema version and a
contiguous sequence, and draft findings receive separate event numbers from the
single writer. Canonical profile hashes and bounded event pages are in place.
Unversioned historical databases are left intact and need an explicit migration
or a new synthetic demo DB. One writer lease is enforced per file within this
process; the local app must use one server process without auto-reload.

Verification: **186 normal tests passed; independent audit 27 passed and 13
failed**. Sources: `artifacts/implementation/atomic-release.xml` and
`artifacts/implementation/atomic-audit-release.xml`. Remaining failures are
worker lifecycle/recovery and evidence evaluation. The local educational demo
delivery map is `docs/demo-today-2026-10-04.md`.

Development has continued here under the existing architecture and audit repair
plan. This document describes the current implementation; the audit report and
its original XML/hash artifacts remain historical evidence.

## Completed first repair: engine integrity

Plan: `docs/superpowers/plans/2026-10-04-engine-integrity-repair.md`.
Execution ledger: `artifacts/implementation/engine-integrity-progress.md`.

- Saved a recoverable pre-repair source ZIP and the original audit results.
- Replaced false Pulse/reference output with `IllustrativeEngineAdapter` and
  explicit mode, model source, versions, assumptions and coverage. The legacy
  class import remains a compatibility alias only; it supplies no reference data.
- Removed invented disease/drug response formulas. Organ quantities are fixed
  educational examples. Fluid actions only add/remove a declared amount from
  illustrative total-volume bookkeeping, with explicit units, route and duration.
- Zero dose does nothing. Infusions end, splitting advance intervals does not
  alter fluid state, invalid/removal-overdraw schedules are rejected atomically,
  and nonfinite/unrepresentable action times cannot corrupt or stall the clock.
- Reset all state on patient initialization. CKD and diabetes are context-only;
  missing measurements remain missing. Supplied measurements and ignored
  personalisation fields are retained and explicitly disclosed as unused by
  this development adapter. Generic CKD is no longer mapped to renal stenosis.
- Unified adapter/coverage capabilities through a strict manifest. Unsupported
  actions, including norepinephrine/oxygen/naloxone/fentanyl in this adapter,
  cannot inherit numerical support from broader Pulse documentation.
- Versioned canonical engine checkpoints include integrity hashes and reject
  corrupted/incompatible content before replacing live state. This does not
  supply the complete worker schedule required for future run recovery/forks.
- Worker records actual adapter identity, refuses explicit mismatched engine
  requests, honors rejected initialize/advance/apply returns and invalid output,
  and blocks unsupported executable actions before initialization. Applied-event
  payloads expose mode, coverage and whether a numerical effect was admitted.
- Default quantities/configuration no longer silently claim Pulse provenance.
- Feasibility distinguishes illustrative development success from verified real
  physiology. Default verified-engine probe exits 1; `--illustrative-only` smoke
  mode exits 0 when its limited lifecycle and isolation checks pass.

## Completed second repair: immutable observer inputs

Plan: `docs/superpowers/plans/2026-10-04-domain-contract-repair.md`.
Ledger: `artifacts/implementation/domain-contract-progress.md`.
Field mapping and examples: `docs/domain-contracts.md`.

- Patient, baseline, config, intervention, quantity and snapshot models are
  frozen, including default/nested mappings and sequences. Detached dumps and
  SQLite/JSON reloads preserve values and restore immutable inputs.
- Quantities have one typed schema. Unknown fields, malformed values, NaN/Inf
  and numeric string/boolean coercion are rejected. Copies with field updates
  revalidate the resulting object, including the legacy `.copy` API. Baseline
  keys/missingness are consistent.
- Evidence-only claims cannot become numerical quantities. Numerical coverage
  requires an explicit source label; verification remains a separate gate.
- Intervention units/routes are recognized and checked for the admitted fluid
  and evidence actions. No clinical dose maxima or patient measurements are
  inferred. Active adapter capabilities still determine numerical support.
- Local runs have explicit engineering limits for horizon/cadence/actions.
  The worker rejects schedules extending beyond the horizon before persistence,
  keeps a frozen schedule, and reconstructs sequenced snapshots without mutation.
- Patient/config/action/snapshot JSON and nested metadata have byte/collection
  limits. This prevents accepted oversized context from multiplying into tens
  of gigabytes of snapshot data. Events have a separate envelope budget that
  accommodates valid observer inputs; aggregate disk/request limits remain work.
- Existing evidence fixtures and audit A37 now construct valid replacements,
  preserving their acceptance intent. Evidence logic and writer behavior remain
  unchanged. Typed draft findings, engine results, recovery commands/checkpoint
  contracts and canonical hashing remain pending foundation work.

## Verification (current)

Normal suite after observer repair: **165 passed**, including 82 new contract
checks. Source: `artifacts/implementation/domain-final.xml`.

Independent audit: **18 passed, 22 failed**. A09–A12 now pass; remaining failures
are known evidence/persistence/lifecycle/recovery defects. Source:
`artifacts/implementation/domain-audit-release.xml`. A fresh read-only reviewer
found a deprecated-copy bypass; reproduced and fixed. I promoted the review's
oversized-metadata concern to an in-scope fix and covered both rejection and a
larger valid schedule. See the ledger for RED→GREEN evidence and all rulings.

## Verification (previous engine tranche)

Normal-collected suite at the engine tranche: **83 passed**, including 44 new integrity and
worker-boundary checks. Source: `artifacts/implementation/release-suite.xml`.

Independent audit regressions: **14 passed, 26 failed** after this tranche.
These remaining failures are tracked foundation work, not hidden behind the
green normal suite. Source: `artifacts/implementation/remaining-audit.xml`.
The original audit was 3 passes/37 failures. A04/A06/A07/A08/A28 were updated to
preserve their acceptance intent against the new action, validity and rejection
contracts; original probe source is preserved in the source ZIP. No probe was
deleted or skipped to conceal a remaining defect.

A fresh read-only reviewer found three in-scope problems: an advertised missing
hepatic metric, a renal stenosis display label still naming CKD, and duration
endpoints that overflowed or rounded back to their start. Each was reproduced,
fixed and covered by new checks; the final 83-test suite includes the fixes.
Additional clock-progress protection was verified in the same fix pass.

The original audit's third passing control is correctly described as SQLite
query-plan/FK/integrity checks; evidence-only isolation was in the original
normal suite and is strengthened by the new tests.

## Run the current checks on Windows

From the project directory in PowerShell:

```powershell
.\scripts\run_tests.ps1
```

The script uses `.venv` if present, otherwise the installed bundled Python,
and the existing isolated `.audit-deps` when available. Supply a different
working interpreter with `-PythonExecutable`. Test-only package versions are
recorded in `artifacts/implementation/requirements-audit.lock`; this is not
a complete product dependency lock or a portability guarantee.

Feasibility CLI with a normal working project Python environment:

```powershell
python -m simulation.feasibility_check --illustrative-only
python -m simulation.feasibility_check
```

The second command is intentionally unsuccessful until genuine physiology is
verified. Recorded outputs: `illustrative-smoke.txt` and
`verified-physiology-probe.txt` under `artifacts/implementation/`.

## Remaining foundation work before Gate 7

1. Verify a genuine physiology engine or exact trace dataset for the actual demo
   scenario; do not promote illustrative output by changing a flag.
2. Finish the remaining draft-finding/engine-result/command/recovery contracts,
   canonical hashing and remaining request/storage bounds alongside persistence/worker
   consumers. Immutable observer inputs and probes A09–A12 are complete.
3. Repair atomic persistence, append-only run/branch history, identities, versions
   and distinct ordered event allocation (A18–A24, A26, A35, A37).
4. Complete worker ownership, idempotency, persisted pause/resume/cancel semantics
   and full worker checkpoint/restore (A25, A29–A31, A36).
5. Repair evidence predicates, exposure timing, canonical context, missingness,
   exact citations and verification/review status (A14–A17, A32–A34 plus F17/F18).

Only then integrate the observer council and downstream API/replay/UI gates.
The current code does not predict patient-specific drug, disease or surgical
outcomes. Evidence validation and clinical validation are separate from the
software test results above.
