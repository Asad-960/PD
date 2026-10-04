"""Single-process local demo API. Synthetic profiles only."""
import asyncio
import os
import uuid
from threading import RLock
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, Optional

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict

from backend.council import OrganCouncil
from backend.database.writer import PersistenceWriter, canonical_profile_hash
from backend.schemas.domain import Intervention, PatientProfile, SimulationConfig
from simulation.adapter import IllustrativeEngineAdapter
from simulation.worker import SimulationWorker
from backend.schemas.intake import PatientIntake
from backend.intake import preflight, prepare_intake, MEASUREMENTS
from backend.catalogue.registry import condition_catalogue, drug_catalogue
from simulation.assessment_adapter import AssessmentTimelineAdapter
from backend.evidence.patient_registry import PatientEvidenceRegistry

PRESETS = {
    "nsaid_dehydration": {
        "name": "Ibuprofen + dehydration",
        "description": "Illustrative fluid removal and qualitative NSAID review.",
        "conditions": ["CKD"],
        "context": {},
        "actions": [
            ("Dehydration", 1000.0, "mL", "environmental", 10.0),
            ("ibuprofen", 800.0, "mg", "oral", 20.0),
        ],
    },
    "chf_saline": {
        "name": "Saline with heart failure",
        "description": "Illustrative added fluid and a source-linked CHF review flag.",
        "conditions": ["CHF"],
        "context": {},
        "actions": [("IV_Saline_Infusion", 750.0, "mL", "intravenous", 15.0)],
    },
    "morphine_liver": {
        "name": "Morphine + hepatic impairment",
        "description": "Qualitative label-based review; clearance is unmodeled.",
        "conditions": ["HepaticCirrhosis"],
        "context": {"hepatic_impairment": "moderate"},
        "actions": [("morphine", 5.0, "mg", "intravenous", 15.0)],
    },
    "diabetes_ckd_nsaid": {
        "name": "Diabetes, CKD + ibuprofen",
        "description": "Diabetes is context only. Glucose and kidney response stay unknown.",
        "conditions": ["Type2DiabetesMellitus", "CKD"],
        "context": {"diabetes": True},
        "actions": [("ibuprofen", 800.0, "mg", "oral", 15.0)],
    },
    "two_drug_review": {
        "name": "Ibuprofen + morphine blend",
        "description": "Two independent medication review flags. Their interaction is not modeled.",
        "conditions": ["CKD", "HepaticCirrhosis"],
        "context": {"hepatic_impairment": "moderate"},
        "actions": [
            ("ibuprofen", 800.0, "mg", "oral", 15.0),
            ("morphine", 5.0, "mg", "intravenous", 20.0),
        ],
    },
}


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    intake: Optional[PatientIntake] = None
    assessment_mode: Literal["evidence_only", "numerical"] = "numerical"
    request_id: Optional[str] = Field(default=None, pattern=r"^[a-f0-9]{32}$")
    preset: Optional[str] = None
    custom_conditions: Optional[list[str]] = None
    custom_actions: Optional[list[list]] = None
    diabetes: bool = False
    horizon_seconds: float = Field(default=60.0, ge=10, le=300)
    sample_cadence_seconds: float = Field(default=5.0, ge=1, le=30)


class DemoService:
    def __init__(self, database_path: str):
        self.writer = PersistenceWriter(database_path)
        self.council = OrganCouncil()
        self.patient_council = OrganCouncil(PatientEvidenceRegistry())
        self.workers: dict[str, SimulationWorker] = {}
        self._start_lock = RLock()

    def close(self):
        for worker in self.workers.values():
            if worker._thread is not None and worker._thread.is_alive():
                worker.cancel()
        for worker in self.workers.values():
            if worker._thread is not None:
                worker._thread.join(timeout=10)
        self.writer.close()

    def start(self, request: RunRequest) -> str:
        with self._start_lock:
            return self._start(request)

    def _start(self, request: RunRequest) -> str:
        if request.intake is not None:
            if request.preset or request.custom_actions is not None or request.custom_conditions is not None:
                raise ValueError("A submitted patient intake cannot also select a legacy preset or action list")
            if request.assessment_mode != "evidence_only":
                raise ValueError("Patient-specific numerical physiology is unavailable. Review coverage and select the evidence assessment explicitly.")
            run_id = "run_" + (request.request_id or uuid.uuid4().hex)
            existing = self.writer.get_run(run_id)
            if existing:
                prior = self.writer.get_patient_profile(existing["patient_id"])
                if prior.model_dump(mode="json")["intake"] != request.intake.model_dump(mode="json"):
                    raise ValueError("This request identifier belongs to a different patient intake")
                return run_id
            profile, config, actions = prepare_intake(request.intake, run_id)
            worker = SimulationWorker(run_id, profile, config, actions, self.writer,
                engine_adapter=AssessmentTimelineAdapter(), council=self.patient_council)
            from backend.intake import capture_assessment_basis
            self.writer.create_run(worker.config, worker.profile, list(worker.interventions),
                assessment_basis=capture_assessment_basis(request.intake, self.patient_council.registry))
            self.workers[run_id] = worker
            worker.start_in_background()
            return run_id
        if request.custom_conditions is not None and request.custom_actions is not None:
            conditions = list(request.custom_conditions)
            context = {}
            raw_actions = request.custom_actions
        else:
            preset_id = request.preset or "nsaid_dehydration"
            if preset_id not in PRESETS:
                raise ValueError("Unknown preset")
            preset = PRESETS[preset_id]
            conditions = list(preset["conditions"])
            context = dict(preset["context"])
            raw_actions = preset["actions"]

        run_id = "run_" + uuid.uuid4().hex[:16]
        if request.diabetes and "Type2DiabetesMellitus" not in conditions:
            conditions.append("Type2DiabetesMellitus")
            context["diabetes"] = True
            
        profile = PatientProfile(
            patient_id="synthetic_" + run_id, age=62, sex="female", mass_kg=72.0,
            conditions=conditions, context=context, baseline_measurements={},
        )
        config = SimulationConfig(
            run_id=run_id, profile_hash=canonical_profile_hash(profile),
            horizon_seconds=request.horizon_seconds,
            sample_cadence_seconds=request.sample_cadence_seconds,
            assumptions={"patient_type": "synthetic educational case"},
        )
        actions = [Intervention(
            event_id=f"{run_id}_action_{index}", ingredient_id=item[0], dose=float(item[1]),
            unit=item[2], route=item[3], simulation_time=float(item[4]),
            idempotency_key=f"{run_id}_key_{index}",
        ) for index, item in enumerate(raw_actions)]
        worker = SimulationWorker(run_id, profile, config, actions, self.writer,
                                  engine_adapter=IllustrativeEngineAdapter(), council=self.council)
        # Reserve identity before launch so clients can immediately fetch it.
        self.writer.create_run(worker.config, worker.profile, list(worker.interventions))
        self.workers[run_id] = worker
        worker.start_in_background()
        return run_id


