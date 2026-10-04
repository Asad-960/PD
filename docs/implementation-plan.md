# Implementation plan

## PHASE 0 — Repository and environment audit

**Goal:** establish a clean implementation foundation.

Gemini should first inspect the repository rather than immediately writing application code.

It should determine:

```text
/
├── frontend/
├── backend/
├── worker/
├── simulation/
├── council/
├── evidence/
├── database/
├── tests/
├── scripts/
└── docs/
```

The exact structure can be chosen by Gemini after inspecting the existing repository, but the boundaries should remain.

### Gemini must establish

* Node LTS version
* Python version
* package manager
* virtual environment
* linting
* formatting
* type checking
* pytest
* Playwright
* environment configuration
* local startup commands

### Acceptance gate

Before moving forward:

```text
frontend starts
backend starts
worker starts
tests run
health endpoint works
database initializes
```

No feature development yet.

---

# PHASE 1 — Pulse feasibility gate

**This must happen before serious application development.**

Time-box it to the architecture's four-hour budget. 

Gemini should create:

```text
simulation/
    adapter.py
    capabilities.py
    pulse_adapter.py
    mock_adapter.py
    manifest.json
```

The interface should resemble:

```python
capabilities()
initialize(profile, assumptions)
apply_event(event)
advance(delta_seconds)
snapshot()
serialize()
restore(checkpoint)
```

Exactly as defined by your architecture. 

### Test the actual laptop

Not Gemini's assumed environment.

Test:

1. Can Pulse launch?
2. Can the reference scenario run?
3. Can state be loaded?
4. Can state be serialized?
5. Can state be restored?
6. Can requested metrics be read?
7. Can a supported condition be applied?
8. Can a supported intervention be applied?
9. How fast does it run?
10. How much RAM does it consume?

### Produce

```text
capability-manifest.json
reference-trace.json
pulse-feasibility-report.md
```

The manifest becomes a **source of truth**.

---

# PHASE 2 — Freeze the capability matrix

This is where Gemini must become extremely strict.

Create something conceptually like:

```text
Scenario / Quantity
────────────────────────────────────
Fluid state             SIMULATED
Blood pressure          SIMULATED
Heart rate              SIMULATED
NSAID renal warning     EVIDENCE_ONLY
Drug-induced GFR        UNSUPPORTED
Diabetes renal effect   UNSUPPORTED
```

Do not hard-code these assumptions throughout the application.

Create one capability service:

```text
CoverageGate
```

Every requested scenario goes through it.

### Why?

Because otherwise you'll eventually have:

```text
UI says supported
backend says unsupported
council assumes supported
chart renders fake value
```

The coverage gate prevents this.

---

# PHASE 3 — Data contracts first

Before building the UI or council, implement the schemas.

Your architecture already defines the key contracts:

* `PatientProfile`
* `Intervention`
* `SimulationConfig`
* `PhysiologySnapshot`
* `AgentFinding`
* `RunEvent`
* `Checkpoint`
* `ReviewRecord` 

Use Pydantic models.

Every object should have:

* schema version
* IDs
* timestamps where applicable
* units
* source/model owner
* coverage
* provenance

### Critical rule

**Never use untyped dictionaries as the application's primary domain contracts.**

You want:

```text
Frontend
   ↓
Pydantic
   ↓
Worker
   ↓
Engine
   ↓
Snapshot
   ↓
Council
```

rather than arbitrary JSON being passed everywhere.

---

# PHASE 4 — SQLite persistence

Build the persistence layer next.

Tables:

```text
patient_profiles
runs
interventions
snapshots
events
checkpoints
findings
evidence_sources
rule_versions
reviews
```

Enable WAL.

Implement a **single persistence writer**.

This is explicitly part of your architecture because multiple concurrent writers would create unnecessary SQLite problems. 

---

# PHASE 5 — Event system

Implement the event model before simulation orchestration.

For example:

