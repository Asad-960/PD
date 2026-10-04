# Today’s local demo delivery map — 2026-10-04, Asia/Karachi

Current checkpoint: Python engine contracts and tests are in place; no API or
frontend exists yet. It is approximately 11:35 PKT at this checkpoint. Target a
locally runnable, reviewable educational demo tonight. These time boxes are
targets, not a promise that unfinished medical validation can be compressed.

## Definition of ready tonight

From one local command (or two clearly documented dev commands), a reviewer can
open the app, select a synthetic patient and tested scenario, inspect supported
and missing data, start a run, watch four organ *observer* panels and a timeline,
disconnect/reconnect and replay committed events, and open the provenance/rule
log. Unsupported actions are rejected or visibly unknown. Drug/disease/surgery
effects without a numerical model are never graphed as patient trajectories.
Run one scripted demo twice with the same semantic results and no test failures
in required paths. A fresh laptop should need only local Python/Node packages,
no paid API key. Supply startup instructions and known limitations in the UI.

## Ordered path and checkpoints

| Target window (PKT) | Work | Evidence before proceeding |
|---|---|---|
| 11:35–13:30 | R3: typed draft findings, atomic SQLite bundles, immutable run/profile/schedule, event versions and IDs | Fault injection rolls back entire transition; replay order and two-run isolation pass |
| 13:30–15:00 | R4: one worker owner, idempotent actions, legal pause/resume/cancel, full worker recovery only if proven | Barrier tests, duplicate-start test, cancel at final advance, restart policy; disable unproven resume |
| 15:00–16:15 | R5: exact canonical/time/unit-aware qualitative rules; verify sources or mark draft/unknown | Positive/negative/missing-data tests; wrong units or future exposures cannot trigger |
| 16:15–17:15 | Gate 7: four deterministic organ observers, stable merge and explicit unknown coverage | Identical input produces identical findings; input remains unchanged |
| 17:15–18:30 | Gate 8/9: FastAPI scenario/run endpoints and committed-event replay stream | API-to-worker tests; cursor/reconnect beyond one page |
| 18:30–21:00 | Gate 10: responsive Next.js dashboard with organ cards, anatomy illustration, controls, charts and audit trail | Browser run, reconnect and unsupported scenario walkthrough |
| 21:00–23:00 | End-to-end, packaging, demo story and visual polish | Clean startup, scripted walkthrough, backup video/screenshots and honest limitations |

If a checkpoint slips, the runnable vertical slice stays first: reliable run →
durable events → API → browser. Defer 3D assets, branching, surgery and advanced
charts until that slice works. 3D is progressive enhancement; a polished,
accessible anatomy illustration and meaningful organ panels are sufficient for
the first demo. Pairwise drug interaction, diabetes trajectory and individual
surgical risk require validated numerical/evidence coverage; current hardware,
adapter and data do not support presenting those as predictions today.

The main implementer can own Python correctness, API and integration. Other
team members can separately prepare UI design, synthetic scenario copy, local
anatomical assets with license notes, and demo testing. This folder currently
has no concurrent teammate edits, so code ownership stays with this session.

Only advance a capability when its actual source and limitations are visible.
Tests verify software behavior, not clinical safety. This project must remain
clearly labeled research/education until external validation exists.