def create_app(database_path: str | None = None) -> FastAPI:
    location = database_path or os.getenv("PDTT_DB_PATH") or str(
        Path(__file__).resolve().parents[1] / "data" / "pdtt-assessments-v3.sqlite")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        Path(location).parent.mkdir(parents=True, exist_ok=True)
        app.state.service = DemoService(location)
        try:
            yield
        finally:
            app.state.service.close()

    app = FastAPI(title="PDTT local education sandbox", version="0.2.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

    def service():
        return app.state.service

    def require_run(run_id: str):
        run = service().writer.get_run(run_id)
        if run is None:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/api/health")
    def health():
        return {"ok": True, "mode": "ILLUSTRATIVE", "clinical_validation": False}

    @app.get("/api/presets")
    def presets():
        return [{"id": key, "name": value["name"], "description": value["description"],
                 "conditions": value["conditions"]} for key, value in PRESETS.items()]

    @app.get("/api/capabilities")
    def capabilities():
        return AssessmentTimelineAdapter().capabilities()

    @app.get("/api/catalogue/conditions")
    def conditions():
        return condition_catalogue()

    @app.get("/api/catalogue/drugs")
    def drugs():
        return drug_catalogue()

    @app.get("/api/catalogue/measurements")
    def measurements():
        return [{"id": key, "name": value[0], "unit": value[1]} for key, value in MEASUREMENTS.items()]

    @app.post("/api/preflight")
    def check_intake(intake: PatientIntake):
        return preflight(intake)

    @app.post("/api/runs", status_code=201)
    def create_run(request: RunRequest):
        try:
            run_id = service().start(request)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"run_id": run_id, "status": "queued"}

    @app.get("/api/runs/{run_id}")
    def get_run(run_id: str):
        run = require_run(run_id)
        snapshot = service().writer.get_latest_snapshot(run_id)
        return {**run, "latest_snapshot": snapshot.model_dump(mode="json") if snapshot else None,
                "latest_sequence": service().writer.last_event_sequence(run_id)}

    @app.get("/api/runs/{run_id}/events")
    def events(run_id: str, after: int = Query(default=-1, ge=-1),
               limit: int = Query(default=200, ge=1, le=500)):
        require_run(run_id)
        page = service().writer.get_events_after(run_id, after, limit)
        return {"events": [item.model_dump(mode="json") for item in page],
                "next_cursor": page[-1].sequence if page else after}

    @app.get("/api/runs/{run_id}/findings")
    def findings(run_id: str):
        require_run(run_id)
        return [item.model_dump(mode="json")
                for item in service().writer.get_findings_for_run(run_id)]

    @app.get("/api/runs/{run_id}/report")
    def report(run_id: str, cursor: Optional[int] = Query(default=None, ge=0)):
        require_run(run_id)
        from backend.reports.service import build_report
        try:
            return build_report(service().writer, run_id, cursor)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/runs/{run_id}/report.pdf")
    def report_pdf(run_id: str, cursor: Optional[int] = Query(default=None, ge=0)):
        require_run(run_id)
        from backend.reports.service import build_report
        from backend.reports.pdf import render_pdf
        try:
            document = build_report(service().writer, run_id, cursor)
            pdf = render_pdf(document)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return Response(content=pdf, media_type="application/pdf", headers={
            "Content-Disposition": f'attachment; filename="PDTT-{run_id}-{document["cursor"]}.pdf"',
            "Cache-Control": "no-store"})

    @app.post("/api/runs/{run_id}/{command}")
    def control(run_id: str, command: Literal["pause", "resume", "cancel"]):
        require_run(run_id)
        worker = service().workers.get(run_id)
        if worker is None:
            raise HTTPException(409, "This process does not own the run; restart is disabled.")
        try:
            getattr(worker, command)()
        except RuntimeError as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"accepted": True, "command": command}

    @app.websocket("/api/runs/{run_id}/stream")
    async def stream(websocket: WebSocket, run_id: str, after: int = -1):
        await websocket.accept()
        if after < -1 or service().writer.get_run(run_id) is None:
            await websocket.close(code=1008, reason="Unknown run or invalid cursor")
            return
        cursor = after
        try:
            while True:
                page = service().writer.get_events_after(run_id, cursor, 200)
                for item in page:
                    await websocket.send_json(item.model_dump(mode="json"))
                    cursor = item.sequence
                run = service().writer.get_run(run_id)
                if run["status"] in ("completed", "failed", "cancelled") and not page:
                    await websocket.close(code=1000)
                    return
                await asyncio.sleep(0.15)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
