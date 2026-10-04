"use client";
import { useEffect, useRef, useState } from "react";
import { Activity, FileText, ChartNoAxesCombined, Download, Play, Pause, RotateCcw, ChevronDown, ExternalLink, ArrowLeft, HeartPulse, Wind, Droplets, TriangleAlert, CircleHelp, Check, RefreshCw } from "lucide-react";
import { ResponsiveContainer, AreaChart, Area, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip, ReferenceLine, ReferenceArea } from "recharts";
import BodyScene from "../simulation/BodyScene";
import { AdministrationSeries, Finding, Organ, ORGANS, ORGAN_COLORS, ORGAN_LABELS, PKSeries, TimelineReport } from "../../lib/contracts";

function readable(value: string) { return value.replaceAll("_", " "); }
function FindingDetails({ finding }: { finding: Finding }) {
  return <div className={`finding ${finding.coverage === "evidence_only" ? "has-concern" : ""}`}>
    <div className="finding-top"><span className={`tag ${finding.coverage === "evidence_only" ? "warning" : "neutral"}`}>{finding.coverage === "evidence_only" ? "Review concern" : "Not assessed"}</span><span className="muted compact">{finding.simulation_time.toFixed(0)} s</span></div>
    <p className="finding-message">{finding.message}</p>
    <details><summary>Reasoning and source <ChevronDown size={15} /></summary><p>{finding.explanation}</p>{Object.keys(finding.inputs_observed).length > 0 && <dl className="observed-facts">{Object.entries(finding.inputs_observed).map(([key, value]) => <div key={key}><dt>{readable(key)}</dt><dd>{String(value)}</dd></div>)}</dl>}{finding.missing_inputs.length > 0 && <p className="muted">Missing: {finding.missing_inputs.map(readable).join(", ")}</p>}<p className="muted">{finding.limitations}</p>{finding.sources.map(source => <a className="source-link" key={source.source_id} href={source.url} target="_blank" rel="noreferrer">{source.title}<ExternalLink size={13} /></a>)}<p className="rule-reference">{finding.rule_id} · Snapshot {finding.source_snapshot_sequence}</p></details>
  </div>;
}

