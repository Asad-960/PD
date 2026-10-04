import json
from pathlib import Path

VERSION = "2026-10-04.1"
BASE = Path(__file__).parent


def condition_catalogue():
    return json.loads((BASE / "conditions.json").read_text(encoding="utf-8"))


def drug_catalogue():
    return json.loads((BASE / "drugs.json").read_text(encoding="utf-8"))


def conditions_by_id():
    return {item["id"]: item for item in condition_catalogue()["conditions"]}


def drugs_by_id():
    return {item["id"]: item for item in drug_catalogue()["drugs"]}
