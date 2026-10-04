# Gemini implementation and critique handoff

Use with `docs/audit-2026-10-04.md`. This is a repair and completion plan, not approval of the current implementation. All gate acceptance criteria below are requirements, not claims that the code already passes.

## 1. Copy this to the implementing Gemini

```text
Implement the Physiological Digital Twin Sandbox incrementally, using the
independent audit docs/audit-2026-10-04.md and this handoff as the repair checklist.
Keep the existing one-engine, observer-council, local architecture. Do not proceed
directly to Gate 7. Start with repair R0, then complete R1–R6 in dependency order.

Inspect the actual files and reproduce the relevant failure before changing code.
For each repair, write a focused regression describing externally observable
behavior, implement the smallest coherent change, and run affected tests plus
the existing regression suite. Preserve test intent when interfaces change.
Never delete, skip or weaken a test to conceal a defect. If a requirement is
incorrect, explain the correction and provide a replacement acceptance case.

Do not call handmade formulas Pulse output or verified reference traces. Do not
equate renal artery stenosis with generic CKD. Missing labs remain missing.
Evidence-only interventions cannot modify numerical physiology. Preserve a
supported qualitative warning even if quantitative personalisation is unknown.

Only the numerical engine owns physiology, and only one run owner advances it.
Agents observe immutable snapshots. One application persistence owner commits
atomic transitions and unique ordered events. Run/branch history is immutable.
No observer allocates stream sequences, opens a writer or modifies the engine.

Keep required runtime local and without paid API dependencies. No cloud LLM,
Redis, PostgreSQL, vector database or microservice is needed for this version.
LLM wording is optional and cannot establish medical facts or alter calculations.

At each gate provide an evidence packet: changed files, resolved audit IDs,
contract/migration changes, exact test commands and exit codes, pass/fail counts,
failure-case results, capability/provenance examples, remaining limits, and the
next gate's entry criteria. Do not assert success from test counts alone.
Do not claim zero bugs, clinical validation, or that a no-alert result means safe.
```

## 2. Copy this to the browser critique Gemini

```text
Act as an independent critic of the current gate, not as a rubber stamp.
Use docs/audit-2026-10-04.md and docs/gemini-handoff-2026-10-04.md.

First state which exact source version and evidence you can inspect. If you
cannot access the repository or execute commands, say that verification is
limited to the supplied source/diff, test files and complete command outputs.
Do not imply that you ran a test or inspected a file you did not receive.

For the current repair/gate:
1. Compare the changed contracts across adapter, domain, SQLite, event payload,
   evidence, API and UI. Check typed round trips and immutable history.
2. Inspect the tests themselves. Include positive, negative, missing-input and
   relevant failure/concurrency cases. Check that the asserted behavior would
   fail on the original defect and that setup does not fabricate the result.
3. Trace one full input through the actual code path to persisted/replayed output.
4. Challenge provenance, units, timing, ownership, idempotency and version claims.
5. Inspect failure atomicity and branch/run isolation, not only happy paths.
6. Classify confirmed defects, prospective risks, and incorrect requirements
   separately. Cite exact file/line or concrete evidence for each conclusion.
7. Return PASS, FAIL or UNVERIFIED for each acceptance criterion. PASS requires
   observable evidence; absent evidence is UNVERIFIED, not an assumed pass.
8. Give the smallest next repair and its acceptance test. No scope expansion.

Do not ask the implementer to paste all source repeatedly. Request the changed
files plus their direct contract dependencies and the gate's evidence packet.
If a critical path is FAIL/UNVERIFIED, do not approve the next dependent gate.
```

The human can relay these packets between browser sessions. An AI's approval is supplementary review; executable checks and inspectable artifacts remain the evidence.

## 3. R0–R6: repair the existing foundation

### R0 — Freeze and reproduce the baseline