```text
RUN_CREATED
RUN_INITIALIZING
RUN_STARTED
INTERVENTION_SCHEDULED
INTERVENTION_APPLIED
SNAPSHOT_COMMITTED
FINDING_CREATED
CHECKPOINT_CREATED
RUN_PAUSED
RUN_COMPLETED
RUN_FAILED
RUN_CANCELLED
```

Every event gets:

```text
run_id
sequence
simulation_time
wall_clock_time
type
payload
parent_causal_ids
schema_version
```

This gives you your replay system almost naturally.

---

# PHASE 6 — Simulation worker

Now implement the actual lifecycle:

```text
Validate
   ↓
Coverage
   ↓
Initialize
   ↓
Checkpoint
   ↓
Schedule events
   ↓
Advance engine
   ↓
Snapshot
   ↓
Council
   ↓
Persist
   ↓
Stream
   ↓
Repeat
```

The architecture defines this lifecycle explicitly. 

### Very important

If an intervention happens at:

```text
t = 120 seconds
```

but you're currently advancing:

```text
t = 60 → 180
```

you cannot just apply it afterward.

The worker must split the interval:

```text
60 → 120
apply event
120 → 180
```

This should have an automated test.

---

# PHASE 7 — Evidence engine

Now build the deterministic evidence registry.

Start **small**.

Do not attempt to build a giant medical knowledge base.

Each rule should contain:

```text
rule_id
ingredient/class
preconditions
mechanism
severity category
source URL
source section
source date
rule version
review status
limitations
```

As your architecture states, draft rules must not enter the primary evidence path until reviewed. 

### Test every rule with:

```text
positive case
negative case
missing-data case
```

---

# PHASE 8 — LangGraph organ council

Only after the simulation snapshots exist.

Implement:

```text
Snapshot
   ↓
Renal
CV
Hepatic
Respiratory
   ↓
Deterministic merge
   ↓
Consistency/evidence node
   ↓
Findings
```

Every agent receives the same immutable snapshot.

### Agent rule

An agent may:

✅ inspect

✅ evaluate

✅ request evidence

✅ request an allowed sensitivity run

❌ modify physiology

❌ modify dose

❌ modify the simulation clock

❌ invent missing measurements

❌ invent a source

❌ create an unsupported numerical trajectory

Your architecture explicitly prevents agents from silently modifying interventions or inventing recommendations. 

---

# PHASE 9 — REST API

Now expose the application contract.

Implement:

```text
GET  /capabilities
GET  /scenarios

POST /runs
GET  /runs/{id}

POST /runs/{id}/commands
POST /runs/{id}/forks

GET  /runs/{id}/events
GET  /runs/{id}/compare

POST /runs/{id}/reviews

GET /evidence/{id}

WS /runs/{id}/stream
```

These are already defined in your architecture. 

Don't let Gemini invent ad-hoc endpoints halfway through the project.

---

# PHASE 10 — Replay and WebSocket recovery

This is where many demos break.

The browser should **never assume it received everything**.

Use:

```text
sequence number
```

Example:

```text
Browser has:
1
2
3
4

connection dies

Server:
5
6
7
8
```

Browser reconnects:

```text
GET events?after_seq=4
```

receives:

```text
5
6
7
8
```

then resumes live WebSocket streaming.

Your architecture explicitly specifies this recovery model. 

---

# PHASE 11 — Frontend

Only now build the beautiful interface.

Structure:

```text
┌─────────────────────────────────────────────────────────┐
│ Patient / Scenario                                     │
├──────────────┬───────────────────────┬────────────────┤
│              │                       │                │
│ Patient      │                       │ Organ Council  │
│              │      3D Anatomy       │                │
│ Interventions│                       │ Findings       │
│              │                       │ Evidence       │
│              │                       │                │
├──────────────┴───────────────────────┴────────────────┤
│ Timeline / Charts / Play / Pause / Scrub / Fork       │
└─────────────────────────────────────────────────────────┘
```

The backend remains authoritative.

