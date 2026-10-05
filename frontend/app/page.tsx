"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Activity, UserRound, HeartPulse, Pill, ClipboardCheck, FileText, ChevronRight, ArrowRight, ArrowLeft, Plus, Trash2, CircleCheck, CircleHelp, TriangleAlert, RefreshCw, ShieldCheck, FlaskConical, Sparkles } from "lucide-react";
import OrganFields from "../components/intake/OrganFields";
import MedicationFields from "../components/intake/MedicationFields";
import ReportView from "../components/report/ReportView";
import { api } from "../lib/api";
import { BPDraft, Condition, Drug, HistoryStatus, MeasurementDraft, MeasurementSpec, MedicationDraft, Organ, OrganDraft, ORGANS, ORGAN_LABELS, PatientDraft, Preflight, TimelineReport } from "../lib/contracts";

const STEPS = [
  { title: "Patient information", short: "Patient", icon: UserRound, description: "Record the patient details and relevant history." },
  { title: "Organ conditions", short: "Conditions", icon: HeartPulse, description: "Record known problems for each of the four systems." },
  { title: "Medication plan", short: "Medications", icon: Pill, description: "Enter the medications to administer and their schedules." },
  { title: "Review & run", short: "Review", icon: ClipboardCheck, description: "Check the patient, medication plan, and available assessment scope." },
  { title: "Simulation & report", short: "Results", icon: FileText, description: "" },
];
const initialPatient: PatientDraft = { name: "", age: "", gender: "", gender_detail: "", sex: "", mass_kg: "", allergies_status: "unknown", allergies: "", current_medications_status: "unknown", current_medications: "" };
const initialOrgans = (): Record<Organ, OrganDraft> => ({ cardiovascular: { status: "", conditions: [] }, renal: { status: "", conditions: [] }, hepatic: { status: "", conditions: [] }, respiratory: { status: "", conditions: [] } });
const initialBP: BPDraft = { status: "", control: "unknown", notes: "", systolic: "", diastolic: "", observed_at: "" };
const firstMedication: MedicationDraft = { key: "med-0", drug_id: "", dose: "", unit: "mg", route: "oral", time_seconds: "0", duration_seconds: "0", repeat_count: "1", interval_seconds: "0" };
function human(value: string) { return value.replaceAll("_", " "); }

function HistoryField({ title, value, onChange, entries, onEntries, placeholder }: { title: string; value: HistoryStatus; onChange: (value: HistoryStatus) => void; entries: string; onEntries: (value: string) => void; placeholder: string }) {
  return <fieldset className="history-field"><legend>{title}</legend><div className="status-options">{[["none_known", "None known"], ["conditions", "Recorded history"], ["unknown", "Unknown"]].map(([id, label]) => <label key={id} className={value === id ? "selected" : ""}><input type="radio" name={title} value={id} checked={value === id} onChange={() => onChange(id as HistoryStatus)} />{label}</label>)}</div>{value === "conditions" && <label className="field"><span>{title} <small>Separate entries with commas</small></span><input required maxLength={1200} value={entries} onChange={e => onEntries(e.target.value)} placeholder={placeholder} /></label>}</fieldset>;
}

