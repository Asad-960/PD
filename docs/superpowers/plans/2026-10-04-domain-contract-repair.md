# Domain contract repair (R2, observer boundary tranche)

Authority: `docs/gemini-handoff-2026-10-04.md` R2 and the accepted physiological
twin design. Continue the existing implementation; do not build council nodes.

## Scope and interfaces

1. Add negative contract tests first. Expected: current mutable/permissive models
   fail immutability, finite/type/unit, unknown-field and validated-copy checks.
2. Implement deeply immutable patient/config/intervention/quantity/snapshot
   inputs with JSON round trips, typed quantities and explicit missingness.
   Consumer interface: mapping reads remain available; dumps remain ordinary JSON.
3. Validate worker schedule and resource limits before persistence; reconstruct
   snapshots with their sequence instead of mutating frozen objects. Update old
   fixtures to construct new validated inputs rather than mutate shared state.
4. Run normal and independent audit suites, obtain one fresh read-only review,
   fix important findings with RED→GREEN tests, and update progress.

## Acceptance and limits

- Reject nonfinite numbers, boolean/string numeric coercion, malformed quantity
  payloads, extra fields and unsafe `model_copy(update=...)` updates.
- Snapshot metadata is immutable recursively and contains only JSON values.
- Patient baseline keys match measurement identifiers; None remains missing.
- Units/routes are structurally recognized; numerical support still requires
  the active adapter capability gate. No clinical dose ceilings are invented.
- Local resource limits: horizon <= 3600 s, <= 10001 cadence snapshots, <= 500
  scheduled interventions; action start/completion must fit the horizon.
- Existing event/finding/checkpoint persistence formats continue to round trip.
  Atomic writer transitions, lifecycle/idempotency and complete checkpoints
  remain separate foundation repairs.

## Review focus

Inspect nested mutability, serialization and validation bypasses, invalid numeric
and metadata types, schedule bounds, adapter compatibility, missingness, and
whether the existing tests still exercise the same acceptance behavior.

Progress: `artifacts/implementation/domain-contract-progress.md`.
