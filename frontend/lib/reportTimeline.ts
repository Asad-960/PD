import { Administration, Finding, Organ, ORGANS, SafetyAlert, TimelineReport, VisualCue } from "./contracts";

type TimedPoint = { time: number; [key: string]: number };

export function valueAtPoints<T extends TimedPoint>(points: T[], time: number, key: keyof T): number | null {
  if (!points.length || !Number.isFinite(time) || time < points[0].time || time > points[points.length - 1].time) return null;
  let beforeIndex = -1;
  for (let index = 0; index < points.length; index++) {
    if (points[index].time <= time) beforeIndex = index;
    else break;
  }
  if (beforeIndex < 0) return null;
  const before = points[beforeIndex];
  if (before.time === time || beforeIndex === points.length - 1) return Number(before[key]);
  const after = points[beforeIndex + 1];
  const fraction = (time - before.time) / (after.time - before.time);
  return Number(before[key]) + (Number(after[key]) - Number(before[key])) * fraction;
}

export type VisibleAdministration = Administration & { name: string; delivered: number };
export type TimelineFrame = {
  time: number;
  cues: Record<Organ, VisualCue[]>;
  findings: Record<Organ, Finding[]>;
  administrations: VisibleAdministration[];
  safetyAlerts: SafetyAlert[];
};

export function projectReportAt(report: TimelineReport, selectedTime: number): TimelineFrame {
  const time = Math.max(0, Math.min(report.last_time, selectedTime));
  const cues = {} as Record<Organ, VisualCue[]>;
  const findings = {} as Record<Organ, Finding[]>;
  for (const organ of ORGANS) {
    const normalized = (report.visual_responses?.[organ]?.cues ?? []).flatMap(cue => {
      if (cue.kind !== "source_linked_caution") return [cue];
      const rules = cue.rule_id ? [cue.rule_id] : cue.rule_ids;
      const exposure = cue.finding_id ? [] : [{ ...cue, kind: "exposure_only" as const,
        rule_id: null, rule_ids: [], finding_id: null }];
      const cautions = rules.flatMap(ruleId => {
        const matching = report.findings_timeline
          .filter(finding => finding.organ === organ && finding.coverage === "evidence_only" &&
            finding.rule_id === ruleId && finding.causal_event_ids?.includes(cue.event_id) &&
            (!cue.finding_id || finding.finding_id === cue.finding_id))
          .sort((a, b) => a.simulation_time - b.simulation_time)[0];
        return matching ? [{ ...cue, rule_id: ruleId, rule_ids: [ruleId],
          finding_id: matching.finding_id, time: matching.simulation_time }] : [];
      });
      return [...exposure, ...cautions];
    });
    const active = normalized.filter(cue => cue.time <= time).sort((a, b) =>
      a.time - b.time || Number(a.kind === "source_linked_caution") - Number(b.kind === "source_linked_caution"));
    cues[organ] = active;
    const byId = new Map(report.findings_timeline.filter(finding => finding.organ === organ &&
      finding.coverage === "evidence_only" && finding.simulation_time <= time)
      .map(finding => [finding.finding_id, finding]));
    findings[organ] = [...new Map(active.filter(cue => cue.kind === "source_linked_caution")
      .map(cue => cue.finding_id ? byId.get(cue.finding_id) : undefined)
      .filter((finding): finding is Finding => Boolean(finding))
      .map(finding => [finding.finding_id, finding] as const)).values()];
  }
  const administrations = (report.administrations ?? []).filter(action => action.simulation_time <= time)
    .map(action => ({...action,
      name: report.medications.find(row => row.drug_id === action.ingredient_id)?.name ?? action.ingredient_id,
      delivered: action.dose * (action.duration
        ? Math.min(1, Math.max(0, (time - action.simulation_time) / action.duration)) : 1),
    }));
  return { time, cues, findings, administrations,
    safetyAlerts: (report.safety_alerts ?? []).filter(alert => alert.time <= time) };
}
