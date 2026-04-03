"""
Fee Schedule PDF Generator — NIHA Fee Schedule & Pricing Matrix.

Generates a branded PDF with all fee tables, volume tiers,
and payment terms pre-filled with NIHA's standard rates.
"""

from datetime import date
from typing import Optional

from reportlab.platypus import Spacer, Paragraph
from reportlab.lib.units import mm

from .styles import (
    build_niha_pdf, gold_separator, thin_separator, filled,
    NihaFonts, NihaColors,
)
from .msa_generator import _data_table


def generate_fee_schedule_pdf(
    client_entity_name: Optional[str] = None,
    client_representative: Optional[str] = None,
    client_email: Optional[str] = None,
    effective_date: Optional[date] = None,
    doc_ref: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate the NIHA Fee Schedule as a branded PDF."""
    eff_date = effective_date or date.today()
    ref = doc_ref or f"NIHA-FEE-{eff_date.strftime('%Y')}-001"

    def content(styles):
        el = []

        # ── TITLE ──
        el.append(Spacer(1, 15 * mm))
        el.append(Paragraph("FEE SCHEDULE &amp;", styles['DocTitle']))
        el.append(Paragraph("PRICING MATRIX", styles['DocTitle']))
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph("Annexure B to the Master Service Agreement", styles['DocSubtitle']))
        el.append(gold_separator())

        date_str = eff_date.strftime("%d %B %Y")
        el.append(Paragraph(f"Effective Date: {filled(date_str)}", styles['Body']))
        el.append(Paragraph(f"Reference: {filled(ref)}", styles['Body']))
        el.append(Paragraph(f"Version: {filled('3.0')}", styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(
            'This Fee Schedule forms Annexure B to the Master Service Agreement and sets out all '
            'fees, commissions, and charges applicable to carbon credit trading services provided by '
            f'{filled("Italy Nihao Group Limited")}.', styles['Body']))
        el.append(Paragraph(
            f'Fees are subject to annual review and may be amended with {filled("sixty (60) days")} '
            f'written notice to the Client.', styles['Body']))
        el.append(Spacer(1, 5 * mm))

        # ── 1. TRADING COMMISSIONS ──
        el.append(Paragraph("1. TRADING COMMISSIONS", styles['SectionHeading']))
        el.append(thin_separator())

        tc = _data_table(styles,
            headers=["Instrument", "Volume Tier", "Commission", "Min Fee", "Basis"],
            rows=[
                [filled("EUA (Phase IV)"), "< 5,000 units", filled("1.75%"), "EUR 500", "Of consideration"],
                [filled("EUA (Phase IV)"), "5,000 - 25,000", filled("1.50%"), "EUR 500", "Of consideration"],
                [filled("EUA (Phase IV)"), "25,000 - 100,000", filled("1.25%"), "EUR 1,000", "Of consideration"],
                [filled("EUA (Phase IV)"), "> 100,000", filled("1.00%"), "EUR 1,500", "Of consideration"],
                [filled("CEA (National)"), "< 50,000 units", filled("2.00%"), "CNY 8,000", "Of consideration"],
                [filled("CEA (National)"), "50,000 - 200,000", filled("1.75%"), "CNY 12,000", "Of consideration"],
                [filled("CEA (Pilot)"), "Any volume", filled("2.50%"), "CNY 10,000", "Of consideration"],
                [filled("VCC (Verra)"), "< 10,000 units", filled("3.00%"), "EUR 800", "Of consideration"],
                [filled("VCC (Verra)"), "10,000+", filled("2.50%"), "EUR 1,200", "Of consideration"],
            ],
            col_widths=[35 * mm, 32 * mm, 28 * mm, 30 * mm, 45 * mm],
        )
        el.append(tc)
        el.append(Spacer(1, 5 * mm))

        # ── 2. CROSS-BORDER CONVERSION FEES ──
        el.append(Paragraph("2. CROSS-BORDER CONVERSION FEES", styles['SectionHeading']))
        el.append(thin_separator())

        cf = _data_table(styles,
            headers=["Conversion Type", "Volume Tier", "Fee Rate", "Minimum", "Basis"],
            rows=[
                ["CEA to EUA", "< 50,000 CEA", filled("3.00%"), "EUR 1,500", "Of delivered EUA value"],
                ["CEA to EUA", "50,000 - 200,000", filled("2.50%"), "EUR 3,000", "Of delivered EUA value"],
                ["EUA to CEA", "Any volume", filled("3.50%"), "EUR 2,000", "Of delivered CEA value"],
                ["CCER Conversion", "Any volume", filled("4.00%"), "EUR 1,000", "Of delivered credit value"],
            ],
            col_widths=[35 * mm, 32 * mm, 25 * mm, 30 * mm, 48 * mm],
        )
        el.append(cf)
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph(
            '<b>Note:</b> Conversion fees include NIHA\'s cross-border facilitation, SAFE clearance '
            'processing, and registry transfer coordination. Exchange fees are passed through at cost.',
            styles['Body']))
        el.append(Spacer(1, 5 * mm))

        # ── 3. CUSTODY & ADMINISTRATION ──
        el.append(Paragraph("3. CUSTODY &amp; ADMINISTRATION FEES", styles['SectionHeading']))
        el.append(thin_separator())

        ca = _data_table(styles,
            headers=["Service", "Fee", "Frequency", "Notes"],
            rows=[
                ["Carbon Credit Custody", filled("0.02% of AUM"), "Monthly", "Month-end MTM value"],
                ["Account Maintenance", filled("EUR 250 / CNY 2,000"), "Quarterly", "Per currency account"],
                ["Portfolio Reporting", filled("Included"), "Monthly", "Via Platform"],
                ["Annual Reconciliation", filled("Included"), "Annual", "External auditor confirmation"],
                ["Additional Registry Accounts", filled("EUR 100"), "One-time", "Set-up fee"],
                ["Regulatory Reporting Support", filled("EUR 500"), "As needed", "Per jurisdiction/report"],
                ["Account Closure", filled("EUR 250"), "One-time", "Final settlement & archival"],
                ["Delayed Settlement (per day)", filled("0.10% of value"), "Daily", "After standard T+3/T+5"],
            ],
            col_widths=[45 * mm, 40 * mm, 30 * mm, 55 * mm],
        )
        el.append(ca)
        el.append(Spacer(1, 5 * mm))

        # ── 4. ONBOARDING & COMPLIANCE ──
        el.append(Paragraph("4. ONBOARDING &amp; COMPLIANCE FEES", styles['SectionHeading']))
        el.append(thin_separator())

        oc = _data_table(styles,
            headers=["Service", "Fee", "Frequency", "Notes"],
            rows=[
                ["Initial Client Onboarding & KYC", filled("Waived"), "One-time", "Absorbed by NIHA"],
                ["Enhanced Due Diligence", filled("EUR 500"), "One-time", "PEP / high-risk jurisdictions"],
                ["Periodic Compliance Reviews", filled("EUR 300"), "Annually", "Post-onboarding"],
            ],
            col_widths=[45 * mm, 40 * mm, 30 * mm, 55 * mm],
        )
        el.append(oc)
        el.append(Spacer(1, 5 * mm))

        # ── 5. MARKET DATA & ADVISORY ──
        el.append(Paragraph("5. MARKET DATA &amp; ADVISORY FEES", styles['SectionHeading']))
        el.append(thin_separator())

        md = _data_table(styles,
            headers=["Service", "Fee", "Frequency", "Notes"],
            rows=[
                ["Carbon Market Intelligence Report", filled("Included"), "Quarterly", "For active clients"],
                ["Bespoke Market Analysis", filled("EUR 500 / report"), "On request", "Sector/jurisdiction specific"],
                ["Real-time Pricing Data", filled("Included"), "Continuous", "Via Platform API"],
                ["Regulatory Update Briefings", filled("Included"), "As issued", "Email distribution"],
            ],
            col_widths=[45 * mm, 40 * mm, 30 * mm, 55 * mm],
        )
        el.append(md)
        el.append(Spacer(1, 5 * mm))

        # ── 6. PAYMENT TERMS ──
        el.append(Paragraph("6. PAYMENT TERMS", styles['SectionHeading']))
        el.append(thin_separator())

        terms = [
            ('<b>6.1</b>', 'Trading commissions are deducted from the transaction proceeds at settlement (T+0).'),
            ('<b>6.2</b>', 'Conversion fees are payable in advance of EUA delivery, or deducted from the delivered EUA value at the Client\'s election.'),
            ('<b>6.3</b>', f'Custody fees are invoiced monthly in arrears, payable within {filled("14 business days")}.'),
            ('<b>6.4</b>', 'All fees are quoted exclusive of applicable taxes. Clients are responsible for their own tax liabilities.'),
            ('<b>6.5</b>', f'Late payment interest: {filled("HSBC Hong Kong Prime Rate + 2%")} per annum, calculated daily.'),
            ('<b>6.6</b>', f'Fee disputes must be raised in writing within {filled("30 days")} of the relevant invoice or deduction.'),
        ]
        for num, text in terms:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ── 7. VOLUME DISCOUNT PROGRAMME ──
        el.append(Paragraph("7. VOLUME DISCOUNT PROGRAMME", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'Clients exceeding certain annual trading volume thresholds qualify for reduced commission rates:',
            styles['Body']))
        el.append(Spacer(1, 3 * mm))

        vd = _data_table(styles,
            headers=["Annual Volume (units)", "Tier", "EUA Discount", "CEA Discount", "VCC Discount"],
            rows=[
                ["< 50,000", filled("Standard"), "—", "—", "—"],
                ["50,000 - 200,000", filled("Silver"), filled("-0.15%"), filled("-0.15%"), filled("-0.25%")],
                ["200,000 - 500,000", filled("Gold"), filled("-0.35%"), filled("-0.35%"), filled("-0.50%")],
                ["> 500,000", filled("Platinum"), filled("-0.50%"), filled("-0.50%"), filled("-0.75%")],
            ],
            col_widths=[38 * mm, 28 * mm, 33 * mm, 33 * mm, 38 * mm],
        )
        el.append(vd)
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(
            'Volume discount tier is assessed annually on 1 January based on the prior calendar '
            'year\'s trading volume. New clients may negotiate their initial tier based on projected volumes.',
            styles['Body']))

        # ── FOOTER NOTE ──
        el.append(Spacer(1, 8 * mm))
        el.append(gold_separator())
        el.append(Paragraph(
            f'<b>Approved by:</b> Managing Director | Date: {filled("20 December 2025")}',
            styles['Body']))
        el.append(Paragraph(
            'This Fee Schedule supersedes all prior fee schedules and is effective from 1 January 2026.',
            styles['Caption']))
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(
            '<i>Note: Text displayed in </i>'
            f'<font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">this style '
            f'(bold italic, blue)</font>'
            '<i> indicates pre-set rates by NIHA. Rates are subject to the revision terms in Article 5 of the MSA.</i>',
            styles['Caption']))

        return el

    return build_niha_pdf(
        doc_ref=ref,
        doc_title="Fee Schedule & Pricing Matrix",
        content_builder=content,
        confidential=True,
        output_path=output_path,
    )
