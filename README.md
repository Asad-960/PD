# PDTT: Patient-specific Drug Therapy Tool (Sandbox)

**Scope Statement**
This is a research and education sandbox. The patient workflow preserves entered facts and calculates an administration ledger, with limited source-linked medication cautions. It does not predict blood concentrations, organ function, injury, or treatment safety. There is no verified patient-specific numerical physiology engine or independent clinical validation. **Never use this output to choose treatment.** Use fictional cases; names and history are stored locally in plaintext.

## Quick Start

From the project directory on this machine (dependencies are already installed):
```powershell
.\scripts\start_app.ps1
```

Open [http://localhost:3000](http://localhost:3000). The API runs on `127.0.0.1:8001`; both servers bind locally. The launcher refuses occupied ports instead of stopping existing programs. To select different ports, run `scripts/start_app.ps1 -FrontendPort 3001 -BackendPort 8002`.

For a fresh environment, install `requirements.txt` and run `npm --prefix frontend install`. `scripts/run_api.py --port 8001` starts the API, then `npm --prefix frontend run dev` starts the frontend. Override `PDTT_API_ORIGIN` when using a different backend port.

## Workflow

Enter age, male/female gender, optional name/weight/measurements and histories; record conditions for all four systems and BP history; add one or more medication rows with compatible routes/units and schedules. Review scope explicitly before starting. The result offers interactive 3D anatomy, condition-linked motion and color cues, time seeking, source-linked organ signals, administered-amount graphs, and a concise two-page PDF. Saved-case restoration retains the editable intake. Editing starts a new case; it does not rewrite an old report.

The catalogue contains 178 condition entries from the supplied documents and 12 medication/formulation entries. Catalogue inclusion is not clinical-model support. Only limited ibuprofen, saline, morphine, and exact-ingredient allergy checks are available. All other organ responses and combination safety remain unassessed.

The 3D body and organ meshes are from the [HuBMAP CCF 3D Reference Object Library](https://hubmapconsortium.github.io/ccf/pages/ccf-3d-reference-library.html), released under CC BY 4.0. The animated patterns are deterministic educational cues derived from the recorded condition catalogue and medication events, not simulated physiology. The backend reports `review_required` for source-linked cautions and `no_flag_in_limited_checks` otherwise; neither value means that an organ or therapy is safe. No Gemini API key is needed or used for medical conclusions.

## Persistence and Verification

New assessments use `data/pdtt-assessments-v3.sqlite`. Older databases and legacy preset API routes are preserved. Each report is cached by run and event cursor; new runs pin the submitted catalogue, evidence metadata, and preflight scope. A PDF uses the same cursor as the displayed report.

Backend: `scripts/run_tests.ps1`. Frontend: `npm --prefix frontend run build`. Browser: from `frontend`, set `PLAYWRIGHT_BROWSERS_PATH` to the absolute `artifacts/browsers` path, then run `npx playwright test`. Browser fixtures use fictional patients. `scripts/verify_rebuild_artifacts.py` checks canvas pixels and renders the browser-exported PDF for inspection using the bundled Python runtime.

See `implementation.md` for the original plan and `docs/rebuild-progress.md` for delivered scope and unresolved clinical/model gates.
