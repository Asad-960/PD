import { test, expect } from "@playwright/test";
import { projectReportAt, valueAtPoints } from "../lib/reportTimeline";
import { TimelineReport } from "../lib/contracts";

test("interpolates only within known segments and preserves bolus jumps", () => {
  const points = [
    { time: 0, value: 0 }, { time: 10, value: 0 },
    { time: 10, value: 80 }, { time: 20, value: 40 },
  ];
  expect(valueAtPoints(points, 5, "value")).toBe(0);
  expect(valueAtPoints(points, 10, "value")).toBe(80);
  expect(valueAtPoints(points, 15, "value")).toBe(60);
  expect(valueAtPoints([{ time: 0, value: 0 }, { time: 60, value: 500 }], 30, "value")).toBe(250);
  expect(valueAtPoints(points, 21, "value")).toBeNull();
});

test("organ caution does not precede its committed finding", () => {
  const report = {
    last_time: 60,
    administrations: [{ event_id: "dose-1", ingredient_id: "ibuprofen", dose: 400,
      unit: "mg", route: "oral", simulation_time: 0, duration: 0 }],
    medications: [{ drug_id: "ibuprofen", name: "Ibuprofen" }],
    safety_alerts: [],
    findings_timeline: [{ finding_id: "finding-1", organ: "renal", coverage: "evidence_only",
      rule_id: "renal-rule", simulation_time: 1, causal_event_ids: ["dose-1"] }],
    visual_responses: {
      renal: { cues: [
        { time: 0, event_id: "dose-1", drug_id: "ibuprofen", drug_name: "Ibuprofen",
          kind: "exposure_only", rule_id: null, rule_ids: [], finding_id: null },
        { time: 1, event_id: "dose-1", drug_id: "ibuprofen", drug_name: "Ibuprofen",
          kind: "source_linked_caution", rule_id: "renal-rule", rule_ids: ["renal-rule"],
          finding_id: "finding-1" },
      ] },
    },
  } as unknown as TimelineReport;
  const before = projectReportAt(report, .5);
  expect(before.cues.renal.map(cue => cue.kind)).toEqual(["exposure_only"]);
  expect(before.findings.renal).toEqual([]);
  const after = projectReportAt(report, 1);
  expect(after.cues.renal.map(cue => cue.kind)).toEqual([
    "exposure_only", "source_linked_caution"]);
  expect(after.findings.renal.map(finding => finding.finding_id)).toEqual(["finding-1"]);
  expect(projectReportAt(report, .5).findings.renal).toEqual([]);
});

test("older cached caution cues are not backdated before their finding", () => {
  const report = {
    last_time: 10, administrations: [], medications: [], safety_alerts: [],
    findings_timeline: [{ finding_id: "old-finding", organ: "renal", coverage: "evidence_only",
      rule_id: "renal-rule", simulation_time: 1, causal_event_ids: ["dose-1"] }],
    visual_responses: { renal: { cues: [
      { time: 0, event_id: "dose-1", drug_id: "ibuprofen", drug_name: "Ibuprofen",
        kind: "source_linked_caution", rule_ids: ["renal-rule"] },
    ] } },
  } as unknown as TimelineReport;
  expect(projectReportAt(report, 0).cues.renal.map(cue => cue.kind)).toEqual(["exposure_only"]);
  expect(projectReportAt(report, 1).findings.renal.map(finding => finding.finding_id)).toEqual(["old-finding"]);
});

test("one finding linked to simultaneous doses is shown once with two cues", () => {
  const caution = (event_id: string) => ({ time: 1, event_id, drug_id: "morphine",
    drug_name: "Morphine", kind: "source_linked_caution", rule_id: "resp-rule",
    rule_ids: ["resp-rule"], finding_id: "shared-finding" });
  const report = { last_time: 10, administrations: [], medications: [],
    findings_timeline: [{ finding_id: "shared-finding", organ: "respiratory",
      coverage: "evidence_only", rule_id: "resp-rule", simulation_time: 1,
      causal_event_ids: ["dose-1", "dose-2"] }],
    visual_responses: { respiratory: { cues: [caution("dose-1"), caution("dose-2")] } },
  } as unknown as TimelineReport;
  const frame = projectReportAt(report, 1);
  expect(frame.cues.respiratory).toHaveLength(2);
  expect(frame.findings.respiratory).toHaveLength(1);
});
