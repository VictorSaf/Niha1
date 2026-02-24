"""
Carbon Derivatives Master Agreement PDF Generator.

Generates a branded PDF for the CDMA (16 Articles + 5 Schedules),
incorporating ISDA/IETA provisions for carbon credit trading.
"""

from datetime import date
from typing import Optional

from reportlab.platypus import Spacer, Paragraph, PageBreak
from reportlab.lib.units import mm

from .styles import (
    build_niha_pdf, gold_separator, thin_separator, filled,
    niha_party_block, client_party_block, signature_block,
    key_terms_table, NihaFonts, NihaColors,
)
from .msa_generator import _data_table


def generate_derivatives_pdf(
    client_entity_name: Optional[str] = None,
    client_entity_type: Optional[str] = None,
    client_jurisdiction: Optional[str] = None,
    client_representative: Optional[str] = None,
    client_email: Optional[str] = None,
    effective_date: Optional[date] = None,
    doc_ref: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate the NIHA Carbon Derivatives Master Agreement as a branded PDF."""
    eff_date = effective_date or date.today()
    ref = doc_ref or f"NIHA-CDMA-{eff_date.strftime('%Y')}-001"

    def content(styles):
        el = []

        # ── TITLE PAGE ──
        el.append(Spacer(1, 20 * mm))
        el.append(Paragraph("CARBON DERIVATIVES", styles['DocTitle']))
        el.append(Paragraph("MASTER AGREEMENT", styles['DocTitle']))
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph(
            "(Incorporating applicable industry-standard carbon credit definitions "
            "and IETA ERPA Provisions)", styles['DocSubtitle']))
        el.append(gold_separator())

        # Key terms summary
        el.append(key_terms_table(styles, [
            ("Agreement Reference", filled(ref), "Pre-set by NIHA"),
            ("Version", filled("1.0"), "Pre-set by NIHA"),
            ("Effective Date", filled(eff_date.strftime("%d %B %Y")), "Pre-set by NIHA"),
            ("Party A", filled("Italy Nihao Group Limited"), "Pre-set by NIHA"),
            ("Party B", client_entity_name or "[Counterparty Name]", "Client data"),
            ("Governing Law", filled("Laws of Hong Kong SAR"), "Pre-set by NIHA"),
            ("Dispute Resolution", filled("HKIAC Arbitration Rules"), "Pre-set by NIHA"),
            ("Default Rate", filled("SOFR + 4% p.a."), "Pre-set by NIHA"),
        ]))
        el.append(Spacer(1, 5 * mm))

        el.append(Paragraph(
            "This Agreement is entered into between the parties for the purpose of "
            "governing bilateral transactions in carbon credits, emission allowances, "
            "and related environmental instruments.",
            styles['Body']))
        el.append(Spacer(1, 3 * mm))

        # ── PARTIES ──
        el.append(Paragraph("THE PARTIES", styles['SectionHeading']))
        el.append(thin_separator())
        el.extend(niha_party_block(styles))
        el.append(Spacer(1, 3 * mm))
        el.extend(client_party_block(
            styles,
            entity_name=client_entity_name,
            entity_type=client_entity_type,
            jurisdiction=client_jurisdiction,
            representative=client_representative,
            email=client_email,
        ))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph(
            'hereinafter referred to as ' + filled('"Party A"') + ' and '
            + filled('"Party B"') + ' respectively, and collectively as the '
            + filled('"Parties"') + '.', styles['Body']))
        el.append(Spacer(1, 5 * mm))

        # ──────────────────────────────────────────────────────────────────────
        # ARTICLE 1 — INTERPRETATION AND DEFINITIONS
        # ──────────────────────────────────────────────────────────────────────
        def art(title):
            el.append(Paragraph(title, styles['ClauseNumber']))
            el.append(thin_separator())

        def cl(num, text):
            el.append(Paragraph(f'<b>{num}</b> {text}', styles['SubClause']))

        def items(lst):
            for item in lst:
                el.append(Paragraph(item, styles['SubClauseItem']))

        art("ARTICLE 1 — INTERPRETATION AND DEFINITIONS")
        cl("1.1", "In this Agreement, unless the context otherwise requires:")
        defs = [
            ('"Allowance"', 'means any unit representing the right to emit one tonne of carbon dioxide equivalent (whole units) issued under an Emissions Trading Scheme, including but not limited to EUA, CEA, and any successor or equivalent instruments;'),
            ('"Business Day"', 'means a day (other than a Saturday, Sunday, or public holiday) on which banks are open for general business in Hong Kong and, if relevant to the Transaction, in the jurisdiction of the applicable Registry;'),
            ('"Carbon Credit"', 'means any Allowance or Offset Credit;'),
            ('"CEEX"', 'means the China Emissions Exchange (Shenzhen), operated by the Shenzhen Emissions Rights Exchange;'),
            ('"Compliance Period"', 'means the period designated by the relevant Emissions Trading Scheme during which an Allowance may be used for compliance;'),
            ('"Confirmation"', 'means each document, including electronic communications, exchanged between the parties confirming the terms of a Transaction entered into under this Agreement;'),
            ('"Conversion Transaction"', 'means a Transaction involving the exchange of one type of Carbon Credit for another, including cross-border CEA-to-EUA conversions;'),
            ('"Delivery"', "means the transfer of Carbon Credits from the Delivering Party's Registry Account to the Receiving Party's Registry Account;"),
            ('"Emissions Trading Scheme"', 'or "ETS" means the EU ETS, China National ETS, Shenzhen Pilot ETS, or any other mandatory cap-and-trade programme;'),
            ('"EUTL"', 'means the European Union Transaction Log;'),
            ('"Event of Default"', 'has the meaning given in Article 10;'),
            ('"HKEX Core Climate"', "means the Hong Kong Exchanges and Clearing Limited's Core Climate platform;"),
            ('"Mark-to-Market Value"', 'means the current market value of all outstanding Transactions calculated in accordance with Article 9;'),
            ('"Offset Credit"', 'means any unit representing a verified reduction or removal of greenhouse gas emissions, including VCU, GS-VER, and CER;'),
            ('"Registry"', 'means EUTL, CEEX, HKEX Core Climate, UNFCCC CDM Registry, Verra Registry, Gold Standard Registry, or any other carbon credit registry designated in a Confirmation;'),
            ('"SAFE"', "means the State Administration of Foreign Exchange of the People's Republic of China;"),
            ('"Settlement Amount"', 'has the meaning given in Article 8;'),
            ('"Transaction"', 'means each transaction entered into between the parties under this Agreement, as evidenced by a Confirmation;'),
            ('"VCC"', 'means a voluntary carbon credit, including VCU and GS-VER.'),
        ]
        for term, meaning in defs:
            el.append(Paragraph(f'<b>{term}</b> {meaning}', styles['SubClauseItem']))
        el.append(Spacer(1, 2 * mm))

        cl("1.2", "Terms defined in the ISDA 2006 Definitions, the applicable "
           "industry-standard carbon credit definitions (2022), and the IETA "
           "Emissions Reduction Purchase Agreement (2023 form) shall, unless "
           "otherwise defined herein, have the meanings given therein.")
        cl("1.3", "References to Articles, Schedules, and Annexes are to articles of, "
           "and schedules and annexes to, this Agreement.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 2 — SCOPE AND SINGLE AGREEMENT ──
        art("ARTICLE 2 — SCOPE AND SINGLE AGREEMENT")
        cl("2.1", 'This Agreement and all Confirmations entered into hereunder form a '
           'single agreement between the parties (the "Agreement"). The parties would '
           'not otherwise enter into any Transaction.')
        cl("2.2", "This Agreement governs the following types of Transactions:")
        items([
            "(a) Spot and forward purchase and sale of Allowances (EUA, CEA);",
            "(b) Spot and forward purchase and sale of Offset Credits (VCU, GS-VER, CER);",
            "(c) Conversion Transactions (CEA\u2192EUA, EUA\u2192CEA);",
            "(d) Options on Carbon Credits;",
            "(e) Carbon Credit swaps (fixed-for-floating, cross-market);",
            "(f) Any other transaction type as mutually agreed and documented in a Confirmation.",
        ])
        cl("2.3", "Each Transaction shall be evidenced by a Confirmation substantially "
           "in the form set out in Schedule 2. In the event of any inconsistency "
           "between the terms of a Confirmation and this Agreement, the Confirmation "
           "shall prevail.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 3 — REPRESENTATIONS AND WARRANTIES ──
        art("ARTICLE 3 — REPRESENTATIONS AND WARRANTIES")
        cl("3.1", "Each party represents and warrants to the other on the date of this "
           "Agreement and on the date of each Transaction that:")
        items([
            "(a) it is duly organised and validly existing under the laws of its jurisdiction of incorporation;",
            "(b) it has the power and authority to execute, deliver, and perform its obligations under this Agreement;",
            "(c) this Agreement constitutes its legal, valid, and binding obligation;",
            "(d) the execution, delivery, and performance of this Agreement does not violate any law, regulation, or contractual obligation binding upon it;",
            "(e) it holds all necessary registrations, licences, and approvals (including Registry Accounts and, where applicable, SAFE approvals) required to perform its obligations;",
            "(f) no Event of Default or Potential Event of Default has occurred and is continuing;",
            "(g) it is acting as principal and not as agent for any other person;",
            "(h) it has made its own independent decision to enter into each Transaction based on its own judgment.",
        ])
        cl("3.2", "Party A additionally represents that:")
        items([
            "(a) carbon credit trading in Hong Kong does not require a licence under the applicable securities and futures legislation in Hong Kong;",
            "(b) it maintains professional indemnity insurance with a minimum coverage of " + filled("USD 5,000,000") + ";",
            "(c) it maintains segregated client accounts and Registry Accounts in accordance with its Custody Agreement and Compliance Policy Manual.",
        ])
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 4 — DELIVERY AND SETTLEMENT ──
        art("ARTICLE 4 — DELIVERY AND SETTLEMENT")
        cl("4.1", '<b>Physical Delivery.</b> Unless otherwise specified in the Confirmation, '
           'each Transaction shall be settled by physical Delivery of the relevant Carbon '
           'Credits against payment of the Settlement Amount ("Delivery versus Payment" or "DvP").')
        cl("4.2", "<b>Delivery Obligations.</b> On the Delivery Date specified in the Confirmation:")
        items([
            "(a) the Delivering Party shall initiate the transfer of the specified quantity and type of Carbon Credits from its Registry Account to the Receiving Party's Registry Account;",
            "(b) the Receiving Party shall make payment of the Settlement Amount in the Agreed Currency to the account specified in the Confirmation.",
        ])
        cl("4.3", "<b>Delivery Completion.</b> Delivery shall be deemed complete upon the "
           "Carbon Credits being credited to the Receiving Party's Registry Account "
           "as confirmed by the relevant Registry.")
        cl("4.4", "<b>Settlement Periods.</b> Unless otherwise agreed:")
        items([
            "(a) EUA Spot Transactions: " + filled("T+2") + ";",
            "(b) CEA Spot Transactions: " + filled("T+3") + " (subject to CEEX settlement cycle and SAFE clearance);",
            "(c) VCC/CER Transactions: " + filled("T+5") + " (subject to registry processing times);",
            "(d) Conversion Transactions: as specified in the Confirmation (typically " + filled("T+10 to T+15") + " for cross-border conversions).",
        ])
        cl("4.5", "<b>Failed Delivery.</b> If the Delivering Party fails to complete "
           "Delivery by the end of the Settlement Period:")
        items([
            "(a) the Receiving Party may, at its option, extend the Settlement Period by up to 5 Business Days;",
            "(b) the Delivering Party shall pay interest on the value of the undelivered Carbon Credits at the Default Rate;",
            "(c) if Delivery is not completed within the extended period, the Receiving Party may declare an Event of Default.",
        ])
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 5 — CONVERSION TRANSACTIONS ──
        art("ARTICLE 5 — CONVERSION TRANSACTIONS")
        cl("5.1", "<b>Conversion Methodology.</b> For CEA\u2192EUA Conversion Transactions:")
        items([
            "(a) the Conversion Ratio shall be the ratio specified in the Confirmation, being the number of EUA deliverable per CEA surrendered;",
            "(b) Party A shall procure the conversion through its established CEEX and EUTL infrastructure, subject to SAFE approval and quota availability;",
            "(c) the conversion fee shall be as specified in the Fee Schedule (Annexure B to the Master Service Agreement).",
        ])
        cl("5.2", "<b>SAFE Compliance.</b> All Conversion Transactions involving CEA are subject to:")
        items([
            "(a) prior SAFE approval for cross-border capital movement;",
            "(b) compliance with NIHA's SAFE-approved annual quota (currently " + filled("CNY 50,000,000") + ");",
            "(c) completion of required SAFE reporting within 5 Business Days of settlement.",
        ])
        cl("5.3", "<b>Conversion Risk.</b> The parties acknowledge that:")
        items([
            "(a) the Conversion Ratio may fluctuate between the Trade Date and the Delivery Date;",
            "(b) SAFE approval is not guaranteed and may be delayed;",
            "(c) neither party shall be liable for losses arising from SAFE refusal or delay, provided the affected party has used best endeavours to obtain approval.",
        ])
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 6 — NETTING ──
        art("ARTICLE 6 — NETTING")
        cl("6.1", "<b>Payment Netting.</b> If on any date amounts would otherwise be payable "
           "in the same currency by each party to the other, the obligations of the "
           "parties to make payment of such amounts shall be automatically satisfied "
           "and discharged and replaced by an obligation on the party owing the larger "
           "amount to pay the other the excess of the larger over the smaller amount.")
        cl("6.2", "<b>Delivery Netting.</b> If on any Delivery Date Carbon Credits of the "
           "same type and Compliance Period would otherwise be deliverable by each "
           "party, the obligations to deliver shall be automatically netted.")
        cl("6.3", "<b>Close-Out Netting.</b> Upon the occurrence of an Event of Default, "
           "close-out netting shall apply in accordance with Article 10.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 7 — CREDIT SUPPORT ──
        art("ARTICLE 7 — CREDIT SUPPORT")
        cl("7.1", "<b>Initial Margin.</b> Party B shall, if required under the Counterparty "
           "Risk Assessment Framework, deliver Initial Margin to Party A in an amount "
           "specified in the Confirmation or as notified by Party A.")
        cl("7.2", "<b>Variation Margin.</b> If the aggregate Mark-to-Market Value of all "
           "outstanding Transactions exceeds the Unsecured Threshold, the party with "
           "the negative exposure shall deliver Variation Margin within "
           + filled("2 Business Days") + " of notification.")
        cl("7.3", "<b>Eligible Collateral.</b> Eligible Collateral comprises:")
        items([
            "(a) Cash in EUR, USD, or CNY (haircut: " + filled("0%") + ");",
            "(b) EUA held in EUTL (haircut: " + filled("15%") + ");",
            "(c) CEA held in CEEX (haircut: " + filled("25%") + ");",
            "(d) Bank guarantees from institutions rated BBB+ or above (haircut: " + filled("5%") + ").",
        ])
        cl("7.4", "<b>Return of Collateral.</b> Collateral shall be returned within "
           + filled("3 Business Days") + " of the relevant obligation being discharged "
           "or the exposure falling below the threshold.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 8 — VALUATION AND MARK-TO-MARKET ──
        art("ARTICLE 8 — VALUATION AND MARK-TO-MARKET")
        cl("8.1", "<b>Daily Valuation.</b> Party A shall calculate the Mark-to-Market Value "
           "of all outstanding Transactions at the close of each Business Day using:")
        items([
            "(a) EUA: ICE Endex EUA Futures (front month) settlement price;",
            "(b) CEA: CEEX daily closing price;",
            "(c) VCC/CER: The average of the last three reported prices on the relevant exchange or platform;",
            "(d) Conversion Transactions: The implied value based on the applicable Conversion Ratio and the relevant market prices of the underlying Carbon Credits.",
        ])
        cl("8.2", "<b>Valuation Dispute.</b> If Party B disputes a valuation, it shall "
           "notify Party A within 2 Business Days with supporting evidence. The parties "
           "shall negotiate in good faith to resolve the dispute within 5 Business Days.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 9 — TAXES AND COSTS ──
        art("ARTICLE 9 — TAXES AND COSTS")
        cl("9.1", "Each party shall be responsible for all taxes imposed on it in respect "
           "of Transactions entered into under this Agreement.")
        cl("9.2", "All payments shall be made free and clear of, and without deduction for, "
           "any taxes, unless required by law. If a deduction is required, the paying "
           "party shall gross up the payment.")
        cl("9.3", "Registry transfer fees shall be borne by the Delivering Party unless "
           "otherwise specified in the Confirmation.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 10 — EVENTS OF DEFAULT AND TERMINATION ──
        el.append(PageBreak())
        art("ARTICLE 10 — EVENTS OF DEFAULT AND TERMINATION")
        cl("10.1", "<b>Events of Default.</b> Each of the following shall constitute an "
           "Event of Default:")
        items([
            "(a) <b>Failure to Pay:</b> failure by a party to make any payment when due, not remedied within 3 Business Days of notice;",
            "(b) <b>Failure to Deliver:</b> failure by a party to make any Delivery when due, not remedied within 5 Business Days of notice;",
            "(c) <b>Breach of Representation:</b> any representation made by a party proves to have been materially incorrect when made;",
            "(d) <b>Breach of Covenant:</b> failure to comply with any material obligation, not remedied within 15 Business Days;",
            "(e) <b>Insolvency:</b> a party becomes insolvent, enters liquidation, or has a receiver appointed;",
            "(f) <b>Cross-Default:</b> default under any other agreement exceeding " + filled("USD 500,000") + ";",
            "(g) <b>Sanctions:</b> a party becomes subject to sanctions prohibiting continued performance;",
            "(h) <b>Registry Suspension:</b> a party's Registry Account is suspended or revoked;",
            "(i) <b>Collateral Default:</b> failure to deliver required collateral within 2 Business Days.",
        ])
        cl("10.2", "<b>Early Termination.</b> Upon an Event of Default, the Non-Defaulting "
           "Party may, by not more than 20 days' notice:")
        items([
            "(a) designate an Early Termination Date for all outstanding Transactions;",
            "(b) calculate the Close-Out Amount for each Terminated Transaction;",
            "(c) apply close-out netting and set-off to determine a single net amount payable.",
        ])
        cl("10.3", "<b>Close-Out Amount.</b> The Close-Out Amount for each Terminated "
           "Transaction shall be the amount of loss or gain that would be incurred by "
           "the Non-Defaulting Party in replacing or providing the economic equivalent "
           "of the material terms.")
        cl("10.4", "<b>Default Rate.</b> Any amount unpaid after the due date shall bear "
           "interest at the Default Rate, being " + filled("SOFR plus 4% per annum") + ".")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 11 — FORCE MAJEURE ──
        art("ARTICLE 11 — FORCE MAJEURE")
        cl("11.1", "Neither party shall be liable for failure to perform if prevented "
           "by a Force Majeure Event, including:")
        items([
            "(a) war, armed conflict, terrorism, or civil unrest;",
            "(b) natural disaster, pandemic, or epidemic;",
            "(c) government action, sanctions, or embargo;",
            "(d) failure or disruption of a Registry or exchange;",
            "(e) failure or disruption of banking systems or payment infrastructure.",
        ])
        cl("11.2", "The affected party shall notify the other within 2 Business Days "
           "and use reasonable endeavours to mitigate the effect.")
        cl("11.3", "If a Force Majeure Event continues for more than "
           + filled("30 Business Days") + ", either party may terminate affected Transactions.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 12 — CONFIDENTIALITY ──
        art("ARTICLE 12 — CONFIDENTIALITY")
        cl("12.1", "Each party shall treat as confidential all information received from "
           "the other in connection with this Agreement, subject to the exceptions in "
           "the Non-Disclosure Agreement.")
        cl("12.2", "Notwithstanding the foregoing, each party may disclose information:")
        items([
            "(a) to the extent required by applicable law, regulation, or court order;",
            "(b) to its professional advisors, auditors, and insurers on a need-to-know basis;",
            "(c) to any regulatory authority having jurisdiction;",
            "(d) with the prior written consent of the other party.",
        ])
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 13 — COMPLIANCE AND REGULATORY ──
        art("ARTICLE 13 — COMPLIANCE AND REGULATORY")
        cl("13.1", "Each party shall comply with all applicable anti-money laundering and "
           "counter-terrorist financing laws, including the applicable legislation in "
           "Hong Kong and the Organised and Serious Crimes Ordinance.")
        cl("13.2", "Each party shall maintain records of all Transactions for a minimum "
           "of " + filled("7 years") + ".")
        cl("13.3", "Party A shall conduct ongoing monitoring and periodic review of "
           "Party B in accordance with its Compliance Policy Manual and Counterparty "
           "Risk Assessment Framework.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 14 — GOVERNING LAW AND DISPUTE RESOLUTION ──
        art("ARTICLE 14 — GOVERNING LAW AND DISPUTE RESOLUTION")
        cl("14.1", "This Agreement shall be governed by and construed in accordance with "
           "the laws of the " + filled("Hong Kong Special Administrative Region") + ".")
        cl("14.2", "Any dispute arising out of or in connection with this Agreement shall "
           "be referred to and finally resolved by arbitration administered by the "
           + filled("Hong Kong International Arbitration Centre") + ' ("HKIAC") under the '
           "HKIAC Administered Arbitration Rules in force at the date of commencement "
           "of the arbitration.")
        cl("14.3", "The arbitral tribunal shall consist of " + filled("three")
           + " arbitrators. The seat of arbitration shall be " + filled("Hong Kong")
           + ". The language of the arbitration shall be " + filled("English") + ".")
        cl("14.4", "The parties agree that the arbitral award shall be final and binding, "
           "and judgment may be entered upon it in any court having jurisdiction.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 15 — MISCELLANEOUS ──
        art("ARTICLE 15 — MISCELLANEOUS")
        cl("15.1", "<b>Entire Agreement.</b> This Agreement (together with all Confirmations "
           "and Schedules) constitutes the entire agreement between the parties.")
        cl("15.2", "<b>Amendment.</b> No amendment to this Agreement shall be effective "
           "unless in writing signed by both parties.")
        cl("15.3", "<b>Assignment.</b> Neither party may assign its rights or obligations "
           "without the prior written consent of the other party.")
        cl("15.4", "<b>Waiver.</b> No failure to exercise any right shall constitute a "
           "waiver thereof.")
        cl("15.5", "<b>Severability.</b> If any provision is held invalid, the remaining "
           "provisions shall continue in full force and effect.")
        cl("15.6", "<b>Notices.</b> All notices shall be in writing and delivered to "
           "the addresses specified in Schedule 1.")
        cl("15.7", "<b>Counterparts.</b> This Agreement may be executed in counterparts, "
           "each of which shall be deemed an original.")
        el.append(Spacer(1, 3 * mm))

        # ── ARTICLE 16 — SCHEDULES ──
        art("ARTICLE 16 — SCHEDULES")
        el.append(Paragraph("The following Schedules form part of this Agreement:",
                            styles['Body']))
        items([
            "Schedule 1 — Party Details and Notices",
            "Schedule 2 — Form of Confirmation",
            "Schedule 3 — Credit Support Annex",
            "Schedule 4 — Registry Account Details",
            "Schedule 5 — Fee Schedule (by reference to " + filled(ref.replace("CDMA", "FEE")) + ")",
        ])
        el.append(Spacer(1, 5 * mm))

        # ══════════════════════════════════════════════════════════════════════
        # SCHEDULE 1 — PARTY DETAILS
        # ══════════════════════════════════════════════════════════════════════
        el.append(PageBreak())
        el.append(Paragraph("SCHEDULE 1 — PARTY DETAILS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Spacer(1, 2 * mm))

        el.append(Paragraph('<b>Party A</b>', styles['SubHeading']))
        el.append(_data_table(styles,
            ["Field", "Details"],
            [
                ["Full Name", filled("Italy Nihao Group Limited")],
                ["Registration", filled("Hong Kong CR No. [________]")],
                ["Address", filled("Suite 2205, 22/F, Tower 2, Lippo Centre, 89 Queensway, Admiralty, Hong Kong")],
                ["Contact", filled("Christian Meier, Director")],
                ["Email", filled("christian@nihagroup.com")],
                ["Telephone", filled("+852 3892 1000")],
                ["EUTL Account", filled("HK-NIHA-EUTL-2025-0001")],
                ["CEEX Account", filled("SZ-NIHA-CEEX-2025-0001 (SAFE Approved)")],
                ["Core Climate", filled("HKEX-CC-NIHA-2025-0001")],
            ],
            col_widths=[45 * mm, 125 * mm],
        ))
        el.append(Spacer(1, 4 * mm))

        el.append(Paragraph('<b>Party B</b>', styles['SubHeading']))
        el.append(_data_table(styles,
            ["Field", "Details"],
            [
                ["Full Name", client_entity_name or "[To be completed in each Confirmation]"],
                ["Registration", "[To be completed]"],
                ["Address", "[To be completed]"],
                ["Contact", client_representative or "[To be completed]"],
                ["Registry Accounts", "[To be completed]"],
            ],
            col_widths=[45 * mm, 125 * mm],
        ))
        el.append(Spacer(1, 5 * mm))

        # ══════════════════════════════════════════════════════════════════════
        # SCHEDULE 2 — FORM OF CONFIRMATION
        # ══════════════════════════════════════════════════════════════════════
        el.append(Paragraph("SCHEDULE 2 — FORM OF CONFIRMATION", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph("Each Confirmation shall include the following minimum particulars:",
                            styles['Body']))
        el.append(Spacer(1, 2 * mm))

        el.append(_data_table(styles,
            ["Field", "Value"],
            [
                ["Confirmation Reference", filled("NIHA-CONF-[YYYY]-[NNNN]")],
                ["Trade Date", "[Date]"],
                ["Effective Date", "[Date]"],
                ["Delivery Date", "[Date]"],
                ["Transaction Type", "[Spot Purchase / Spot Sale / Forward / Conversion / Swap / Option]"],
                ["Carbon Credit Type", "[EUA / CEA / VCU / GS-VER / CER / Other]"],
                ["Quantity", "[Number] whole units"],
                ["Price / Conversion Ratio", "[Amount per unit / Ratio]"],
                ["Settlement Currency", "[EUR / USD / CNY]"],
                ["Settlement Amount", "[Total payable]"],
                ["Delivering Party", "[Party A / Party B]"],
                ["Receiving Party", "[Party A / Party B]"],
                ["Delivering Party Registry Account", "[Account reference]"],
                ["Receiving Party Registry Account", "[Account reference]"],
                ["Fee / Commission", "[Amount and basis]"],
                ["Collateral Requirements", "[If applicable]"],
                ["Special Conditions", "[If any]"],
            ],
            col_widths=[55 * mm, 115 * mm],
        ))
        el.append(Spacer(1, 5 * mm))

        # ── EXECUTION / SIGNATURE ──
        el.append(PageBreak())
        el.append(Paragraph("EXECUTION", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            "IN WITNESS WHEREOF, the parties have executed this Carbon Derivatives "
            "Master Agreement as of the date first written above.",
            styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.extend(signature_block(styles, client_entity_name=client_entity_name))
        el.append(Spacer(1, 5 * mm))

        # ── LEGEND ──
        el.append(gold_separator())
        el.append(Paragraph(
            '<i>Note: Text displayed in </i>'
            f'<font name="{NihaFonts.FILLED}" color="{NihaColors.FILLED_BLUE}">this style</font>'
            '<i> indicates information pre-completed by NIHA.</i>',
            styles['Caption']))

        return el

    return build_niha_pdf(
        doc_ref=ref,
        doc_title="Carbon Derivatives Master Agreement",
        content_builder=content,
        confidential=True,
        output_path=output_path,
    )
