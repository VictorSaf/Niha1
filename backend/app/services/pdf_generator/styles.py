"""
NIHA PDF Design System — Institutional Document Styling.

Color palette, typography, paragraph styles, and reusable components
for all NIHA platform PDF documents.

Design principles:
  - Navy + Gold accent for institutional authority
  - Times headers, Helvetica body for clean readability
  - Pre-filled NIHA data in Helvetica-BoldOblique (italic blue)
  - Wet-ink signature area with NIHA representative details
  - Headers/footers with document reference and confidential marks
"""

import io
from datetime import datetime
from typing import Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether,
)


# =============================================================================
# COLOR PALETTE
# =============================================================================

class NihaColors:
    """NIHA brand colors for PDF documents."""
    NAVY = HexColor("#1B2A4A")
    NAVY_LIGHT = HexColor("#2D4A7A")
    NAVY_MUTED = HexColor("#4A6A9A")

    GOLD = HexColor("#C4993B")
    GOLD_LIGHT = HexColor("#E8D5A8")
    GOLD_PALE = HexColor("#F5ECD7")

    DARK = HexColor("#1A1A2E")
    MUTED = HexColor("#555566")
    LIGHT = HexColor("#888899")

    FILLED_BLUE = HexColor("#1A5276")
    FILLED_BG = HexColor("#EBF5FB")

    WHITE = HexColor("#FFFFFF")
    BACKGROUND = HexColor("#FAFBFD")
    BORDER = HexColor("#D5D8DC")

    SIG_LINE = HexColor("#1B2A4A")
    SIG_BG = HexColor("#F8F9FA")


# =============================================================================
# TYPOGRAPHY
# =============================================================================

class NihaFonts:
    """Font configuration — built-in PDF fonts for maximum compatibility."""
    TITLE = "Times-Bold"
    SUBTITLE = "Times-Roman"
    HEADING = "Times-Bold"

    BODY = "Helvetica"
    BODY_BOLD = "Helvetica-Bold"
    BODY_ITALIC = "Helvetica-Oblique"

    FILLED = "Helvetica-BoldOblique"  # Pre-filled NIHA data

    MONO = "Courier"
    MONO_BOLD = "Courier-Bold"


# =============================================================================
# PARAGRAPH STYLES
# =============================================================================

def create_niha_styles() -> StyleSheet1:
    """Create the complete NIHA stylesheet for PDF documents."""
    styles = StyleSheet1()

    styles.add(ParagraphStyle(
        name='DocTitle', fontName=NihaFonts.TITLE, fontSize=22, leading=28,
        textColor=NihaColors.NAVY, alignment=TA_CENTER,
        spaceAfter=4 * mm, spaceBefore=6 * mm,
    ))
    styles.add(ParagraphStyle(
        name='DocSubtitle', fontName=NihaFonts.SUBTITLE, fontSize=13, leading=17,
        textColor=NihaColors.NAVY_LIGHT, alignment=TA_CENTER, spaceAfter=8 * mm,
    ))
    styles.add(ParagraphStyle(
        name='SectionHeading', fontName=NihaFonts.HEADING, fontSize=12, leading=16,
        textColor=NihaColors.NAVY, spaceBefore=8 * mm, spaceAfter=3 * mm,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='SubHeading', fontName=NihaFonts.HEADING, fontSize=10.5, leading=14,
        textColor=NihaColors.NAVY_LIGHT, spaceBefore=5 * mm, spaceAfter=2 * mm,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='Body', fontName=NihaFonts.BODY, fontSize=10, leading=14,
        textColor=NihaColors.DARK, alignment=TA_JUSTIFY,
        spaceBefore=1.5 * mm, spaceAfter=1.5 * mm,
    ))
    styles.add(ParagraphStyle(
        name='BodyBold', fontName=NihaFonts.BODY_BOLD, fontSize=10, leading=14,
        textColor=NihaColors.DARK, alignment=TA_JUSTIFY,
        spaceBefore=1.5 * mm, spaceAfter=1.5 * mm,
    ))
    styles.add(ParagraphStyle(
        name='BodyIndent', fontName=NihaFonts.BODY, fontSize=10, leading=14,
        textColor=NihaColors.DARK, alignment=TA_JUSTIFY,
        spaceBefore=1 * mm, spaceAfter=1 * mm, leftIndent=10 * mm,
    ))
    styles.add(ParagraphStyle(
        name='FilledData', fontName=NihaFonts.FILLED, fontSize=10, leading=14,
        textColor=NihaColors.FILLED_BLUE, alignment=TA_LEFT,
        spaceBefore=1 * mm, spaceAfter=1 * mm,
    ))
    styles.add(ParagraphStyle(
        name='Caption', fontName=NihaFonts.BODY, fontSize=8, leading=11,
        textColor=NihaColors.LIGHT, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='RefCode', fontName=NihaFonts.MONO, fontSize=8.5, leading=11,
        textColor=NihaColors.MUTED, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='ClauseNumber', fontName=NihaFonts.HEADING, fontSize=11, leading=15,
        textColor=NihaColors.NAVY, spaceBefore=7 * mm, spaceAfter=2 * mm,
        keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name='SubClause', fontName=NihaFonts.BODY, fontSize=10, leading=14,
        textColor=NihaColors.DARK, alignment=TA_JUSTIFY,
        spaceBefore=1.5 * mm, spaceAfter=1.5 * mm, leftIndent=5 * mm,
    ))
    styles.add(ParagraphStyle(
        name='SubClauseItem', fontName=NihaFonts.BODY, fontSize=10, leading=14,
        textColor=NihaColors.DARK, alignment=TA_JUSTIFY,
        spaceBefore=1 * mm, spaceAfter=1 * mm, leftIndent=12 * mm,
    ))
    styles.add(ParagraphStyle(
        name='TableHeader', fontName=NihaFonts.BODY_BOLD, fontSize=9, leading=12,
        textColor=NihaColors.WHITE, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='TableCell', fontName=NihaFonts.BODY, fontSize=9, leading=12,
        textColor=NihaColors.DARK, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='TableCellFilled', fontName=NihaFonts.FILLED, fontSize=9, leading=12,
        textColor=NihaColors.FILLED_BLUE, alignment=TA_LEFT,
    ))
    styles.add(ParagraphStyle(
        name='Footer', fontName=NihaFonts.BODY, fontSize=7.5, leading=10,
        textColor=NihaColors.LIGHT, alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        name='SignatureLabel', fontName=NihaFonts.BODY, fontSize=9, leading=12,
        textColor=NihaColors.MUTED, spaceBefore=2 * mm,
    ))
    styles.add(ParagraphStyle(
        name='SignatureName', fontName=NihaFonts.BODY_BOLD, fontSize=10, leading=13,
        textColor=NihaColors.NAVY,
    ))
    styles.add(ParagraphStyle(
        name='SignatureTitle', fontName=NihaFonts.BODY_ITALIC, fontSize=9, leading=12,
        textColor=NihaColors.NAVY_MUTED,
    ))

    return styles


