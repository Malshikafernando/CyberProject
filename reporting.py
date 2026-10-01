from __future__ import annotations

from io import BytesIO
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


INK = colors.HexColor("#071B22")
PANEL = colors.HexColor("#102F31")
PANEL_SOFT = colors.HexColor("#163B3C")
EMERALD = colors.HexColor("#00A86B")
MINT = colors.HexColor("#62E6B1")
MINT_SOFT = colors.HexColor("#ECFFF7")
WHITE = colors.HexColor("#FFFFFF")
MUTED = colors.HexColor("#B7CEC5")
BORDER = colors.HexColor("#285052")
LOW = colors.HexColor("#25C889")
MEDIUM = colors.HexColor("#F2AE3B")
HIGH = colors.HexColor("#F26B6B")


def _safe(value) -> str:
    return str(value if value is not None else "Not provided").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class ProbabilityBar(Flowable):
    def __init__(self, label: str, value: int, color: colors.Color, width: float = 154 * mm):
        super().__init__()
        self.label = label
        self.value = max(0, min(100, value))
        self.bar_color = color
        self.width = width
        self.height = 14 * mm

    def draw(self):
        canvas = self.canv
        canvas.setFillColor(MUTED)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawString(0, 8 * mm, self.label)
        canvas.setFillColor(WHITE)
        canvas.drawRightString(self.width, 8 * mm, f"{self.value}%")
        canvas.setFillColor(colors.HexColor("#244648"))
        canvas.roundRect(0, 2.2 * mm, self.width, 3.2 * mm, 1.6 * mm, fill=1, stroke=0)
        if self.value > 0:
            canvas.setFillColor(self.bar_color)
            canvas.roundRect(0, 2.2 * mm, self.width * self.value / 100, 3.2 * mm, 1.6 * mm, fill=1, stroke=0)


def _styles():
    base = getSampleStyleSheet()
    return {
        "eyebrow": ParagraphStyle("eyebrow", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=MINT, spaceAfter=5, uppercase=True),
        "title": ParagraphStyle("title", parent=base["Title"], fontName="Helvetica-Bold", fontSize=28, leading=31, textColor=WHITE, alignment=TA_LEFT, spaceAfter=8),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, textColor=WHITE, spaceBefore=4, spaceAfter=10),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=WHITE, spaceBefore=2, spaceAfter=7),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7, leading=13, textColor=MUTED, spaceAfter=7),
        "body_white": ParagraphStyle("body_white", parent=base["BodyText"], fontName="Helvetica", fontSize=8.7, leading=13, textColor=WHITE, spaceAfter=5),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="Helvetica", fontSize=7.2, leading=10, textColor=MUTED),
        "stat_label": ParagraphStyle("stat_label", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=6.8, leading=8, textColor=MUTED, uppercase=True),
        "stat_value": ParagraphStyle("stat_value", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=WHITE),
        "center": ParagraphStyle("center", parent=base["Normal"], fontName="Helvetica-Bold", fontSize=8, leading=10, textColor=WHITE, alignment=TA_CENTER),
        "right": ParagraphStyle("right", parent=base["Normal"], fontName="Helvetica", fontSize=7.5, leading=10, textColor=MUTED, alignment=TA_RIGHT),
    }