1. Preserve current files and audit artifacts. If version control is absent, establish a local repository/snapshot before repairs; no remote publication is required.
2. Establish a working Python executable, isolated environment and pinned dependency versions. Record OS, Python, SQLite and package versions; resolve the WindowsApps alias rather than assuming `python` works.
3. Run the existing suite and the independent probes. Keep the observed pre-repair XML and file hashes as historical audit evidence.
4. Create a checklist of F01–F20 with owner, regression, resolution and verified source version. Normalize numbering: Gates 0–6 are foundation, Gate 7 council, Gate 8 REST, Gate 9 streaming/recovery, Gate 10 UI. Do not use “Phase 8” to mean Gate 8 when it means council.

Exit: reproducible baseline and a repair checklist. Original results were 39 existing passes and 37 failures/3 passing controls among 40 audit checks; do not present these as current results after edits.

Prompt suffix: “Perform R0 only. Report actual execution evidence and environment limitations; do not change application logic yet.”

### R1 — Establish truthful engine mode and effective capabilities

Resolve F01, F03–F05, the provenance portion of F02, and source precision in F17.

1. Select a verifiable execution path. Use actual Pulse if its lifecycle and chosen scenario work on this machine. Otherwise use genuine generated traces with exact scenario provenance, or keep the current adapter explicitly illustrative. Do not let an import check alone establish an engine version or compatibility verdict.
2. Genuine traces require the producing engine/version, command/scenario, effective baseline/assumptions, action schedule, quantity units, sample times, scenario hash and trace content hash. Keep trace generation reproducible and generation artifacts local.
3. Capability output must be derived from the active adapter and tested scenarios. Separate active numerical support from general Pulse documentation and evidence support. Unsupported inputs remain visible, with no numerical effect.
4. Remove generic CKD → renal stenosis mapping. Maintain specific diseases/context without manufactured labs. Fix misleading presets and explanatory documents.
5. If illustrative mode remains, all numbers and comparisons visibly carry that mode throughout API/persistence/UI. A replay supports only exact cached scenarios; reject unsupported numerical modifications. An evidence-only branch may change warnings with identical physiological curves, but cannot claim an improved outcome.
6. Verify exact source URLs/sections; downgrade unverifiable extracts and review claims. Do not enable broad opioid class extrapolations from a single morphine label.

Exit: provenance probe fails on missing/mismatched source; adapter capability/action matrix has no false positive; zero-dose/no-op tests and evidence isolation pass; chosen-mode feasibility output is honest. Native failure with illustrative fallback is “illustrative lifecycle passed, Pulse feasibility unverified,” not “Pulse passed.”

Prompt suffix: “Complete R1. Demonstrate where every displayed quantity came from, and test every action advertised by the active adapter. Report the actual supported demo scope.”

### R2 — Make contracts strict and safe for observers

Resolve F02, F06–F07, and define new contracts needed for F08/F12/F18 before persistence changes.

1. Adopt one strict domain vocabulary for mode, coverage, ingredient IDs, conditions, validity, units and statuses. Extra fields at public boundaries fail explicitly; adapter-specific output is converted through a documented mapper.
2. Use typed finite values and immutable nested council inputs. Do not leave an arbitrary dictionary alternative in quantity validation. Measured values, engine model values, context and explicit assumptions are distinct.
3. Reset initialization state; record applied/ignored/context-only baseline inputs. None/is_missing must stay consistent after any allowed update, not only construction.
4. Define `DraftFinding` with source snapshot identity, relevant observed inputs, predicate outcomes, rule/source versions and missing inputs. It has no stream sequence. Define persisted findings/events separately.
5. Define typed `ApplyResult`, `AdvanceResult`, commands, complete `CheckpointState` and version compatibility. Define which fields form canonical hashes and exclude incidental wall-clock metadata from deterministic content.
6. Validate finite bounded horizons, sample/event counts, schedule times, ingredient-specific units/routes, dose semantics and payload size. Do not silently convert unsupported units or infer a patient's measurements.

Exit: A02–A03, A08–A13 or their interface-equivalent replacements pass. Schema/JSON manifest round trips preserve metadata. Deliberate invalidity and malformed quantity cannot become valid output. Two observers cannot affect one another's inputs.

Prompt suffix: “Complete R2 with a field-by-field adapter/domain/database mapping and negative validation examples. Do not build council nodes yet.”

