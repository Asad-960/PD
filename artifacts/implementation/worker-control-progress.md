# SDD ledger — plan: docs/superpowers/plans/2026-10-04-worker-control.md

Baseline R3: 186 normal passes; independent audit 27 pass / 13 fail.
User explicitly instructed self-implementation without questions or delegation.
Pre-flight: worker command acknowledgements consume event sequences through
writer bundles; `_current_seq` and committed cursor must stay aligned.
Pre-flight: checkpoint includes a current not-yet-applied action; adapter
checkpoint alone lacks worker schedule. Existing adapter-restore test must read
the engine portion of the complete checkpoint and preserve its behavior.
