# Implementation status — 2026-10-04

The architecture below describes the intended product. The current numerical
adapter is explicitly **illustrative**, with fixed educational organ values and
fluid amount bookkeeping only. It does not run Pulse or replay verified traces,
and it cannot predict patient-specific drug, disease or surgical outcomes.
See `docs/implementation-progress.md` and the active capability manifest for
implemented behavior and remaining gates. Evidence review is still pending.

## 1. The architecture in very simple terms

Think of your system as a **simulation laboratory**.

You create a fake patient:

> “Patient A, 62 kg, certain baseline measurements, certain conditions, these medications.”

Then you say:

> “At simulation time = 2 hours, give this intervention / introduce this stressor.”

Your system then has **one real physiological simulation** and several observers.

### The most important idea

**There is only ONE body.**

The numerical physiology engine owns the body's actual physiological state.

The organs do **not** each calculate their own blood pressure, drug concentration, fluid volume, etc.

That is exactly what your architecture establishes: one authoritative physiological state, with the agents owning findings rather than competing copies of physiology. 

Think of it like this:

```text
                    SYNTHETIC PATIENT
                           │
                           ▼
                  ┌─────────────────┐
                  │  SIMULATION      │
                  │  ENGINE / PULSE  │
                  │                  │
                  │  THE ONE BODY   │
                  └────────┬────────┘
                           │
                    physiological
                      snapshot
                           │
          ┌────────────────┼────────────────┐
          │                │                │
          ▼                ▼                ▼
       RENAL        CARDIOVASCULAR       HEPATIC
       AGENT             AGENT            AGENT
          │                │                │
          └────────────────┼────────────────┘
                           │
                      RESPIRATORY
                         AGENT
                           │
                           ▼
                   CONSISTENCY /
                   EVIDENCE CHECK
                           │
                           ▼
                      FINDINGS
                           │
                           ▼
                         UI
```

So the agents aren't four independent physiological simulators.

They are more like **four expert inspectors looking at the same patient's latest lab/state snapshot**.

---

# 2. What each major component actually does

### Next.js

This is your **control room**.

It lets the user:

* create the synthetic patient
* choose interventions
* start/pause a simulation
* see the anatomy
* see charts
* inspect organ findings
* scrub through time
* fork a scenario
* compare two branches
* inspect evidence

It **does not calculate physiology**.

Your architecture deliberately puts the UI in the presentation/input role. 

---

### FastAPI

This is the **gatekeeper**.

The browser says:

> “Run this patient with these interventions.”

FastAPI checks:

* Is the patient valid?
* Are units valid?
* Is the dose valid?
* Is the route supported?
* Is this scenario supported by the engine?
* Are required measurements missing?
* Is this an evidence-only situation?
* Is this unsupported?

Only after that does it allow the appropriate path.

---

### Simulation Worker

This is extremely important.

It is the **only component allowed to advance the physiological simulation**.

It:

1. receives the validated scenario
2. initializes the engine
3. schedules events
4. advances simulation time
5. captures snapshots
6. triggers council evaluation
7. persists results

The council never takes over the simulation loop. 

---

### Pulse

Pulse is potentially your **physics/physiology engine**.

But there is a major caveat:

**We cannot assume it supports the exact scenario you want.**

Your architecture explicitly requires a four-hour feasibility gate to establish:

* compatible runtime
* loading
* serialization
* metrics
* supported conditions
* supported interventions
* supported patient parameters
* actual runtime
* capability manifest

before building the rest of the product around it. 

This is the single most important implementation rule.

---

### LangGraph

LangGraph is **not the physiological simulator**.

It is the **orchestrator of the organ council**.

For example:

```text
Pulse snapshot
      │
      ├──► Renal evaluation
      ├──► Cardiovascular evaluation
      ├──► Hepatic evaluation
      └──► Respiratory evaluation
                    │
                    ▼
             Consistency check
                    │
                    ▼
                Findings
```

The agents all read the same immutable snapshot.

That means if the engine says:

```text
volume = X
blood_pressure = Y
heart_rate = Z
```

every organ sees those same values.

No agent gets to secretly modify them.

---

### Evidence Registry

This is the other half of your system.

Suppose Pulse can't quantitatively model:

> “NSAID + dehydration → kidney risk”

You **must not invent a numerical kidney deterioration curve**.

Instead:

```text
Numerical engine:
    "I don't model this medication effect."

Evidence registry:
    "There is a documented risk relationship."

System:
    Evidence-only finding
```

That's why your architecture has separate:

* `engine_simulated`
* `evidence_only`
* `illustrative`
* `unsupported`

coverage states. 

This is one of the strongest parts of the architecture.

---

# 3. The entire system in one example

Imagine your demo patient is:

```text
Synthetic Patient
Age: 55
Mass: 70 kg

Baseline:
- selected physiological measurements
- some renal measurements
- some missing measurements

Context:
- diabetes = true

Intervention:
- volume depletion
- medication event
```

The system first asks:

### Step 1 — Can I actually simulate this?

```text
Coverage check
       │
       ├── Supported numerical physiology
       │
       ├── Evidence-only medication warning
       │
       └── Unsupported quantities
```

The system might conclude:

```text
Fluid-state trajectory → ENGINE_SIMULATED

NSAID kidney-risk relationship → EVIDENCE_ONLY

Exact drug-induced GFR change → UNSUPPORTED
```

Then the engine runs.

At `t = 0`:

```text
Snapshot 001
```

At `t = 60 sec`:

```text
Snapshot 002
```

At `t = 120 sec`:

```text
Snapshot 003
```

etc.

The council periodically looks at those snapshots.

Renal agent might produce:

```text
Finding:
volume-related renal perfusion concern

Inputs:
- modeled volume state
- baseline renal measurement

Coverage:
engine_simulated
```

The evidence subsystem might separately produce:

```text
Finding:
NSAID-associated renal risk under volume depletion

Coverage:
evidence_only

Numerical drug effect:
NOT MODELED
```

That distinction is crucial.

Your UI can then show:

```text
PHYSIOLOGY
──────────────
[chart]

EVIDENCE WARNING
──────────────
NSAID + volume depletion
Documented renal risk

Model limitation:
Drug-induced renal trajectory
not quantitatively simulated.
```

That's a scientifically honest demo.

---

# 4. Branching is basically "save game → change one thing → replay"

This part is particularly good for a hackathon demo.

Imagine:

```text
Patient
  │
  ▼
Run
  │
  │
  ├── checkpoint
  │
  ▼
Intervention
```

You save a checkpoint **before** the intervention.

Then:

```text
                 CHECKPOINT
                     │
            ┌────────┴────────┐
            │                 │
            ▼                 ▼
        BASELINE          INTERVENTION
            │                 │
            ▼                 ▼
         Run A              Run B
```

Then compare:

```text
time ─────────────────────────►

Run A ────────────────
Run B ────────────────

Δ = Run B - Run A
```

But only for quantities that:

* both branches support
* use compatible units
* use compatible models

which your architecture explicitly requires. 

---

# 5. The implementation philosophy I want Gemini to follow

I would **not** give Gemini one gigantic prompt saying:

> “Build this whole architecture.”

That is exactly how you end up with something that looks impressive but has hidden broken contracts.

Instead, use Gemini as an implementation engineer with **hard phase gates**.

The rule should be:

> **Never proceed to the next phase if the current phase's acceptance tests fail.**

And especially:

> **Never fake an unsupported physiological capability just to make the demo work.**

---