Zustand should only manage UI state such as:

```text
selected run
selected organ
cursor
render state
```

Not:

```text
blood pressure
drug concentration
physiology state
```

Those belong to backend snapshots.

---

# PHASE 12 — 3D anatomy

This comes **late**.

Three.js / React Three Fiber is presentation only.

It should never calculate:

```text
kidney function
blood pressure
drug metabolism
```

The anatomy receives:

```text
organ state
finding state
selection
animation state
```

And renders it.

If WebGL dies:

```text
3D disappears
```

but:

```text
charts remain
findings remain
timeline remains
evidence remains
```

Exactly as your architecture requires. 

---

# PHASE 13 — Branching

Implement:

```text
checkpoint
    ↓
fork
    ↓
restore
    ↓
apply changed intervention
    ↓
rerun
    ↓
compare
```

Never mutate the original run.

The original is immutable history.

Branch B gets:

```text
parent_run_id
checkpoint_id
branch_changes
configuration_hash
```

This is what makes the demo genuinely compelling.

---

# PHASE 14 — Comparison engine

Separate the comparisons.

### Physiological

```text
Run A BP
Run B BP
Δ
```

only if both are genuinely supported.

### Evidence

```text
Rule X fired in A
Rule X did not fire in B
```

### Sensitivity

```text
parameter range
      ↓
bounded runs
      ↓
range of model outputs
```

And explicitly label this:

> Parameter-sensitivity range

not:

> 23% probability of kidney injury

Your architecture explicitly prohibits interpreting sensitivity envelopes as patient probabilities. 

---

# PHASE 15 — Missing-data system

This needs to be a **first-class feature**, not an error message.

For example:

```text
Renal function
───────────────
eGFR: NOT PROVIDED

This finding cannot be quantitatively evaluated.

Required:
• eGFR
• measurement time

[Enter measurement]
```

And importantly:

```text
Diabetes = YES
```

must **not automatically create:

```text
renal impairment = X
```

Your architecture specifically says a diagnosis/metadata flag cannot manufacture a missing physiological measurement. 

---

# PHASE 16 — Failure handling

Gemini should deliberately break the system.

Test:

### Bad units

```text
dose = "banana"
```

→ reject.

### Unsupported drug

→ coverage warning.

### Missing measurement

→ unknown/missing-input state.

### Engine failure

→ failed run + last valid snapshot marked stale.

### WebSocket failure

→ reconnect/replay.

### Worker crash

→ checkpoint retained.

### WebGL failure

→ UI continues without 3D.

### Optional LLM unavailable

→ deterministic templates continue.

These failure behaviors are already specified in the architecture. 

---

# PHASE 17 — Verification

This is where you make the project **demo-safe**.

You need two test categories.

## Scientific/integrity tests

Test:

```text
same input → same output
```

within defined numerical tolerance.

Test:

```text
unsupported medication
        ↓
NEVER
        ↓
numerical medication trajectory
```

Test event timing.

Test units.

Test invariants.

Test branch reproducibility.

Test evidence rules independently.

These requirements come directly from your acceptance criteria. 

---

## Engineering tests

Run:

```text
create
 ↓
run
 ↓
inspect
 ↓
scrub
 ↓
fork
 ↓
compare
 ↓
review
```

as one complete Playwright journey.

Then:

```text
disconnect WebSocket
reconnect
```

Then:

```text
restart worker
recover
```

Then:

```text
disable WebGL
```

Then:

```text
disconnect internet
```

The complete demo must still work locally.

---

# PHASE 18 — Performance test on the actual laptop

Your architecture deliberately targets conservative hardware.

So don't let Gemini tell you:

> “Performance should be fine.”

Measure it.

Record:

```text
startup time
engine initialization
simulation runtime
RAM usage
frontend FPS
WebSocket throughput
SQLite size
```

The architecture's target is roughly **2–5 compact updates/sec** for simulation streaming and **30–60 visual FPS** where hardware permits; those are targets, not assumptions. 

