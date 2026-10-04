"use client";
import { useState } from "react";
import { HeartPulse, Wind, Droplets, Activity, Plus, X, Search } from "lucide-react";
import { Condition, Organ, OrganDraft, ORGANS, ORGAN_LABELS, ORGAN_COLORS } from "../../lib/contracts";

const icons = { cardiovascular: HeartPulse, renal: Droplets, hepatic: Activity, respiratory: Wind };

export default function OrganFields({ values, catalogue, onChange }: { values: Record<Organ, OrganDraft>; catalogue: Condition[]; onChange: (organ: Organ, value: OrganDraft) => void }) {
  const [searches, setSearches] = useState<Record<string, string>>({});
  return <div className="organ-intake">{ORGANS.map(organ => {
    const Icon = icons[organ];
    const value = values[organ];
    const available = catalogue.filter(c => c.organ === organ && !value.conditions.some(s => s.condition_id === c.id) && c.name.toLowerCase().includes((searches[organ] || "").toLowerCase()));
    const groups = Array.from(new Set(available.map(c => c.group)));
    return <section className="organ-section" key={organ}>
      <div className="section-heading"><span className="organ-icon" style={{ color: ORGAN_COLORS[organ], backgroundColor: `${ORGAN_COLORS[organ]}12` }}><Icon size={22} /></span><h3>{ORGAN_LABELS[organ]}</h3><span className="muted compact">{catalogue.filter(c => c.organ === organ).length} conditions</span></div>
      <fieldset className="status-options"><legend className="sr-only">{ORGAN_LABELS[organ]} history</legend>{[["none_known", "No known problem"], ["conditions", "Known conditions"], ["unknown", "Unknown / not assessed"]].map(([id, label]) => <label key={id} className={value.status === id ? "selected" : ""}><input type="radio" name={`${organ}-status`} value={id} checked={value.status === id} onChange={() => onChange(organ, { status: id as OrganDraft["status"], conditions: id === "conditions" ? value.conditions : [] })} />{label}</label>)}</fieldset>
      {value.status === "conditions" && <div className="condition-editor">
        <div className="condition-search"><Search size={16} /><input aria-label={`Search ${ORGAN_LABELS[organ]} conditions`} placeholder="Search conditions" value={searches[organ] || ""} onChange={e => setSearches({ ...searches, [organ]: e.target.value })} /></div>
        <label className="field"><span>Add a condition</span><select aria-label={`Add ${ORGAN_LABELS[organ]} condition`} value="" onChange={e => { if (e.target.value) { onChange(organ, { ...value, conditions: [...value.conditions, { condition_id: e.target.value, severity: "unknown", subtype: "unknown", notes: "" }] }); setSearches({ ...searches, [organ]: "" }); } }}><option value="">Select a condition...</option>{groups.map(group => <optgroup key={group} label={group}>{available.filter(c => c.group === group).map(c => <option key={c.id} value={c.id}>{c.name}</option>)}</optgroup>)}</select></label>
        {value.conditions.map((selected, index) => {
          const info = catalogue.find(c => c.id === selected.condition_id)!;
          const update = (changes: Partial<typeof selected>) => onChange(organ, { ...value, conditions: value.conditions.map((c, i) => i === index ? { ...c, ...changes } : c) });
          return <div className="condition-row" key={selected.condition_id}>
            <div className="condition-title"><strong>{info.name}</strong><button type="button" className="icon-button" title={`Remove ${info.name}`} aria-label={`Remove ${info.name}`} onClick={() => onChange(organ, { ...value, conditions: value.conditions.filter((_, i) => i !== index) })}><X size={17} /></button></div>
            <div className="form-grid"><label className="field"><span>Stage / severity</span><select value={selected.severity} onChange={e => update({ severity: e.target.value })}>{info.severity_options.map(s => <option key={s} value={s}>{s === "unknown" ? "Unknown" : s}</option>)}</select></label>{info.subtypes && <label className="field"><span>Subtype</span><select value={selected.subtype} onChange={e => update({ subtype: e.target.value })}>{info.subtypes.map(s => <option key={s} value={s}>{s === "unknown" ? "Unknown" : s}</option>)}</select></label>}<label className={`field ${!info.subtypes ? "" : "span-2"}`}><span>Relevant history <small>Optional</small></span><input maxLength={300} value={selected.notes} onChange={e => update({ notes: e.target.value })} placeholder="Recorded history or complications" /></label></div>
            <details className="source-note"><summary>Condition reference</summary>{info.references.map((r, i) => <p key={i}>{r.document} · {r.section}</p>)}</details>
          </div>;
        })}
        {!value.conditions.length && <p className="empty-inline">Select at least one condition for this system.</p>}
      </div>}
    </section>;
  })}</div>;
}
