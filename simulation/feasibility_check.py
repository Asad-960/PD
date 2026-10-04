"""Honest Gate 1 probe: illustrative lifecycle is separate from real physiology."""
import argparse
import importlib
import os
import platform
import sys
import time
from pathlib import Path

import psutil

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from simulation.adapter import IllustrativeEngineAdapter


def check_pulse_native_sdk():
    """Import presence probe only; it does not verify Kitware identity or lifecycle."""
    try:
        module = importlib.import_module("pulse")
    except Exception as error:
        return False, f"Import probe unavailable: {type(error).__name__}: {error}. No OS/compiler compatibility verdict is implied."
    return True, f"A pulse module imports from {getattr(module, '__file__', 'unknown location')}; Kitware identity and lifecycle remain unverified."


def run_feasibility():
    started = time.perf_counter()
    process = psutil.Process(os.getpid())
    before = process.memory_info().rss / 1024**2
    importable, import_detail = check_pulse_native_sdk()
    engine = IllustrativeEngineAdapter()
    manifest = engine.capabilities()
    initialized = engine.initialize({"run_id": "illustrative_feasibility", "conditions": ["CKD"],
                                     "context": {"diabetes": True}, "baseline_measurements": {}})
    action_ok = engine.apply_event({"event_id": "fluid_probe", "ingredient_id": "saline",
                                   "dose": 600, "unit": "mL", "route": "intravenous",
                                   "simulation_time": 0, "duration": 60})
    stepping = time.perf_counter()
    advance_ok = all(engine.advance(1) for _ in range(120))
    step_duration = time.perf_counter() - stepping
    snapshot = engine.snapshot()
    snapshot_ok = snapshot["is_valid"] and snapshot["simulation_time"] == 120 and all(
        q["capability"] == "illustrative" for q in snapshot["quantities"].values())
    checkpoint = engine.serialize()
    clone = IllustrativeEngineAdapter()
    restored = clone.restore(checkpoint)
    restore_ok = restored and clone.snapshot() == snapshot
    # Two initially identical runs isolate evidence exposure from fluid progression.
    control = IllustrativeEngineAdapter()
    control.restore(checkpoint)
    evidence_ok = clone.apply_event({"event_id": "evidence_probe", "ingredient_id": "ibuprofen",
                                    "dose": 800, "unit": "mg", "route": "oral",
                                    "simulation_time": 120, "duration": 0})
    clone.advance(60)
    control.advance(60)
    evidence_isolation = evidence_ok and clone.snapshot()["quantities"] == control.snapshot()["quantities"]
    lifecycle = bool(initialized and action_ok and advance_ok and snapshot_ok and restore_ok and evidence_isolation)
    physiology_verified = manifest["physiology_engine_verified"] and manifest["execution_mode"] != "ILLUSTRATIVE"
    after = process.memory_info().rss / 1024**2
    result = {
        "python_version": platform.python_version(), "platform": platform.platform(),
        "pulse_module_importable": importable, "pulse_probe_detail": import_detail,
        "pulse_native_available": False, "physiology_engine_verified": physiology_verified,
        "execution_mode": manifest["execution_mode"], "engine_name": manifest["engine_name"],
        "engine_version": manifest["engine_version"],
        "initialization": "PASS" if initialized else "FAIL", "step_advance": "PASS" if advance_ok else "FAIL",
        "snapshot": "PASS" if snapshot_ok else "FAIL", "restore": "PASS" if restore_ok else "FAIL",
        "evidence_isolation": "PASS" if evidence_isolation else "FAIL",
        "illustrative_lifecycle_passed": lifecycle, "gate1_passed": bool(lifecycle and physiology_verified),
        "illustrative_steps_per_sec": round(120 / step_duration, 1),
        "memory_rss_mb": round(after, 2), "memory_delta_mb": round(after - before, 2),
        "total_elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
    }
    print("PDTT ENGINE FEASIBILITY — ILLUSTRATIVE DEVELOPMENT MODE")
    print(f"Python: {sys.executable}")
    print(f"Pulse import probe: {import_detail}")
    print(f"Illustrative lifecycle: {'PASS' if lifecycle else 'FAIL'}")
    print(f"Evidence-only numerical isolation: {'PASS' if evidence_isolation else 'FAIL'}")
    print("Real Pulse / genuine reference-trace lifecycle: UNVERIFIED")
    print(f"Gate 1 verified-physiology status: {'PASS' if result['gate1_passed'] else 'NOT PASSED'}")
    print(f"Illustrative adapter RSS: {after:.2f} MB; this is not a Pulse benchmark.")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--illustrative-only", action="store_true",
                        help="Run a development smoke check; does not approve verified physiology")
    arguments = parser.parse_args()
    results = run_feasibility()
    passed = results["illustrative_lifecycle_passed"] if arguments.illustrative_only else results["gate1_passed"]
    sys.exit(0 if passed else 1)