### R3 — Repair persistence, identities and event allocation

Resolve F08–F12, F18–F19 storage portions.

1. Migrate SQLite deliberately with schema version and backup/compatibility policy. Preserve old records or explicitly start a new synthetic demo database; never reinterpret mislabeled old traces as verified data.
2. Use run-scoped/global unique identities consistently. Enforce run ownership in row keys and foreign keys. Same identity plus identical payload can be an exact retry; a changed payload or owner must fail. A new run/branch owns new IDs.
3. Freeze run profile/config and append-only snapshots/events. Persist complete schedule before execution and immutable rule/source versions used by the run.
4. Implement one atomic transition-bundle writer for snapshot/findings/events, action/checkpoint records, and status/lifecycle events. No nested helper commits. Rollback restores all affected rows on failure.
5. Choose one event numbering convention. Recommended: per run, committed event sequence starts at 1 and is contiguous; allocate from committed history inside the owner/writer boundary. Keep source snapshot sequence separate. Multiple draft findings get distinct event sequences in stable order. Nodes never allocate sequences.
6. Preserve event schema versions and canonical JSON without field loss. Enforce bounded queries and define pagination metadata. Validate payload run IDs against row run IDs.
7. Register one application writer; prevent accidental per-worker/per-request writers. Process workers, if selected, communicate via IPC. WAL/busy timeout are secondary safeguards, not ownership enforcement.

Exit: multi-finding persistence, same IDs across branches, changed retries, crash/fault injection, FK violation rollback and event-version round-trip tests pass. File-backed tests verify WAL/FKs and compare indexed columns with decoded payloads. No emitted event precedes its successful transaction commit.

Prompt suffix: “Complete R3. Show SQL constraints, atomic transaction boundaries, fault-injection results and sequence examples for a snapshot with two findings.”

### R4 — Repair the worker and control lifecycle

Resolve F04 return handling, F12–F14 execution portions and F19 cleanup.

1. Validate run/config identity and immutable schedule at construction. Start one owner per run. Engine operations occur only in that owner, sequentially.
2. Use a command queue with run-scoped idempotency keys and explicit acknowledgements. Duplicate command/action retries cannot apply twice; conflicting duplicate payloads fail.
3. Define legal lifecycle transitions: created → initializing → running; running ↔ paused; cancellation/failure/completion are terminal. Specify pause-before-start and invalid/terminal commands rather than relying on flags.
4. At safe boundaries drain commands, split exactly at scheduled actions, checkpoint before consuming/applying the action, and check controls after each advance and between actions. Keep solver steps independent of UI cadence.
5. Honor typed initialization/advance/action outcomes. Evidence-only events are recorded in exposure context without changing numerical state. Unsupported or rejected actions do not become applied events.
6. Acknowledge pause only when no advance is active; acknowledge cancel according to the documented safe-boundary policy. Final-advance cancel cannot emit completion. Exactly one terminal outcome is persisted.
7. Make restore reload clock, complete pending schedule, applied keys, engine version/state and effective config. Reject incompatible hashes/versions. Do not reset an existing run's event sequence on recovery.
8. Shutdown stops and joins workers, drains commits and closes resources. Persistence failure cannot erase the original engine failure. Restart declares interrupted runs explicitly; actual resume is only offered when verified.

Exit: deterministic boundary tests t=0, non-cadence, simultaneous, horizon; duplicate start/commands; barrier-controlled pause/resume/cancel during final advance; engine false/exception; run-ID mismatch; crash/restart tests pass. Original tests that merely allow all snapshots after pause must be strengthened.

Prompt suffix: “Complete R4 with a lifecycle table and synchronization-barrier tests. Demonstrate cancellation during the last engine advance and restore-and-continue equivalence.”

### R5 — Repair deterministic evidence evaluation

Resolve F15–F18.

