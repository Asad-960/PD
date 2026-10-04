# R3 atomic persistence and identity repair

Implement against `docs/gemini-handoff-2026-10-04.md` R3 and the original design.
Today's delivery path is `docs/demo-today-2026-10-04.md`. Keep this repair usable
by the local demo; do not claim it restores clinical validity.

1. RED: file-backed rollback fault, exact/changed retries, run ownership,
   scheduled action registration, event-version round trip, and sequence tests.
2. New empty database uses schema v2 with event version and profile digest.
   An unversioned existing PDTT database is retained and rejected with a clear
   migration message; no old Pulse-labeled data is silently reinterpreted.
3. Compute canonical profile SHA-256 over stable JSON. Worker binds this to the
   effective config; writer verifies matching digest. Existing tests using dummy
   hashes must be updated to the actual contract without losing their behavior.
4. One writer performs each bundle in BEGIN IMMEDIATE / COMMIT or ROLLBACK.
   Snapshot+event, checkpoint+event, status+event and action+event share a
   transaction. Existing standalone write methods remain explicit adapters.
5. Reject changed retries; allow exact retries. Scope identities to run or
   require globally unique IDs with run ownership checks. Preserve event
   schema versions. Bound cursor pages and enforce increasing sequence.
6. Introduce a draft finding with source snapshot identity and no event
   sequence. Assign event sequences in the writer when persisting multiple
   drafts, ordered by stable identity.
7. Re-run normal and independent audit suites; update acceptance probes whose
   old call boundary is replaced by an atomic bundle. One fresh review.

Exit: no orphan transition rows after injected failure; no run/fork overwrites;
two findings have distinct event sequences; old unversioned files are preserved;
strict replay and field round trips verified. Remaining worker/evidence defects
stay visible and block Gate 7.

Ledger: `artifacts/implementation/atomic-persistence-progress.md`.
