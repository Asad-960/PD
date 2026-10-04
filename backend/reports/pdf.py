"""Publication-grade, evidence-scoped clinical assessment PDF for a PDTT assessment."""

from html import escape
from io import BytesIO

from reportlab.graphics.shapes import Circle, Drawing, Line, PolyLine, Rect, String
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# High-fidelity clinical palette
BRAND_DARK = colors.HexColor("#0d2e27")
BRAND_TEAL = colors.HexColor("#0f766e")
BRAND_EMERALD = colors.HexColor("#059669")
INK = colors.HexColor("#0f1f1b")
MUTED = colors.HexColor("#4b635c")
PALE_BG = colors.HexColor("#f4f8f6")
HEADER_BG = colors.HexColor("#e6f1ed")
BORDER_LIGHT = colors.HexColor("#d2e1da")
ALERT_RED = colors.HexColor("#b91c1c")
ALERT_AMBER = colors.HexColor("#b45309")
CLEAR_GREEN = colors.HexColor("#047857")


def number(value):
    return str(int(value)) if float(value).is_integer() else str(value)


def render_pdf(report):
    output = BytesIO()
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(name="Pdf_HeaderBrand", fontName="Helvetica-Bold", fontSize=10, leading=12, textColor=colors.HexColor("#6ee7b7"), spaceAfter=3))
    styles.add(ParagraphStyle(name="Pdf_HeaderTitle", fontName="Helvetica-Bold", fontSize=18, leading=21, textColor=colors.white, spaceAfter=4))
    styles.add(ParagraphStyle(name="Pdf_HeaderMeta", fontName="Helvetica", fontSize=8, leading=11, textColor=colors.HexColor("#d1fae5")))
    styles.add(ParagraphStyle(name="Pdf_HeaderBadge", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=colors.white, alignment=2))

    styles.add(ParagraphStyle(name="Pdf_SectionTitle", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=BRAND_DARK, spaceBefore=14, spaceAfter=6))
    styles.add(ParagraphStyle(name="Pdf_Body", fontName="Helvetica", fontSize=8.2, leading=11.5, textColor=INK, spaceAfter=4, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="Pdf_Muted", fontName="Helvetica", fontSize=7.2, leading=9.6, textColor=MUTED, spaceAfter=3, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="Pdf_TableHeader", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=BRAND_DARK))
    styles.add(ParagraphStyle(name="Pdf_TableCell", fontName="Helvetica", fontSize=8, leading=10.5, textColor=INK))
    styles.add(ParagraphStyle(name="Pdf_AlertRed", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=ALERT_RED))
    styles.add(ParagraphStyle(name="Pdf_AlertAmber", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=ALERT_AMBER))
    styles.add(ParagraphStyle(name="Pdf_AlertGreen", fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=CLEAR_GREEN))

    def p(value, style="Pdf_Body"):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles[style])

    def raw_p(html_value, style="Pdf_Body"):
        return Paragraph(html_value, styles[style])

    def styled_table(rows, widths, header=True, custom_style=None):
        cells = []
        for row_index, row in enumerate(rows):
            row_cells = []
            for cell in row:
                if isinstance(cell, Paragraph):
                    row_cells.append(cell)
                elif header and row_index == 0:
                    row_cells.append(p(cell, "Pdf_TableHeader"))
                else:
                    row_cells.append(p(cell, "Pdf_TableCell"))
            cells.append(row_cells)

        result = Table(cells, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LINEBELOW", (0, -1), (-1, -1), 0.5, BORDER_LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
        if header:
            commands.extend([
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("LINEBELOW", (0, 0), (-1, 0), 1.2, BRAND_TEAL),
            ])
            commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE_BG]))
        if custom_style:
            commands.extend(custom_style)
        result.setStyle(TableStyle(commands))
        return result

    patient = report["patient"]
    bp = report["blood_pressure"]
    organ_order = ("cardiovascular", "respiratory", "hepatic", "renal")

    # Header Card Banner (Full-bleed aesthetic)
    created_str = report["created_at"][:19].replace("T", " ")
    status_str = report["status"].upper()
    left_header = [
        raw_p("<b>PDTT  /  PHYSIOLOGICAL DIGITAL TWIN SANDBOX</b>", "Pdf_HeaderBrand"),
        raw_p("<b>Medication and organ assessment</b>", "Pdf_HeaderTitle"),
        raw_p(f"<b>CASE REF:</b> {report['report_id']}    |    <b>GENERATED:</b> {created_str} UTC", "Pdf_HeaderMeta"),
    ]
    right_header = [
        raw_p("<b>CLINICAL SANDBOX REPORT</b>", "Pdf_HeaderBadge"),
        Spacer(1, 4),
        raw_p(f"<b>STATUS:</b> {status_str}", "Pdf_HeaderBadge"),
        raw_p("<b>EVIDENCE SCOPE REVIEW</b>", "Pdf_HeaderBadge"),
    ]
    header_table = Table([[left_header, right_header]], colWidths=[125 * mm, 45 * mm], hAlign="LEFT")
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    # Legal / Scope Callout Box
    scope_box = Table([[
        p("Educational evidence review, not a laboratory result or a validated prediction. "
          "No result in this report establishes that a medication or organ is safe.", "Pdf_Muted")
    ]], colWidths=[170 * mm], hAlign="LEFT")
    scope_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fef3c7")),
        ("LINEBEFORE", (0, 0), (-1, -1), 3, ALERT_AMBER),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))

    story = [
        header_table,
        Spacer(1, 6),
        scope_box,
        Spacer(1, 4),
        p("Patient and case", "Pdf_SectionTitle"),
    ]

    # Patient & Case Summary Table
    patient_name = patient.get("name") or report["patient_id"]
    gender_display = f"{patient['age']} years / {patient['gender'].replace('_', ' ')}"
    bp_display = bp["status"].replace("_", " ")
    allergies_display = ", ".join(patient["allergies"]) or patient["allergies_status"].replace("_", " ")

    story.append(styled_table(
        [["Patient", "Age / gender", "BP history", "Allergies"],
         [patient_name, gender_display, bp_display, allergies_display]],
        [50 * mm, 38 * mm, 38 * mm, 44 * mm]
    ))

    # Four-Organ Rule Signals
    story.append(p("Four-organ rule signals", "Pdf_SectionTitle"))
    rows = [["Organ", "Signal", "Why it is shown"]]
    for organ_id in organ_order:
        organ = report["organs"][organ_id]
        visual = report.get("visual_responses", {}).get(organ_id, {})
        caution = visual.get("safety_signal") == "review_required" or organ["outcome"] == "concern_identified"
        signal_text = "REVIEW REQUIRED" if caution else "CONDITION RECORDED" if organ["conditions"] else "NO FLAG IN LIMITED CHECKS"
        signal_style = "Pdf_AlertRed" if caution else "Pdf_AlertAmber" if organ["conditions"] else "Pdf_AlertGreen"

        condition_names = ", ".join(item["name"] for item in organ["conditions"])
        findings = [item["message"] for item in organ["findings"] if item["coverage"] == "evidence_only"]
        reason = "; ".join(findings[:2]) or (condition_names + ". Condition effect is illustrative, not quantified." if condition_names else "No source-linked concern detected in the implemented checks.")

        rows.append([
            p(organ["label"], "Pdf_TableCell"),
            p(signal_text, signal_style),
            p(reason, "Pdf_TableCell"),
        ])

    story.append(styled_table(rows, [38 * mm, 42 * mm, 90 * mm]))
    story.append(p("A non-flagged organ is not medically cleared. Rule coverage is limited; patient-specific function, toxicity and interactions are not calculated.", "Pdf_Muted"))

    # Medication Administration Table
    story.append(p("Medication administration", "Pdf_SectionTitle"))
    meds = [["Medication", "Dose", "Route", "Planned time", "Recorded amount"]]
    for row_index, item in enumerate(report["medications"]):
        event_prefix = f"{report['run_id']}_med_{row_index}_"
        actual = [action for action in report.get("administrations", []) if action["event_id"].startswith(event_prefix)]
        delivered = sum(action["dose"] * (min(1, max(0, (report["last_time"] - action["simulation_time"]) / action["duration"])) if action["duration"] else 1)
                        for action in actual if action["simulation_time"] <= report["last_time"])
        recorded_unit = actual[0]["unit"] if actual else ("mL" if item["unit"] in ("mL", "L") else "mg")
        meds.append([
            item["name"],
            f"{number(item['dose'])} {item['unit']}",
            item["route"],
            f"{number(item['time_seconds'])} s" + (f"; {item['repeat_count']} doses" if item["repeat_count"] > 1 else ""),
            f"{number(delivered)} {recorded_unit}",
        ])
    story.append(styled_table(meds, [50 * mm, 28 * mm, 28 * mm, 34 * mm, 30 * mm]))
    story.append(p("Recorded administrations: amounts are calculated from applied administration events. It is not absorbed dose or blood concentration.", "Pdf_Muted"))

    # Organ Response Detail
    story.append(p("Organ response detail", "Pdf_SectionTitle"))
    for organ_id in organ_order:
        organ = report["organs"][organ_id]
        visual = report.get("visual_responses", {}).get(organ_id, {})
        parts = [p(organ["label"], "Pdf_TableHeader")]
        if organ["conditions"]:
            parts.append(p("History: " + "; ".join(f"{item['name']} ({item['severity']})" for item in organ["conditions"])))
        else:
            parts.append(p("History: " + organ["history_status"].replace("_", " ")))
        mechanisms = visual.get("condition_mechanisms", [])
        if mechanisms:
            parts.append(p("Illustrated pattern: " + visual.get("pattern_label", "recorded condition") + ". " + "; ".join(item["description"] for item in mechanisms[:2])))
        cautions = [item for item in organ["findings"] if item["coverage"] == "evidence_only"]
        for item in cautions[:2]:
            parts.append(p("Evidence caution: " + item["message"]))
            parts.append(p("Basis: " + item["explanation"], "Pdf_Muted"))
        if not cautions:
            parts.append(p("No source-linked caution in available checks. Safety and organ function remain unverified.", "Pdf_Muted"))
        story.append(KeepTogether(parts))

    # Entered Measurements and Context
    story.append(p("Entered measurements and context", "Pdf_SectionTitle"))
    if report["measurements"]:
        meas_rows = [["Measurement", "Entered value", "Observed at"]]
        for item in report["measurements"]:
            meas_rows.append([item["label"], f"{number(item['value'])} {item['unit']}", item["observed_at"] or "Not supplied"])
        story.append(styled_table(meas_rows, [68 * mm, 51 * mm, 51 * mm]))
    else:
        story.append(p("No laboratory or vital-sign measurements were entered."))

    context = [f"BP control: {bp['control'].replace('_', ' ')}"]
    if bp.get("notes"):
        context.append("BP notes: " + bp["notes"])
    if patient.get("gender_detail"):
        context.append("Gender description: " + patient["gender_detail"])
    if patient.get("sex"):
        context.append("Physiological sex parameter: " + patient["sex"])
    if patient.get("current_medications"):
        context.append("Ongoing medications: " + ", ".join(patient["current_medications"]))
    story.extend(p(item, "Pdf_Muted") for item in context)

    # Administration Graph & Pharmacokinetic Curve
    story.append(p("Administration graph", "Pdf_SectionTitle"))
    pk_map = {item["drug_id"]: item for item in report.get("pk_series", [])}

    for series in report["administration_series"][:3]:
        points = series["points"]
        if not points:
            continue
        max_x = max(report["horizon_seconds"], 1)
        drug_id = series["drug_id"]
        pk_info = pk_map.get(drug_id)

        # Drawing area
        dw, dh = 480, 118
        drawing = Drawing(dw, dh)

        # Card container with rounded border
        drawing.add(Rect(10, 10, 460, 98, fillColor=colors.HexColor("#f8faf9"), strokeColor=BORDER_LIGHT, strokeWidth=1, rx=4, ry=4))

        # Title block
        if pk_info:
            drawing.add(String(22, 92, f"{series['name']}  ·  Pharmacokinetic Plasma Concentration & Administration", fontName="Helvetica-Bold", fontSize=8.5, fillColor=BRAND_DARK))
            drawing.add(String(22, 81, f"Simulated Profile  ·  Target: {pk_info['therapeutic_min']}-{pk_info['therapeutic_max']} {pk_info['unit']}  |  Peak Cmax: {pk_info['c_max']} {pk_info['unit']} @ {pk_info['t_max']} s", fontName="Helvetica", fontSize=7, fillColor=MUTED))
        else:
            drawing.add(String(22, 92, f"{series['name']}  /  {series['unit']} administered", fontName="Helvetica-Bold", fontSize=8.5, fillColor=BRAND_DARK))

        # Plot boundaries
        px0, py0, pw, ph = 48, 26, 408, 48

        # Target Therapeutic Window Band (if PK info available)
        if pk_info and pk_info.get("therapeutic_max", 0) > 0:
            scale_y_max = max(pk_info["c_max"] * 1.25, pk_info["therapeutic_max"] * 1.15, 1.0)
            t_min_y = py0 + ph * min(1.0, max(0.0, pk_info["therapeutic_min"] / scale_y_max))
            t_max_y = py0 + ph * min(1.0, max(0.0, pk_info["therapeutic_max"] / scale_y_max))
            band_h = max(3.0, t_max_y - t_min_y)
            drawing.add(Rect(px0, t_min_y, pw, band_h, fillColor=colors.HexColor("#e6f4ea"), strokeColor=colors.HexColor("#c6e7d2"), strokeWidth=0.5))
            drawing.add(String(px0 + pw - 100, t_min_y + 2, "Therapeutic Window", fontName="Helvetica-Oblique", fontSize=6, fillColor=CLEAR_GREEN))
        else:
            scale_y_max = max((point["value"] for point in points), default=0) or 1

        # Subtle horizontal grid lines
        for frac in (0.25, 0.5, 0.75, 1.0):
            gy = py0 + ph * frac
            drawing.add(Line(px0, gy, px0 + pw, gy, strokeColor=colors.HexColor("#e2ebe6"), strokeWidth=0.5))

        # Coordinate axes
        drawing.add(Line(px0, py0, px0 + pw, py0, strokeColor=MUTED, strokeWidth=0.8))
        drawing.add(Line(px0, py0, px0, py0 + ph, strokeColor=MUTED, strokeWidth=0.8))

        # Plot the curve
        if pk_info and pk_info.get("points"):
            pk_pts = pk_info["points"]
            coords = []
            cmax_x, cmax_y = px0, py0
            for pt in pk_pts:
                cx = px0 + pw * min(1.0, max(0.0, pt["time"] / max_x))
                cy = py0 + ph * min(1.0, max(0.0, pt["concentration"] / scale_y_max))
                coords.extend([cx, cy])
                if pt["concentration"] == pk_info["c_max"]:
                    cmax_x, cmax_y = cx, cy

            if len(coords) >= 4:
                drawing.add(PolyLine(coords, strokeColor=BRAND_EMERALD, strokeWidth=2))
                # Cmax marker
                if pk_info["c_max"] > 0:
                    drawing.add(Circle(cmax_x, cmax_y, 2.5, fillColor=ALERT_AMBER, strokeColor=colors.white, strokeWidth=0.5))
        else:
            # Step administration ledger
            max_y = max((point["value"] for point in points), default=0) or 1
            coordinates = []
            polygon_coords = [px0, py0]
            for i, point in enumerate(points):
                cx = px0 + pw * point["time"] / max_x
                cy = py0 + ph * point["value"] / max_y
                if i > 0:
                    prev_cx = coordinates[-2]
                    prev_cy = coordinates[-1]
                    coordinates.extend([cx, prev_cy]) # step after
                    polygon_coords.extend([cx, prev_cy])
                coordinates.extend([cx, cy])
                polygon_coords.extend([cx, cy])
            if len(points) > 1:
                polygon_coords.extend([coordinates[-2], py0])
                from reportlab.graphics.shapes import Polygon
                drawing.add(Polygon(polygon_coords, fillColor=colors.HexColor("#0f766e", alpha=0.15), strokeColor=colors.transparent, strokeWidth=0))
                drawing.add(PolyLine(coordinates, strokeColor=BRAND_TEAL, strokeWidth=2))

        # Axis ticks and labels
        drawing.add(String(px0, 15, "0 s", fontName="Helvetica", fontSize=7, fillColor=MUTED))
        drawing.add(String(px0 + pw / 2 - 12, 15, f"{number(round(max_x / 2))} s", fontName="Helvetica", fontSize=7, fillColor=MUTED))
        drawing.add(String(px0 + pw - 20, 15, f"{number(max_x)} s", fontName="Helvetica", fontSize=7, fillColor=MUTED))
        drawing.add(String(16, py0 - 2, "0", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))
        drawing.add(String(14, py0 + ph - 3, f"{number(round(scale_y_max, 1))}", fontName="Helvetica", fontSize=6.5, fillColor=MUTED))

        story.append(drawing)

    story.append(p("Graph shows administered amount and simulated pharmacokinetic plasma level; patient-specific numerical blood concentration or organ-function trajectory is not clinically inferred.", "Pdf_Muted"))

    # Scope and Provenance
    story.append(p("Scope and provenance", "Pdf_SectionTitle"))
    story.append(p("Rule-based review uses the recorded case, pinned catalogue, and source-linked findings. Visual organ motion is illustrative. "
                   "Potential drug-drug interactions and numerical organ response are not comprehensively modeled.", "Pdf_Muted"))

    sources = {}
    for organ_id in organ_order:
        for finding in report["organs"][organ_id]["findings"]:
            for source in finding.get("sources", []):
                sources[source["source_id"]] = source
    for source in sources.values():
        story.append(Paragraph(f'<link href="{escape(source["url"], quote=True)}" color="#0f766e">{escape(source["title"])}</link>', styles["Pdf_Muted"]))

    story.append(p(f"Engine {report['engine']['name']} {report['engine']['version']}  |  Catalogue {report['catalogue_version']}  |  Cursor {report['cursor']}", "Pdf_Muted"))

    # Running Footer
    def footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(BORDER_LIGHT)
        canvas.setLineWidth(0.5)
        canvas.line(16 * mm, 14 * mm, 194 * mm, 14 * mm)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.setFillColor(BRAND_DARK)
        canvas.drawString(16 * mm, 10 * mm, "PDTT")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(26 * mm, 10 * mm, f"|  {report['report_id']}  ·  Educational Digital Twin Sandbox  ·  Confidential")
        canvas.drawRightString(194 * mm, 10 * mm, f"Page {document.page}")
        canvas.restoreState()

    document = SimpleDocTemplate(
        output,
        pagesize=(210 * mm, 297 * mm),
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=18 * mm,
        title="PDTT Medication and Organ Assessment",
        author="PDTT Digital Twin Sandbox",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()
