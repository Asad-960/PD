"use client";
import { useState } from "react";
import { Plus, Trash2, Pill, ShieldAlert, Sparkles, Filter, Info } from "lucide-react";
import { Drug, MedicationDraft } from "../../lib/contracts";

export function blankMedication(): MedicationDraft {
  return { key: crypto.randomUUID(), drug_id: "", dose: "", unit: "mg", route: "oral", time_seconds: "0", duration_seconds: "0", repeat_count: "1", interval_seconds: "0" };
}

const CATEGORY_MAP: Record<string, { label: string; short: string; badgeClass: string }> = {
  "Painkillers & Analgesics": { label: "Painkillers & Analgesics", short: "Painkillers", badgeClass: "cat-pain" },
  "Cardiovascular & Antihypertensives": { label: "Cardiovascular & Antihypertensives", short: "Cardiovascular", badgeClass: "cat-cv" },
  "Emergency & Antidotes": { label: "Emergency & Antidotes", short: "Emergency / Antidotes", badgeClass: "cat-emergency" },
  "Diuretics & Renal": { label: "Diuretics & Fluid Balance", short: "Diuretics", badgeClass: "cat-diuretic" },
  "Metabolic & Antidiabetic": { label: "Metabolic & Endocrine", short: "Metabolic", badgeClass: "cat-metabolic" },
  "Intravenous Solutions & Fluids": { label: "Intravenous Solutions & Fluids", short: "IV Fluids", badgeClass: "cat-fluids" },
};

function getCategoryName(drug: Drug): string {
  if (drug.category && CATEGORY_MAP[drug.category]) return drug.category;
  if (["NSAID", "Opioid", "Analgesic"].includes(drug.class)) return "Painkillers & Analgesics";
  if (["ACE inhibitor", "ARB", "Calcium channel blocker"].includes(drug.class)) return "Cardiovascular & Antihypertensives";
  if (drug.class === "Opioid antagonist") return "Emergency & Antidotes";
  if (drug.class === "Loop diuretic") return "Diuretics & Renal";
  if (drug.class === "Biguanide") return "Metabolic & Antidiabetic";
  if (drug.class === "Crystalloid fluid") return "Intravenous Solutions & Fluids";
  return "Other Medications";
}