function AmountChart({ series, report, time }: { series: AdministrationSeries; report: TimelineReport; time?: number }) {
  const [chartMode, setChartMode] = useState<"pk" | "cumulative">("pk");
  const pk = report.pk_series?.find(p => p.drug_id === series.drug_id);

  // If no PK available, fallback to cumulative
  const activeMode = pk ? chartMode : "cumulative";

  const currentPkVal = pk && time !== undefined
    ? pk.points.find(p => p.time >= time)?.concentration ?? pk.points[pk.points.length - 1]?.concentration
    : null;

  return (
    <div className="amount-chart enhanced-chart-card">
      <div className="chart-header-row">
        <div className="chart-title">
          <div className="title-with-pill">
            <strong>{series.name}</strong>
            <span className="chart-type-tag">
              {activeMode === "pk" ? "Simulated PK Plasma Profile" : "Cumulative Delivery Ledger"}
            </span>
          </div>
          <span className="muted compact">
            {activeMode === "pk" ? `Plasma Concentration (${pk?.unit})` : `Administered amount (${series.unit})`}
          </span>
        </div>

        {pk && (
          <div className="chart-mode-toggle" role="group" aria-label="Chart display mode">
            <button
              type="button"
              className={`mode-btn ${activeMode === "pk" ? "active" : ""}`}
              onClick={() => setChartMode("pk")}
            >
              PK Curve
            </button>
            <button
              type="button"
              className={`mode-btn ${activeMode === "cumulative" ? "active" : ""}`}
              onClick={() => setChartMode("cumulative")}
            >
              Cumulative
            </button>
          </div>
        )}
      </div>

      {/* KPI metric chips for PK curve */}
      {activeMode === "pk" && pk && (
        <div className="pk-metrics-strip">
          <div className="metric-chip">
            <span className="chip-label">Peak Cmax:</span>
            <strong>{pk.c_max} {pk.unit}</strong>
          </div>
          <div className="metric-chip">
            <span className="chip-label">Tmax:</span>
            <strong>{pk.t_max} s</strong>
          </div>
          <div className="metric-chip">
            <span className="chip-label">Target Range:</span>
            <span className="target-badge">{pk.therapeutic_min} – {pk.therapeutic_max} {pk.unit}</span>
          </div>
          <div className="metric-chip">
            <span className="chip-label">Elimination t½:</span>
            <span>~{Math.round(pk.t_half_seconds / 60)} min</span>
          </div>
          {currentPkVal !== null && (
            <div className="metric-chip live-scrub">
              <span className="chip-label">Level @ {time?.toFixed(0)}s:</span>
              <strong style={{ color: "#059669" }}>{currentPkVal} {pk.unit}</strong>
            </div>
          )}
        </div>
      )}

      <div className="chart-surface">
        <ResponsiveContainer width="100%" height="100%">
          {activeMode === "pk" && pk ? (
            <AreaChart data={pk.points} margin={{ top: 16, right: 24, bottom: 6, left: 10 }}>
              <defs>
                <linearGradient id={`pkGrad_${series.drug_id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.45} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#e4ece7" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                type="number"
                domain={[0, report.horizon_seconds]}
                allowDuplicatedCategory
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#cbd5e1" }}
                unit="s"
              />
              <YAxis
                width={52}
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#cbd5e1" }}
                domain={[0, "auto"]}
              />
              {/* Shaded Therapeutic Target Window */}
              {pk.therapeutic_max > 0 && (
                <ReferenceArea
                  y1={pk.therapeutic_min}
                  y2={pk.therapeutic_max}
                  fill="#10b98114"
                  stroke="#10b98135"
                  strokeDasharray="2 2"
                />
              )}
              {/* Peak Cmax Reference Line */}
              {pk.c_max > 0 && (
                <ReferenceLine
                  y={pk.c_max}
                  stroke="#d97706"
                  strokeDasharray="3 3"
                  strokeWidth={1.2}
                />
              )}
              {/* Scheduled administration times */}
              {report.schedule.filter(s => s.ingredient_id === series.drug_id).map((s, i) => (
                <ReferenceLine key={i} x={s.simulation_time} stroke="#94a3b8" strokeDasharray="3 4" />
              ))}
              {/* Playback time scrubber */}
              {time !== undefined && (
                <ReferenceLine x={time} stroke="#f97316" strokeWidth={2} />
              )}
              <Tooltip
                formatter={value => [`${Number(value).toFixed(2)} ${pk.unit}`, "Simulated Concentration"]}
                labelFormatter={value => `${Number(value).toFixed(1)} s`}
                contentStyle={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 6,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="concentration"
                stroke="#059669"
                strokeWidth={2.5}
                fillOpacity={1}
                fill={`url(#pkGrad_${series.drug_id})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          ) : (
            <AreaChart data={series.points} margin={{ top: 16, right: 24, bottom: 6, left: 10 }}>
              <defs>
                <linearGradient id={`cumGrad_${series.drug_id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#0f766e" stopOpacity={0.35} />
                  <stop offset="95%" stopColor="#0f766e" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="#e4ece7" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                type="number"
                domain={[0, report.horizon_seconds]}
                allowDuplicatedCategory
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#cbd5e1" }}
                unit="s"
              />
              <YAxis
                width={52}
                tick={{ fontSize: 11, fill: "#64748b" }}
                tickLine={false}
                axisLine={{ stroke: "#cbd5e1" }}
                domain={[0, "auto"]}
              />
              <Tooltip
                formatter={value => [`${Number(value).toLocaleString()} ${series.unit}`, "Administered"]}
                labelFormatter={value => `${Number(value).toFixed(1)} seconds`}
                contentStyle={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: 6,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.08)",
                  fontSize: 12,
                }}
              />
              <Area
                type="stepAfter"
                dataKey="value"
                stroke="#0f766e"
                strokeWidth={2.5}
                fillOpacity={1}
                fill={`url(#cumGrad_${series.drug_id})`}
                dot={false}
                isAnimationActive={false}
              />
              {report.schedule.filter(s => s.ingredient_id === series.drug_id).map((s, i) => (
                <ReferenceLine key={i} x={s.simulation_time} stroke="#94a3b8" strokeDasharray="3 4" />
              ))}
              {time !== undefined && (
                <ReferenceLine x={time} stroke="#f97316" strokeWidth={2} />
              )}
            </AreaChart>
          )}
        </ResponsiveContainer>
      </div>
      <div className="chart-legend-row">
        {activeMode === "pk" ? (
          <span className="legend-note">
            Shaded band indicates therapeutic target window · Smooth curve models absorption and elimination kinetics.
          </span>
        ) : (
          <span className="legend-note">
            Calculated arithmetic ledger of administered doses over time.
          </span>
        )}
      </div>
    </div>
  );
}

export default function ReportView({ report, onNewCase, onRefresh }: { report: TimelineReport; onNewCase: () => void; onRefresh: () => void }) {
  const [tab, setTab] = useState<"body" | "report" | "graphs">("body");
  const [selected, setSelected] = useState<Organ>("cardiovascular");
  const [time, setTime] = useState(0);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(10);
  const [seriesId, setSeriesId] = useState(report.administration_series[0]?.drug_id || "");
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState("");
  const playTime = useRef(0);
  const finalStarted = useRef(report.is_final);
  useEffect(() => {
    if (report.is_final && !finalStarted.current) {
      finalStarted.current = true;
      playTime.current = 0; setTime(0); setPlaying(true);
    }
  }, [report.is_final]);
  useEffect(() => {
    if (!playing || tab !== "body") return;
    let raf: number;
    let last = performance.now();
    const advance = (now: number) => {
      playTime.current = Math.min(report.last_time, playTime.current + Math.min((now-last)/1000, .1) * speed);
      last = now;
      setTime(playTime.current);
      if (playTime.current >= report.last_time) { setPlaying(false); return; }
      raf = requestAnimationFrame(advance);
    };
    raf = requestAnimationFrame(advance);
    return () => cancelAnimationFrame(raf);
  }, [playing, speed, report.last_time, tab]);
  useEffect(() => { if (!seriesId && report.administration_series[0]) setSeriesId(report.administration_series[0].drug_id); }, [report, seriesId]);
  const seek = (next: number) => { playTime.current = next; setTime(next); };
  const visible = report.findings_timeline.filter(f => f.organ === selected && f.simulation_time <= time);
  const latest = new Map<string, Finding>();
  visible.forEach(f => latest.set(f.rule_id || f.finding_id, f));
  const visibleFindings = [...latest.values()].filter(f => f.coverage === "evidence_only");
  const visual = report.visual_responses?.[selected];
  const visibleCues = visual?.cues.filter(cue => cue.time <= time) || [];
  const selectedSignal = visibleFindings.length ? "Review required" : visual?.condition_mechanisms.length ? "Condition recorded" : "No concern in checked rules";
  const concerns = ORGANS.filter(organ => report.findings_timeline.some(f => f.organ === organ && f.coverage === "evidence_only" && f.simulation_time <= time));
  const series = report.administration_series.find(s => s.drug_id === seriesId) || report.administration_series[0];
  const activeMedications = (report.administrations || []).filter(m => m.simulation_time <= time).map(m => ({ ...m,
    name: report.medications.find(row => row.drug_id === m.ingredient_id)?.name || m.ingredient_id,
    delivered: m.dose * (m.duration ? Math.min(1, Math.max(0, (time - m.simulation_time) / m.duration)) : 1) }));
  const icons = { cardiovascular: HeartPulse, respiratory: Wind, renal: Droplets, hepatic: Activity };
  const SelectedIcon = icons[selected];

  async function download() {
    setDownloading(true); setDownloadError("");
    try {
      const response = await fetch(`/api/runs/${report.run_id}/report.pdf?cursor=${report.cursor}`);
      if (!response.ok) throw new Error("The PDF could not be generated. Retry the download.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a"); link.href = url; link.download = `${report.report_id}.pdf`; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 10000);
    } catch (error) { setDownloadError(error instanceof Error ? error.message : "Download failed."); }
    finally { setDownloading(false); }
  }

  return <div className="result-workspace">
    <div className="result-heading"><div><span className="tag neutral">{report.is_final ? "Assessment complete" : `Partial · ${report.status}`}</span><h1>{report.patient.name || "Patient assessment"}</h1><p className="muted">{report.patient.age} years · {readable(report.patient.gender)} · {report.report_id}</p></div><div className="result-actions"><button type="button" className="secondary-button" onClick={onNewCase}><ArrowLeft size={16} />Edit case</button><button type="button" className="primary-button" disabled={downloading} onClick={download}>{downloading ? <RefreshCw className="spin" size={17} /> : <Download size={17} />}{downloading ? "Generating..." : "Download PDF"}</button></div></div>
    {downloadError && <div className="error-message" role="alert">{downloadError}</div>}
    <div className="result-tabs" role="tablist" aria-label="Assessment views">{[{ id: "body", name: "Body simulation", icon: Activity }, { id: "report", name: "Assessment report", icon: FileText }, { id: "graphs", name: "Graphs", icon: ChartNoAxesCombined }].map(item => <button type="button" role="tab" aria-selected={tab === item.id} key={item.id} onClick={() => setTab(item.id as typeof tab)} className={tab === item.id ? "active" : ""}><item.icon size={18} />{item.name}</button>)}<span className="tab-status"><span className="coverage-dot evidence" />Evidence assessment</span></div>

    {tab === "body" && <>
      <div className="simulation-layout"><div className="body-column"><BodyScene selected={selected} onSelect={setSelected} playing={playing} time={time} sex={report.patient.sex === "female" || report.patient.gender === "female" || report.patient.gender === "woman" ? "female" : "male"} responses={report.visual_responses} />
        <div className="playback"><div className="playback-top"><button type="button" className="play-button" title={playing ? "Pause playback" : "Play playback"} aria-label={playing ? "Pause playback" : "Play playback"} onClick={() => { if (time >= report.last_time) seek(0); setPlaying(!playing); }}>{playing ? <Pause size={18} fill="currentColor" /> : <Play size={18} fill="currentColor" />}</button><button type="button" className="icon-button" aria-label="Replay from start" title="Replay from start" onClick={() => { seek(0); setPlaying(true); }}><RotateCcw size={17} /></button><span className="time-counter">{time.toFixed(0)} <span>/ {report.last_time.toFixed(0)} s</span></span><label className="speed-control"><span>Speed</span><select aria-label="Playback speed" value={speed} onChange={e => setSpeed(Number(e.target.value))}>{[1, 5, 10, 20, 50].map(s => <option key={s} value={s}>{s}x</option>)}</select></label></div><input className="timeline-slider" aria-label="Simulation time" type="range" min="0" max={report.last_time || 1} step="0.1" value={time} onChange={e => { setPlaying(false); seek(Number(e.target.value)); }} /><div className="timeline-labels"><span>0 s</span><span>Administration timeline</span><span>{report.last_time.toFixed(0)} s</span></div></div>
      </div><aside className="organ-inspection"><div className="organ-switcher">{ORGANS.map(organ => { const Icon = icons[organ]; return <button type="button" key={organ} className={`icon-button ${selected === organ ? "selected" : ""}`} title={ORGAN_LABELS[organ]} aria-label={`Inspect ${ORGAN_LABELS[organ]}`} onClick={() => setSelected(organ)} style={{ color: ORGAN_COLORS[organ] }}><Icon size={20} /></button>; })}</div>
        <div className="inspection-title"><SelectedIcon size={24} color={ORGAN_COLORS[selected]} /><h2>{ORGAN_LABELS[selected]}</h2></div><div className={`organ-verdict ${visibleFindings.length ? "alert" : visual?.condition_mechanisms.length ? "history" : "clear"}`}><span>Rule-based signal</span><strong>{selectedSignal}</strong><small>{visibleFindings.length ? "A source-linked caution applies to this case." : "Not a declaration that this organ or regimen is safe."}</small></div><div className="inspection-history"><span className="muted compact">Recorded conditions</span>{report.organs[selected].conditions.length ? report.organs[selected].conditions.map(c => <div key={c.condition_id}><strong>{c.name}</strong><span>{c.severity === "unknown" ? "Stage unknown" : c.severity}</span></div>) : <p>{readable(report.organs[selected].history_status)}</p>}</div>
        {visual && <div className="visual-response"><span className="muted compact">Visual response</span><strong>{visual.pattern_label}</strong>{visual.condition_mechanisms.map(item => <p key={item.condition_id}><b>{item.condition_name}:</b> {item.description}</p>)}{!visual.condition_mechanisms.length && <p>Resting motion is shown. No condition-specific response was entered for this organ.</p>}{visibleCues.map(cue => <p key={cue.event_id}><b>{cue.drug_name}:</b> {cue.kind === "source_linked_caution" ? "Evidence caution shown by red pulse." : "Exposure shown; no drug effect is predicted."}</p>)}</div>}
        {visibleFindings.length ? visibleFindings.map(f => <FindingDetails finding={f} key={f.rule_id} />) : <div className="unassessed-state"><CircleHelp size={23} /><strong>No source-linked caution at this time</strong><p>The available checks do not establish organ function or medication safety.</p></div>}
        <div className="active-exposures"><h3>Recorded administrations</h3>{activeMedications.length ? activeMedications.map(m => <div key={m.event_id}><span>{m.name}<small>At {m.simulation_time}s{m.duration ? " · Infusion" : ""}</small></span><strong>{m.delivered.toLocaleString(undefined, { maximumSignificantDigits: 15 })} {m.unit}</strong></div>) : <p className="muted">None yet</p>}</div>
      </aside></div>
      {series && <div className="compact-chart-band"><div className="chart-band-heading"><h3>Administration record</h3><select aria-label="Chart medication" value={series.drug_id} onChange={e => setSeriesId(e.target.value)}>{report.administration_series.map(s => <option key={s.drug_id} value={s.drug_id}>{s.name}</option>)}</select></div><AmountChart series={series} report={report} time={time} /><p className="muted compact">Administered amounts are schedule arithmetic. Blood concentration and organ-response graphs are unavailable.</p></div>}
    </>}

    {tab === "report" && <article className="lab-report"><div className="lab-report-header"><div className="report-brand"><span className="brand-mark"><Activity size={25} /></span><strong>PDTT</strong></div><div><h2>Medication and Organ Assessment</h2><p>{new Date(report.created_at).toLocaleString("en-PK", { timeZone: "Asia/Karachi" })} · {report.report_id}</p></div></div><div className="report-scope-note"><TriangleAlert size={17} /><span>Evidence assessment only. Simulated outputs are not laboratory results or validated patient-specific predictions.</span></div><div className="report-organ-strip">{ORGANS.map(organ => { const caution = report.organs[organ].outcome === "concern_identified"; const condition = Boolean(report.organs[organ].conditions.length); return <div key={organ} className={`report-organ-signal ${caution ? "alert" : condition ? "history" : "quiet"}`}><span>{ORGAN_LABELS[organ]}</span><strong>{caution ? "Review required" : condition ? "Condition recorded" : "No flag in limited checks"}</strong></div>; })}</div>
      <section className="report-section"><h3>Patient details</h3><dl className="patient-report-grid"><div><dt>Name / identifier</dt><dd>{report.patient.name || report.patient_id}</dd></div><div><dt>Age</dt><dd>{report.patient.age} years</dd></div><div><dt>Gender</dt><dd>{readable(report.patient.gender)}{report.patient.gender_detail && `: ${report.patient.gender_detail}`}</dd></div><div><dt>Body mass</dt><dd>{report.patient.mass_kg === null ? "Not supplied" : `${report.patient.mass_kg} kg`}</dd></div><div><dt>BP history</dt><dd>{readable(report.blood_pressure.status)}</dd></div><div><dt>Allergies</dt><dd>{report.patient.allergies.join(", ") || readable(report.patient.allergies_status)}</dd></div><div><dt>Ongoing medications</dt><dd>{report.patient.current_medications.join(", ") || readable(report.patient.current_medications_status)}</dd></div><div><dt>Assessment status</dt><dd>{report.is_final ? "Final report" : `Partial: ${report.status}`}</dd></div></dl></section>
      <section className="report-section"><h3>History context</h3><p>BP control: {readable(report.blood_pressure.control)}</p>{report.blood_pressure.notes && <p>{report.blood_pressure.notes}</p>}{ORGANS.flatMap(organ => report.organs[organ].conditions.filter(c => c.notes || c.subtype !== "unknown").map(c => <p key={`${organ}-${c.condition_id}`}><strong>{c.name}</strong>{c.subtype !== "unknown" && ` · ${c.subtype}`}{c.notes && `: ${c.notes}`}</p>))}</section>
      <section className="report-section"><h3>Medication plan</h3><div className="table-scroll"><table><thead><tr><th>Medication</th><th>Dose / amount</th><th>Route</th><th>Schedule</th><th>Coverage</th></tr></thead><tbody>{report.medications.map((m, i) => <tr key={i}><td><strong>{m.name}</strong><small>{m.drug_class}</small></td><td>{m.dose} {m.unit}</td><td>{readable(m.route)}</td><td>At {m.time_seconds}s{m.repeat_count > 1 ? `, ${m.repeat_count}x every ${m.interval_seconds}s` : ""}{m.duration_seconds > 0 && ` over ${m.duration_seconds}s`}</td><td><span className="tag neutral">{readable(m.coverage)}</span></td></tr>)}</tbody></table></div></section>
      <section className="report-section"><h3>Four-system assessment</h3>{ORGANS.map(organ => { const Icon = icons[organ]; const response = report.visual_responses?.[organ]; const caution = report.organs[organ].outcome === "concern_identified"; return <div className="organ-report-section" key={organ}><div className="section-heading"><Icon color={ORGAN_COLORS[organ]} size={22} /><h4>{ORGAN_LABELS[organ]}</h4><span className={`tag ${caution ? "warning" : "neutral"}`}>{caution ? "Review required" : response?.condition_mechanisms.length ? "Condition recorded" : "No flag in limited checks"}</span></div><p className="muted">{report.organs[organ].conditions.map(c => `${c.name} (${c.severity})`).join(", ") || `History: ${readable(report.organs[organ].history_status)}`}</p>{response && <p><strong>Illustrated response: {response.pattern_label}.</strong> {response.condition_mechanisms.map(item => item.description).join("; ")}</p>}{report.organs[organ].findings.filter(f => f.coverage === "evidence_only").map(f => <FindingDetails key={f.rule_id} finding={f} />)}<p>Clinical safety and organ function remain unverified.</p></div>; })}</section>
      <section className="report-section"><h3>Entered measurements</h3>{report.measurements.length ? <div className="table-scroll"><table><thead><tr><th>Measurement</th><th>Entered value</th><th>Unit</th><th>Observed at</th><th>Source</th></tr></thead><tbody>{report.measurements.map(m => <tr key={m.name}><td>{m.label}</td><td>{m.value}</td><td>{m.unit}</td><td>{m.observed_at || "Not supplied"}</td><td>{m.provenance}</td></tr>)}</tbody></table></div> : <div className="empty-measurements"><CircleHelp size={20} /><p>No measurements were supplied. Missing lab values remain unknown.</p></div>}<p className="muted compact">No normality interpretation or reference range is inferred from these entries.</p></section>
      <section className="report-section"><h3>Medication interactions</h3>{report.interactions.length ? report.interactions.map((pair, i) => <div key={i} className="interaction-row"><strong>{pair.drug_a} + {pair.drug_b}</strong><span className="tag neutral">Not assessed</span><p>{pair.explanation}</p></div>) : <p>Comprehensive interaction assessment is unavailable. A single medication does not imply a safe regimen.</p>}</section>
      <section className="report-section"><h3>Available graphs</h3>{report.administration_series.map(s => <AmountChart key={s.drug_id} series={s} report={report} />)}<p className="muted compact">These graphs show administered amounts, not concentrations or organ response.</p></section>
      <section className="report-section"><h3>Missing information and limits</h3><ul className="limits-list">{[...report.scope.missing_information, ...report.limitations].map((line, i) => <li key={i}>{line}</li>)}</ul><details className="source-note"><summary>Assessment provenance</summary><p>{report.engine.name} {report.engine.version}</p><p>Catalogue {report.catalogue_version} · Event cursor {report.cursor}</p><p>Run {report.run_id}</p></details></section>
    </article>}

    {tab === "graphs" && <div className="graphs-view"><div className="section-heading"><h2>Administration timeline</h2><span className="tag neutral">Arithmetic ledger</span></div>{report.administration_series.map(s => <AmountChart key={s.drug_id} series={s} report={report} />)}<div className="unavailable-graphs"><CircleHelp size={25} /><div><h3>Physiological response graphs unavailable</h3><p>Blood pressure, filtration, liver markers, oxygenation, and drug concentrations need a verified numerical model. Entered baseline measurements are retained in the report.</p></div></div></div>}
    <div className="result-footer"><span>{report.report_id} · {report.is_final ? "Completed" : "Partial report"}</span><span>{report.snapshots.length} recorded snapshots</span><button type="button" className="text-button" onClick={onRefresh}><RefreshCw size={14} />Refresh assessment</button></div>
  </div>;
}