1. Use canonical ingredient and condition IDs, never event IDs as ingredients. Define whether the evaluator receives active exposure or full schedule; enforce the time contract at that boundary. Define how existing medications enter exposure context.
2. Express predicates with typed `all/any/not` logic and TRUE/FALSE/UNKNOWN outcomes. Distinguish absent quantity, outside scope and criterion not met. Unit-aware min/max bounds must use the intended logic.
3. Separate condition-based caution from lab-dependent personalised assessment. Missing eGFR cannot manufacture a number or wipe out a documented qualitative caution that does not require it.
4. Cover severe hepatic context explicitly or expose a scope limitation. Dose/rate/route-specific claims require matching predicates and sources. Do not call every exposure critical or invent probabilities.
5. Persist exact rule/source versions and source verification/review status. Eligibility must be explicit: software evidence verification is not qualified clinical review. With no clinical reviewer, label the demo rules accordingly and avoid claiming they are clinically reviewed.
6. Produce complete, sorted derivations tied to source snapshots and causal intervention IDs. Validate registry references and required files at startup. Missing evidence degrades openly or blocks that capability, not to an empty “no risk” result.

Exit: each rule has independent positive, negative, missing-required-input, alias, wrong-trigger, timing and scope tests. Cross-run identity and repeat/hash-seed determinism hold. Every enabled claim has a verified supporting document/section. No-match is never displayed as safe.

Prompt suffix: “Complete R5. Provide a predicate truth table and the exact source supporting each enabled claim. Distinguish evidence verification from clinical review.”

### R6 — Re-audit the repaired foundation

1. Run existing tests and all still-applicable adversarial regressions. Where interfaces have changed, replace probes with behavior-equivalent tests, documenting why; do not aim to satisfy obsolete implementation details.
2. A01 currently checks that the formulas are illustrative. If replaced by actual verified traces/engine, replace it with a real provenance validation test. A24 currently injects between two old writer calls; with atomic bundles, inject inside each transaction stage. A32 may be verified at the active-exposure caller instead of the pure evaluator. A34 is the corrected warning requirement.
3. Include file-backed SQLite, round-trip/version, two-run isolation, stable finding sequencing, lifecycle barriers, restoration and corruption tests. Use exact commands/outputs and updated source hashes.
4. Verify the feasibility gate matches actual provenance, not just snapshot shape. Resolve or visibly disable affected capabilities. Review remaining moderate issues with explicit reason/acceptance criteria before proceeding.

Exit: no unresolved foundational critical defect; every enabled capability satisfies its defined contracts; no failed essential acceptance check is silently deferred. This approves an engineering integration boundary, not clinical use.

Prompt suffix: “Perform R6 only and return an evidence-based ready/not-ready verdict for Gate 7. List unresolved requirements without declaring them passed.”

## 4. Gates 7–16: complete the product

### Gate 7 — Deterministic LangGraph organ council

Entry: R6 accepted.

Build four pure observer nodes for renal, cardiovascular, hepatic and respiratory. Input is the same immutable snapshot plus canonical effective context, relevant exposures and pinned rule/capability versions. Each node outputs typed drafts under separate fields or safe reducers. Partition rules by organ to avoid accidental repeated evaluation. Merge sorts/deduplicates by a declared stable identity; consistency checks run identity, source snapshot, versions, evidence eligibility and coverage. It rejects unsupported numerical claims. No LLM, engine handle, DB handle, sequence allocator or mutable physiological state inside nodes.

The run owner commits the snapshot and accepted drafts in one sequenced bundle. Choose a bounded evaluation failure policy and expose it. A graph persistence checkpoint never substitutes for engine/worker state.

Acceptance: same input yields same semantic drafts; input hash unchanged; parallel completion order cannot change output order; empty/unsupported organ coverage is unknown rather than optimal; two findings persist without collision; node failure cannot produce a safe/complete council verdict.

Gate prompt: “Implement Gate 7 only against the approved immutable input/draft-output contract. Include deterministic merge, mutation, sequence integration and observer-failure tests. Keep numerical ownership in the worker.”

Reference: [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api). Deterministic graph functions do not require a paid model API.

### Gate 8 — FastAPI REST, controller and scenario presets

