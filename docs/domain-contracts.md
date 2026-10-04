# Domain contracts after the observer boundary repair

This is an engineering contract for a local educational sandbox. It does not
establish medical validity or numerical drug/disease coverage. The current
adapter emits explicitly illustrative quantities.

## Ownership and serialization

`BaselineMeasurement`, `PatientProfile`, `Intervention`, `SimulationConfig`,
`QuantitySnapshot` and `PhysiologySnapshot` reject ordinary attribute mutation.
Maps inside these inputs are immutable, sequences are tuples, and snapshot
metadata is recursively frozen. Dumps detach the stored nested data. JSON dumps
and JSON reloads retain all fields and restore immutable containers.

Council observers receive these values, never the engine or writer handle.
Construct a replacement through `model_copy(update=...)` when a field changes;
our override revalidates the entire replacement. The legacy `copy` API also
revalidates, including its include/exclude selection; removing required fields
fails validation rather than creating a partial domain object. Do not use `model_construct`
for untrusted input. This is protection against accidental shared-state mutation,
not a Python security boundary against code deliberately bypassing attributes.

Pydantic's default frozen models and copy behavior are insufficient for this
boundary: nested dictionaries still need freezing and copy updates need explicit
validation. See [Pydantic model documentation](https://docs.pydantic.dev/latest/concepts/models/).

All models forbid unknown fields. Floats are strict and finite; numeric strings
and booleans are rejected as numbers. Sequence/age/cursor fields reject boolean
coercion. Missing baseline values are still None with `is_missing=True`, and a
baseline mapping key must equal the measurement's `name`. Conditions do not
create measurements. Quantity entries have exactly one typed contract; malformed
entries cannot escape through an arbitrary dictionary alternative.

Evidence-only findings cannot provide numerical quantities. Engine/illustrative
quantities require an explicit source; that source label alone is not evidence
of verification. Existing unspecified-source fixtures are marked unsupported.

## Adapter/domain/database mapping

The writer has not yet received its atomic persistence repair. The following
documents field preservation, including existing defects still awaiting repair.

| Contract | Fields and adapter/domain mapping | SQLite mapping and current limits |
|---|---|---|
| BaselineMeasurement | `name`, `value`, `unit`, `measurement_time`, `source`, `is_missing`; profile input only, current illustrative engine discloses ignored inputs | Nested unchanged in `patient_profiles.data.baseline_measurements`; no baseline is inferred |
| PatientProfile | `patient_id`, `age`, `sex`, `mass_kg`, `baseline_measurements`, `conditions`, `context`, `current_medications`, `allergies` | Full JSON in `patient_profiles.data`; identifier also `patient_id`; **profile upsert can still change history** |
| SimulationConfig | `run_id`, `engine_name`, `engine_version`, `profile_hash`, `horizon_seconds`, `sample_cadence_seconds`, `assumptions`; worker binds actual adapter identity/mode | Full JSON in `runs.config`, `run_id` also indexed; **canonical profile hashing and immutable config persistence pending** |
| Intervention | `event_id`, `ingredient_id`, `dose`, `unit`, `route`, `simulation_time`, `duration`, `idempotency_key`; worker supplies a detached dict to adapter | Full JSON in `interventions.payload`; event/run/time also columns; **run-scoped identity and full upfront schedule persistence pending** |
| QuantitySnapshot | Adapter metric payload `value`, `unit`, `source`, `capability` | Typed entry in `snapshots.data.quantities`; no arbitrary dictionary alternative |
| PhysiologySnapshot | Adapter `simulation_time`, `quantities`, `coverage_flags`, `is_valid`, `numerical_error_code`, `is_stale`; worker binds `run_id` and allocates `sequence` through a validated replacement | Full JSON in `snapshots.data`; run/seq/time/valid/stale also columns; **record/event atomicity and overwrite rejection pending** |
| AgentFinding | `finding_id`, `run_id`, `sequence`, `simulation_time`, `organ`, `category`, `severity`, `inputs_observed`, `rule_id`, `evidence_ids`, `coverage`, `message`, `limitations` | Full JSON in `findings.data`; identity/run/seq/time/organ/category/severity/coverage also columns; **run-scoped IDs and distinct event allocation pending** |
| RunEvent | `schema_version`, `run_id`, `sequence`, `simulation_time`, `wall_clock_time`, `event_type`, `payload`, `parent_causal_ids` | All except **schema_version** have matching columns/JSON; reader still supplies `1.0.0` and **loses nondefault versions**; pending migration |
| Checkpoint | `checkpoint_id`, `run_id`, `simulation_time`, `sequence`, `serialized_engine_state`, `event_cursor`, `content_hash` | Matching columns; `serialized_engine_state` maps to `serialized_state`; **full worker recovery schedule/state pending** |
| ReviewRecord | `review_id`, `run_id`, `reviewer`, `timestamp`, `status`, `acknowledged_limitations`, `notes` | Matching columns, limitations JSON; **review history still mutable** |

Findings/events/checkpoint/review records remain mutable objects for the existing
writer/lifecycle interfaces. Their validated construction and assignment are
strict; append-only storage and immutable event construction remain separate
repairs. In-place edits of their mutable collections are not a validated API.

## Intervention and run validation

The unit/route vocabularies are explicit, and admitted saline, dehydration,
NSAID and morphine actions check compatible shapes using the existing canonical
alias registry. Dehydration fractions are in [0,1]. This does not authorize all
listed routes for a medication or add numerical support for an unknown drug.
The active adapter capability gate still decides executable support.

The local demo permits a maximum 3600-second horizon, 10001 cadence snapshots
including the baseline, and 500 scheduled actions. Interval-split and action
snapshots are additional, bounded by the action count. These are engineering
limits, not clinical dose recommendations. The worker rejects start/completion
times beyond the horizon before creating a run. Same-time actions retain input
order. Input schedule is a tuple of frozen interventions.

UTF-8 serialized input limits are 16 KiB per profile, 8 KiB per config, 2 KiB per
intervention and 32 KiB per snapshot; events have a separate 256 KiB envelope
limit. Patient collections hold at most 64 entries, snapshots at most 128
quantities, and snapshot metadata at most 1024 values, depth 32, and 4096
characters per string/key. Event payload limits allow 4096 values and larger
strings to accommodate valid inputs and coverage reports. These caps do not
replace a future HTTP request-size or total run/storage budget. Event payload
in-place edits still require validation at the repaired writer boundary.

Measurement/quantity unit strings are currently nonempty declarations, not
verified dimensional contracts. The existing evidence evaluator can still
evaluate a MAP labeled `mg` or eGFR labeled `banana`. Unit-aware evidence and
adapter quantity mapping must be fixed before council consumption; no unit
conversion or clinical dose ceiling has been invented here.

Examples rejected before execution:

```python
QuantitySnapshot(value="banana", unit="bpm")
SimulationConfig(run_id="r", profile_hash="h", horizon_seconds=float("inf"))
Intervention(event_id="i", ingredient_id="morphine", dose=5, unit="mL",
             route="oral", simulation_time=0, idempotency_key="i")
snapshot.model_copy(update={"sequence": True})
```

Next foundation work: atomic append-only persistence, canonical identities and
hashes, worker lifecycle/recovery, and evidence correctness. Gate 7 is still
blocked on that work and genuine engine/scenario verification.