# =============================================================================
# REUSABLE COMPONENTS
# =============================================================================

def gold_separator():
    """Thin gold horizontal line."""
    return HRFlowable(
        width="100%", thickness=0.75, color=NihaColors.GOLD,
        spaceBefore=3 * mm, spaceAfter=3 * mm,
    )


def thin_separator():
    """Subtle thin line."""
    return HRFlowable(
        width="100%", thickness=0.4, color=NihaColors.BORDER,
        spaceBefore=2 * mm, spaceAfter=2 * mm,
    )


def filled(text: str) -> str:
    """Wrap text in the pre-filled data font inline within a Paragraph."""
    return f'<font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">{text}</font>'


def niha_party_block(styles, label: str = "Party A") -> list:
    """Pre-filled NIHA company information block."""
    data = [
        [Paragraph(f"<b>{label} — NIHA Limited</b>", styles['Body']), ''],
        [Paragraph("Registration:", styles['Caption']),
         Paragraph("Italy Nihao Group Limited", styles['FilledData'])],
        [Paragraph("Registered Address:", styles['Caption']),
         Paragraph("Suite 1201, 12/F, Two Harbourfront,<br/>"
                    "22 Tak Fung Street, Hung Hom, Kowloon,<br/>"
                    "Hong Kong SAR", styles['FilledData'])],
        [Paragraph("Represented by:", styles['Caption']),
         Paragraph("Mr. Christian Meier, Director", styles['FilledData'])],
        [Paragraph("Contact:", styles['Caption']),
         Paragraph("legal@niha.com", styles['FilledData'])],
    ]
    table = Table(data, colWidths=[35 * mm, 130 * mm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), NihaColors.NAVY),
        ('TEXTCOLOR', (0, 0), (1, 0), NihaColors.WHITE),
        ('FONTNAME', (0, 0), (1, 0), NihaFonts.BODY_BOLD),
        ('BACKGROUND', (1, 1), (1, -1), NihaColors.FILLED_BG),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 1, NihaColors.GOLD),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, NihaColors.BORDER),
        ('GRID', (0, 1), (-1, -1), 0.3, NihaColors.BORDER),
    ]))
    return [table]


