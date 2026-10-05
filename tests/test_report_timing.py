from types import SimpleNamespace

from backend.catalogue.registry import drugs_by_id
from backend.reports.visual_response import build_visual_responses


def intake_without_conditions():
    return SimpleNamespace(organs={organ: SimpleNamespace(conditions=[])
                                   for organ in ("cardiovascular", "respiratory", "renal", "hepatic")})


def administration(event_id, drug_id, time):
    return {"event_id": event_id, "ingredient_id": drug_id, "simulation_time": time}


def finding(event_id, rule_id, organ, time):
    return {"finding_id": f"{rule_id}-{time}", "organ": organ,
            "coverage": "evidence_only", "rule_id": rule_id,
            "simulation_time": time, "causal_event_ids": [event_id]}


def test_exposure_and_caution_have_distinct_committed_onsets():
    responses = build_visual_responses(intake_without_conditions(), {}, drugs_by_id(),
        [administration("dose-1", "ibuprofen", 0)],
        [finding("dose-1", "RULE_NSAID_RENAL_HEMODYNAMIC", "renal", 1)])
    cues = responses["renal"]["cues"]
    assert [(cue["kind"], cue["time"]) for cue in cues] == [
        ("exposure_only", 0), ("source_linked_caution", 1)]
    assert [cue for cue in cues if cue["kind"] == "source_linked_caution"][0]["finding_id"] == "RULE_NSAID_RENAL_HEMODYNAMIC-1"


def test_repeat_doses_keep_event_identity_and_deduplicate_snapshots():
    administrations = [administration("dose-1", "morphine", 0),
                       administration("dose-2", "morphine", 20)]
    findings = [finding("dose-1", "RULE_MORPHINE_RESPIRATORY", "respiratory", 1),
                finding("dose-1", "RULE_MORPHINE_RESPIRATORY", "respiratory", 2),
                finding("dose-2", "RULE_MORPHINE_RESPIRATORY", "respiratory", 21)]
    cues = build_visual_responses(intake_without_conditions(), {}, drugs_by_id(),
                                  administrations, findings)["respiratory"]["cues"]
    assert [(cue["event_id"], cue["kind"], cue["time"]) for cue in cues] == [
        ("dose-1", "exposure_only", 0),
        ("dose-1", "source_linked_caution", 1),
        ("dose-2", "exposure_only", 20),
        ("dose-2", "source_linked_caution", 21)]


def test_no_caution_without_committed_finding():
    cues = build_visual_responses(intake_without_conditions(), {}, drugs_by_id(),
                                  [administration("dose-1", "ibuprofen", 0)],
                                  [])["renal"]["cues"]
    assert len(cues) == 1
    assert cues[0]["kind"] == "exposure_only"