Create writer/controller/registry in application lifespan, and stop/join/drain/close on shutdown. Run one API process in the local demo; reload/multiple server workers must not spawn duplicate run owners. Keep blocking simulation and SQLite operations off the async event loop. If a child process is needed, it owns only its engine and sends bundles to the parent writer through bounded IPC; otherwise document the verified thread mode.

Freeze initial endpoints:

| Endpoint | Contract |
|---|---|
| `GET /capabilities` | Active adapter mode/provenance, supported actions/metrics, evidence scope and versions. |
| `GET /scenarios` | Versioned synthetic presets with assumptions and tested coverage. |
| `POST /runs` | Validate → persist immutable config/profile/full schedule → acknowledge created run → start one owner. Idempotent request handling. |
| `GET /runs/{id}` | Persisted status, versions, latest committed snapshot, coverage/limitations. |
| `POST /runs/{id}/commands` | Queue command; return command identity/accepted status, then persist eventual applied/rejected acknowledgement. |
| `GET /runs/{id}/events?after_seq=...&limit=...` | Bounded ordered committed events with pagination cursor. |
| `GET /evidence/{id}` | Exact pinned source/rule metadata, not a live unversioned lookup. |
| `POST /runs/{id}/reviews` | Auditable review record; no change to physiological history. |

Fork/compare endpoints are implemented with Gate 12; do not return fake success placeholders. Unknown IDs, bad units/nonfinite data, invalid lifecycle commands and unsupported numerical requests have documented errors. Browser-visible coverage is the same decision used by worker validation. Bind locally with explicit local origins; no cloud authentication stack is needed for synthetic offline demo data.

Acceptance: API validation and actual worker effects match; duplicate requests produce one run/action; restart/shutdown close owners/connections; two run IDs remain isolated; error bodies preserve reason/coverage. Presets do not claim two-drug interactions, diabetes trajectories or surgery outcomes that the installed model does not support.

Gate prompt: “Implement Gate 8 only. Show OpenAPI contracts, controller ownership and shutdown tests. Requests never directly advance the engine.”

Reference: [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/).

### Gate 9 — Resilient committed-event streaming and replay

Use SQLite's committed event log as the sole delivery source. A simple bounded DB-polling stream by `after_seq` is appropriate for a local hackathon and avoids a replay-to-live subscription race. Run blocking queries off the event loop; do not read all findings/history into memory. Wakeup notifications may reduce latency but cannot replace durable cursor reads.

`WS /runs/{id}/stream?after_seq=N` repeatedly reads ordered pages greater than N, delivers all events, then continues waiting/polling. The client advances its cursor only after applying an event. Heartbeats carry no physiological/event sequence. Validate cursors/limits and run identity. Store/replay original schema versions. Define duplicate delivery as normal, rejected conflicting duplicates as an integrity error, and gap detection as a replay request. Bound outbound buffers, polling and reconnect backoff; slow clients cannot block simulation commits. Disconnect/reconnect uses the same log and last applied cursor, with no separate unsafe “history then subscribe” handoff.

Acceptance: disconnect during commit, pagination beyond 100 events, duplicate delivery, missing sequence, restart, slow client, terminal run, invalid cursor and switched-run stale connection. Assert exact eventually reconstructed history, not just an open socket. No event is delivered before its transaction commits.

Gate prompt: “Implement Gate 9 only from the committed log. Demonstrate disconnect/replay across more than one page, a slow client and a concurrent commit. Explain how the replay/live gap is avoided.”

Reference: [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/). Durable replay and single-owner policies are application requirements beyond its basic connection examples.

### Gate 10 — Next.js UI and state synchronization

Use generated API types plus runtime validation for event envelopes. Maintain backend-derived cached data in frontend state; this is legitimate. The prohibition is computing authoritative physiology locally, not storing received snapshots in Zustand. Keep per-run cursor/state and a connection generation token so a previous socket cannot update a newly selected run.

Reducer applies known versions in sequence, ignores identical duplicates, detects gaps and rejects wrong-run/unknown-version payloads. Use persisted source snapshot identity to associate findings. Historical timeline mode remains distinct from the latest live snapshot; incoming live events do not move a clinician's scrub cursor unexpectedly.

