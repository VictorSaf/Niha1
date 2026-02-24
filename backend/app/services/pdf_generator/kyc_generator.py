"""
KYC / Client Onboarding Application PDF Generator.

Generates a branded PDF with all KYC form sections (A–I),
form tables, checkbox fields, and compliance review section.
"""

from datetime import date
from typing import Optional

from reportlab.platypus import Spacer, Paragraph, Table, TableStyle, PageBreak
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

from .styles import (
    build_niha_pdf, gold_separator, thin_separator, filled,
    signature_block, NihaFonts, NihaColors,
)


def _form_table(styles, rows: list[list[str]], col_widths=None):
    """Two-column form table (label | value) with NIHA styling."""
    widths = col_widths or [55 * mm, 115 * mm]
    data = []
    for label, value in rows:
        data.append([
            Paragraph(f'<b>{label}</b>', styles['Body']),
            Paragraph(value, styles['Body']),
        ])
    t = Table(data, colWidths=widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), HexColor("#F0F3F7")),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return t


def _checkbox_block(styles, options: list[str]):
    """Render a single-cell checkbox list."""
    text = '<br/>'.join(f'\u2610 {opt}' for opt in options)
    data = [[Paragraph(text, styles['Body'])]]
    t = Table(data, colWidths=[170 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F9FAFB")),
        ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _person_table(styles, title: str, fields: list[tuple[str, str]]):
    """Titled person-info table (Director, UBO, Signatory)."""
    el = []
    el.append(Paragraph(f'<b>{title}</b>', styles['SubHeading']))
    el.append(Spacer(1, 1 * mm))
    el.append(_form_table(styles, fields))
    el.append(Spacer(1, 3 * mm))
    return el


def _internal_review_table(styles):
    """Compliance review table (for internal use)."""
    from .msa_generator import _data_table
    rows = [
        ["Application Reference No.", "___________________________"],
        ["Date Received", "___________________________"],
        ["Compliance Officer", "___________________________"],
        ["Identity Verification", "\u2610 Pass  \u2610 Fail  \u2610 Pending"],
        ["Sanctions Screening", "\u2610 Clear  \u2610 Match (refer)  \u2610 Pending"],
        ["PEP Screening", "\u2610 Clear  \u2610 PEP Identified (EDD required)  \u2610 Pending"],
        ["Adverse Media Check", "\u2610 Clear  \u2610 Findings (refer)  \u2610 Pending"],
        ["Source of Funds Verification", "\u2610 Satisfactory  \u2610 Further info required  \u2610 Rejected"],
        ["Risk Classification", "\u2610 Low  \u2610 Medium  \u2610 High  \u2610 Unacceptable"],
        ["EDD Required?", "\u2610 Yes  \u2610 No"],
        ["Approval Decision", "\u2610 Approved  \u2610 Approved with conditions  \u2610 Declined"],
        ["Conditions (if any)", "___________________________"],
        ["Approved by (Name & Title)", "___________________________"],
        ["Approval Date", "___________________________"],
        ["Next Review Date", filled("12 months from approval / Earlier if risk triggers")],
    ]
    return _form_table(styles, rows, col_widths=[55 * mm, 115 * mm])


def generate_kyc_pdf(
    client_entity_name: Optional[str] = None,
    client_representative: Optional[str] = None,
    client_email: Optional[str] = None,
    effective_date: Optional[date] = None,
    doc_ref: Optional[str] = None,
    output_path: Optional[str] = None,
    form_data: Optional[dict] = None,
    documents_status: Optional[list[dict]] = None,
) -> bytes:
    """Generate the NIHA Client Onboarding / KYC Application as a branded PDF.

    Args:
        form_data: KYC form data dict from KYCFormData model (optional).
            If provided, sections E/F/G/H will be pre-filled with client responses.
        documents_status: List of {"type": "REGISTRATION", "status": "approved", "file_name": "..."}.
            If provided, the document checklist will show ☑ for uploaded docs.
    """
    eff_date = effective_date or date.today()
    ref = doc_ref or f"NIHA-OBD-{eff_date.strftime('%Y')}-001"
    fd = form_data or {}

    blank = "___________________________"

    # Helper to get PEP status from form_data for a given role
    def _pep_display(role: str, index: int) -> str:
        """Return '☑ Yes ☐ No' or '☐ Yes ☑ No' based on form data."""
        pep_list = fd.get("pep_declarations") or []
        matches = [p for p in pep_list if p.get("role") == role]
        if index < len(matches):
            is_pep = matches[index].get("is_pep", False)
            return f"{'☑' if is_pep else '☐'} Yes  {'☐' if is_pep else '☑'} No"
        return "\u2610 Yes  \u2610 No"

    # Helper for checkbox lists from form data
    def _check_list(options: list[tuple[str, str]], selected: list[str] | None) -> list[str]:
        """Return list of '☑ label' or '☐ label' based on selected keys."""
        sel = set(selected or [])
        return [f"{'☑' if key in sel else '☐'} {label}" for key, label in options]

    def content(styles):
        el = []

        # ── TITLE ──
        el.append(Spacer(1, 15 * mm))
        el.append(Paragraph("CLIENT ONBOARDING", styles['DocTitle']))
        el.append(Paragraph("APPLICATION", styles['DocTitle']))
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph("Know Your Customer (KYC) Due Diligence Pack", styles['DocSubtitle']))
        el.append(Spacer(1, 1 * mm))
        el.append(Paragraph(
            f"Version {filled('1.0')} — {filled(eff_date.strftime('%B %Y'))}",
            styles['DocSubtitle']))
        el.append(gold_separator())
        el.append(Paragraph(f"Reference: {filled(ref)}", styles['Body']))
        el.append(Spacer(1, 5 * mm))

        # ── INSTRUCTIONS ──
        el.append(Paragraph("INSTRUCTIONS TO APPLICANT", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'Italy Nihao Group Limited ("NIHA" or "the Company") is committed to maintaining '
            'the highest standards of client due diligence in accordance with the applicable '
            'anti-money laundering and counter-terrorist financing legislation in Hong Kong '
            '("applicable legislation") and FATF Recommendations.',
            styles['Body']))
        el.append(Paragraph(
            'Please complete all sections of this application form in full. Incomplete '
            'applications will not be processed and will be returned to the applicant. '
            'All supporting documentation must be certified copies unless originals are provided.',
            styles['Body']))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph('<b>Required Supporting Documents</b>', styles['SubHeading']))
        # Map document types to checklist descriptions
        _doc_type_map = {
            "REGISTRATION": "Certificate of Incorporation (or equivalent constitutional document)",
            "ARTICLES": "Memorandum and Articles of Association (or equivalent)",
            "PROOF_AUTHORITY": "Board Resolution / Power of Attorney authorising representative",
            "ID": "Identification documents for Authorised Signatories (passport + proof of address)",
            "FINANCIAL_STATEMENTS": "Audited Financial Statements (most recent 2 financial years)",
            "TAX_CERTIFICATE": "Tax Identification Number (TIN) certificate",
            "CONTACT_INFO": "Representative Contact Information",
            "GHG_PERMIT": "GHG Emissions Permit (if applicable)",
        }
        _uploaded_types = set()
        if documents_status:
            _uploaded_types = {d["type"] for d in documents_status if d.get("status") in ("approved", "pending")}

        docs_checklist = [
            ("REGISTRATION", "Certificate of Incorporation (or equivalent constitutional document)"),
            ("ARTICLES", "Memorandum and Articles of Association (or equivalent)"),
            (None, "Register of Directors and Company Secretary"),
            (None, "Register of Shareholders / Members (showing ultimate beneficial owners)"),
            (None, "Certificate of Good Standing (issued within 3 months)"),
            ("PROOF_AUTHORITY", "Board Resolution authorising entry into this engagement"),
            ("ID", "Identification documents for all Authorised Signatories (passport + proof of address)"),
            (None, "Identification documents for all Ultimate Beneficial Owners (>25% ownership)"),
            ("FINANCIAL_STATEMENTS", "Audited Financial Statements (most recent 2 financial years)"),
            (None, "Bank Reference Letter (issued within 3 months)"),
            ("TAX_CERTIFICATE", "Tax Identification Number (TIN) certificate"),
            (None, "Source of Funds declaration (see Section F)"),
            (None, "AML/KYC policy of applicant entity (if applicable)"),
            (None, "Carbon market experience documentation (if applicable)"),
        ]
        for doc_type, label in docs_checklist:
            checked = doc_type in _uploaded_types if doc_type else False
            icon = '\u2611' if checked else '\u2610'
            el.append(Paragraph(f'{icon} {label}', styles['SubClauseItem']))
        el.append(Spacer(1, 5 * mm))

        # ── SECTION A — APPLICANT ENTITY DETAILS ──
        el.append(Paragraph("SECTION A — APPLICANT ENTITY DETAILS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(_form_table(styles, [
            ["Full Legal Name", client_entity_name or blank],
            ["Trading Name (if different)", blank],
            ["Country of Incorporation", blank],
            ["Date of Incorporation", blank],
            ["Company Reference Number", blank],
            ["Legal Entity Identifier (LEI)", blank],
            ["Registered Office Address", blank],
            ["Principal Business Address", blank],
            ["Telephone Number", blank],
            ["Email Address", client_email or blank],
            ["Website", blank],
            ["Tax Identification Number (TIN)", blank],
            ["VAT/GST Registration (if applicable)", blank],
        ]))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph('<b>Nature of Business</b>', styles['SubHeading']))
        el.append(_checkbox_block(styles, [
            "Energy / Utilities",
            "Financial Services / Investment",
            "Manufacturing / Industrial",
            "Environmental / Sustainability Consultancy",
            "Trading / Commodities",
            "Government / Public Sector",
            "Other (please specify): ___________________________",
        ]))
        el.append(Spacer(1, 5 * mm))

        # ── SECTION B — DIRECTORS AND OFFICERS ──
        el.append(Paragraph("SECTION B — DIRECTORS AND OFFICERS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'Please provide details of all current directors, company secretary, '
            'and senior officers.', styles['Body']))
        el.append(Spacer(1, 2 * mm))

        for i in range(1, 4):
            person_fields = [
                ("Full Name", blank),
                ("Position / Title", blank),
                ("Nationality", blank),
                ("Date of Birth", blank),
                ("Passport / ID Number", blank),
                ("Residential Address", blank),
                ("Politically Exposed Person (PEP)?", _pep_display("director", i - 1)),
            ]
            el.extend(_person_table(styles, f"Director / Officer {i}", person_fields))
        el.append(Spacer(1, 3 * mm))

        # ── SECTION C — ULTIMATE BENEFICIAL OWNERS ──
        el.append(PageBreak())
        el.append(Paragraph("SECTION C — ULTIMATE BENEFICIAL OWNERS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'Please provide details of all natural persons who ultimately own or control '
            'more than 25% of the shares, voting rights, or economic interest of the '
            'Applicant Entity, directly or indirectly.', styles['Body']))
        el.append(Spacer(1, 2 * mm))

        for i in range(1, 3):
            ubo_fields = [
                ("Full Name", blank),
                ("Nationality", blank),
                ("Date of Birth", blank),
                ("Passport / ID Number", blank),
                ("Residential Address", blank),
                ("Percentage of Ownership (%)", blank),
                ("Nature of Control", blank),
                ("Politically Exposed Person (PEP)?", _pep_display("ubo", i - 1)),
                ("Source of Wealth", blank),
            ]
            el.extend(_person_table(styles, f"Beneficial Owner {i}", ubo_fields))
        el.append(Spacer(1, 3 * mm))

        # ── SECTION D — AUTHORISED SIGNATORIES ──
        el.append(Paragraph(
            "SECTION D — AUTHORISED SIGNATORIES AND REPRESENTATIVES",
            styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'The following individuals are authorised to give instructions, sign documents, '
            'and execute transactions on behalf of the Applicant Entity in connection with '
            'carbon credit services provided by NIHA.', styles['Body']))
        el.append(Spacer(1, 2 * mm))

        sig_fields = [
            ("Full Name", client_representative or blank),
            ("Position / Title", blank),
            ("Email Address", client_email or blank),
            ("Telephone Number", blank),
            ("Specimen Signature", blank),
            ("Authority Level", "\u2610 Full Authority  \u2610 Limited (specify): ___________"),
        ]
        el.extend(_person_table(styles, "Authorised Signatory 1", sig_fields))

        sig2_fields = [
            ("Full Name", blank),
            ("Position / Title", blank),
            ("Email Address", blank),
            ("Telephone Number", blank),
            ("Specimen Signature", blank),
            ("Authority Level", "\u2610 Full Authority  \u2610 Limited (specify): ___________"),
        ]
        el.extend(_person_table(styles, "Authorised Signatory 2", sig2_fields))
        el.append(Spacer(1, 3 * mm))

        # ── SECTION E — CARBON MARKET EXPERIENCE ──
        el.append(PageBreak())
        el.append(Paragraph(
            "SECTION E — CARBON MARKET EXPERIENCE AND INVESTMENT PROFILE",
            styles['SectionHeading']))
        el.append(thin_separator())

        # Pre-fill from form_data if available
        _has_exp = fd.get("has_carbon_experience")
        _exp_yes_no = (
            f"{'☑' if _has_exp else '☐'} Yes  {'☐' if _has_exp else '☑'} No"
            if _has_exp is not None else "\u2610 Yes  \u2610 No"
        )
        _exp_years = filled(fd.get("carbon_experience_years")) if fd.get("carbon_experience_years") else blank

        # Carbon credits traded — keys must match frontend: 'EUA', 'CER', 'VER/VCU', 'CEA', 'Other'
        _credit_options = [
            ("EUA", "EU Allowances (EUA)"),
            ("CER", "Certified Emission Reductions (CER)"),
            ("VER/VCU", "Voluntary Carbon Credits (VER/VCU)"),
            ("CEA", "Chinese Emission Allowances (CEA)"),
            ("Other", "Other carbon instruments"),
        ]
        _traded = fd.get("carbon_credits_traded") or []
        _credits_display = ', '.join(
            label for key, label in _credit_options if key in _traded
        ) or blank

        el.append(Paragraph('<b>E.1 Carbon Market Experience</b>', styles['SubHeading']))
        el.append(_form_table(styles, [
            ("Prior carbon credit trading experience?", _exp_yes_no),
            ("If yes, number of years", _exp_years),
            ("Carbon registries used", blank),
            ("Estimated annual trading volume (EUR)", blank),
            ("Types of carbon credits traded", _credits_display),
        ]))
        el.append(Spacer(1, 3 * mm))

        # Investment objectives — keys must match frontend: 'compliance', 'diversification',
        # 'trading', 'offsetting', 'arbitrage', 'accumulation'
        _obj_options = [
            ("compliance", "Compliance obligation fulfilment (EU ETS / China ETS)"),
            ("diversification", "Portfolio diversification into carbon assets"),
            ("trading", "Speculative trading / market-making"),
            ("offsetting", "Voluntary carbon offsetting (ESG / CSR commitments)"),
            ("arbitrage", "Cross-border CEA-EUA conversion arbitrage"),
            ("accumulation", "Long-term carbon credit accumulation"),
        ]
        _selected_objs = fd.get("investment_objectives") or []

        el.append(Paragraph('<b>E.2 Investment Objectives</b>', styles['SubHeading']))
        obj_lines = _check_list(_obj_options, _selected_objs)
        obj_lines.append("\u2610 Other (please specify): ___________________________")
        text = '<br/>'.join(obj_lines)
        obj_data = [[Paragraph(text, styles['Body'])]]
        obj_tbl = Table(obj_data, colWidths=[170 * mm])
        obj_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F9FAFB")),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        el.append(obj_tbl)
        el.append(Spacer(1, 3 * mm))

        # Risk appetite
        _risk = fd.get("risk_appetite")
        _risk_options = [
            ("conservative", "Conservative — Capital preservation priority; low tolerance for loss"),
            ("moderate", "Moderate — Balanced risk/return; accepts moderate short-term volatility"),
            ("aggressive", "Aggressive — High return priority; accepts significant volatility and potential loss"),
        ]
        risk_lines = _check_list(_risk_options, [_risk] if _risk else [])
        el.append(Paragraph('<b>E.3 Risk Appetite</b>', styles['SubHeading']))
        risk_text = '<br/>'.join(risk_lines)
        risk_data = [[Paragraph(risk_text, styles['Body'])]]
        risk_tbl = Table(risk_data, colWidths=[170 * mm])
        risk_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F9FAFB")),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        el.append(risk_tbl)
        el.append(Spacer(1, 5 * mm))

        # ── SECTION F — SOURCE OF FUNDS ──
        el.append(Paragraph(
            "SECTION F — SOURCE OF FUNDS AND WEALTH DECLARATION",
            styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'In accordance with the applicable anti-money laundering and counter-terrorist '
            'financing legislation in Hong Kong and FATF Recommendations, the Applicant is '
            'required to provide a comprehensive declaration regarding the origin of funds '
            'to be used in connection with carbon credit transactions.', styles['Body']))
        el.append(Spacer(1, 2 * mm))

        # Source of funds from form_data
        _sof_options = [
            ("operating_revenue", "Operating revenue / Business profits"),
            ("investment_returns", "Investment returns / Capital gains"),
            ("bank_loan", "Bank loan / Credit facility"),
            ("shareholder_capital", "Shareholder capital contribution"),
            ("government_grant", "Government grant / Subsidy"),
        ]
        _selected_sof = fd.get("source_of_funds") or []

        el.append(Paragraph('<b>F.1 Source of Funds for Carbon Transactions</b>', styles['SubHeading']))
        sof_lines = _check_list(_sof_options, _selected_sof)
        sof_lines.append("\u2610 Other (please specify): ___________________________")
        sof_text = '<br/>'.join(sof_lines)
        sof_data = [[Paragraph(sof_text, styles['Body'])]]
        sof_tbl = Table(sof_data, colWidths=[170 * mm])
        sof_tbl.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), HexColor("#F9FAFB")),
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        el.append(sof_tbl)
        el.append(Spacer(1, 3 * mm))

        # Expected volume & intended use (simplified — no bank details)
        _exp_vol = filled(fd.get("expected_annual_volume")) if fd.get("expected_annual_volume") else blank
        el.append(Paragraph('<b>F.2 Expected Transaction Profile</b>', styles['SubHeading']))
        el.append(_form_table(styles, [
            ("Expected annual transaction volume (EUR)", _exp_vol),
        ]))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph('<b>F.3 Intended Use of Carbon Credits</b>', styles['SubHeading']))
        _intended = fd.get("intended_use_description") or ""
        area_content = filled(_intended) if _intended else '<br/><br/><br/><br/>'
        area_data = [[Paragraph(area_content, styles['Body'])]]
        area_tbl = Table(area_data, colWidths=[170 * mm], rowHeights=[25 * mm])
        area_tbl.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        el.append(area_tbl)
        el.append(Spacer(1, 5 * mm))

        # ── SECTION G — TAX DECLARATIONS ──
        el.append(Paragraph("SECTION G — TAX DECLARATIONS", styles['SectionHeading']))
        el.append(thin_separator())

        _tax_country = filled(fd.get("tax_residency_country")) if fd.get("tax_residency_country") else blank
        _crs = fd.get("subject_to_crs")
        _crs_display = (
            f"{'☑' if _crs else '☐'} Yes  {'☐' if _crs else '☑'} No"
            if _crs is not None else "\u2610 Yes  \u2610 No"
        )

        el.append(Paragraph('<b>G.1 Tax Residency</b>', styles['SubHeading']))
        el.append(_form_table(styles, [
            ("Country/Jurisdiction of Tax Residency", _tax_country),
            ("Tax Identification Number (TIN)", blank),
            ("Subject to CRS/AEOI reporting?", _crs_display),
        ]))
        el.append(Spacer(1, 5 * mm))

        # ── SECTION H — DECLARATIONS AND UNDERTAKINGS ──
        el.append(PageBreak())
        el.append(Paragraph(
            "SECTION H — DECLARATIONS AND UNDERTAKINGS",
            styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'The undersigned, being duly authorised to act on behalf of the Applicant '
            'Entity, hereby declares and undertakes as follows:', styles['Body']))
        el.append(Spacer(1, 2 * mm))

        declarations = [
            ('info_true', 'All information provided in this application is true, complete, and accurate '
             'in all material respects as at the date of this application.'),

            ('no_sanctions', 'The Applicant Entity is not, and none of its directors, officers, beneficial '
             'owners, or authorised signatories are, the subject of any sanctions imposed by '
             'the United Nations, the European Union, the United States, the United Kingdom, '
             'or Hong Kong SAR.'),

            ('no_investigation', 'The Applicant Entity is not, and none of its directors, officers, or beneficial '
             'owners are, under investigation or have been convicted of any offence relating to '
             'money laundering, terrorist financing, fraud, tax evasion, or any other financial '
             'crime in any jurisdiction.'),

            ('lawful_funds', 'The funds to be used in connection with carbon credit transactions originate from '
             'lawful sources and do not represent the proceeds of any criminal activity.'),

            ('notify_changes', 'The Applicant Entity shall promptly notify NIHA of any material change to the '
             'information provided in this application, including changes to beneficial ownership, '
             'directorship, authorised signatories, or financial standing.'),

            ('niha_principal', 'The Applicant Entity acknowledges that NIHA operates as a principal counterparty '
             'in carbon credit transactions and is not acting as broker, agent, trustee, or '
             'investment adviser.'),

            ('risk_disclosure', 'The Applicant Entity acknowledges that it has received, read, and understood '
             'the Risk Disclosure Statement provided by NIHA and accepts the risks associated '
             'with carbon credit trading.'),

            ('ongoing_dd', 'The Applicant Entity consents to NIHA conducting ongoing due diligence, including '
             'but not limited to enhanced checks on transactions, counterparties, and beneficial '
             'ownership structures.'),

            ('right_to_decline', 'The Applicant Entity acknowledges that NIHA reserves the right to decline this '
             'application or terminate the business relationship at any time if, in NIHA\'s '
             'sole discretion, the risk profile of the Applicant is deemed unacceptable.'),
        ]
        _accepted_decls = set(fd.get("declarations_accepted") or [])
        for i, (key, decl) in enumerate(declarations, 1):
            icon = '☑' if key in _accepted_decls else '☐'
            el.append(Paragraph(f'{icon} {i}. {decl}', styles['SubClauseItem']))
        el.append(Spacer(1, 5 * mm))

        # ── SECTION I — EXECUTION ──
        el.append(Paragraph("SECTION I — EXECUTION", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'By signing below, the undersigned confirms that they are duly authorised '
            'to sign this application on behalf of the Applicant Entity and that all '
            'information provided herein is true and correct.', styles['Body']))
        el.append(Spacer(1, 3 * mm))

        # Signature block — Applicant side
        el.extend(signature_block(styles, client_entity_name=client_entity_name))
        el.append(Spacer(1, 5 * mm))

        # ── INTERNAL USE ONLY — COMPLIANCE REVIEW ──
        el.append(PageBreak())
        el.append(Paragraph(
            "FOR INTERNAL USE ONLY — COMPLIANCE REVIEW",
            styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            '<i>This section is to be completed by the NIHA Compliance Officer '
            'and is not to be provided to the Applicant.</i>', styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.append(_internal_review_table(styles))
        el.append(Spacer(1, 5 * mm))

        el.append(Paragraph('<b>Notes / Additional Comments:</b>', styles['SubHeading']))
        notes_data = [[Paragraph('<br/><br/><br/><br/><br/>', styles['Body'])]]
        notes_tbl = Table(notes_data, colWidths=[170 * mm], rowHeights=[30 * mm])
        notes_tbl.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, HexColor("#B0B8C8")),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        el.append(notes_tbl)

        # ── LEGEND ──
        el.append(Spacer(1, 8 * mm))
        el.append(gold_separator())
        el.append(Paragraph(
            '<i>Note: Text displayed in </i>'
            f'<font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">this style</font>'
            '<i> indicates information pre-completed by NIHA.</i>',
            styles['Caption']))

        return el

    return build_niha_pdf(
        doc_ref=ref,
        doc_title="Client Onboarding Application",
        content_builder=content,
        confidential=True,
        output_path=output_path,
    )
