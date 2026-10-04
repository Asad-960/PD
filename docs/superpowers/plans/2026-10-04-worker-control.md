# R4 local worker ownership and control repair

Source: `docs/gemini-handoff-2026-10-04.md` R4. Today’s target is a reliable
local run with pause/resume/cancel and traceable schedule. Fork/restore remains
disabled until replay equivalence is proven; complete worker state is persisted
to support that later.

1. RED: duplicate active owner, action idempotency, pause/resume event
   acknowledgement, cancel during the last advance, and checkpoint schedule.
2. Keep exactly one active worker per run in the local process. Repeated
   `start_in_background` returns the existing thread while active; terminal
   runs cannot restart through this worker.
3. Serialize command requests in a queue. The worker acknowledges at safe
   boundaries by committing status+event atomically. Cancel wakes a paused run.
   Check controls after every advance and between same-time actions.
4. Deduplicate same-key/same-action requests; reject conflicting use of a key.
   Preserve exact action order for distinct keys at the same simulation second.
5. Persist full worker checkpoint state: engine serialization, clock, effective
   config/profile/version, pending schedule including the not-yet-applied action,
   applied keys and event cursor, with content hash. Verify before future restore.
6. Tests and independent audit. No REST/UI may claim crash resume or forks until
   uninterrupted vs restored execution is proved.

Ledger: `artifacts/implementation/worker-control-progress.md`.