Build patient/context editor, scenario controls, metrics, council findings, evidence/assumption drawer, timeline and connection/status indicators. Render measured, simulated/replayed, illustrative, evidence-only and unavailable data with explicit provenance. Missing lab is a visible missing state. “No warning fired” is not green clinical clearance. Known evidence warning and unknown quantitative assessment may appear together. No fabricated health score or probability.

Acceptance: reducers tested against a saved event stream; refresh/reconnect/replay reconstruct state; wrong-run socket ignored; historical/live display coherent; invalid/unknown payload fails visibly; unsupported and missing data remain visible. Run a real API/browser journey before spending time on anatomy.

Gate prompt: “Implement Gate 10 only against the approved API/event contracts. Verify state reducer replay and a browser create/run/inspect/reconnect journey. Do not calculate physiology in the browser.”

### Gate 11 — Lightweight anatomy with graceful fallback

Add R3F/Three.js as presentation. Use local low-complexity/licensed assets, restrained effects and an adaptive rendering budget for the Ryzen laptop. Organ color comes from declared finding/coverage status, with gray/unknown as necessary and text/icons so color is not the sole indicator. Do not present evidence-only status as numerical organ failure. On WebGL/context failure, charts, controls, findings, timeline and evidence remain usable.

Acceptance: force WebGL failure/context loss; keyboard access; assets available offline; measure real frame time before adding effects. No model download on startup.

Gate prompt: “Implement Gate 11 with lightweight local anatomy and a tested 2D fallback. Keep the audit/provenance meaning consistent with the text panels.”

### Gate 12 — Verified forks and comparison

Add `POST /runs/{id}/forks` and a documented comparison read endpoint. Branch identity/config/profile/schedule/checkpoint provenance is immutable and independent of the parent. Restore the full approved worker checkpoint, including an unapplied current action and same-time ordering. Changing an already-applied action requires a checkpoint before that action; do not undo it by editing history.

A genuine engine may compute a supported branch. Replay may compare exact pre-recorded branches with matching provenance, but must reject arbitrary uncached numerical changes. Illustrative mode may demonstrate branch mechanics with its label carried everywhere. Evidence-only changes can change qualitative findings while numbers remain unchanged; the product must explain that limit.

Compare matching units, aligned times, comparable modes and source versions. Show evidence differences separately from physiological differences. Prefer one changed input for the core demo; if both drug and fluid change, state that attribution to a single cause is unavailable. No “23% AKI probability,” clinical dose optimization or surgery safety conclusion from a sensitivity envelope.

Acceptance: uninterrupted versus restored execution; parent hashes unchanged; run-scoped IDs; multiple same-time actions; modified pre-action versus invalid post-action branch; same-input branch equivalence within declared solver tolerance; evidence-only branch numeric invariance; mismatched units/versions rejected or explicitly noncomparable.

Gate prompt: “Implement Gate 12 only with complete checkpoint lineage. Prove parent immutability, restore equivalence and the distinction between recomputation and exact replay.”

### Gate 13 — Complete failure handling

Exercise wrong units, missing baselines, unsupported drug, missing/invalid evidence files, engine rejection/crash, persistence failure, worker interruption, council exception, WebSocket loss, unknown schema version, WebGL loss and unavailable optional explanation model. Each path has a defined visible outcome; no fallback relabels unsupported results as simulated. Stale state is explicit. Do not reopen terminal runs through a resume flag.

Acceptance: failure matrix with automated or reproducible manual evidence, exact persisted status/events and remaining recoverable state. This consolidates failure tests already required in earlier gates; do not postpone foundational failure handling until here.

Gate prompt: “Complete Gate 13 using deliberate fault injection. Show what remains trustworthy and recoverable for each failure, without inventing success.”

### Gate 14 — End-to-end verification and independent re-review

Run domain/persistence/worker/evidence/council/API tests plus Playwright create → run → inspect → scrub → fork → compare → review. Add reconnect/replay, restart recovery and WebGL fallback journeys. Compare provenance labels and values across database, REST, stream and browser. Repeat only to investigate failures or newly changed behavior; do not inflate confidence by reporting repetitive test counts.

