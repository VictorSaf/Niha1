"""
Risk Disclosure Statement PDF Generator.

Generates a branded PDF with all risk categories, WARNING boxes,
party identification, recitals, and client acknowledgement section.

Aligned with NDA/MSA/Custody/Derivatives structure:
  - Party blocks (NIHA + Client)
  - Recitals referencing relationship context
  - Full client data (entity_type, jurisdiction, email)
"""

from datetime import date
from typing import Optional

from reportlab.platypus import Spacer, Paragraph, Table, TableStyle
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor

from .styles import (
    build_niha_pdf, gold_separator, thin_separator, filled,
    niha_party_block, client_party_block, signature_block,
    NihaFonts, NihaColors,
)


def _warning_box(styles, text: str):
    """Create a styled WARNING box."""
    data = [[Paragraph(f'<b>WARNING:</b> {text}', styles['Body'])]]
    table = Table(data, colWidths=[160 * mm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), HexColor("#FFF3CD")),
        ('BOX', (0, 0), (-1, -1), 1.5, HexColor("#D4A012")),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    return table


def generate_risk_disclosure_pdf(
    client_entity_name: Optional[str] = None,
    client_entity_type: Optional[str] = None,
    client_jurisdiction: Optional[str] = None,
    client_email: Optional[str] = None,
    client_representative: Optional[str] = None,
    effective_date: Optional[date] = None,
    doc_ref: Optional[str] = None,
    output_path: Optional[str] = None,
) -> bytes:
    """Generate the NIHA Risk Disclosure Statement as a branded PDF."""
    eff_date = effective_date or date.today()
    ref = doc_ref or f"NIHA-RDS-{eff_date.strftime('%Y')}-001"

    # Display helpers
    niha_name = "Italy Nihao Group Limited"

    def content(styles):
        el = []

        # ── TITLE ──
        el.append(Spacer(1, 15 * mm))
        el.append(Paragraph("RISK DISCLOSURE", styles['DocTitle']))
        el.append(Paragraph("STATEMENT", styles['DocTitle']))
        el.append(Spacer(1, 2 * mm))
        el.append(Paragraph(f"Version {filled('1.0')} — {filled(eff_date.strftime('%B %Y'))}", styles['DocSubtitle']))
        el.append(gold_separator())

        # Effective date & reference
        date_str = eff_date.strftime("%d %B %Y")
        el.append(Paragraph(f"Effective Date: {filled(date_str)}", styles['Body']))
        el.append(Paragraph(f"Reference: {filled(ref)}", styles['Body']))
        el.append(Spacer(1, 5 * mm))

        # ── PARTIES ──
        el.append(Paragraph("between", styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.extend(niha_party_block(styles, label="Disclosing Party"))
        el.append(Spacer(1, 3 * mm))
        el.append(Paragraph("and", styles['Body']))
        el.append(Spacer(1, 3 * mm))
        el.extend(client_party_block(
            styles,
            label="Client — Receiving Party",
            entity_name=client_entity_name,
            entity_type=client_entity_type,
            jurisdiction=client_jurisdiction,
            representative=client_representative,
            email=client_email,
        ))
        el.append(Spacer(1, 5 * mm))

        # ── RECITALS ──
        el.append(Paragraph("RECITALS", styles['SectionHeading']))
        el.append(thin_separator())

        niha_display = filled(niha_name)
        client_display = filled(client_entity_name) if client_entity_name else '"the Client"'
        client_type_display = filled(client_entity_type) if client_entity_type else "[type of entity]"
        client_juris_display = filled(client_jurisdiction) if client_jurisdiction else "[jurisdiction]"

        el.append(Paragraph(
            f'(A) {niha_display} (<b>"NIHA"</b>) is a company incorporated under the laws '
            f'of Hong Kong SAR, engaged in cross-border carbon credit trading, facilitation, '
            f'and related services.',
            styles['Body']
        ))
        el.append(Paragraph(
            f'(B) {client_display} (<b>"Client"</b>) is a {client_type_display} '
            f'incorporated/established under the laws of {client_juris_display}, which has '
            f'entered into, or is contemplating entering into, a business relationship with '
            f'NIHA pursuant to the Master Service Agreement and related agreements.',
            styles['Body']
        ))
        el.append(Paragraph(
            '(C) Prior to engaging in any carbon credit transactions or related services, '
            'NIHA is required to provide the Client with a comprehensive disclosure of the '
            'risks inherent in carbon credit trading and related activities.',
            styles['Body']
        ))
        el.append(Paragraph(
            '(D) This Risk Disclosure Statement is supplementary to and should be read in '
            'conjunction with the Master Service Agreement, the Custody Agreement, and the '
            'Carbon Derivatives Master Agreement, as applicable.',
            styles['Body']
        ))
        el.append(Spacer(1, 3 * mm))

        # ── IMPORTANT NOTICE ──
        el.append(Paragraph(
            f'<b>IMPORTANT: THIS DOCUMENT MUST BE READ IN FULL BEFORE ENTERING INTO ANY '
            f'TRANSACTION WITH {niha_name.upper()}</b>', styles['BodyBold']))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph(
            f'This Risk Disclosure Statement ("Statement") is issued by '
            f'{filled(niha_name)} ("NIHA") to provide prospective and existing '
            'clients with a comprehensive description of the risks associated with carbon credit '
            'trading and related services.', styles['Body']))
        el.append(Paragraph(
            'This Statement does not purport to disclose all risks. Clients should not rely solely '
            'on this document and should undertake their own independent investigation and due diligence.',
            styles['Body']))
        el.append(Spacer(1, 3 * mm))

        el.append(_warning_box(styles,
            'Carbon credit trading involves substantial risk of financial loss. The value of carbon '
            'credits can fluctuate significantly and may decline to zero. Past performance is not '
            'indicative of future results.'))
        el.append(Spacer(1, 5 * mm))

        # ── 1. PURPOSE ──
        el.append(Paragraph("1. PURPOSE AND SCOPE", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'This Risk Disclosure Statement is issued by NIHA to provide prospective and existing '
            'clients with a comprehensive description of the risks associated with carbon credit '
            'trading and related facilitation services provided by NIHA.', styles['Body']))

        # ── 2. GENERAL MARKET RISKS ──
        el.append(Paragraph("2. GENERAL MARKET RISKS", styles['SectionHeading']))
        el.append(thin_separator())

        el.append(Paragraph("<b>2.1 Price Volatility</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon credit prices are subject to significant volatility driven by regulatory '
            'announcements, supply and demand dynamics, seasonal factors, geopolitical events, and '
            'macroeconomic conditions. EU Allowances (EUA) and China Emission Allowances (CEA) have '
            'experienced substantial price movements in response to policy changes and trading patterns.',
            styles['Body']))
        el.append(Spacer(1, 2 * mm))
        el.append(_warning_box(styles,
            'There is no guarantee that carbon credits will maintain their value. Price declines of '
            '50% or more within a single calendar year have occurred in established carbon markets.'))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph("<b>2.2 Liquidity Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon credit markets may experience periods of reduced liquidity, particularly for less '
            'actively traded instruments, pilot market allocations, or during periods of market stress. '
            'Reduced liquidity may result in wider bid-ask spreads, difficulty in executing transactions '
            'at desired prices, or inability to execute transactions at all within a reasonable timeframe.',
            styles['Body']))

        el.append(Paragraph("<b>2.3 Market Disruption Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon markets may be subject to trading suspensions, circuit breakers, or market closures '
            'imposed by exchange operators, regulatory authorities, or registry administrators. Such '
            'disruptions may occur with or without notice and may prevent clients from liquidating or '
            'acquiring positions.', styles['Body']))

        # ── 3. REGULATORY AND LEGAL RISKS ──
        el.append(Paragraph("3. REGULATORY AND LEGAL RISKS", styles['SectionHeading']))
        el.append(thin_separator())

        el.append(Paragraph("<b>3.1 Regulatory Change Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon markets operate within regulatory frameworks that are subject to change. '
            'Governments and supranational bodies may at any time introduce new legislation, amend '
            'existing regulations, or modify the scope of carbon trading schemes. Examples include:',
            styles['Body']))
        for item in [
            'The European Union may adjust the cap on EUA allocations, modify the Market Stability Reserve mechanism, or change eligibility criteria under the EU ETS.',
            'The People\'s Republic of China may modify its national ETS design, adjust pilot scheme rules, restrict foreign participation, or impose new qualification requirements.',
            'Hong Kong SAR may introduce a licensing regime applicable to carbon credit intermediaries or may reclassify certain carbon credits as regulated products.',
        ]:
            el.append(Paragraph(f'• {item}', styles['SubClauseItem']))

        el.append(Paragraph("<b>3.2 Cross-Border Legal Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon credit transactions facilitated by NIHA may involve parties and assets in multiple '
            'jurisdictions with differing legal systems. The enforceability of contractual rights, the '
            'validity of carbon credit transfers, and the treatment of disputes may differ significantly '
            'across EU, PRC, and Hong Kong legal frameworks.', styles['Body']))

        el.append(Paragraph("<b>3.3 Tax Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'The tax treatment of carbon credit transactions is evolving and varies across jurisdictions. '
            'Profits, losses, and transfers of carbon credits may be subject to income tax, capital gains '
            'tax, value-added tax, withholding tax, and other levies. Clients are solely responsible for '
            'determining their tax obligations and for complying with applicable tax laws.', styles['Body']))

        el.append(Paragraph("<b>3.4 Sanctions and Compliance Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'NIHA is obliged to comply with applicable sanctions regimes, including those administered by '
            'the United Nations, European Union, United States, United Kingdom, and Hong Kong. Changes in '
            'sanctions designations may prevent NIHA from executing transactions with affected clients.',
            styles['Body']))

        # ── 4. OPERATIONAL AND COUNTERPARTY RISKS ──
        el.append(Paragraph("4. OPERATIONAL AND COUNTERPARTY RISKS", styles['SectionHeading']))
        el.append(thin_separator())

        el.append(Paragraph("<b>4.1 Registry and Infrastructure Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Carbon credits exist as entries in electronic registries maintained by third-party operators. '
            'The security, availability, and accuracy of these registries are beyond NIHA\'s control. '
            'Registry outages, system errors, security breaches, or regulatory changes may prevent the '
            'transfer, delivery, or retirement of carbon credits.', styles['Body']))

        el.append(Paragraph("<b>4.2 Settlement Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Where settlement is not conducted on a delivery-versus-payment (DVP) basis, there is a risk '
            'that one party may fulfil its obligation while the other fails, resulting in financial loss.',
            styles['Body']))

        el.append(Paragraph("<b>4.3 Counterparty Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'NIHA operates as a principal counterparty in carbon credit transactions. Clients bear '
            'exposure to NIHA\'s creditworthiness and operational continuity. While NIHA maintains '
            'segregated client accounts, insolvency of NIHA could result in delays or complications '
            'in the return of client assets.', styles['Body']))
        el.append(Spacer(1, 2 * mm))
        el.append(_warning_box(styles,
            'In the event of NIHA\'s insolvency, client assets may be subject to claims by creditors '
            'notwithstanding the segregation measures described in the Custody Agreement (as defined in '
            'the Master Service Agreement). The legal protection afforded to client assets in Hong Kong '
            'insolvency proceedings may be limited.'))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph("<b>4.4 Technology and Cyber Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'NIHA\'s operations depend upon the proper functioning of its technology systems. System '
            'failures, software errors, cyber-attacks, or malicious intrusions could result in service '
            'interruptions, data loss, or unauthorised access to sensitive information.', styles['Body']))

        # ── 5. CROSS-BORDER AND CONVERSION RISKS ──
        el.append(Paragraph("5. CROSS-BORDER AND CONVERSION RISKS", styles['SectionHeading']))
        el.append(thin_separator())

        el.append(Paragraph("<b>5.1 CEA-EUA Conversion Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'NIHA offers a service enabling conversion between Chinese Emission Allowances (CEA) and '
            'EU Allowances (EUA) pursuant to the Carbon Derivatives Master Agreement. This conversion '
            'is not a direct exchange recognised by any regulatory authority but rather a bilateral '
            'arrangement effected through NIHA\'s principal counterparty mechanism. There is no official '
            'exchange rate between CEA and EUA.', styles['Body']))
        el.append(Spacer(1, 2 * mm))
        el.append(_warning_box(styles,
            'The CEA-EUA conversion service is a bilateral arrangement with NIHA as counterparty. '
            'There is no official exchange rate between these instruments, and the conversion ratio '
            'offered by NIHA includes a spread reflecting NIHA\'s costs, risks, and profit. The ratio '
            'is subject to market conditions and is not guaranteed.'))
        el.append(Spacer(1, 3 * mm))

        el.append(Paragraph("<b>5.2 Foreign Exchange Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Where transactions involve currencies other than the client\'s base currency, the client '
            'bears foreign exchange risk. Fluctuations in exchange rates (including EUR, CNY, HKD, and '
            'USD) may affect the value of transactions, deposits, and the client\'s portfolio value.',
            styles['Body']))

        el.append(Paragraph("<b>5.3 Capital Controls and Transfer Risk</b>", styles['SubHeading']))
        el.append(Paragraph(
            'Certain jurisdictions, including the PRC, impose restrictions on cross-border capital '
            'movements. These restrictions may limit the ability to remit funds, transfer carbon credits, '
            'or repatriate proceeds. NIHA is not liable for delays due to capital control restrictions.',
            styles['Body']))

        # ── 6. RISK OF TOTAL LOSS ──
        el.append(Paragraph("6. RISK OF TOTAL LOSS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'It is possible that the entire value of a client\'s carbon credit portfolio may be lost. '
            'This may occur as a result of:', styles['Body']))
        for item in [
            'Regulatory action that renders carbon credits invalid, non-transferable, or worthless.',
            'Permanent closure or discontinuation of a carbon trading scheme or registry.',
            'Fraud, misrepresentation, or error in the issuance or verification of carbon credits.',
            'Insolvency or default of NIHA or a counterparty.',
            'Force majeure events that prevent the operation of carbon markets.',
            'Adverse regulatory changes that eliminate or diminish the value of carbon credits as compliance instruments.',
        ]:
            el.append(Paragraph(f'• {item}', styles['SubClauseItem']))

        # ── 7. NO INVESTMENT ADVICE ──
        el.append(Paragraph("7. NO INVESTMENT ADVICE", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'NIHA does not provide investment, financial, legal, or tax advice. Nothing in NIHA\'s '
            'communications, documentation, or services constitutes a recommendation to buy, sell, '
            'hold, or convert any carbon credits.', styles['Body']))
        el.append(Paragraph(
            'NIHA\'s market intelligence and reporting services are provided for informational purposes '
            'only and should not be construed as investment advice.', styles['Body']))

        # ── 8. SUITABILITY ──
        el.append(Paragraph("8. SUITABILITY", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'Carbon credit trading may not be suitable for all investors. Clients should carefully '
            'consider whether carbon credit trading is appropriate for their financial situation, '
            'investment objectives, experience, and risk tolerance.', styles['Body']))

        # ── 9. RELATIONSHIP TO OTHER AGREEMENTS ──
        el.append(Paragraph("9. RELATIONSHIP TO OTHER AGREEMENTS", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'This Risk Disclosure Statement forms part of the contractual framework between NIHA and '
            'the Client. It should be read in conjunction with:', styles['Body']))
        for item in [
            'The <b>Master Service Agreement</b> — governing overall service terms, fees, and liability.',
            'The <b>Custody Agreement</b> — governing the safekeeping and segregation of client assets.',
            'The <b>Carbon Derivatives Master Agreement</b> — governing CEA-EUA swap transactions.',
            'The <b>Fee Schedule</b> — detailing applicable transaction and service charges.',
        ]:
            el.append(Paragraph(f'• {item}', styles['SubClauseItem']))
        el.append(Paragraph(
            'In the event of any inconsistency between this Statement and the Master Service Agreement, '
            'the Master Service Agreement shall prevail unless the inconsistency relates to the '
            'disclosure of a specific risk, in which case this Statement shall prevail.',
            styles['Body']))

        # ── 10. CLIENT ACKNOWLEDGEMENT ──
        el.append(Paragraph("10. CLIENT ACKNOWLEDGEMENT", styles['SectionHeading']))
        el.append(thin_separator())
        el.append(Paragraph(
            'By signing below, the Client acknowledges and confirms that:', styles['Body']))

        acks = [
            'The Client has received, read, and understood this Risk Disclosure Statement in its entirety.',
            'The Client acknowledges that the risks described herein are not exhaustive.',
            'The Client has had the opportunity to seek independent legal, financial, and tax advice.',
            'The Client\'s decision to trade in carbon credits is based on the Client\'s own judgement and assessment.',
            'The Client understands and accepts that the value of carbon credits may decline and that the Client may suffer a total loss of invested capital.',
            'The Client\'s acknowledgement does not in any way limit or exclude NIHA\'s liability for fraud or fraudulent misrepresentation.',
        ]
        for ack in acks:
            el.append(Paragraph(f'• {ack}', styles['SubClauseItem']))

        # ── SIGNATURE ──
        el.extend(signature_block(styles, client_entity_name=client_entity_name))

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
        doc_title="Risk Disclosure Statement",
        content_builder=content,
        confidential=True,
        output_path=output_path,
    )