export default function Home() {
  const [step, setStep] = useState(0);
  const [patient, setPatient] = useState<PatientDraft>(initialPatient);
  const [organs, setOrgans] = useState(initialOrgans);
  const [bp, setBP] = useState<BPDraft>(initialBP);
  const [medications, setMedications] = useState<MedicationDraft[]>([firstMedication]);
  const [measurements, setMeasurements] = useState<MeasurementDraft[]>([]);
  const [horizon, setHorizon] = useState("300");
  const [conditions, setConditions] = useState<Condition[]>([]);
  const [drugs, setDrugs] = useState<Drug[]>([]);
  const [measurementSpecs, setMeasurementSpecs] = useState<MeasurementSpec[]>([]);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [checks, setChecks] = useState<Preflight | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [report, setReport] = useState<TimelineReport | null>(null);
  const [runId, setRunId] = useState("");
  const [restoreId, setRestoreId] = useState("");
  const [retry, setRetry] = useState(0);
  const requestKey = useRef("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([api<{ conditions: Condition[] }>("/catalogue/conditions"), api<{ drugs: Drug[] }>("/catalogue/drugs"), api<MeasurementSpec[]>("/catalogue/measurements"), api<{ ok: boolean }>("/health")])
      .then(([c, d, m, health]) => { if (!cancelled) { setConditions(c.conditions); setDrugs(d.drugs); setMeasurementSpecs(m); setOnline(health.ok); setError(""); } })
      .catch(problem => { if (!cancelled) { setError(problem.message); setOnline(false); } })
      .finally(() => { if (!cancelled) setLoading(false); });
    setRestoreId(localStorage.getItem("pdtt-patient-run") || "");
    return () => { cancelled = true; };
  }, [retry]);

  const refreshReport = useCallback(async (id: string) => {
    const data = await api<TimelineReport>(`/runs/${id}/report`);
    setReport(data);
    return data;
  }, []);
  useEffect(() => {
    if (!runId || report?.is_final || ["cancelled", "failed"].includes(report?.status || "")) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const data = await api<TimelineReport>(`/runs/${runId}/report`);
        if (cancelled) return;
        setReport(data);
        if (!["completed", "cancelled", "failed"].includes(data.status)) timer = setTimeout(poll, 700);
      } catch (problem) { if (!cancelled) setError(problem instanceof Error ? problem.message : "The assessment connection was interrupted."); }
    }
    poll();
    return () => { cancelled = true; clearTimeout(timer); };
  }, [runId, report?.is_final, report?.status]);

  const patientUpdate = (changes: Partial<PatientDraft>) => { setPatient(p => ({ ...p, ...changes })); setChecks(null); setAccepted(false); requestKey.current = ""; };
  const measurementsUpdate = (values: React.SetStateAction<MeasurementDraft[]>) => { setMeasurements(values); setChecks(null); setAccepted(false); requestKey.current = ""; };
  const changeOrgan = (organ: Organ, value: OrganDraft) => {
    setOrgans(previous => ({ ...previous, [organ]: value })); setChecks(null); setAccepted(false); requestKey.current = "";
    if (organ === "cardiovascular") {
      const hypertension = value.conditions.some(c => conditions.find(i => i.id === c.condition_id)?.canonical_id === "EssentialHypertension");
      if (hypertension) setBP(previous => ({ ...previous, status: "hypertension" }));
      else if (bp.status === "hypertension") setBP(previous => ({ ...previous, status: "unknown", control: "unknown" }));
    }
  };
  const changeBP = (changes: Partial<BPDraft>) => {
    setBP(previous => ({ ...previous, ...changes })); setChecks(null); setAccepted(false); requestKey.current = "";
    if (changes.status === "hypertension") {
      setOrgans(previous => ({ ...previous, cardiovascular: { status: "conditions", conditions: previous.cardiovascular.conditions.some(c => conditions.find(i => i.id === c.condition_id)?.canonical_id === "EssentialHypertension") ? previous.cardiovascular.conditions : [...previous.cardiovascular.conditions, { condition_id: "hypertension", severity: "unknown", subtype: "unknown", notes: "" }] } }));
    } else if (changes.status) {
      setOrgans(previous => { const remaining = previous.cardiovascular.conditions.filter(c => conditions.find(i => i.id === c.condition_id)?.canonical_id !== "EssentialHypertension"); return { ...previous, cardiovascular: { ...previous.cardiovascular, conditions: remaining, status: previous.cardiovascular.status === "conditions" && !remaining.length ? "unknown" : previous.cardiovascular.status } }; });
    }
  };
  function payload() {
    const entries = (value: string) => value.split(",").map(v => v.trim()).filter(Boolean);
    return { patient: { ...patient, name: patient.name.trim() || null, age: Number(patient.age), mass_kg: patient.mass_kg ? Number(patient.mass_kg) : null, sex: patient.gender === "male" || patient.gender === "female" ? patient.gender : null, allergies: patient.allergies_status === "conditions" ? entries(patient.allergies) : [], current_medications: patient.current_medications_status === "conditions" ? entries(patient.current_medications) : [] },
      organs, blood_pressure: { ...bp, systolic: bp.systolic ? Number(bp.systolic) : null, diastolic: bp.diastolic ? Number(bp.diastolic) : null },
      medications: medications.map(({ key, ...m }) => ({ ...m, dose: Number(m.dose), time_seconds: Number(m.time_seconds), duration_seconds: Number(m.duration_seconds), repeat_count: Number(m.repeat_count), interval_seconds: Number(m.repeat_count) > 1 ? Number(m.interval_seconds) : 0 })),
      measurements: measurements.map(({ key, ...m }) => ({ ...m, value: Number(m.value) })), horizon_seconds: Number(horizon) };
  }
  function go(next: number) { setError(""); setStep(next); window.scrollTo({ top: 0, behavior: "smooth" }); }
  async function next(event: React.FormEvent) {
    event.preventDefault(); setError("");
    if (step === 0) { go(1); return; }
    if (step === 1) {
      for (const organ of ORGANS) {
        if (!organs[organ].status) { setError(`Select a history response for ${ORGAN_LABELS[organ]}.`); return; }
        if (organs[organ].status === "conditions" && !organs[organ].conditions.length) { setError(`Add a known condition for ${ORGAN_LABELS[organ]}, or change its history status.`); return; }
      }
      if (!bp.status) { setError("Select the patient's blood-pressure history."); return; }
      if (!!bp.systolic !== !!bp.diastolic || (bp.systolic && Number(bp.diastolic) >= Number(bp.systolic))) { setError("Enter a complete BP reading with systolic pressure greater than diastolic pressure."); return; }
      go(2); return;
    }
    if (step === 2) {
      if (!medications.length) { setError("Add at least one planned medication."); return; }
      setBusy(true);
      try { const result = await api<Preflight>("/preflight", { method: "POST", body: JSON.stringify(payload()) }); setChecks(result); setAccepted(false); go(3); }
      catch (problem) { setError(problem instanceof Error ? problem.message : "The intake could not be validated."); }
      finally { setBusy(false); }
      return;
    }
    if (step === 3) {
      if (!accepted || !checks?.can_run_evidence) return;
      setBusy(true);
      try {
        requestKey.current ||= crypto.randomUUID().replaceAll("-", "");
        const created = await api<{ run_id: string }>("/runs", { method: "POST", body: JSON.stringify({ intake: payload(), assessment_mode: "evidence_only", request_id: requestKey.current }) });
        setReport(null); setRunId(created.run_id); localStorage.setItem("pdtt-patient-run", created.run_id); setRestoreId(created.run_id); go(4);
      } catch (problem) { setError(problem instanceof Error ? problem.message : "The assessment could not start."); }
      finally { setBusy(false); }
    }
  }
  async function restore() {
    setBusy(true); setError("");
    try {
      const data = await refreshReport(restoreId);
      const input = data.intake;
      const value = input?.patient || data.patient;
      setPatient({ ...value, name: value.name || "", age: String(value.age), gender: value.gender === "woman" ? "female" : value.gender === "man" ? "male" : value.gender === "female" || value.gender === "male" ? value.gender : "", mass_kg: value.mass_kg === null ? "" : String(value.mass_kg), sex: value.sex || "", allergies_status: value.allergies_status as HistoryStatus, current_medications_status: value.current_medications_status as HistoryStatus, allergies: value.allergies.join(", "), current_medications: value.current_medications.join(", ") });
      setOrgans(Object.fromEntries(ORGANS.map(organ => [organ, input?.organs[organ] || { status: data.organs[organ].history_status, conditions: data.organs[organ].conditions.map(c => ({ condition_id: c.condition_id, severity: c.severity, subtype: c.subtype, notes: c.notes })) }])) as Record<Organ, OrganDraft>);
      const pressure = input?.blood_pressure || data.blood_pressure;
      setBP({ ...pressure, systolic: pressure.systolic === null ? "" : String(pressure.systolic), diastolic: pressure.diastolic === null ? "" : String(pressure.diastolic), observed_at: input?.blood_pressure.observed_at || "" });
      setMedications((input?.medications || data.medications).map(m => ({ key: crypto.randomUUID(), drug_id: m.drug_id, dose: String(m.dose), unit: m.unit, route: m.route, time_seconds: String(m.time_seconds), duration_seconds: String(m.duration_seconds), repeat_count: String(m.repeat_count), interval_seconds: String(m.interval_seconds) })));
      setMeasurements((input?.measurements || data.measurements.filter(m => !["systolic", "diastolic"].includes(m.name)).map(m => ({ ...m, source: "user_entered" }))).map(m => ({ ...m, key: crypto.randomUUID(), value: String(m.value) })));
      setHorizon(String(input?.horizon_seconds || data.horizon_seconds));
      setChecks(null); setAccepted(false); requestKey.current = ""; setRunId(data.run_id); go(4);
    } catch (problem) { setError(problem instanceof Error ? problem.message : "The previous report is unavailable."); }
    finally { setBusy(false); }
  }
  function resetCase() { setPatient(initialPatient); setOrgans(initialOrgans()); setBP(initialBP); setMedications([{ ...firstMedication, key: crypto.randomUUID() }]); setMeasurements([]); setChecks(null); setAccepted(false); setRunId(""); setReport(null); requestKey.current = ""; go(0); }

  const loadScenario = (type: "opioid" | "renal" | "cardiac") => {
    if (type === "opioid") {
      setPatient({
        name: "Marcus Vance",
        age: "32",
        gender: "male",
        gender_detail: "",
        sex: "male",
        mass_kg: "76",
        allergies_status: "none_known",
        allergies: "",
        current_medications_status: "none_known",
        current_medications: "",
      });
      setOrgans({
        cardiovascular: { status: "none_known", conditions: [] },
        renal: { status: "none_known", conditions: [] },
        hepatic: { status: "none_known", conditions: [] },
        respiratory: { status: "none_known", conditions: [] },
      });
      setBP({
        status: "none_known",
        control: "unknown",
        notes: "",
        systolic: "118",
        diastolic: "74",
        observed_at: "",
      });
      setMedications([
        {
          key: crypto.randomUUID(),
          drug_id: "morphine",
          dose: "20",
          unit: "mg",
          route: "intravenous",
          time_seconds: "0",
          duration_seconds: "0",
          repeat_count: "1",
          interval_seconds: "0",
        },
        {
          key: crypto.randomUUID(),
          drug_id: "naloxone",
          dose: "0.4",
          unit: "mg",
          route: "intravenous",
          time_seconds: "60",
          duration_seconds: "0",
          repeat_count: "1",
          interval_seconds: "0",
        },
      ]);
      setMeasurements([]);
      setHorizon("300");
    } else if (type === "renal") {
      setPatient({
        name: "Eleanor Vance",
        age: "68",
        gender: "female",
        gender_detail: "",
        sex: "female",
        mass_kg: "64",
        allergies_status: "none_known",
        allergies: "",
        current_medications_status: "none_known",
        current_medications: "",
      });
      setOrgans({
        cardiovascular: {
          status: "conditions",
          conditions: [{ condition_id: "chronic_hypertension", severity: "moderate", subtype: "unknown", notes: "" }],
        },
        renal: {
          status: "conditions",
          conditions: [{ condition_id: "acute_kidney_injury_prerenal", severity: "moderate", subtype: "unknown", notes: "" }],
        },
        hepatic: { status: "none_known", conditions: [] },
        respiratory: { status: "none_known", conditions: [] },
      });
      setBP({
        status: "hypertension",
        control: "uncontrolled",
        notes: "Severe essential hypertension",
        systolic: "168",
        diastolic: "98",
        observed_at: "",
      });
      setMedications([
        {
          key: crypto.randomUUID(),
          drug_id: "lisinopril",
          dose: "20",
          unit: "mg",
          route: "oral",
          time_seconds: "0",
          duration_seconds: "0",
          repeat_count: "1",
          interval_seconds: "0",
        },
        {
          key: crypto.randomUUID(),
          drug_id: "ibuprofen",
          dose: "400",
          unit: "mg",
          route: "oral",
          time_seconds: "0",
          duration_seconds: "0",
          repeat_count: "1",
          interval_seconds: "0",
        },
      ]);
      setMeasurements([]);
      setHorizon("300");
    } else if (type === "cardiac") {
      setPatient({
        name: "Arthur Pendelton",
        age: "74",
        gender: "male",
        gender_detail: "",
        sex: "male",
        mass_kg: "82",
        allergies_status: "none_known",
        allergies: "",
        current_medications_status: "none_known",
        current_medications: "",
      });
      setOrgans({
        cardiovascular: {
          status: "conditions",
          conditions: [{ condition_id: "heart_failure", severity: "moderate", subtype: "unknown", notes: "" }],
        },
        renal: { status: "none_known", conditions: [] },
        hepatic: { status: "none_known", conditions: [] },
        respiratory: { status: "none_known", conditions: [] },
      });
      setBP({
        status: "hypertension",
        control: "controlled",
        notes: "CHF with stable preserved EF",
        systolic: "138",
        diastolic: "86",
        observed_at: "",
      });
      setMedications([
        {
          key: crypto.randomUUID(),
          drug_id: "furosemide",
          dose: "40",
          unit: "mg",
          route: "intravenous",
          time_seconds: "0",
          duration_seconds: "0",
          repeat_count: "1",
          interval_seconds: "0",
        },
        {
          key: crypto.randomUUID(),
          drug_id: "saline",
          dose: "500",
          unit: "mL",
          route: "intravenous",
          time_seconds: "30",
          duration_seconds: "120",
          repeat_count: "1",
          interval_seconds: "0",
        },
      ]);
      setMeasurements([]);
      setHorizon("600");
    }
    setChecks(null);
    setAccepted(false);
    requestKey.current = "";
    setError("");
  };

  const conditionCount = ORGANS.reduce((count, organ) => count + organs[organ].conditions.length, 0);
  const completePatient = Number.isInteger(Number(patient.age)) && Number(patient.age) >= 1 && Number(patient.age) <= 129 && Boolean(patient.gender);
  const completeOrgans = ORGANS.every(organ => organs[organ].status && (organs[organ].status !== "conditions" || organs[organ].conditions.length)) && Boolean(bp.status);
  const canNavigate = (index: number) => index === 0 || (index === 1 && completePatient) || (index === 2 && completePatient && completeOrgans) || (index === 3 && Boolean(checks)) || (index === 4 && Boolean(report));

  return <div className="app-shell"><header className="app-header"><a className="brand" href="/" aria-label="PDTT home"><span className="brand-mark"><Activity size={24} /></span><strong>PDTT</strong><span className="brand-caption">Patient therapy assessment</span></a><div className="header-right"><span className="education-label"><FlaskConical size={15} />Research & education</span><span className={`service-status ${online ? "online" : ""}`}><span />{online ? "Service connected" : loading ? "Connecting" : "Service unavailable"}</span></div></header>
    <div className={`workspace ${step === 4 ? "showing-results" : ""}`}><aside className="workflow-sidebar"><div className="sidebar-label">Assessment workflow</div><nav aria-label="Assessment workflow">{STEPS.map((item, index) => <button type="button" key={item.title} disabled={!canNavigate(index)} className={`workflow-step ${index === step ? "active" : ""} ${index < step ? "done" : ""}`} onClick={() => go(index)}><span className="step-symbol">{index < step ? <CircleCheck size={19} /> : <item.icon size={19} />}</span><span><strong>{item.title}</strong><small>{index === step ? "In progress" : index < step ? "Recorded" : `Step ${index + 1}`}</small></span>{index === step && <ChevronRight size={15} />}</button>)}</nav><div className="sidebar-footer"><ShieldCheck size={21} /><p>Clinical validation unavailable</p><small>Results describe the scope of available evidence and calculations.</small></div><button type="button" className="text-button new-case" onClick={resetCase}><Plus size={16} />New case</button></aside>
      <main className="main-workspace">
        {error && <div className="error-message" role="alert"><TriangleAlert size={18} /><span>{error}</span></div>}
        {loading ? <div className="loading-view"><RefreshCw className="spin" size={26} /><h2>Connecting to the assessment service</h2></div> : !online ? <div className="loading-view"><TriangleAlert size={28} /><h2>Assessment service unavailable</h2><button type="button" className="primary-button" onClick={() => setRetry(r => r + 1)}><RefreshCw size={17} />Retry connection</button></div> : step === 4 ? report ? <ReportView key={report.run_id} report={report} onNewCase={() => { setChecks(null); setAccepted(false); requestKey.current = ""; go(0); }} onRefresh={() => refreshReport(runId).catch(e => setError(e.message))} /> : <div className="loading-view"><Activity className="spin" size={28} /><h2>Preparing the assessment</h2><p>Recording the patient profile and medication schedule.</p><button type="button" className="secondary-button" onClick={() => refreshReport(runId).catch(e => setError(e.message))}><RefreshCw size={16} />Refresh</button></div> : <div className="intake-layout"><div className="intake-main"><div className="page-heading"><div className="breadcrumb">New assessment <ChevronRight size={13} />{STEPS[step].short}</div><h1>{step === 3 ? "Review the assessment" : STEPS[step].title}</h1><p>{STEPS[step].description}</p></div>
        {restoreId && step === 0 && <div className="previous-report"><FileText size={17} /><span>A previous assessment is available on this device.</span><button type="button" className="text-button" disabled={busy} onClick={restore}>Open report<ChevronRight size={14} /></button></div>}
        <form onSubmit={next}>
          {step === 0 && <>
            {/* Quick 1-Click Demo Scenarios for Presentations */}
            <div className="demo-preset-banner" role="region" aria-label="Quick Demo Clinical Scenarios">
              <div className="demo-banner-header">
                <div className="demo-banner-title">
                  <Sparkles size={16} />
                  <span>1-Click Hackathon Demo Scenarios</span>
                </div>
                <span className="demo-banner-caption">Click to auto-populate complex clinical cases instantly</span>
              </div>
              <div className="demo-preset-grid">
                <button
                  type="button"
                  className="demo-preset-card"
                  onClick={() => loadScenario("opioid")}
                >
                  <span className="demo-card-tag">Emergency & Pain</span>
                  <strong className="demo-card-name">Opioid Overdose + Naloxone Rescue</strong>
                  <span className="demo-card-detail">Morphine 20mg IV followed by Naloxone 0.4mg antidote at 60s (PK antagonist rescue profile)</span>
                </button>

                <button
                  type="button"
                  className="demo-preset-card"
                  onClick={() => loadScenario("renal")}
                >
                  <span className="demo-card-tag">Renal & CV Risk</span>
                  <strong className="demo-card-name">Hypertensive Crisis + CKD Vulnerability</strong>
                  <span className="demo-card-detail">Lisinopril 20mg + Ibuprofen 400mg with CKD (Inspect Kidneys Posterior View)</span>
                </button>

                <button
                  type="button"
                  className="demo-preset-card"
                  onClick={() => loadScenario("cardiac")}
                >
                  <span className="demo-card-tag">Fluid & Diuretics</span>
                  <strong className="demo-card-name">Heart Failure Volume Management</strong>
                  <span className="demo-card-detail">Furosemide 40mg IV + Saline 0.9% 500mL infusion (Loop diuretic vs IV crystalloid)</span>
                </button>
              </div>
            </div>

            <section className="form-section"><h3>Patient details</h3><div className="form-grid"><label className="field span-2"><span>Patient name <small>Optional</small></span><input aria-label="Patient name" maxLength={160} autoComplete="off" value={patient.name} onChange={e => patientUpdate({ name: e.target.value })} placeholder="Name or local identifier" /></label><label className="field"><span>Age <small>years</small></span><input aria-label="Patient age" required type="number" min="1" max="129" step="1" value={patient.age} onChange={e => patientUpdate({ age: e.target.value })} placeholder="Age" /></label><label className="field"><span>Gender</span><select aria-label="Patient gender" required value={patient.gender} onChange={e => patientUpdate({ gender: e.target.value, sex: e.target.value })}><option value="">Select gender...</option><option value="male">Male</option><option value="female">Female</option></select></label><label className="field"><span>Body mass <small>kg, if known</small></span><input aria-label="Body mass" type="number" min="0.1" max="349.9" step="any" value={patient.mass_kg} onChange={e => patientUpdate({ mass_kg: e.target.value })} placeholder="Not supplied" /></label></div></section>
            <section className="form-section"><h3>Relevant history</h3><HistoryField title="Allergies" value={patient.allergies_status} onChange={status => patientUpdate({ allergies_status: status, allergies: status === "conditions" ? patient.allergies : "" })} entries={patient.allergies} onEntries={value => patientUpdate({ allergies: value })} placeholder="e.g. ibuprofen, penicillin" /><HistoryField title="Ongoing medications" value={patient.current_medications_status} onChange={status => patientUpdate({ current_medications_status: status, current_medications: status === "conditions" ? patient.current_medications : "" })} entries={patient.current_medications} onEntries={value => patientUpdate({ current_medications: value })} placeholder="Current medication names" /></section>
            <section className="form-section measurements-section"><div className="section-heading"><h3>Baseline measurements</h3><span className="muted compact">Optional</span></div>{measurements.map((m, index) => <div className="measurement-row" key={m.key}><label className="field"><span>Measurement</span><select required value={m.name} aria-label={`Measurement ${index + 1}`} onChange={e => { const info = measurementSpecs.find(spec => spec.id === e.target.value); measurementsUpdate(previous => previous.map((row, i) => i === index ? { ...row, name: e.target.value, unit: info?.unit || "" } : row)); }}><option value="">Select...</option>{measurementSpecs.filter(spec => spec.id === m.name || !measurements.some(row => row.name === spec.id)).map(spec => <option key={spec.id} value={spec.id}>{spec.name}</option>)}</select></label><label className="field"><span>Value <small>{m.unit}</small></span><input required aria-label={`Measurement value ${index + 1}`} type="number" step="any" min="0" value={m.value} onChange={e => measurementsUpdate(previous => previous.map((row, i) => i === index ? { ...row, value: e.target.value } : row))} /></label><label className="field"><span>Observed at <small>Optional</small></span><input type="datetime-local" value={m.observed_at} onChange={e => measurementsUpdate(previous => previous.map((row, i) => i === index ? { ...row, observed_at: e.target.value } : row))} /></label><button type="button" className="icon-button" aria-label={`Remove measurement ${index + 1}`} title="Remove measurement" onClick={() => measurementsUpdate(previous => previous.filter((_, i) => i !== index))}><Trash2 size={17} /></button></div>)}<button type="button" className="text-button" disabled={measurements.length >= measurementSpecs.length} onClick={() => measurementsUpdate(previous => [...previous, { key: crypto.randomUUID(), name: "", value: "", unit: "", observed_at: "", source: "user_entered" }])}><Plus size={16} />Add measurement</button>{!measurements.length && <p className="muted compact">Unentered measurements remain unknown.</p>}</section>
          </>}
          {step === 1 && <><OrganFields values={organs} catalogue={conditions} onChange={changeOrgan} /><section className="form-section"><div className="section-heading"><HeartPulse size={22} color="#b45164" /><h3>Blood pressure</h3></div><div className="form-grid"><label className="field"><span>BP-related history</span><select aria-label="BP-related history" required value={bp.status} onChange={e => changeBP({ status: e.target.value, control: "unknown" })}><option value="">Select history...</option><option value="none_known">No known BP issue</option><option value="hypertension">Hypertension / high BP</option><option value="hypotension">Hypotension / low BP</option><option value="other">Other documented issue</option><option value="unknown">Unknown / not assessed</option></select></label>{bp.status === "hypertension" && <label className="field"><span>Hypertension control</span><select aria-label="Hypertension control" value={bp.control} onChange={e => changeBP({ control: e.target.value })}><option value="unknown">Unknown</option><option value="controlled">Controlled</option><option value="uncontrolled">Uncontrolled</option></select></label>}<label className="field"><span>Systolic <small>mmHg, if measured</small></span><input aria-label="Systolic blood pressure" type="number" step="any" min="1" max="400" placeholder="Not supplied" value={bp.systolic} onChange={e => changeBP({ systolic: e.target.value })} /></label><label className="field"><span>Diastolic <small>mmHg, if measured</small></span><input aria-label="Diastolic blood pressure" type="number" step="any" min="1" max="300" placeholder="Not supplied" value={bp.diastolic} onChange={e => changeBP({ diastolic: e.target.value })} /></label><label className="field"><span>Reading observed at <small>Optional</small></span><input type="datetime-local" value={bp.observed_at} onChange={e => changeBP({ observed_at: e.target.value })} /></label><label className="field span-2"><span>BP history notes <small>Optional</small></span><input maxLength={300} value={bp.notes} onChange={e => changeBP({ notes: e.target.value })} placeholder="Recorded BP issue or measurement context" /></label></div></section></>}
          {step === 2 && <MedicationFields values={medications} catalogue={drugs} onChange={values => { setMedications(values); setChecks(null); setAccepted(false); requestKey.current = ""; }} horizon={horizon} onHorizon={value => { setHorizon(value); setChecks(null); setAccepted(false); requestKey.current = ""; }} />}
          {step === 3 && checks && <div className="review-view"><section className="review-patient"><UserRound size={24} /><div><h3>{patient.name || "Unnamed patient"}</h3><p>{patient.age} years · {human(patient.gender)}{patient.mass_kg && ` · ${patient.mass_kg} kg`}</p></div><button type="button" className="text-button" onClick={() => go(0)}>Edit</button></section><section className="review-section"><div className="section-heading"><h3>Organ history</h3><button type="button" className="text-button" onClick={() => go(1)}>Edit</button></div>{ORGANS.map(organ => <div className="review-line" key={organ}><strong>{ORGAN_LABELS[organ]}</strong><span>{organs[organ].conditions.map(c => `${conditions.find(i => i.id === c.condition_id)?.name} (${c.severity})`).join(", ") || human(organs[organ].status)}</span></div>)}<div className="review-line"><strong>Blood pressure</strong><span>{human(bp.status)}{bp.systolic && ` · ${bp.systolic}/${bp.diastolic} mmHg`}</span></div></section><section className="review-section"><div className="section-heading"><h3>Medication plan</h3><button type="button" className="text-button" onClick={() => go(2)}>Edit</button></div>{medications.map((m, i) => <div className="review-medication" key={m.key}><span className="med-number">{i + 1}</span><div><strong>{drugs.find(d => d.id === m.drug_id)?.name}</strong><p>{m.dose} {m.unit} · {m.route} · At {m.time_seconds} s{Number(m.repeat_count) > 1 && ` · ${m.repeat_count}x every ${m.interval_seconds} s`}</p></div></div>)}<p className="muted compact">{checks.schedule_count} administration(s) over {horizon} seconds</p></section>
            {checks.errors.length > 0 && <div className="validation-errors"><TriangleAlert size={19} /><div><strong>Correct these entries before starting</strong><ul>{checks.errors.map((e, i) => <li key={i}>{e.field}: {e.message}</li>)}</ul></div></div>}
            <section className="coverage-review"><div className="section-heading"><FlaskConical size={21} /><h3>Available assessment</h3><span className="tag neutral">Evidence only</span></div>{checks.medication_coverage.map((m, i) => <div className="coverage-line" key={i}><span className={`coverage-dot ${m.coverage === "evidence_only" ? "evidence" : "unknown"}`} /><div><strong>{m.name}</strong><p>Catalogue associations: {m.associated_organs?.length ? m.associated_organs.map(organ => ORGAN_LABELS[organ]).join(", ") : "not recorded in this assessment"}</p><p>Reviewed caution rules: {m.reviewed_rule_organs?.length ? m.reviewed_rule_organs.map(organ => ORGAN_LABELS[organ]).join(", ") : "none"}</p><p>{m.scope}</p></div></div>)}<div className="coverage-limit"><CircleHelp size={19} /><p>Numerical organ response and drug concentrations are unavailable. The body animation is explanatory; graphs show recorded administration amounts.</p></div>{checks.missing_information.length > 0 && <details className="missing-details" open><summary>Missing information and assessment gaps <span>{checks.missing_information.length}</span></summary><ul>{checks.missing_information.map((line, i) => <li key={i}>{line}</li>)}</ul></details>}{checks.warnings.length > 0 && <div className="warning-message">{checks.warnings.map((line, i) => <p key={i}>{line}</p>)}</div>}<label className="assessment-consent"><input type="checkbox" checked={accepted} onChange={e => setAccepted(e.target.checked)} /><span>Run the evidence assessment with these stated limits. I understand it does not establish treatment safety.</span></label></section></div>}
          <div className="form-actions">{step > 0 && <button type="button" className="secondary-button" onClick={() => go(step - 1)}><ArrowLeft size={16} />Back</button>}<span className="form-step-count">Step {step + 1} of 4</span><button className="primary-button" type="submit" disabled={busy || (step === 3 && (!accepted || !checks?.can_run_evidence))}>{busy ? <RefreshCw className="spin" size={17} /> : step === 3 ? <Activity size={18} /> : null}{busy ? "Please wait..." : step === 3 ? "Run assessment" : step === 2 ? "Review assessment" : "Continue"}{!busy && step !== 3 && <ArrowRight size={16} />}</button></div>
        </form></div><aside className="case-summary"><h3>Case summary</h3><div className="summary-patient"><span className="patient-avatar"><UserRound size={24} /></span><div><strong>{patient.name || "New patient"}</strong><span>{patient.age ? `${patient.age} years` : "Age not entered"}{patient.gender && ` · ${human(patient.gender)}`}</span></div></div><div className="summary-section"><span>Organ history</span><strong>{conditionCount} recorded {conditionCount === 1 ? "condition" : "conditions"}</strong><div className="organ-summary-lines">{ORGANS.map(organ => <div key={organ}><span>{ORGAN_LABELS[organ]}</span>{organs[organ].status ? <CircleCheck size={14} /> : <span className="unfilled-dot" />}</div>)}</div></div><div className="summary-section"><span>Medication plan</span>{medications.filter(m => m.drug_id).length ? medications.filter(m => m.drug_id).map(m => <div className="summary-drug" key={m.key}><Pill size={14} /><span>{drugs.find(d => d.id === m.drug_id)?.name}<small>{m.dose || "Dose not entered"}{m.dose && ` ${m.unit}`}</small></span></div>) : <p>No medications entered</p>}</div><div className="summary-section"><span>Measured data</span><strong>{measurements.length + (bp.systolic && bp.diastolic ? 2 : 0)} entered values</strong></div><div className="summary-bottom"><ShieldCheck size={17} /><p>Assessment records stay in the local project database.</p></div></aside></div>}
      </main>
    </div><footer className="app-footer"><span>PDTT · Multi-organ assessment</span><span>Cardiovascular · Renal · Hepatic · Respiratory</span></footer>
  </div>;
}