Acceptance: clean setup reproduces the same supported demo, no unresolved critical defect, and all essential journeys pass with artifacts. Review known limitations and pin dependencies/assets. Test success is software verification, not clinical validation.

Gate prompt: “Perform Gate 14 verification and report actual commands, exit codes and browser artifacts. Return a release checklist with remaining limits.”

### Gate 15 — Measure actual laptop performance

Measure chosen-mode cold start, initialization, simulation runtime versus simulated horizon, peak RSS, DB commit/replay latency, queue depth, CPU, browser frame time and SQLite size. Run `EXPLAIN QUERY PLAN` on populated history for event/snapshot/finding queries. File-backed tests measure real persistence. Confirm cancellation/control latency stays bounded under representative load. Choose observed limits for max concurrent runs/history size; one active run with limited comparison is a reasonable initial target for this hardware.

The design targets roughly 2–5 compact display updates/second and a smooth anatomy view where hardware permits; integration/output cadence and display cadence are separate. These are targets to measure, not promises. Skip local language models on the critical path; CPU/RAM should go to the engine and browser. Record any thread-versus-process choice and its evidence.

Acceptance: measured results on the actual laptop with explicit model mode and acceptable demo limits; no growing backlog or unbounded buffers. Do not advertise illustrative adapter performance as Pulse performance.

Gate prompt: “Perform Gate 15 on the demo laptop and report measured numbers, not estimates. Apply only optimizations justified by a measured bottleneck.”

### Gate 16 — Offline rehearsal and release freeze

Bundle local assets, fonts, evidence, verified traces if used, scenario presets and dependencies/build output. Provide a one-command Windows startup script, health check, stop procedure, setup README and mode/provenance explanation. Verify a cold launch without internet; Swagger/UI assets must not be secretly pulled from a CDN. Check local paths/ports and do not expose external services unnecessarily.

Rehearse the three-minute journey: synthetic patient → supported scenario → organ finding with source → pre-action branch → honest comparison → missing/unsupported limit → offline reproducibility. Keep a proven exact replay/recording backup whose provenance/mode is visible. Freeze features once the complete journey works; keep final hours for rehearsing and repairing failures.

Acceptance: two successful cold offline launches, one complete timed demo, graceful fallback demonstration and recoverable saved runs. Final package contains capability matrix, limitations, source/version ledger, acceptance artifacts and startup instructions.

Gate prompt: “Complete Gate 16 and rehearse offline from a stopped application. Report launch commands, timed journey and backup behavior; do not introduce new features.”

## 5. Team and time allocation

For two main builders, one owns Python contracts/engine/persistence/council/controller; the other owns generated frontend types, replay reducer and UI. Agree on the strict event/API contract before parallel implementation. The other three people can verify exact source sections, execute acceptance cases on a clean setup, prepare lightweight assets and rehearse the pitch. They must not change physiological rules ad hoc to make screenshots look better.

Use remaining time based on the actual deadline, not an assumed fresh 48 hours: foundation repairs first; one full working scenario before adding more; branch comparison next; anatomy polish after the full API/recovery journey works. If real Pulse or genuine traces cannot be proven in time, reduce the claimed scope to an explicitly illustrative/evidence sandbox. Credible limits are a stronger demonstration than false quantitative authority. This cannot guarantee a hackathon ranking.

## 6. Per-gate evidence packet template

```text
Gate/repair:
Source version or file hashes:
Intended observable behavior:
Changed files and audit IDs resolved:
Domain/DB/API/event/UI contract changes:
Migration/compatibility policy:
Relevant regression demonstrated before fix:
Exact test commands, exit codes and counts:
Negative/missing/failure/concurrency results:
Sample persisted and replayed output (synthetic data):
Engine mode, capability/source/rule versions:
Remaining defects and explicitly disabled capabilities:
Acceptance criteria PASS / FAIL / UNVERIFIED:
Next gate entry criteria:
```

Keep implementation and review separate: source changes are reviewable, tests are independently meaningful, results are reproducible, and unverified claims stay unverified.
