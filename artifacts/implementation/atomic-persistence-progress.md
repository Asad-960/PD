# SDD ledger — plan: docs/superpowers/plans/2026-10-04-atomic-persistence.md

Baseline R2: 165 normal passes, independent audit 18 pass / 22 fail.
Git is absent; preserve source ZIPs and hashes instead of using commit-bound
skill scripts. No live application database exists in the workspace.

Pre-flight: writer/schema migration produces a verified event version column;
reader consumes it. Existing data without schema version must be left intact.
Pre-flight: writer profile hash verifies config; worker constructs effective
hash, and direct tests use the canonical helper. Changed-hash retries still fail.
Pre-flight: bundle writer owns event numbering and snapshot storage; worker
must use bundle calls to prevent orphan rows. Drafts never allocate numbers.

Task 1: complete — eight initial acceptance checks all RED
(`atomic-red.xml`): immutable run/schedule, profile hash, rollback, event version,
snapshot/action retries and legacy DB preservation.

Task 2: complete — fresh schema v2; old unversioned files explicitly rejected
without modification; canonical profile digest; immutable profile/run/schedule;
event-version column and strict event order. After implementation 8/8 GREEN
(`atomic-green1.xml`). Direct test fixtures changed to canonical hashes; worker
computes its effective hash before registration. No database file preexisted.

Task 3: complete — `_transaction` rolls back all bundle rows on error;
worker uses the same bundle for snapshot/event, checkpoint/event, action/event,
and status/event. DraftFinding is immutable and carries source snapshot identity,
predicate outcomes, missing inputs, pinned source versions and causal IDs. Writer
sorts/deduplicates drafts, assigns distinct contiguous stream sequences and
stores full derivations; two-finding and mid-bundle fault cases RED→GREEN.

Task 4: complete — exact retries accepted, changed/foreign-owner retries
rejected, one in-process file writer lease, repeated-close lease safety, and
bounded event pages. Extra 3 safety checks RED→GREEN (`atomic-extra-red.xml`,
`atomic-extra-green.xml`), repeat-close RED→GREEN (`atomic-close-red.xml`,
`atomic-close-green.xml`), contiguous sequence/initial-schedule retry
RED→GREEN (`atomic-seq-red.xml`, `atomic-seq-green.xml`), and page/schedule
metadata RED→GREEN (`atomic-pages-red.xml`, `atomic-pages-green.xml`).

Task 5: complete — A19 and A24 probes updated to test the new bundle boundary,
not the obsolete two-call flow. A35 accepts validation rejection with rollback.
Old source remains in the R2 ZIP, and no probe was skipped. Full normal suite
186/186 (`atomic-release.xml`); independent audit 27 pass / 13 fail
(`atomic-audit-release.xml`).

Final self-review: user requested that I do all work myself, so no reviewer
subagent was dispatched. Found and fixed: stale initial schedule comparisons
would reject exact run retries after a later approved action; event gaps were
possible; a repeated close could release the current writer's lease. The RED→
GREEN tests and green whole suite above cover each. Cost of self-review: weaker
independent scrutiny; downstream end-to-end checks remain necessary today.

Ruling: `:memory:` databases are independent test writers; the file-writer
lease is within one process. The local app must run one server process without
reload. Cost if violated: another process could write the same SQLite file.
Ruling: unknown legacy schema stays intact and requires an explicit migration or
new demo DB. Cost: an old DB cannot be opened directly by this build.
Ruling: exact retries compare semantic event fields and leave original wall time;
cost: a retry with different incidental timestamp is treated as the same event.
Ruling: legacy standalone writer methods remain for tests/tools; the worker uses
bundles. Cost: callers using standalone snapshot writes can still create
orphan snapshots; API must use the worker/controller path only.

Next: R4 worker ownership/lifecycle and recovery policy. Then evidence rules,
council, API, stream and frontend, per `docs/demo-today-2026-10-04.md`.
