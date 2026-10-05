"""Unit-safe illustrative one-compartment math; never enables its own models."""

import math


def _concentration_at(time, events, ka, ke, vd_l, factor, excluded=()):
    contributions = []
    for event in events:
        if event["event_id"] in excluded or time < event["simulation_time"]:
            continue
        dose = event["dose"]
        elapsed = time - event["simulation_time"]
        duration = event.get("duration", 0)
        if event["route"] == "intravenous":
            if duration:
                infusion_elapsed = min(elapsed, duration)
                delivered = (dose / duration) / (ke * vd_l) * (-math.expm1(-ke * infusion_elapsed))
                value = delivered * math.exp(-ke * max(0, elapsed - duration))
            else:
                value = dose / vd_l * math.exp(-ke * elapsed)
        else:
            if math.isclose(ka, ke, rel_tol=1e-10):
                value = dose / vd_l * ka * elapsed * math.exp(-ke * elapsed)
            else:
                value = dose * ka / (vd_l * (ka - ke)) * (
                    math.exp(-ke * elapsed) - math.exp(-ka * elapsed))
        contributions.append(max(0.0, value))
    return math.fsum(contributions) * factor


def build_illustrative_pk(administrations: list[dict], drugs: dict,
                          horizon_seconds: float, cursor_time: float,
                          parameter_sets: dict | None = None) -> list[dict]:
    """Return only explicitly supplied illustrative models; production has none."""
    parameter_sets = parameter_sets or {}
    window_end = max(0.0, min(horizon_seconds, cursor_time))
    result = []
    for drug_id in dict.fromkeys(item["ingredient_id"] for item in administrations):
        params = parameter_sets.get(drug_id)
        events = [item for item in administrations if item["ingredient_id"] == drug_id]
        if (not params or not events or not params.get("model_id") or
                not params.get("parameter_source") or
                any(event["unit"] != "mg" or event["route"] not in params.get("routes", [])
                    for event in events)):
            continue
        ka, ke, vd_l = (params[key] for key in ("ka", "ke", "vd_l"))
        if not all(math.isfinite(value) and value > 0 for value in (ka, ke, vd_l)):
            continue
        unit = params.get("unit")
        if unit not in ("mg/L", "mcg/L"):
            continue
        factor = 1000 if unit == "mcg/L" else 1
        times = {0.0, window_end}
        for index in range(60):
            times.add(window_end * index / 59)
        for event in events:
            start = event["simulation_time"]
            if start > window_end:
                continue
            times.add(start)
            end = start + event.get("duration", 0)
            if start <= end <= window_end:
                times.add(end)
            if event["route"] != "intravenous":
                oral_peak = start + (1 / ke if math.isclose(ka, ke, rel_tol=1e-10)
                                     else math.log(ka / ke) / (ka - ke))
                if start <= oral_peak <= window_end:
                    times.add(oral_peak)
        points = []
        for time in sorted(times):
            boluses = {event["event_id"] for event in events
                       if event["route"] == "intravenous" and event.get("duration", 0) == 0
                       and event["simulation_time"] == time}
            if boluses and time > 0:
                before = _concentration_at(time, events, ka, ke, vd_l, factor, boluses)
                points.append({"time": time, "value": before, "concentration": before})
            current = _concentration_at(time, events, ka, ke, vd_l, factor)
            points.append({"time": time, "value": current, "concentration": current})
        peak_index = max(range(len(points)), key=lambda index: points[index]["concentration"])
        peak = points[peak_index]
        result.append({"drug_id": drug_id, "name": drugs[drug_id]["name"],
                       "unit": unit, "c_max": peak["concentration"], "t_max": peak["time"],
                       "peak_index": peak_index, "peak_kind": "within_window",
                       "window_start": 0.0, "window_end": window_end,
                       "model_id": params["model_id"], "status": "illustrative",
                       "parameter_source": params["parameter_source"],
                       "provenance": "Illustrative one-compartment formula; not patient-specific",
                       "points": points})
    return result