def _page_background(canvas, doc, logo_path: Path):
    width, height = A4
    canvas.saveState()
    canvas.setFillColor(INK)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#0A252B"))
    canvas.circle(width - 8 * mm, height - 14 * mm, 55 * mm, fill=1, stroke=0)
    canvas.setFillColor(PANEL)
    canvas.roundRect(18 * mm, height - 28 * mm, width - 36 * mm, 16 * mm, 4 * mm, fill=1, stroke=0)
    if logo_path.exists():
        canvas.setFillColor(MINT_SOFT)
        canvas.roundRect(22 * mm, height - 25.5 * mm, 47 * mm, 11 * mm, 2.5 * mm, fill=1, stroke=0)
        canvas.drawImage(str(logo_path), 24 * mm, height - 24.2 * mm, width=43 * mm, height=8.5 * mm, preserveAspectRatio=True, mask="auto", anchor="c")
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(width - 22 * mm, height - 20.5 * mm, "CONFIDENTIAL - CYBERSECURITY RISK ASSESSMENT")
    canvas.setStrokeColor(BORDER)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7)
    canvas.drawString(18 * mm, 10.5 * mm, "CyberRisk Compass | Academic decision-support system")
    canvas.drawRightString(width - 18 * mm, 10.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _panel(content, widths=None, padding=10, background=PANEL):
    table = Table(content, colWidths=widths, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), padding),
        ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ("TOPPADDING", (0, 0), (-1, -1), padding),
        ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def build_risk_report_pdf(context: dict, logo_path: Path) -> BytesIO:
    output = BytesIO()
    styles = _styles()
    doc = BaseDocTemplate(
        output,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=35 * mm,
        bottomMargin=20 * mm,
        title="CyberRisk Compass - Cybersecurity Risk Assessment",
        author="CyberRisk Compass",
        subject="Role-based cybersecurity risk assessment report",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="report", showBoundary=0)
    doc.addPageTemplates(PageTemplate(id="dark-report", frames=[frame], onPage=lambda c, d: _page_background(c, d, logo_path)))

    risk_level = context["risk_level"]
    accent = {"Low": LOW, "Medium": MEDIUM, "High": HIGH}.get(risk_level, EMERALD)
    bars = context["bars"]
    reference = context.get("assessment_reference") or "Not supplied"
    story = []

    story.extend([
        Paragraph("ROLE-BASED CYBERSECURITY INTELLIGENCE", styles["eyebrow"]),
        Paragraph("Cybersecurity Risk Assessment", styles["title"]),
        Paragraph(_safe(context["explanation"]), styles["body"]),
        Spacer(1, 4 * mm),
    ])

    risk_block = Table([
        [Paragraph("PREDICTED RISK", styles["stat_label"]), Paragraph("PREDICTION CONFIDENCE", styles["stat_label"]), Paragraph("ACTION PRIORITY", styles["stat_label"])],
        [Paragraph(f'<font color="{accent.hexval()}">{_safe(risk_level)} risk</font>', styles["stat_value"]), Paragraph(f'{_safe(context.get("confidence", max(bars.values())))}%', styles["stat_value"]), Paragraph(_safe(context.get("action_priority", "Review")), styles["stat_value"])],
    ], colWidths=[doc.width / 3] * 3)
    risk_block.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PANEL),
        ("BOX", (0, 0), (-1, -1), 0.8, accent),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, 0), 10), ("BOTTOMPADDING", (0, 0), (-1, 0), 3),
        ("TOPPADDING", (0, 1), (-1, 1), 2), ("BOTTOMPADDING", (0, 1), (-1, 1), 12),
    ]))
    story.extend([risk_block, Spacer(1, 7 * mm)])

    story.extend([Paragraph("Risk probability profile", styles["h1"])])
    color_map = {"Low": LOW, "Medium": MEDIUM, "High": HIGH}
    for label in ("Low", "Medium", "High"):
        story.append(ProbabilityBar(label, int(bars.get(label, 0)), color_map[label], doc.width))
    story.append(Spacer(1, 4 * mm))

    summary_left = [
        Paragraph("EXECUTIVE SUMMARY", styles["eyebrow"]),
        Paragraph("Recommended direction", styles["h2"]),
        Paragraph(_safe(context["recommendation"]), styles["body"]),
    ]
    summary_right = [
        Paragraph("ASSESSMENT DETAILS", styles["eyebrow"]),
        Paragraph(f'<b>Reference:</b> {_safe(reference)}', styles["body_white"]),
        Paragraph(f'<b>Generated:</b> {_safe(context["generated_at"])}', styles["body_white"]),
        Paragraph(f'<b>Model:</b> {_safe(context.get("model_version", "2.0.0"))}', styles["body_white"]),
        Paragraph(f'<b>Training focus:</b> {_safe(context.get("training_focus", "General security awareness"))}', styles["body_white"]),
    ]
    story.extend([_panel([[summary_left, summary_right]], [doc.width * .58, doc.width * .42]), Spacer(1, 7 * mm)])

    story.append(Paragraph("Priority findings", styles["h1"]))
    strengths = [Paragraph(f'<font color="#62E6B1"><b>CONTROL</b></font><br/>{_safe(item)}', styles["body_white"]) for item in context["strengths"]]
    concerns = [Paragraph(f'<font color="#F2AE3B"><b>ATTENTION</b></font><br/>{_safe(item)}', styles["body_white"]) for item in context["concerns"]]
    finding_rows = []
    for index in range(max(len(strengths), len(concerns))):
        finding_rows.append([strengths[index] if index < len(strengths) else "", concerns[index] if index < len(concerns) else ""])
    findings_panel = _panel(finding_rows, [doc.width / 2] * 2, padding=9, background=PANEL_SOFT)
    story[-1:] = [KeepTogether([Paragraph("Priority findings", styles["h1"]), findings_panel])]
    story.append(Spacer(1, 7 * mm))

    story.extend([Paragraph("Prioritized action plan", styles["h1"])])
    recommendation_details = context.get("recommendation_details", [])
    if recommendation_details:
        for index, item in enumerate(recommendation_details, start=1):
            meta = f'{_safe(item.get("priority", "Priority"))} | {_safe(item.get("suggested_timeframe", "Planned"))} | Owner: {_safe(item.get("responsible_owner", "Security team"))}'
            content = [[
                Paragraph(f'<font color="#62E6B1">{index:02d}</font>', styles["stat_value"]),
                [Paragraph(_safe(item.get("recommendation_title", "Security improvement")), styles["h2"]), Paragraph(meta, styles["small"]), Paragraph(_safe(item.get("recommendation_description", "")), styles["body"])],
            ]]
            story.extend([KeepTogether(_panel(content, [14 * mm, doc.width - 14 * mm], padding=9, background=PANEL)), Spacer(1, 3 * mm)])
    else:
        story.append(_panel([[Paragraph(_safe(context["recommendation"]), styles["body_white"])]], [doc.width]))

    story.extend([PageBreak(), Paragraph("Assessment evidence", styles["eyebrow"]), Paragraph("Submitted assessment details", styles["title"]), Paragraph("The following values were supplied to the trained prediction pipeline. They provide an auditable record of the assessment context.", styles["body"]), Spacer(1, 3 * mm)])
    for section in context["input_sections"]:
        rows = [[Paragraph("INDICATOR", styles["stat_label"]), Paragraph("SUBMITTED VALUE", styles["stat_label"])]]
        for label, value in section["items"]:
            rows.append([Paragraph(_safe(label), styles["body"]), Paragraph(f'<b>{_safe(value)}</b>', styles["body_white"])])
        table = Table(rows, colWidths=[doc.width * .66, doc.width * .34], repeatRows=1, hAlign="LEFT")
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PANEL_SOFT),
            ("BACKGROUND", (0, 1), (-1, -1), PANEL),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.3, BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.extend([Paragraph(_safe(section["title"]), styles["h2"]), table, Spacer(1, 6 * mm)])

    story.extend([
        Spacer(1, 3 * mm),
        _panel([[Paragraph("IMPORTANT", styles["eyebrow"]), Paragraph("This report is an academic decision-support output. It does not replace a professional cybersecurity audit, penetration test, compliance review, or incident investigation.", styles["body"])]], [25 * mm, doc.width - 25 * mm], padding=10, background=PANEL_SOFT),
    ])

    doc.build(story)
    output.seek(0)
    return output