---

# PHASE 19 — Offline rehearsal

Kill internet.

Then launch from scratch.

The complete presentation should still work.

Your architecture specifically calls for local assets, evidence, cached traces and offline demonstration capability. 

Prepare:

```text
START_DEMO.bat
README.md
demo-scenario.json
capability-manifest.json
reference-trace.json
```

And a backup replay mode if live Pulse integration becomes unreliable.

---

# PHASE 20 — Final three-minute demo

Your final journey should be almost exactly:

```text
0:00
Create synthetic patient

        ↓

0:25
Run scenario

        ↓

1:10
Click renal finding

        ↓

1:45
Fork checkpoint

        ↓

2:00
Change intervention

        ↓

2:25
Compare branches

        ↓

2:35
Show unsupported/missing input

        ↓

2:45
Show reproducibility/offline architecture

        ↓

3:00
Done
```

That matches the presentation flow in your architecture. 

---

# 7. The implementation order I would actually give Gemini

This is the critical part.

Don't let Gemini interpret the entire architecture as permission to build everything simultaneously.

Give it these gates:

```text
GATE 0
Repository + environment
        ↓
GATE 1
Pulse feasibility
        ↓
GATE 2
Capability manifest
        ↓
GATE 3
Domain contracts
        ↓
GATE 4
SQLite + event persistence
        ↓
GATE 5
Simulation worker
        ↓
GATE 6
Evidence registry
        ↓
GATE 7
LangGraph council
        ↓
GATE 8
REST + WebSocket
        ↓
GATE 9
Replay/recovery
        ↓
GATE 10
Frontend
        ↓
GATE 11
3D
        ↓
GATE 12
Branching/comparison
        ↓
GATE 13
Failure handling
        ↓
GATE 14
Automated verification
        ↓
GATE 15
Performance
        ↓
GATE 16
Offline rehearsal
        ↓
SHIP
```

**No jumping ahead because a later feature looks more exciting.**

---

# 8. The most important anti-error rules for Gemini

I would put these at the very top of its implementation instructions.

### Rule 1 — Never fabricate physiology

If the engine doesn't support it:

```text
UNSUPPORTED
```

or:

```text
EVIDENCE_ONLY
```

Never:

```text
invented numerical trajectory
```

---

### Rule 2 — Backend is authoritative

The browser never becomes the source of truth.

---

### Rule 3 — One physiological owner

Only the simulation engine owns numerical physiological state.

---

### Rule 4 — Agents don't mutate physiology

Agents inspect and report.

---

### Rule 5 — No silent assumptions

Missing:

```text
eGFR
glucose
liver function
```

means missing.

Not:

```text
let's estimate something so the chart looks nice
```

---

### Rule 6 — No fake provenance

Every finding needs:

```text
inputs
+
rule/model
+
source
+
limitations
```

Your architecture explicitly defines a finding as a stored derivation rather than an opaque AI explanation. 

---

### Rule 7 — Every feature gets a test

Gemini should not consider a feature finished because the UI appears to work.

It is finished when:

```text
implementation
+
unit tests
+
integration test
+
failure test
```

all pass.

---

### Rule 8 — Don't add infrastructure unless necessary

No:

```text
Kubernetes
Redis
Postgres
cloud queues
cloud LLM
vector database
microservices
```

for this version.

Your architecture intentionally keeps the hackathon version as a local modular monolith. 

---

### Rule 9 — Don't add AI just because the project is called AI

The primary path should work without an LLM.

The optional local model only improves presentation wording.

If it crashes:

```text
simulation continues
```

Exactly as designed. 

---

### Rule 10 — Every phase must leave the repository runnable

This is especially important with Gemini.

After every phase:

```text
git checkpoint
↓
tests
↓
run application
↓
verify
```

Never accumulate 15 untested changes.

---

# 9. What I would tell Gemini 3.1 Pro High

You can give Gemini the architecture file plus an implementation-instructions document based on the following philosophy:

> **You are implementing an existing architecture, not redesigning it.**
>
> Treat the architecture document as the source of truth.
>
> Before writing substantial code, inspect the repository and establish the current state.
>
> Implement incrementally through gated phases.
>
> Never proceed past a phase with failing acceptance tests.
>
> Never invent physiological capabilities that have not been verified against the installed engine.
>
> Never generate numerical physiological effects for unsupported interventions.
>
> Never allow LangGraph agents to own or mutate numerical physiological state.
>
> The simulation engine is the sole owner of physiological state.
>
> FastAPI owns validation and run control.
>
> The worker owns simulation execution.
>
> SQLite has one persistence writer.
>
> The frontend is never authoritative for simulation state.
>
> Every finding must be traceable to inputs, model/rule, evidence, assumptions, coverage, and limitations.
>
> Missing measurements remain missing.
>
> Unsupported capabilities become explicit `unsupported` or `evidence_only` states.
>
> Do not hide errors behind fallbacks that could make an unsupported result appear simulated.
>
> Every new feature must include automated tests and failure-path tests.
>
> At every phase, run the relevant test suite and verify the application manually before continuing.
>
> If an architectural assumption is contradicted by the actual installed Pulse/runtime/API, stop at the relevant gate and report the discrepancy rather than silently changing the architecture.
>
> Prefer the smallest implementation that satisfies the architecture and acceptance criteria.
>
> Do not introduce unnecessary infrastructure or dependencies.
>
> The final system must run completely offline after setup and must degrade gracefully when Pulse, WebSocket, WebGL, evidence retrieval, or optional explanation functionality fails.

---

# 10. One change I strongly recommend to the implementation process

Your architecture itself is solid, but because **Pulse compatibility has not actually been tested yet**, I would make the very first Gemini task extraordinarily small:

> **Do not build the application yet. Prove the engine.**

The first milestone should literally be:

```text
python feasibility_check.py
```

and its output should tell you:

```text
Pulse available: YES/NO

Runtime:
...

Reference scenario:
PASS/FAIL

Initialize:
PASS/FAIL

Snapshot:
PASS/FAIL

Serialize:
PASS/FAIL

Restore:
PASS/FAIL

Supported conditions:
...

Supported interventions:
...

Supported metrics:
...

Measured runtime:
...

Measured RAM:
...

Capability manifest:
CREATED
```

Only if that succeeds should Gemini start implementing the actual twin.

That one decision substantially reduces the chance of spending half the hackathon building beautiful infrastructure around a physiology capability that turns out not to support your intended scenario.

---

## 11. The final mental model

If you remember only this:

```text
              USER
               │
               ▼
        ┌───────────────┐
        │    NEXT.JS    │
        │  presentation │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │    FASTAPI    │
        │ validate/gate │
        └───────┬───────┘
                │
        ┌───────┴────────┐
        │                │
        ▼                ▼
   NUMERICAL         EVIDENCE
     ENGINE            RULES
        │                │
        │                │
        ▼                │
   ONE BODY             │
        │                │
        └───────┬────────┘
                ▼
        ┌───────────────┐
        │ ORGAN COUNCIL │
        │  LangGraph    │
        └───────┬───────┘
                ▼
          FINDINGS
                │
                ▼
        ┌───────────────┐
        │    SQLITE     │
        │ history/state │
        └───────┬───────┘
                ▼
              UI
```

**Engine = body.**

**FastAPI = gatekeeper.**

**Worker = controls time.**

**LangGraph = council of observers.**

**Evidence registry = documented knowledge.**

**SQLite = memory/history.**

**Next.js = control room.**

**WebSocket = live feed.**

**Checkpoint = save point.**

**Fork = alternate timeline.**

**Coverage labels = honesty mechanism.**

And the single most important principle is:

> **If the system doesn't know, the product should visibly say it doesn't know.**

That is what makes this architecture much safer and more defensible than simply making an LLM pretend to be a physiological twin.