def client_party_block(
    styles,
    label: str = "Party B — Counterparty",
    entity_name: Optional[str] = None,
    entity_type: Optional[str] = None,
    jurisdiction: Optional[str] = None,
    representative: Optional[str] = None,
    email: Optional[str] = None,
) -> list:
    """Client information block — pre-filled where data is available, blanks otherwise."""
    blank = "_" * 50

    def val_or_blank(v):
        if v:
            return Paragraph(v, styles['FilledData'])
        return Paragraph(blank, styles['Body'])

    data = [
        [Paragraph(f"<b>{label}</b>", styles['Body']), ''],
        [Paragraph("Entity Name:", styles['Caption']), val_or_blank(entity_name)],
        [Paragraph("Type / Jurisdiction:", styles['Caption']),
         val_or_blank(f"{entity_type or '___'}, incorporated under the laws of {jurisdiction}" if jurisdiction else None)],
        [Paragraph("Represented by:", styles['Caption']), val_or_blank(representative)],
        [Paragraph("Email:", styles['Caption']), val_or_blank(email)],
    ]
    table = Table(data, colWidths=[35 * mm, 130 * mm])
    table.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('BACKGROUND', (0, 0), (1, 0), NihaColors.NAVY_LIGHT),
        ('TEXTCOLOR', (0, 0), (1, 0), NihaColors.WHITE),
        ('FONTNAME', (0, 0), (1, 0), NihaFonts.BODY_BOLD),
        ('BACKGROUND', (1, 1), (1, -1), NihaColors.FILLED_BG if entity_name else NihaColors.WHITE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW', (0, 0), (-1, 0), 1, NihaColors.GOLD),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, NihaColors.BORDER),
        ('GRID', (0, 1), (-1, -1), 0.3, NihaColors.BORDER),
    ]))
    return [table]


def signature_block(
    styles,
    niha_signatory: str = "Christian Meier",
    niha_title: str = "Director",
    client_entity_name: Optional[str] = None,
    include_date: bool = True,
) -> list:
    """Dual-party signature block. NIHA pre-signed, client blank for wet-ink."""
    elements = []
    elements.append(Spacer(1, 8 * mm))
    elements.append(gold_separator())
    elements.append(Paragraph("IN WITNESS WHEREOF", styles['SectionHeading']))
    elements.append(Paragraph(
        "the parties have executed this Agreement on the date first written above.",
        styles['Body']
    ))
    elements.append(Spacer(1, 6 * mm))

    # NIHA column
    niha_col = []
    niha_col.append(Paragraph("<b>For and on behalf of</b>", styles['SignatureLabel']))
    niha_col.append(Paragraph("<b>Italy Nihao Group Limited</b>", styles['SignatureName']))
    niha_col.append(Spacer(1, 14 * mm))
    niha_col.append(HRFlowable(width="80%", thickness=0.5, color=NihaColors.SIG_LINE, spaceAfter=1*mm))
    niha_col.append(Paragraph(niha_signatory, styles['FilledData']))
    niha_col.append(Paragraph(niha_title, styles['SignatureTitle']))
    if include_date:
        niha_col.append(Spacer(1, 3 * mm))
        niha_col.append(Paragraph(
            f'Date: <font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">'
            f'{datetime.now().strftime("%d %B %Y")}</font>',
            styles['SignatureLabel']
        ))

    # Client column
    client_col = []
    client_col.append(Paragraph("<b>For and on behalf of</b>", styles['SignatureLabel']))
    client_label = client_entity_name or "[Counterparty Entity]"
    client_col.append(Paragraph(f"<b>{client_label}</b>", styles['SignatureName']))
    client_col.append(Spacer(1, 14 * mm))
    client_col.append(HRFlowable(width="80%", thickness=0.5, color=NihaColors.SIG_LINE, spaceAfter=1*mm))
    client_col.append(Paragraph("Name: ________________________", styles['SignatureLabel']))
    client_col.append(Paragraph("Title: ________________________", styles['SignatureLabel']))
    client_col.append(Spacer(1, 3 * mm))
    client_col.append(Paragraph("Date: ________________________", styles['SignatureLabel']))

    sig_table = Table([[niha_col, client_col]], colWidths=[82 * mm, 82 * mm])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BACKGROUND', (0, 0), (0, 0), NihaColors.FILLED_BG),
        ('BACKGROUND', (1, 0), (1, 0), NihaColors.SIG_BG),
        ('BOX', (0, 0), (0, 0), 0.5, NihaColors.NAVY_MUTED),
        ('BOX', (1, 0), (1, 0), 0.5, NihaColors.BORDER),
    ]))
    elements.append(sig_table)
    return elements


