# SDD ledger — plan: docs/superpowers/plans/2026-10-04-domain-contract-repair.md

Baseline: previous engine tranche has 83 normal passes; independent audit 14
passes / 26 failures. Historical audit and source ZIP remain unchanged.

Pre-flight: immutable contracts → worker sequence assignment and evidence test
fixtures: reconstruct validated replacements; do not mutate observer inputs.
Pre-flight: immutable mappings → adapter/SQLite: preserve ordinary JSON dumps
and round-trip tests. Metadata must be JSON, not arbitrary Python objects.
Pre-flight: schedule bounds → worker: reject before persistence or initialization.

Ruling: no Git repository is present, so retain the plan and verification ledger
in the existing workspace instead of using Git-dependent skill scripts. Cost:
no commit-based rollback; historical source ZIP remains available.
Ruling: R2 is staged. Typed engine results, versioned full worker checkpoints and
commands will land with worker/recovery repair, where their consumers exist.
Cost: council remains blocked until those remaining foundation contracts land.
Ruling: 3600 s / 10001 cadence snapshots / 500 actions are local engineering
limits, not clinical limits. Interval splitting adds snapshots; total bounded
output also depends on the action limit. Cost: longer research runs require
explicit resource planning and updated limits.

Task 1: complete — 65 acceptance tests added before implementation. First run
found a duplicate-keyword fixture bug; fixed that fixture before changing code.
Valid RED: 55 failures / 10 existing-validity passes (`domain-red2.xml`).

Task 2: complete — frozen validated models and immutable mappings, finite strict
numbers, typed quantities, missingness/key consistency, action shape validation,
JSON serialization/schema and validated-copy behavior. Initial GREEN: 65/65
(`domain-green.xml`). Added 8 more checks for defaults, other record numerics and
numerical provenance: 8 failed / 65 passed (`domain-extra-red.xml`), then fixed.

Task 3: complete — immutable tuple schedule, <=500 actions, horizon/completion
bounds before persistence; worker reconstructs sequenced snapshot. Integration
run caught the adapter expecting an ordinary JSON assumptions dict; corrected
the explicit dump boundary (no adapter or evidence logic changes). Evidence
fixtures now construct new validated profiles/snapshots. A37 constructs a valid
competing snapshot to continue testing append-only persistence, still unfixed.
Whole normal suite GREEN: 156/156 (`domain-suite2.xml`), no warnings.

Task 4: complete — final normal suite 165/165, no warnings (`domain-final.xml`);
independent audit 18 passes / 22 remaining known failures
(`domain-audit-release.xml`). A09–A12 now pass. No deleted/skipped probes.

Final fresh reviewer: domain_contract_review (read-only; independently ran
156/156 before the fix pass). Found one Important copy bypass, no Critical
in-scope defects. Reviewer context and focus in `domain-review-package.md`.

Final: fixed inherited deprecated `copy(update=...)` validation/freezing bypass —
two regression tests RED→GREEN, plus valid replacement behavior.

Final: Ruling: promoted oversized-payload concern from staged deferral to an
Important in-scope resource defect. 1000 x 4096-character condition labels could
produce ~4.1 MB snapshots (~41 GB for 10001, before duplicate event payloads).
Added observer byte/width/nesting budgets now. Cost: large datasets must use an
explicit later resource policy; aggregate disk and HTTP request limits remain.
Six rejected-payload checks RED→GREEN (`domain-review-red.xml`,
`domain-review-green.xml`). The one fix pass then caught event/snapshot limits
that disagreed: valid larger context/schedule failed after registration. Explicit
larger event envelope budget and 150-action integration check RED→GREEN
(`domain-size-boundary-red.xml`, `domain-size-boundary-green.xml`).

Final: Ruling: baseline/quantity dimension checks remain evidence/adapter repair.
Reviewer reproduced wrong-unit input creating an inappropriate critical finding
in the existing registry. Council consumption remains blocked on its correction;
cost: existing evidence output is not suitable for decision-making meanwhile.
Final: Ruling: no universal dynamic-engine conversion or clinical dose ceilings
are inferred. No new clinical adapter exists. Cost: additional engines/routes
must declare and validate units and dose semantics explicitly.
Final: Ruling: findings/events/checkpoints/reviews remain mutable for the existing
writer interfaces, as documented; in-place collection edits need repaired writer
validation. Cost: these are not safe shared council-input objects.
Final: Ruling: canonical hashes, append-only/atomic storage, ownership/idempotency,
lifecycle and complete recovery stay separate tranches. Cost: 22 independent
audit checks still fail; Gate 7 cannot be approved yet.
Final: Ruling: DraftFinding must land at the beginning of persistence repair,
before separating source snapshot identity from allocated event sequences.
Engine-result/command/full-checkpoint types land with worker consumers. Cost:
do not wire council nodes against the old persisted AgentFinding shape.
Final: Ruling: model_construct, object.__setattr__, direct __dict__ edits and
explicit container reinitialization are deliberate Python bypasses, not the
accidental mutation contract. Cost: do not run hostile observer Python code.
Final: Ruling: software contract tests do not verify physiological/clinical
validity. Cost: the current demonstration remains illustrative and educational.

No deferred minor findings. Preserve the ledger/artifacts in this Git-less
workspace; no merge, push or branch cleanup applies. Final per-field mappings,
negative examples and remaining limits: `docs/domain-contracts.md`.