export default function MedicationFields({ values, catalogue, onChange, horizon, onHorizon }: { values: MedicationDraft[]; catalogue: Drug[]; onChange: (values: MedicationDraft[]) => void; horizon: string; onHorizon: (value: string) => void }) {
  const [selectedFilter, setSelectedFilter] = useState<string>("all");

  const update = (index: number, changes: Partial<MedicationDraft>) => onChange(values.map((row, i) => i === index ? { ...row, ...changes } : row));

  // Group catalogue items by clinical category
  const categories = Object.keys(CATEGORY_MAP);
  const groupedDrugs = categories.reduce<Record<string, Drug[]>>((acc, cat) => {
    acc[cat] = catalogue.filter(d => getCategoryName(d) === cat);
    return acc;
  }, {});

  return <div>
    <div className="section-heading">
      <div>
        <h3>Planned medications</h3>
        <p className="muted compact" style={{ marginTop: 2 }}>Classified by clinical therapeutic mechanism (Analgesics, Cardiovascular, Emergency, etc.)</p>
      </div>
      <span className="muted compact">{values.length} {values.length === 1 ? "medication" : "medications"}</span>
    </div>

    {/* Quick Category Filter Pills */}
    <div className="drug-category-filter-bar" role="group" aria-label="Filter drugs by classification">
      <span className="filter-label"><Filter size={13} /> Classify by type:</span>
      <button
        type="button"
        className={`category-pill ${selectedFilter === "all" ? "active" : ""}`}
        onClick={() => setSelectedFilter("all")}
      >
        All ({catalogue.length})
      </button>
      {categories.map(cat => {
        const meta = CATEGORY_MAP[cat];
        const count = groupedDrugs[cat]?.length || 0;
        if (!count) return null;
        return (
          <button
            type="button"
            key={cat}
            className={`category-pill ${selectedFilter === cat ? "active" : ""}`}
            onClick={() => setSelectedFilter(selectedFilter === cat ? "all" : cat)}
            title={meta.label}
          >
            {meta.short} ({count})
          </button>
        );
      })}
    </div>

    <div className="medication-list">
      {values.map((row, index) => {
        const drug = catalogue.find(d => d.id === row.drug_id);
        const drugCategory = drug ? getCategoryName(drug) : null;
        const catMeta = drugCategory ? CATEGORY_MAP[drugCategory] : null;

        // Filter catalogue if user picked a category filter, but always keep the currently selected drug visible
        const displayedCatalogue = selectedFilter === "all"
          ? catalogue
          : catalogue.filter(d => getCategoryName(d) === selectedFilter || d.id === row.drug_id);

        const displayedGrouped = categories.reduce<Record<string, Drug[]>>((acc, cat) => {
          const inGroup = displayedCatalogue.filter(d => getCategoryName(d) === cat);
          if (inGroup.length) acc[cat] = inGroup;
          return acc;
        }, {});

        return (
          <section className="medication-row enhanced-card" key={row.key}>
            <div className="medication-heading">
              <span className="med-icon-wrap"><Pill size={18} /></span>
              <div className="med-title-group">
                <strong>Medication {index + 1}</strong>
                {drug && (
                  <div className="med-tags">
                    {catMeta && (
                      <span className={`tag category-badge ${catMeta.badgeClass}`}>
                        {catMeta.short}
                      </span>
                    )}
                    <span className="tag neutral drug-class-badge">{drug.class}</span>
                  </div>
                )}
              </div>
              <button
                type="button"
                className="icon-button push-right"
                title="Remove medication"
                aria-label={`Remove medication ${index + 1}`}
                onClick={() => onChange(values.filter((_, i) => i !== index))}
              >
                <Trash2 size={16} />
              </button>
            </div>

            <div className="medication-grid">
              <label className="field medication-select">
                <span>Medication / formulation <small>(Grouped by therapeutic class)</small></span>
                <select
                  aria-label={`Medication ${index + 1}`}
                  required
                  value={row.drug_id}
                  onChange={e => {
                    const selected = catalogue.find(d => d.id === e.target.value);
                    update(index, {
                      drug_id: e.target.value,
                      unit: selected?.units[0] || "mg",
                      route: selected?.routes[0] || "oral",
                      duration_seconds: "0"
                    });
                  }}
                >
                  <option value="">Select medication...</option>
                  {Object.entries(displayedGrouped).map(([cat, list]) => (
                    <optgroup key={cat} label={cat.toUpperCase()}>
                      {list.map(d => (
                        <option value={d.id} key={d.id}>
                          {d.name} · {d.formulation} ({d.class})
                        </option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Dose / amount</span>
                <input
                  aria-label={`Dose ${index + 1}`}
                  required
                  type="number"
                  min="0.000001"
                  max="1000000000"
                  step="any"
                  placeholder="Amount"
                  value={row.dose}
                  onChange={e => update(index, { dose: e.target.value })}
                />
              </label>

              <label className="field">
                <span>Unit</span>
                <select
                  aria-label={`Unit ${index + 1}`}
                  value={row.unit}
                  onChange={e => update(index, { unit: e.target.value })}
                >
                  {(drug?.units || ["mg"]).map(u => <option key={u}>{u}</option>)}
                </select>
              </label>

              <label className="field">
                <span>Route</span>
                <select
                  aria-label={`Route ${index + 1}`}
                  value={row.route}
                  onChange={e => update(index, { route: e.target.value, duration_seconds: "0" })}
                >
                  {(drug?.routes || ["oral"]).map(r => (
                    <option key={r} value={r}>{r.replaceAll("_", " ")}</option>
                  ))}
                </select>
              </label>
            </div>

            <div className="schedule-grid">
              <label className="field">
                <span>Start time <small>seconds</small></span>
                <input
                  aria-label={`Start time ${index + 1}`}
                  required
                  type="number"
                  min="0"
                  max="3600"
                  step="any"
                  value={row.time_seconds}
                  onChange={e => update(index, { time_seconds: e.target.value })}
                />
              </label>

              <label className="field">
                <span>Administrations</span>
                <input
                  aria-label={`Administrations ${index + 1}`}
                  required
                  type="number"
                  min="1"
                  max="20"
                  step="1"
                  value={row.repeat_count}
                  onChange={e => update(index, { repeat_count: e.target.value })}
                />
              </label>

              {Number(row.repeat_count) > 1 && (
                <label className="field">
                  <span>Interval <small>seconds</small></span>
                  <input
                    aria-label={`Interval ${index + 1}`}
                    required
                    type="number"
                    min="0.001"
                    max="3600"
                    step="any"
                    value={row.interval_seconds}
                    onChange={e => update(index, { interval_seconds: e.target.value })}
                  />
                </label>
              )}

              {row.route === "intravenous" && (
                <label className="field">
                  <span>Infusion duration <small>seconds; 0 = bolus</small></span>
                  <input
                    aria-label={`Infusion duration ${index + 1}`}
                    required
                    type="number"
                    min="0"
                    max="3600"
                    step="any"
                    value={row.duration_seconds}
                    onChange={e => update(index, { duration_seconds: e.target.value })}
                  />
                </label>
              )}
            </div>

            {drug && (
              <div className="medication-scope">
                <span className={`coverage-dot ${drug.evidence_available ? "evidence" : "unknown"}`} />
                <div className="scope-text">
                  <strong>{drug.rule_scope}</strong>
                  {drug.target_organs?.length > 0 && (
                    <span className="target-organs-hint">
                      Catalogue organ associations (not predicted effects): {drug.target_organs.join(", ")}
                    </span>
                  )}
                </div>
              </div>
            )}
          </section>
        );
      })}
    </div>

    <div className="medication-actions-bar">
      <button
        type="button"
        className="secondary-button"
        disabled={values.length >= 24}
        onClick={() => onChange([...values, blankMedication()])}
      >
        <Plus size={16} /> Add medication
      </button>

      <div className="horizon-row">
        <label className="field">
          <span>Assessment horizon <small>seconds</small></span>
          <input
            aria-label="Assessment horizon"
            required
            type="number"
            min="10"
            max="3600"
            step="any"
            value={horizon}
            onChange={e => onHorizon(e.target.value)}
          />
        </label>
      </div>
    </div>
  </div>;
}