def key_terms_table(styles, terms: list[tuple[str, str, str]]) -> Table:
    """
    Create a summary table. Each term is (label, value, status).
    Pre-filled values use the FilledData style.
    """
    header = [
        Paragraph("Term", styles['TableHeader']),
        Paragraph("Detail", styles['TableHeader']),
        Paragraph("Status", styles['TableHeader']),
    ]
    rows = [header]
    for i, (label, value, status) in enumerate(terms):
        rows.append([
            Paragraph(label, styles['TableCell']),
            Paragraph(value, styles['TableCellFilled']),
            Paragraph(status, styles['TableCellFilled']),
        ])

    table = Table(rows, colWidths=[40 * mm, 70 * mm, 50 * mm])
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), NihaColors.NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), NihaColors.WHITE),
        ('GRID', (0, 0), (-1, -1), 0.4, NihaColors.BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, NihaColors.GOLD),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    # Alternating row backgrounds
    for i in range(1, len(rows)):
        bg = NihaColors.FILLED_BG if i % 2 == 1 else NihaColors.WHITE
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))

    table.setStyle(TableStyle(style_cmds))
    return table


# =============================================================================
# HEADER / FOOTER — NihaDocTemplate
# =============================================================================

class NihaDocTemplate:
    """Custom page template with NIHA branding — header and footer on every page."""

    def __init__(self, doc_ref: str, doc_title: str, confidential: bool = True):
        self.doc_ref = doc_ref
        self.doc_title = doc_title
        self.confidential = confidential

    def header_footer(self, canvas_obj, doc):
        """Draw header and footer on every page."""
        canvas_obj.saveState()
        width, height = A4

        # ── HEADER ──
        canvas_obj.setStrokeColor(NihaColors.GOLD)
        canvas_obj.setLineWidth(1.5)
        canvas_obj.line(20 * mm, height - 15 * mm, width - 20 * mm, height - 15 * mm)

        canvas_obj.setFont(NihaFonts.HEADING, 9)
        canvas_obj.setFillColor(NihaColors.NAVY)
        canvas_obj.drawString(20 * mm, height - 13 * mm, "NIHA")

        canvas_obj.setFont(NihaFonts.BODY, 7)
        canvas_obj.setFillColor(NihaColors.NAVY_MUTED)
        canvas_obj.drawString(35 * mm, height - 13 * mm, "Carbon Trading Platform")

        canvas_obj.setFont(NihaFonts.MONO, 7.5)
        canvas_obj.setFillColor(NihaColors.MUTED)
        canvas_obj.drawRightString(width - 20 * mm, height - 13 * mm, self.doc_ref)

        # ── FOOTER ──
        canvas_obj.setStrokeColor(NihaColors.GOLD)
        canvas_obj.setLineWidth(0.75)
        canvas_obj.line(20 * mm, 18 * mm, width - 20 * mm, 18 * mm)

        if self.confidential:
            canvas_obj.setFont(NihaFonts.BODY_BOLD, 6.5)
            canvas_obj.setFillColor(NihaColors.GOLD)
            canvas_obj.drawString(20 * mm, 14 * mm, "CONFIDENTIAL")

        canvas_obj.setFont(NihaFonts.BODY, 7.5)
        canvas_obj.setFillColor(NihaColors.LIGHT)
        canvas_obj.drawCentredString(width / 2, 14 * mm, f"Page {doc.page}")

        canvas_obj.setFont(NihaFonts.BODY, 6.5)
        canvas_obj.setFillColor(NihaColors.LIGHT)
        canvas_obj.drawRightString(
            width - 20 * mm, 14 * mm, f"\u00a9 {datetime.now().year} Italy Nihao Group Limited"
        )

        canvas_obj.restoreState()


# =============================================================================
# MAIN BUILDER
# =============================================================================

def build_niha_pdf(
    doc_ref: str,
    doc_title: str,
    content_builder,  # callable(styles) -> list of flowables
    confidential: bool = True,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Build a NIHA-branded PDF document and return as bytes.

    Args:
        doc_ref: Document reference (e.g. "NIHA-NDA-2026-001")
        doc_title: Document title for metadata
        content_builder: Function(styles) -> list of Flowable elements
        confidential: Whether to show CONFIDENTIAL mark
        output_path: Optional file path to also save to disk

    Returns:
        PDF content as bytes
    """
    template = NihaDocTemplate(doc_ref, doc_title, confidential)
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=22 * mm,
        bottomMargin=24 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        title=doc_title,
        author="Italy Nihao Group Limited",
        subject=doc_ref,
    )

    styles = create_niha_styles()
    elements = content_builder(styles)

    doc.build(elements, onFirstPage=template.header_footer, onLaterPages=template.header_footer)

    pdf_bytes = buffer.getvalue()
    buffer.close()

    if output_path:
        with open(output_path, 'wb') as f:
            f.write(pdf_bytes)

    return pdf_bytes
