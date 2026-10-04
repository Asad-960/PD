"""Derive a source-linked condition catalogue from the supplied references."""
import hashlib
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def catalogue():
    items = {}
    aliases = {"ckd": "CKD", "renal_artery_stenosis": "ChronicRenalStenosis",
               "heart_failure": "CHF", "hypertension": "EssentialHypertension",
               "chronic_hypertension": "EssentialHypertension", "copd": "ChronicObstructivePulmonaryDisease",
               "cirrhosis": "HepaticCirrhosis", "diabetes_mellitus": "Type2DiabetesMellitus"}

    def add(name, organ, group, source, section, mechanism=""):
        identifier = slug(name)
        if identifier in items:
            items[identifier]["references"].append({"document": source, "section": section})
            return
        items[identifier] = {"id": identifier, "name": name, "organ": organ, "group": group,
            "canonical_id": aliases.get(identifier, identifier), "mechanism": mechanism,
            "coverage": "context_only", "numerical_supported": False,
            "references": [{"document": source, "section": section}],
            "severity_options": ["unknown", "mild", "moderate", "severe"]}
        if identifier == "ckd":
            items[identifier]["severity_options"] = ["unknown", "G1", "G2", "G3a", "G3b", "G4", "G5"]
        if identifier in ("cirrhosis", "decompensated_cirrhosis"):
            items[identifier]["severity_options"] = ["unknown", "Child-Pugh A", "Child-Pugh B", "Child-Pugh C"]
        if identifier == "heart_failure":
            items[identifier]["subtypes"] = ["unknown", "HFrEF", "HFpEF", "HFmrEF"]

    renal = "Renal_Agent_Framework.docx"
    with ZipFile(ROOT / "scenarios - conditions" / renal) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))
    tables = root.findall(".//w:tbl", NS)
    groups = {
        4: ("renal", "Kidney conditions"), 5: ("cardiovascular", "Circulatory contributors"),
        6: ("renal", "Metabolic contributors"), 7: ("hepatic", "Liver and kidney conditions"),
        8: ("respiratory", "Respiratory contributors"), 9: ("renal", "Infection and systemic illness"),
        10: ("renal", "Autoimmune contributors"), 11: ("renal", "Blood and systemic contributors"),
        12: ("renal", "Volume and stress context"),
    }
    for number, (organ, group) in groups.items():
        for row in tables[number - 1].findall("w:tr", NS)[1:]:
            cells = [" ".join(t.text or "" for t in cell.findall(".//w:t", NS))
                     for cell in row.findall("w:tc", NS)]
            if cells:
                add(cells[0].replace("\u2014", "-"), organ, group, renal,
                    f"Table {number}", cells[1] if len(cells) > 1 else "")
    cv = "Hypertension|Coronary artery disease|Prior myocardial infarction|Heart failure|Prior CABG|Prior PCI or stents|Atrial fibrillation|Other arrhythmia|Valvular disease|Peripheral arterial disease|Congenital heart disease|Acute coronary syndrome|Cardiogenic shock|Acute heart failure decompensation|Hypertensive emergency|Pulmonary embolism|Aortic dissection|Cardiac tamponade"
    for name in cv.split("|"):
        add(name, "cardiovascular", "Heart and circulation", "Document1.pdf", "Pages 1-2")
    hepatic = "Drug-induced liver injury|Acetaminophen hepatotoxicity|NSAID-associated liver injury|Hepatitis A|Hepatitis B|Hepatitis C|Hepatitis D|Hepatitis E|MASLD|MetALD|Alcohol-related liver disease|Autoimmune hepatitis|Primary biliary cholangitis|Primary sclerosing cholangitis|Haemochromatosis|Wilson disease|Alpha-1 antitrypsin deficiency|Cirrhosis|Portal hypertension|Acute liver failure|Acute-on-chronic liver failure|Ischaemic hepatitis|Congestive hepatopathy|Hepatic encephalopathy|Hepatocellular carcinoma|Cholangiocarcinoma|Hepatopulmonary syndrome|Portopulmonary hypertension|Hepatic hydrothorax|Ascites|Hepatorenal syndrome"
    for name in hepatic.split("|"):
        add(name, "hepatic", "Liver conditions", "Hepatic_Agent_Data_Report (1) (1).docx", "Sections 5-7")
    respiratory = "COPD|Asthma|Hypoxemia|Hypoxia|Hypercapnia|Respiratory acidosis|Pulmonary edema|Bronchoconstriction|Airway obstruction|Anaphylaxis|Respiratory depression|ARDS|Pneumonia|Respiratory failure|Sepsis|Septic shock|Diabetes mellitus|Metabolic acidosis"
    for name in respiratory.split("|"):
        add(name, "respiratory", "Lung and breathing conditions", "Respiratory Agent Architecture.pdf", "Pages 1-4")
    return {"version": "2026-10-04.1", "source_status": "supplied_design_references_not_clinical_validation",
        "documents": [{"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in (ROOT / "scenarios - conditions").iterdir() if p.suffix in (".pdf", ".docx")],
        "conditions": list(items.values())}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(catalogue(), ensure_ascii=True, indent=2))
