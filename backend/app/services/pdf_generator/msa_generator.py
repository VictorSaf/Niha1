"""
MSA PDF Generator — Master Service Agreement for Carbon Credit Facilitation.

Generates a branded PDF with:
  - NIHA data pre-filled (italic blue font)
  - Client data pre-filled where available, blank lines where not
  - Full 23-article MSA + 4 Schedules based on the approved DOCX template
  - NIHA representative signature pre-applied
  - Counterparts clause for wet-ink execution
"""

from datetime import date, datetime
from typing import Optional

from reportlab.platypus import Spacer, PageBreak, Paragraph
from reportlab.lib.units import mm

from .styles import (
    build_niha_pdf,
    create_niha_styles,
    gold_separator,
    thin_separator,
    filled,
    niha_party_block,
    client_party_block,
    signature_block,
    key_terms_table,
    NihaFonts,
    NihaColors,
    NihaDocTemplate,
)
from reportlab.platypus import Table, TableStyle, KeepTogether


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a styled data table (navy header, alternating rows)
# ─────────────────────────────────────────────────────────────────────────────

def _data_table(styles, headers: list[str], rows: list[list[str]], col_widths=None):
    """Generic NIHA-styled data table."""
    header_row = [Paragraph(h, styles['TableHeader']) for h in headers]
    data = [header_row]
    for row in rows:
        data.append([Paragraph(c, styles['TableCell']) for c in row])

    ncols = len(headers)
    if col_widths is None:
        avail = 170  # mm
        col_widths = [avail / ncols * mm] * ncols

    table = Table(data, colWidths=col_widths)
    cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), NihaColors.NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), NihaColors.WHITE),
        ('GRID', (0, 0), (-1, -1), 0.4, NihaColors.BORDER),
        ('LINEBELOW', (0, 0), (-1, 0), 1.2, NihaColors.GOLD),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    for i in range(1, len(data)):
        bg = NihaColors.FILLED_BG if i % 2 == 1 else NihaColors.WHITE
        cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    table.setStyle(TableStyle(cmds))
    return table


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def generate_msa_pdf(
    client_entity_name: Optional[str] = None,
    client_entity_type: Optional[str] = None,
    client_jurisdiction: Optional[str] = None,
    client_representative: Optional[str] = None,
    client_email: Optional[str] = None,
    effective_date: Optional[date] = None,
    doc_ref: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """
    Generate the NIHA Master Service Agreement as a branded PDF.

    Returns:
        PDF content as bytes
    """
    eff_date = effective_date or date.today()
    ref = doc_ref or f"NIHA-MSA-{eff_date.strftime('%Y')}-{eff_date.strftime('%m%d')}"

    def content(styles):
        el = []

        # ── TITLE PAGE ──────────────────────────────────────────────────────
        el.append(Spacer(1, 15 * mm))
        el.append(Paragraph("MASTER SERVICE AGREEMENT", styles['DocTitle']))
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph(
            "for Carbon Credit Facilitation Services",
            styles['DocSubtitle']
        ))
        el.append(gold_separator())

        # Effective date & ref
        date_str = eff_date.strftime("%d %B %Y")
        el.append(Paragraph(f"Effective Date: {filled(date_str)}", styles['Body']))
        el.append(Paragraph(f"Reference: {filled(ref)}", styles['Body']))
        el.append(Paragraph(
            f"Governed by the Laws of {filled('Hong Kong Special Administrative Region')}",
            styles['Body']
        ))
        el.append(Spacer(1, 5 * mm))

        # ── PARTIES ─────────────────────────────────────────────────────────
        el.append(Paragraph("between", styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.extend(niha_party_block(styles, label="Service Provider"))
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph("and", styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.extend(client_party_block(
            styles,
            label="Client",
            entity_name=client_entity_name,
            entity_type=client_entity_type,
            jurisdiction=client_jurisdiction,
            representative=client_representative,
            email=client_email,
        ))
        el.append(Spacer(1, 5 * mm))

        # ── RECITALS ────────────────────────────────────────────────────────
        el.append(Paragraph("RECITALS", styles['SectionHeading']))
        el.append(thin_separator())

        niha = filled("Italy Nihao Group Limited")
        recitals = [
            f'WHEREAS the Service Provider ({niha}) is a company incorporated under the laws '
            f'of Hong Kong SAR, with established expertise in cross-border carbon credit '
            f'facilitation, operating as a facilitator of transactions;',

            'WHEREAS the Service Provider has maintained active participation in carbon credit '
            'markets, facilitating access to cross-border carbon credit markets for its clients '
            'through its proprietary infrastructure;',

            'WHEREAS the Client wishes to engage the Service Provider to facilitate access to '
            'cross-border carbon credit markets, including but not limited to the acquisition, '
            'conversion, custody, delivery, and retirement;',

            'WHEREAS the structural separation between EU and PRC carbon markets, including '
            'mutually exclusive regulatory regimes and the absence of cross-border recognition '
            'mechanisms, necessitates an intermediation structure;',

            'WHEREAS the parties wish to establish a comprehensive framework governing their '
            'commercial relationship on the terms and conditions set out herein;',
        ]
        for r in recitals:
            el.append(Paragraph(r, styles['Body']))

        el.append(Paragraph(
            'NOW, THEREFORE, in consideration of the mutual promises, covenants, and agreements '
            'herein contained, and for other good and valuable consideration, the receipt and '
            'sufficiency of which are hereby acknowledged:',
            styles['BodyBold']
        ))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 1 — DEFINITIONS AND INTERPRETATION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 1 — DEFINITIONS AND INTERPRETATION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>1.1</b> In this Agreement, unless the context otherwise requires:', styles['SubClause']))

        definitions = [
            ('"Applicable Law"', 'means all laws, regulations, rules, orders, directives, circulars, and guidelines applicable in Hong Kong SAR, the European Union, the PRC, and any other relevant jurisdiction, as amended from time to time.'),
            ('"Business Day"', 'means a day on which banks are open for general business in Hong Kong SAR, excluding Saturdays, Sundays, and gazetted public holidays.'),
            ('"Carbon Credits"', 'means any and all carbon emission allowances, certificates, or credits, including: (i) European Union Allowances ("EUA"); (ii) China Emission Allowances ("CEA"); (iii) China Certified Emission Reductions (CCER); and (iv) Voluntary Carbon Credits (VCC).'),
            ('"Confirmation"', 'means the electronic document generated by the Platform evidencing the terms of a Transaction, accessible to the Client through the Platform and delivered by email.'),
            ('"Conversion"', 'means the process by which the Service Provider, acting as principal, acquires Carbon Credits of one type and delivers Carbon Credits of another type to the Client, effecting a cross-border facilitation.'),
            ('"Custody Agreement"', 'means the Carbon Credit Custody Agreement entered into between the parties on or about the date of this Agreement.'),
            ('"Fee Schedule"', 'means the schedule of fees set out in Schedule A, as may be amended from time to time in accordance with Article 5.'),
            ('"NDA"', 'means the Non-Disclosure and Non-Circumvention Agreement entered into between the parties on or about the date of this Agreement.'),
            ('"Platform"', f'means the NIHA Carbon Platform accessible at {filled("https://nihacarbon.com")} or such successor URL as the Service Provider may notify to the Client.'),
            ('"Protected Relationship"', 'has the meaning given to it in the NDA and, for the purposes of this Agreement, includes any client, counterparty, supplier, introducer, registry, exchange, bank, or other business contact.'),
            ('"Registry"', 'means any registry or platform used for the issuance, holding, transfer, retirement, or cancellation of Carbon Credits, including those listed in Schedule C.'),
            ('"Segregated Account"', 'means the client money account described in Article 7.'),
            ('"Services"', 'means the services described in Article 2.'),
            ('"Transaction"', 'means any acquisition, sale, conversion (swap), delivery, or retirement of Carbon Credits pursuant to this Agreement.'),
        ]
        for term, defn in definitions:
            el.append(Paragraph(f'<b>{term}</b> {defn}', styles['SubClauseItem']))

        interp = [
            ('<b>1.2</b>', 'References to "parties" means the Service Provider and the Client, and "party" means either of them.'),
            ('<b>1.3</b>', 'Headings are for convenience only and shall not affect interpretation.'),
            ('<b>1.4</b>', 'References to legislation include amendments, re-enactments, and subsidiary legislation.'),
            ('<b>1.5</b>', 'This Agreement shall be read in conjunction with the NDA and the Custody Agreement. In the event of conflict between this Agreement and the NDA regarding matters other than confidentiality and non-circumvention, the MSA shall prevail. Regarding confidentiality and non-circumvention, the NDA shall take precedence.'),
        ]
        for num, text in interp:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 2 — SCOPE OF SERVICES
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 2 — SCOPE OF SERVICES", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph('<b>2.1</b> The Service Provider shall provide the following services to the Client:', styles['SubClause']))

        services = [
            ('(a)', '<b>Carbon Credit Acquisition:</b> facilitating the sourcing and acquisition of Carbon Credits from PRC pilot ETS markets, voluntary carbon markets, and other approved markets;'),
            ('(b)', '<b>Cross-Border Conversion (Swap):</b> facilitating the conversion of Carbon Credits from one type to another (e.g., CEA to EUA or EUA to CEA) through the Service Provider\'s principal counterparty mechanism;'),
            ('(c)', '<b>Custody:</b> holding and safeguarding Carbon Credits in accordance with the Custody Agreement;'),
            ('(d)', '<b>Delivery:</b> transferring Carbon Credits to Registry accounts designated by the Client;'),
            ('(e)', '<b>Retirement:</b> retiring Carbon Credits on the Client\'s behalf for compliance or voluntary purposes;'),
            ('(f)', '<b>Market Intelligence:</b> providing periodic market reports on carbon credit pricing, trends, and regulatory developments;'),
            ('(g)', '<b>Platform Access:</b> granting the Client access to the Platform for transaction management, reporting, and communication.'),
        ]
        for lbl, text in services:
            el.append(Paragraph(f'{lbl} {text}', styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>2.2</b> The Service Provider may introduce additional services from time to time, '
            'which shall be offered to the Client by written notice. Such additional services shall '
            'be subject to the terms of this Agreement or such other terms as the parties may agree '
            'in writing.', styles['SubClause']))
        el.append(Paragraph(
            '<b>2.3</b> The Service Provider does not provide investment advice, tax advice, or '
            'legal advice. The Client is responsible for obtaining its own independent professional '
            'advice in relation to Transactions.', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 3 — ROLE OF THE SERVICE PROVIDER
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 3 — ROLE OF THE SERVICE PROVIDER", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>3.1</b> The Client acknowledges and agrees that the Service Provider acts as a '
            'facilitator of cross-border carbon credit transactions. Due to the structural '
            'separation between EU and PRC carbon markets, the Service Provider necessarily '
            'operates as a principal counterparty to the Client.', styles['SubClause']))

        el.append(Paragraph('<b>3.2</b> Under this structure, the Service Provider:', styles['SubClause']))
        for item in [
            '(a) acquires Carbon Credits in its own name and for its own account as a necessary step to facilitate cross-border value exchanges for the Client;',
            '(b) bears market risk, regulatory risk, and operational risk during the intermediation period between acquisition and delivery;',
            '(c) earns compensation through fees as set out in the Fee Schedule (Schedule A) and, where applicable, through the spread between its acquisition cost and the facilitation price offered to the Client;',
            '(d) has no obligation to disclose its acquisition cost or its upstream counterparties to the Client.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph('<b>3.3</b> For the avoidance of doubt, the Service Provider is NOT acting as:', styles['SubClause']))
        for item in [
            '(a) a trustee or fiduciary (except as expressly provided in the Custody Agreement);',
            '(b) an investment adviser or financial adviser;',
            '(c) an exchange or marketplace operator.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>3.4</b> The Service Provider\'s facilitation price to the Client shall reflect: '
            '(i) the prevailing market price of the relevant Carbon Credits; '
            '(ii) the cross-border facilitation cost; '
            '(iii) the Service Provider\'s compensation spread; and '
            '(iv) all applicable fees as set out in Schedule A.', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 4 — TRANSACTION EXECUTION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 4 — TRANSACTION EXECUTION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>4.1</b> The Client may request a Transaction by submitting an instruction through '
            'the Platform or by authenticated written means. Each instruction shall specify:',
            styles['SubClause']))
        for item in [
            '(a) the type and volume of Carbon Credits (in whole units);',
            '(b) whether the Transaction is an acquisition, conversion (swap), delivery, retirement, or sale;',
            '(c) any preferred settlement date or special conditions.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        a4_clauses = [
            ('<b>4.2</b>', f'The Service Provider shall use commercially reasonable efforts to execute the Transaction and shall provide the Client with a Confirmation within {filled("two (2) Business Days")} of execution.'),
            ('<b>4.3</b>', f'A Transaction is binding upon both parties from the moment the Confirmation is issued. The Client has {filled("twenty-four (24) hours")} to notify the Service Provider of any discrepancy in the Confirmation; failure to notify shall constitute acceptance of the Confirmation terms.'),
        ]
        for num, text in a4_clauses:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        el.append(Paragraph('<b>4.4</b> The Service Provider may decline to execute a Transaction if:', styles['SubClause']))
        for item in [
            '(a) the Client has insufficient funds on deposit;',
            '(b) execution would cause the Service Provider to breach Applicable Law;',
            '(c) market conditions render execution impracticable or would result in pricing materially adverse to the Client;',
            '(d) the requested Carbon Credits are not available in the relevant market within a reasonable timeframe.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>4.5</b> The Service Provider shall notify the Client promptly of any refusal, '
            'with reasons, and shall propose alternative arrangements where possible.',
            styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 5 — PRICING AND FEES
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 5 — PRICING AND FEES", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>5.1</b> The Client shall pay the Service Provider fees in accordance with the '
            'Fee Schedule (Schedule A). Fees are payable in the currency specified in the relevant '
            'Confirmation or the Fee Schedule.', styles['SubClause']))

        el.append(Paragraph('<b>5.2</b> All prices quoted by the Service Provider include the Service Provider\'s facilitation spread. Benchmark references are:', styles['SubClause']))
        for item in [
            f'(a) EUA: {filled("ICE Endex EUA Futures (front month)")} or equivalent publicly available benchmark;',
            f'(b) CEA/SZA: {filled("Official closing price published by the relevant PRC pilot ETS exchange")};',
            f'(c) VCC: {filled("Published price on Core Climate")} or equivalent marketplace.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        a5_rest = [
            ('<b>5.3</b>', f'The Service Provider may revise the Fee Schedule by giving {filled("sixty (60) days")} written notice. Any single revision shall not increase any fee rate by more than {filled("twenty-five percent (25%)")} relative to the then-current rate.'),
            ('<b>5.4</b>', '<b>Swap (Conversion) Fee Methodology:</b> For CEA-to-EUA conversions, the platform fee is calculated and deducted in CEA units before execution against the order book. The fee amount in CEA is computed by the formula: ' + filled("(CEA Volume) x (Fee Rate)") + ', rounded up to the nearest whole unit.'),
            ('<b>5.5</b>', 'All fees are exclusive of value-added tax, goods and services tax, or equivalent taxes, which shall be charged at the applicable rate and borne by the Client.'),
            ('<b>5.6</b>', 'The Service Provider may deduct fees from the Client\'s funds in the Segregated Account or from the Client\'s Carbon Credit holdings (as applicable), provided that: (i) the fee has accrued; and (ii) the Service Provider has given the Client written notice.'),
        ]
        for num, text in a5_rest:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 6 — SETTLEMENT AND DELIVERY
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 6 — SETTLEMENT AND DELIVERY", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>6.1</b> Settlement shall be on a delivery-versus-payment ("DVP") basis unless '
            'otherwise agreed in the Confirmation.', styles['SubClause']))

        el.append(Paragraph(
            '<b>6.2</b> Standard settlement windows are as follows (all timelines expressed in '
            'Business Days from trade date "T"):', styles['SubClause']))

        # Settlement table
        settle_table = _data_table(styles,
            headers=["Transaction Type", "Settlement Window"],
            rows=[
                ["CEA Cash Purchase", filled("T+3 (standard); T+5 (complex)")],
                ["Swap — CEA leg", filled("T+2")],
                ["Swap — EUA leg", filled("T+3")],
                ["EUA Cash Purchase", filled("T+2")],
                ["VCC Retirement/Delivery", filled("T+5")],
            ],
            col_widths=[85 * mm, 85 * mm],
        )
        el.append(settle_table)
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph(
            f'<b>6.3</b> If the Service Provider is unable to settle by the settlement date due to '
            f'causes beyond its reasonable control (including Registry delays, regulatory actions, or '
            f'counterparty defaults), the Service Provider may extend settlement by up to '
            f'{filled("thirty (30) additional Business Days")} with notice to the Client.',
            styles['SubClause']))
        el.append(Paragraph(
            '<b>6.4</b> If settlement cannot be effected within the extended period, the Client may '
            'elect to: (i) continue to wait; (ii) cancel the Transaction and receive a full refund '
            'of funds paid; or (iii) accept alternative arrangements proposed by the Service Provider.',
            styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 7 — CLIENT FUNDS
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 7 — CLIENT FUNDS", styles['ClauseNumber']))
        el.append(thin_separator())

        a7 = [
            ('<b>7.1</b>', 'The Client shall deposit funds with the Service Provider in advance of Transactions, by wire transfer to the Designated Bank Account set out in Schedule D.'),
            ('<b>7.2</b>', f'Client funds shall be held in a segregated bank account (the "Segregated Account") at a {filled("licensed Hong Kong bank")}, separate from the Service Provider\'s operational accounts.'),
            ('<b>7.3</b>', 'The Service Provider shall not use Client funds for any purpose other than: (i) executing Transactions on behalf of the Client; (ii) deducting accrued fees; and (iii) returning funds to the Client upon request.'),
            ('<b>7.4</b>', 'Interest accrued on the Segregated Account shall be for the Client\'s benefit, net of withholding tax and bank charges.'),
            ('<b>7.5</b>', f'The Client may request return of unencumbered funds at any time by written request. The Service Provider shall effect return within {filled("five (5) Business Days")} of receipt of such request.'),
        ]
        for num, text in a7:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 8 — CARBON CREDIT CUSTODY
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 8 — CARBON CREDIT CUSTODY", styles['ClauseNumber']))
        el.append(thin_separator())

        a8 = [
            ('<b>8.1</b>', 'Carbon Credits acquired pursuant to this Agreement shall be held in custody in accordance with the Custody Agreement.'),
            ('<b>8.2</b>', 'The Service Provider holds legal title to Carbon Credits in custody; the Client holds beneficial ownership as recorded in the Client Ledger maintained by the Service Provider.'),
            ('<b>8.3</b>', 'The terms of the Custody Agreement are incorporated by reference into this Agreement to the extent relevant.'),
        ]
        for num, text in a8:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 9 — REPORTING AND TRANSPARENCY
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 9 — REPORTING AND TRANSPARENCY", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph('<b>9.1</b> The Service Provider shall provide the Client with:', styles['SubClause']))
        for item in [
            f'(a) Transaction Confirmations within {filled("two (2) Business Days")} of each Transaction;',
            f'(b) monthly custody and cash statements within {filled("ten (10) Business Days")} of month-end;',
            '(c) quarterly market intelligence reports;',
            '(d) annual audit confirmation of custody holdings and segregated funds.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>9.2</b> The Client shall have access to real-time portfolio information through the '
            'Platform, including current Carbon Credit holdings, EUR balance, and transaction history.',
            styles['SubClause']))
        el.append(Paragraph(
            '<b>9.3</b> Benchmark pricing references shall be published on the Platform daily, based '
            'on ICE EUA spot and relevant PRC pilot ETS exchange prices.', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 10 — REPRESENTATIONS AND WARRANTIES
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 10 — REPRESENTATIONS AND WARRANTIES", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>10.1</b> Each party represents and warrants to the other, as of the Effective Date '
            'and on each trade date, that:', styles['SubClause']))
        for item in [
            '(a) it is duly organised and validly existing under the laws of its jurisdiction;',
            '(b) it has full corporate power and authority to execute and perform this Agreement;',
            '(c) this Agreement constitutes a legal, valid, and binding obligation;',
            '(d) no consent, approval, or authorisation of any governmental authority is required that has not been obtained;',
            '(e) it is not insolvent, bankrupt, or subject to winding-up proceedings.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph('<b>10.2</b> The Service Provider additionally represents that:', styles['SubClause']))
        for item in [
            '(a) it maintains adequate operational, technical, and compliance infrastructure to perform the Services;',
            '(b) it implements AML/KYC procedures aligned with applicable anti-money laundering and counter-terrorist financing legislation in Hong Kong;',
            '(c) it has access to the Registries and markets listed in Schedule C;',
            '(d) should any new regulatory requirement be introduced that materially affects the Services, the Service Provider shall promptly notify the Client and take all reasonable steps to comply or to propose alternative arrangements.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph('<b>10.3</b> The Client represents that:', styles['SubClause']))
        for item in [
            '(a) it is acting for its own account and has made its own independent decision to enter into Transactions;',
            '(b) it has sufficient knowledge and experience to evaluate the risks of carbon credit trading;',
            '(c) it is not relying on the Service Provider for investment advice or recommendations.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 11 — RISK ACKNOWLEDGEMENT
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 11 — RISK ACKNOWLEDGEMENT", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>11.1</b> The Client acknowledges the risks set out in the Custody Agreement and '
            'additionally acknowledges:', styles['SubClause']))
        risks = [
            ('(a)', '<b>Market Risk:</b> Carbon credit prices may fluctuate significantly and without warning;'),
            ('(b)', '<b>Conversion Risk:</b> The CEA/EUA conversion ratio is not fixed and depends on prevailing market conditions at the time of the swap;'),
            ('(c)', '<b>Regulatory Risk:</b> Changes in EU ETS, PRC ETS, or Hong Kong regulation may materially affect Carbon Credit values, availability, or transferability;'),
            ('(d)', '<b>Liquidity Risk:</b> PRC pilot markets may have limited liquidity, affecting execution timing and pricing;'),
            ('(e)', '<b>Cross-Border Risk:</b> Currency fluctuation, legal divergence, and political risks inherent in EU-China transactions;'),
            ('(f)', '<b>Technology Risk:</b> Platform, Registry, or communication system failures may delay Transactions.'),
        ]
        for lbl, text in risks:
            el.append(Paragraph(f'{lbl} {text}', styles['SubClauseItem']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 12 — INDEMNIFICATION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 12 — INDEMNIFICATION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>12.1</b> The Client shall indemnify and hold harmless the Service Provider against '
            'all losses, damages, costs, and expenses (including reasonable legal fees) arising from:',
            styles['SubClause']))
        for item in [
            '(a) any breach of the Client\'s representations, warranties, or obligations under this Agreement;',
            '(b) any instruction given by the Client that is subsequently found to be unauthorised, erroneous, or fraudulent;',
            '(c) any tax liability arising from the Client\'s Transactions.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>12.2</b> The Service Provider shall indemnify and hold harmless the Client against '
            'all losses arising from:', styles['SubClause']))
        for item in [
            '(a) breach of the Service Provider\'s representations, warranties, or obligations;',
            '(b) gross negligence or wilful misconduct of the Service Provider;',
            '(c) failure to properly segregate Client funds or maintain accurate custody records.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 13 — LIMITATION OF LIABILITY
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 13 — LIMITATION OF LIABILITY", styles['ClauseNumber']))
        el.append(thin_separator())

        a13 = [
            ('<b>13.1</b>', f'The Service Provider\'s aggregate liability under or in connection with this Agreement shall not exceed the total fees paid by the Client to the Service Provider in the {filled("twelve (12) months")} preceding the event giving rise to liability.'),
            ('<b>13.2</b>', 'Neither party shall be liable to the other for any indirect, consequential, special, or punitive damages, including loss of profits, loss of opportunity, or loss of anticipated savings, except where such liability arises from: (a) fraud or wilful misconduct; (b) breach of confidentiality obligations under Article 14 or the NDA; (c) breach of non-circumvention obligations under Article 18 or the NDA.'),
            ('<b>13.3</b>', 'Nothing in this Agreement shall exclude or limit either party\'s liability for fraud, wilful default, death or personal injury caused by negligence, or any liability that cannot be excluded or limited under Applicable Law.'),
        ]
        for num, text in a13:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 14 — CONFIDENTIALITY
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 14 — CONFIDENTIALITY", styles['ClauseNumber']))
        el.append(thin_separator())

        a14 = [
            ('<b>14.1</b>', 'Each party shall keep confidential all Confidential Information (as defined in the NDA) received from the other in connection with this Agreement, including but not limited to: transaction details, pricing, market information, counterparty identities, and regulatory interactions.'),
            ('<b>14.2</b>', 'The confidentiality obligations under this Article 14 are supplementary to and shall be read in conjunction with the NDA. In the event of any conflict or inconsistency between the confidentiality obligations under this Article and those in the NDA, the NDA shall prevail.'),
            ('<b>14.3</b>', 'Exceptions to confidentiality: information that is publicly available through no fault of the Receiving Party, independently developed, lawfully received from a third party without restriction, or required to be disclosed by law or court order (provided notice is given where permitted).'),
            ('<b>14.4</b>', f'This confidentiality obligation survives termination for a period of {filled("five (5) years")}.'),
        ]
        for num, text in a14:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 15 — DATA PROTECTION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 15 — DATA PROTECTION", styles['ClauseNumber']))
        el.append(thin_separator())

        a15 = [
            ('<b>15.1</b>', 'Each party shall comply with all applicable data protection laws in relation to personal data processed under this Agreement, including applicable Hong Kong data privacy legislation and, where applicable, the General Data Protection Regulation (GDPR) and PRC data protection requirements.'),
            ('<b>15.2</b>', 'Personal data shall be processed only for the purposes of performing this Agreement and complying with Applicable Law. Each party shall be an independent data controller in respect of personal data it collects and processes.'),
        ]
        for num, text in a15:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 16 — AML AND COMPLIANCE
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 16 — ANTI-MONEY LAUNDERING AND COMPLIANCE", styles['ClauseNumber']))
        el.append(thin_separator())

        a16_top = [
            ('<b>16.1</b>', 'The Client shall provide all information and documentation reasonably requested by the Service Provider for AML/KYC purposes in a timely manner.'),
            ('<b>16.2</b>', f'The Service Provider may suspend Services or refuse to execute a Transaction if the Client fails to provide requested AML/KYC information within {filled("ten (10) Business Days")}.'),
            ('<b>16.3</b>', 'The Service Provider reserves the right to file suspicious transaction reports with the Joint Financial Intelligence Unit (JFIU) without notifying the Client, as required by law.'),
        ]
        for num, text in a16_top:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        el.append(Paragraph('<b>16.4</b> The Client represents that:', styles['SubClause']))
        for item in [
            '(a) it is not a sanctioned person or entity under the sanctions programmes of the United Nations, European Union, United States, United Kingdom, or Hong Kong;',
            '(b) funds deposited with the Service Provider are derived from lawful sources;',
            '(c) it will not use the Services for money laundering, terrorist financing, sanctions evasion, or any unlawful purpose.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 17 — ANTI-BRIBERY AND ANTI-CORRUPTION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 17 — ANTI-BRIBERY AND ANTI-CORRUPTION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>17.1</b> Each party represents that it has not, and undertakes that it shall not, '
            'in connection with this Agreement:', styles['SubClause']))
        for item in [
            '(a) offer, promise, give, or authorise the giving of any bribe, kickback, or other corrupt payment to any person, including any government official, public officer, or political party;',
            '(b) request, agree to receive, or accept any bribe, kickback, or other corrupt payment;',
            '(c) take any action that would cause either party to violate applicable anti-bribery and anti-corruption legislation in Hong Kong, the European Union, or any other relevant jurisdiction.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>17.2</b> Each party shall maintain adequate procedures designed to prevent bribery '
            'and corruption by its officers, employees, agents, and any persons performing services '
            'on its behalf.', styles['SubClause']))
        el.append(Paragraph(
            '<b>17.3</b> Each party shall promptly notify the other if it becomes aware of any '
            'breach or suspected breach of this Article 17. A breach of this Article shall constitute '
            'a material breach entitling the non-breaching party to terminate this Agreement immediately.',
            styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 18 — NON-CIRCUMVENTION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 18 — NON-CIRCUMVENTION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>18.1</b> The non-circumvention and non-solicitation obligations set out in the NDA '
            'are hereby incorporated by reference and shall apply mutatis mutandis to the parties\' '
            'relationship under this Agreement.', styles['SubClause']))

        el.append(Paragraph(
            f'<b>18.2</b> Without prejudice to the generality of the NDA provisions, the Client '
            f'undertakes that during the term of this Agreement and for a period of '
            f'{filled("two (2) years")} following its termination or expiry, it shall not:',
            styles['SubClause']))
        for item in [
            '(a) directly or indirectly contact, deal with, or transact with any Protected Relationship of the Service Provider for the purpose of conducting carbon credit business that would circumvent the Service Provider\'s involvement;',
            '(b) use information obtained through the Platform or the performance of this Agreement to identify, approach, or solicit counterparties, registries, or market participants known to the Service Provider;',
            '(c) establish or assist in the establishment of any competing cross-border carbon credit facilitation service that exploits Protected Relationships.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>18.3</b> This Article 18 shall not restrict the Client from conducting business with '
            'any person or entity with whom the Client had a pre-existing relationship prior to the '
            'date of this Agreement, evidenced by written documentation.', styles['SubClause']))
        el.append(Paragraph(
            '<b>18.4</b> In the event of a breach of this Article 18, the Service Provider shall be '
            'entitled to injunctive relief and to recover from the Client any profits derived from '
            'the circumventing activity, in addition to other remedies available at law.',
            styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 19 — FORCE MAJEURE
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 19 — FORCE MAJEURE", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            '<b>19.1</b> Neither party shall be liable for failure to perform due to events beyond '
            'its reasonable control ("Force Majeure"), including:', styles['SubClause']))
        for item in [
            '(a) natural disasters, pandemics, wars, civil unrest, or government actions;',
            '(b) changes in Applicable Law or regulatory requirements that render performance unlawful or impracticable;',
            '(c) Registry outages, cyber attacks, or critical infrastructure failures;',
            '(d) sanctions or trade restrictions imposed by any government;',
            '(e) suspension of trading on any relevant exchange or market.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            f'<b>19.2</b> The affected party shall give notice within {filled("five (5) Business Days")} '
            f'and use reasonable efforts to mitigate the impact.', styles['SubClause']))
        el.append(Paragraph(
            f'<b>19.3</b> If the Force Majeure event continues for more than {filled("sixty (60) days")}, '
            f'either party may terminate this Agreement on {filled("thirty (30) days")} written notice.',
            styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 20 — TERM AND TERMINATION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 20 — TERM AND TERMINATION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            f'<b>20.1</b> This Agreement commences on the date of execution by both parties (the '
            f'"Effective Date") and continues for an initial term of {filled("twelve (12) months")}, '
            f'automatically renewing for successive twelve-month periods unless terminated in '
            f'accordance with this Article.', styles['SubClause']))
        el.append(Paragraph(
            f'<b>20.2</b> Either party may terminate by giving {filled("ninety (90) days")} written '
            f'notice before the end of the then-current term.', styles['SubClause']))

        el.append(Paragraph(
            '<b>20.3</b> Either party may terminate immediately by written notice if:', styles['SubClause']))
        for item in [
            f'(a) the other party commits a material breach that is not remedied within {filled("thirty (30) days")} of written notice specifying the breach;',
            '(b) the other party becomes insolvent, enters liquidation, or is subject to analogous proceedings;',
            '(c) a change in Applicable Law makes performance of this Agreement unlawful;',
            '(d) the other party commits a breach of Article 17 (Anti-Bribery).',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 21 — CONSEQUENCES OF TERMINATION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 21 — CONSEQUENCES OF TERMINATION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph('<b>21.1</b> Upon termination, the Service Provider shall:', styles['SubClause']))
        for item in [
            '(a) cease executing new Transactions;',
            f'(b) complete all pending Transactions within {filled("twenty (20) Business Days")} (or such longer period as may be reasonably necessary);',
            f'(c) transfer all Carbon Credits held in custody to Client-designated Registry accounts within {filled("twenty (20) Business Days")};',
            f'(d) return all Client funds (net of accrued fees and charges) within {filled("ten (10) Business Days")};',
            f'(e) deliver a final statement of account within {filled("twenty (20) Business Days")}.',
        ]:
            el.append(Paragraph(item, styles['SubClauseItem']))

        el.append(Paragraph(
            '<b>21.2</b> Termination does not affect accrued rights or obligations, nor obligations '
            'that by their nature survive termination, including: confidentiality (Article 14 and NDA), '
            'non-circumvention (Article 18 and NDA), indemnification obligations, and representations '
            'and warranties made on trade dates.', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 22 — GOVERNING LAW AND DISPUTE RESOLUTION
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 22 — GOVERNING LAW AND DISPUTE RESOLUTION", styles['ClauseNumber']))
        el.append(thin_separator())

        el.append(Paragraph(
            f'<b>22.1</b> This Agreement is governed by and shall be construed in accordance with '
            f'the laws of {filled("Hong Kong Special Administrative Region")}.', styles['SubClause']))
        el.append(Paragraph(
            f'<b>22.2</b> <b>Negotiation:</b> In the event of any dispute, the parties shall first '
            f'attempt to resolve through good faith negotiations between senior representatives within '
            f'{filled("thirty (30) days")} of written notice of the dispute.', styles['SubClause']))
        el.append(Paragraph(
            f'<b>22.3</b> <b>Mediation:</b> If not resolved through negotiation, either party may '
            f'refer the dispute to mediation administered by the {filled("Hong Kong Mediation Centre")}.',
            styles['SubClause']))
        el.append(Paragraph(
            f'<b>22.4</b> <b>Arbitration:</b> If not resolved through mediation within '
            f'{filled("sixty (60) days")}, either party may refer the dispute to final and binding '
            f'arbitration under the {filled("HKIAC Administered Arbitration Rules")}.', styles['SubClause']))
        el.append(Paragraph(
            '<b>22.5</b> Notwithstanding the above, either party may seek injunctive or other equitable '
            'relief from the courts of Hong Kong to protect its rights pending the outcome of any dispute '
            'resolution procedure under this Article 22.', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # ARTICLE 23 — GENERAL PROVISIONS
        # ════════════════════════════════════════════════════════════════════
        el.append(Paragraph("ARTICLE 23 — GENERAL PROVISIONS", styles['ClauseNumber']))
        el.append(thin_separator())

        a23 = [
            ('<b>23.1</b>', '<b>Entire Agreement:</b> This Agreement (together with the NDA, the Custody Agreement, and all Schedules) constitutes the entire agreement between the parties regarding the subject matter hereof and supersedes all prior negotiations, understandings, and agreements.'),
            ('<b>23.2</b>', '<b>Amendments:</b> No amendment to this Agreement shall be effective unless made in writing and signed by an authorised representative of each party.'),
            ('<b>23.3</b>', '<b>Waiver:</b> No failure or delay by either party in exercising any right shall constitute a waiver of that right, nor shall any single or partial exercise preclude further exercise.'),
            ('<b>23.4</b>', '<b>Severability:</b> If any provision is held invalid or unenforceable, the remaining provisions shall continue in full force and effect. The parties shall negotiate in good faith to replace the invalid provision with a valid one that achieves the original intent.'),
            ('<b>23.5</b>', f'<b>Assignment:</b> No assignment without prior written consent. The Service Provider may assign to a wholly-owned subsidiary upon {filled("thirty (30) days")} written notice, provided the assignee assumes all obligations.'),
            ('<b>23.6</b>', '<b>Third Party Rights:</b> Nothing in this Agreement confers rights on any third party under applicable third party rights legislation.'),
            ('<b>23.7</b>', '<b>Notices:</b> All notices shall be in writing and delivered to the addresses set out in Schedule D, or as subsequently notified. Notices by email shall be valid only if followed by a hard copy sent by registered mail or internationally recognised courier.'),
            ('<b>23.8</b>', '<b>Counterparts:</b> This Agreement may be executed in counterparts, each of which shall constitute an original and all of which together shall constitute one and the same agreement.'),
            ('<b>23.9</b>', '<b>No Partnership or Agency:</b> Nothing in this Agreement shall be construed as creating a partnership, joint venture, or employment relationship between the parties.'),
            ('<b>23.10</b>', '<b>Order of Precedence:</b> In the event of conflict between the main body of this Agreement and any Schedule, the main body shall prevail. In the event of conflict between this Agreement and the NDA or Custody Agreement, the order of precedence is: (i) NDA (for confidentiality and non-circumvention matters); (ii) this Agreement (for services and facilitation); (iii) Custody Agreement (for custody-specific matters).'),
        ]
        for num, text in a23:
            el.append(Paragraph(f'{num} {text}', styles['SubClause']))

        # ════════════════════════════════════════════════════════════════════
        # SCHEDULES
        # ════════════════════════════════════════════════════════════════════
        el.append(PageBreak())
        el.append(Paragraph("SCHEDULE A — FEE SCHEDULE", styles['SectionHeading']))
        el.append(gold_separator())
        el.append(Paragraph(
            'The following fee rates apply to Services provided under this Agreement. '
            'All fee rates are subject to revision in accordance with Article 5.3.',
            styles['Body']))
        el.append(Spacer(1, 3 * mm))

        fee_table = _data_table(styles,
            headers=["Service", "Fee Rate", "Currency / Basis"],
            rows=[
                [f"CEA Cash Purchase Commission", filled("1.5%"), "of transaction value (EUR)"],
                [f"Swap (Conversion) Fee", filled("2.0%"), "of source CC volume (e.g. CEA), rounded up"],
                ["Custody Fee", "As per Custody Agreement", "See Custody Agreement"],
                ["Platform Access", filled("Included"), "No separate charge"],
                ["Market Intelligence Reports", filled("Included"), "Quarterly"],
            ],
            col_widths=[60 * mm, 50 * mm, 60 * mm],
        )
        el.append(fee_table)
        el.append(Spacer(1, 4 * mm))

        el.append(Paragraph('<b>Notes:</b>', styles['Body']))
        el.append(Paragraph(
            f'1. <b>Swap Fee Methodology:</b> The swap fee is calculated in the source Carbon Credit '
            f'currency (e.g., CEA for a CEA-to-EUA swap). The fee amount is: {filled("Volume x Fee Rate")}, '
            f'rounded up to the nearest whole unit.', styles['SubClause']))
        el.append(Paragraph(
            f'2. <b>Benchmark References:</b> EUA — {filled("ICE Endex EUA Futures (front month)")}; '
            f'CEA/SZA — {filled("Official closing price of the relevant PRC pilot ETS exchange")}; '
            f'VCC — {filled("Core Climate or equivalent marketplace")}.', styles['SubClause']))
        el.append(Paragraph(
            f'3. <b>Fee Cap:</b> Any single fee revision under Article 5.3 shall not increase any rate by more than {filled("25%")} relative to the then-current rate.',
            styles['SubClause']))

        # ── SCHEDULE B ──
        el.append(PageBreak())
        el.append(Paragraph("SCHEDULE B — SERVICE LEVEL STANDARDS", styles['SectionHeading']))
        el.append(gold_separator())

        sla_table = _data_table(styles,
            headers=["Transaction Type", "Settlement Timeline", "Remedy for Breach"],
            rows=[
                ["CEA Cash Purchase", filled("T+3 (standard); T+5 (complex)"), "Extension up to T+30 with notice"],
                ["Swap — CEA leg", filled("T+2"), "Extension up to T+30 with notice"],
                ["Swap — EUA leg", filled("T+3"), "Extension up to T+30 with notice"],
                ["EUA Cash Purchase", filled("T+2"), "Extension up to T+30 with notice"],
                ["VCC Retirement/Delivery", filled("T+5"), "Extension up to T+30 with notice"],
                ["Confirmation Delivery", filled("T+2"), "Service Provider notification"],
                ["Monthly Statements", filled("M+10 Business Days"), "Service Provider notification"],
                ["Fund Return", filled("5 Business Days"), "Client may escalate per Art. 22"],
            ],
            col_widths=[55 * mm, 55 * mm, 60 * mm],
        )
        el.append(sla_table)

        # ── SCHEDULE C ──
        el.append(PageBreak())
        el.append(Paragraph("SCHEDULE C — APPROVED REGISTRIES AND MARKETS", styles['SectionHeading']))
        el.append(gold_separator())
        el.append(Paragraph(
            'This list may be updated by the Service Provider from time to time with prior written '
            'notice to the Client. Addition of new registries or markets shall not constitute an '
            'amendment to this Agreement.', styles['Body']))
        el.append(Spacer(1, 3 * mm))

        reg_table = _data_table(styles,
            headers=["Registry / Market", "Region", "Credit Types"],
            rows=[
                [filled("EU Transaction Log (EUTL)"), "European Union", "EUA"],
                [filled("CEEX Shenzhen"), "PRC (Guangdong)", "CEA / SZA"],
                [filled("CEEX Shanghai"), "PRC (Shanghai)", "CEA / SHEA"],
                [filled("Shanghai Environment & Energy Exchange"), "PRC (National)", "CEA / CCER"],
                [filled("Verra Registry"), "Global", "VCS / VCC"],
                [filled("Gold Standard Registry"), "Global", "GS VER"],
            ],
            col_widths=[65 * mm, 45 * mm, 60 * mm],
        )
        el.append(reg_table)

        # ── SCHEDULE D ──
        el.append(PageBreak())
        el.append(Paragraph("SCHEDULE D — DESIGNATED BANK ACCOUNTS AND NOTICES", styles['SectionHeading']))
        el.append(gold_separator())

        el.append(Paragraph("<b>1. SERVICE PROVIDER DESIGNATED BANK ACCOUNT (SEGREGATED CLIENT ACCOUNT)</b>", styles['SubHeading']))
        bank_table = _data_table(styles,
            headers=["Field", "Detail"],
            rows=[
                ["Account Name", filled("Italy Nihao Group Limited — Client Segregated Account")],
                ["Bank Name", "[Licensed Hong Kong Bank — to be completed upon onboarding]"],
                ["Account Number", "[To be completed upon onboarding]"],
                ["SWIFT/BIC", "[To be completed upon onboarding]"],
                ["Beneficiary", filled("Italy Nihao Group Limited")],
                ["Reference", "[Client ID to be provided upon engagement]"],
            ],
            col_widths=[55 * mm, 115 * mm],
        )
        el.append(bank_table)
        el.append(Spacer(1, 5 * mm))

        el.append(Paragraph("<b>2. ADDRESSES FOR NOTICES</b>", styles['SubHeading']))

        client_name_display = client_entity_name or "[Client Full Legal Name]"
        client_rep_display = client_representative or "[Designated Contact Person]"
        client_email_display = client_email or "[Email to be provided by Client]"

        notice_table = _data_table(styles,
            headers=["", "Service Provider", "Client"],
            rows=[
                ["Entity Name:", filled("Italy Nihao Group Limited"), filled(client_name_display) if client_entity_name else client_name_display],
                ["Attention:", filled("Legal Department"), filled(client_rep_display) if client_representative else client_rep_display],
                ["Address:", filled("Suite 1201, 12/F, Two Harbourfront, 22 Tak Fung Street, Hung Hom, Kowloon, Hong Kong SAR"), "[Address to be provided by Client]"],
                ["Email:", filled("legal@niha.com"), filled(client_email_display) if client_email else client_email_display],
            ],
            col_widths=[30 * mm, 70 * mm, 70 * mm],
        )
        el.append(notice_table)
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(
            '<b>Note:</b> Notices by email are valid only if followed by a hard copy sent by '
            'registered mail or internationally recognised courier within five (5) Business Days, '
            'as specified in Article 23.7.', styles['Body']))

        # ── KEY TERMS SUMMARY TABLE ─────────────────────────────────────────
        el.append(Spacer(1, 5 * mm))
        el.append(Paragraph("KEY TERMS SUMMARY", styles['SectionHeading']))
        el.append(thin_separator())

        terms = [
            ("Initial Term", "12 months (auto-renewal)", "Pre-set by NIHA"),
            ("Termination Notice", "90 days written notice", "Pre-set by NIHA"),
            ("CEA Commission", "1.5% of transaction value", "Pre-set by NIHA"),
            ("Swap Fee", "2.0% of source CC volume", "Pre-set by NIHA"),
            ("CEA Cash Settlement", "T+3 (standard)", "Pre-set by NIHA"),
            ("Swap Settlement", "CEA T+2, EUA T+3", "Pre-set by NIHA"),
            ("Liability Cap", "12 months fees", "Pre-set by NIHA"),
            ("Confidentiality Survival", "5 years post-termination", "Pre-set by NIHA"),
            ("Non-Circumvention", "2 years post-termination", "Pre-set by NIHA"),
            ("Governing Law", "Hong Kong SAR", "Pre-set by NIHA"),
            ("Dispute Resolution", "Negotiation → Mediation → HKIAC", "Pre-set by NIHA"),
        ]
        el.append(key_terms_table(styles, terms))

        # ── SIGNATURE BLOCK ─────────────────────────────────────────────────
        el.extend(signature_block(
            styles,
            client_entity_name=client_entity_name,
        ))

        # ── LEGEND ──────────────────────────────────────────────────────────
        el.append(Spacer(1, 8 * mm))
        el.append(gold_separator())
        el.append(Paragraph(
            '<i>Note: Text displayed in </i>'
            f'<font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">this style '
            f'(bold italic, blue)</font>'
            '<i> indicates information pre-completed by NIHA. '
            'Fields with underlines (________) are to be completed by the counterparty.</i>',
            styles['Caption']
        ))

        return el

    return build_niha_pdf(
        doc_ref=ref,
        doc_title="Master Service Agreement — Carbon Credit Facilitation",
        content_builder=content,
        confidential=True,
        output_path=output_path,
    )
