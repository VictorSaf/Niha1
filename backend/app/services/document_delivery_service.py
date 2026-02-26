"""
Document delivery service — returns document bytes for a given document_id and user.

Used by the Document Library download endpoint and by email flows that attach
journey-appropriate documents (e.g. account_approved → MSA, Custody, Fee Schedule,
Risk Disclosure, Derivatives; deposit_announced → Bank Confirmations, Registry Overview).
NDA for invitation emails (pre_nda_invitation, introducer_nda_invitation) is generated via
get_document_bytes("nda", get_system_user_for_document_generation(), db) so a single
source (generated NDA) is used everywhere.

See docs/DOCUMENT_EMAIL_MAPPING.md for the mapping of email template → documents.
"""

import logging
import os
from types import SimpleNamespace
from typing import Any, Optional

from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.models import UserRole

# Import catalog and role check from the shared document catalog (single source of truth)
from .document_catalog import DOCUMENT_CATALOG, user_has_min_role

logger = logging.getLogger(__name__)


def get_system_user_for_document_generation() -> Any:
    """
    Minimal user object for get_document_bytes when generating documents in system context
    (e.g. NDA PDF for invitation emails). Has ADMIN role so access checks pass; client
    fields (entity, email, etc.) are None so generated PDFs get blank placeholders.
    """
    return SimpleNamespace(
        role=UserRole.ADMIN,
        entity=None,
        email=None,
        first_name=None,
        last_name=None,
        id=None,
    )


def _client_data_from_user(user: Any) -> dict:
    """Build client data dict from a User (with optional entity) for PDF generators."""
    entity = getattr(user, "entity", None)
    return {
        "client_entity_name": entity.name if entity else None,
        "client_entity_type": getattr(entity, "entity_type", None) if entity else None,
        "client_jurisdiction": (
            entity.jurisdiction.value if entity and getattr(entity, "jurisdiction", None) else None
        ),
        "client_email": getattr(user, "email", None),
        "client_representative": (
            f"{getattr(user, 'first_name', '') or ''} {getattr(user, 'last_name', '') or ''}".strip()
            or None
        ),
    }


async def get_document_bytes(
    document_id: str,
    user: Any,
    db: AsyncSession,
    role_override: Optional[UserRole] = None,
) -> tuple[bytes, str]:
    """
    Return (bytes, filename) for the given document_id, for the given user.

    Access is checked using user.role unless role_override is set (e.g. FUNDING
    when sending deposit_announced email right after role transition).

    Raises:
        ValueError: document_id not in catalog or access denied.
        FileNotFoundError: static file not found on server.
    """
    doc = None
    for d in DOCUMENT_CATALOG:
        if d["id"] == document_id:
            doc = d
            break

    if not doc:
        raise ValueError(f"Document not found: {document_id}")

    user_role = role_override if role_override is not None else (
        UserRole(user.role) if isinstance(user.role, str) else user.role
    )

    if doc["admin_only"] and user_role != UserRole.ADMIN:
        raise ValueError(f"Access denied — admin only document: {document_id}")

    if not doc["admin_only"]:
        try:
            min_role = UserRole(doc["min_role"])
        except ValueError:
            raise ValueError(f"Invalid document configuration: {document_id}")
        if not user_has_min_role(user_role, min_role):
            raise ValueError(
                f"Access denied — requires role {doc['min_role']} or higher for {document_id}"
            )

    cd = _client_data_from_user(user)

    # ── Generated PDFs ──
    if document_id == "nda":
        from app.services.pdf_generator import generate_nda_pdf
        pdf_bytes = generate_nda_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return (pdf_bytes, "Nihao_Group_NDA.pdf")

    if document_id == "msa":
        from app.services.pdf_generator import generate_msa_pdf
        pdf_bytes = generate_msa_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return (pdf_bytes, "Nihao_Group_MSA.pdf")

    if document_id == "custody":
        from app.services.pdf_generator import generate_custody_pdf
        pdf_bytes = generate_custody_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return (pdf_bytes, "Nihao_Group_Custody_Agreement.pdf")

    if document_id == "fee_schedule":
        from app.services.pdf_generator import generate_fee_schedule_pdf
        pdf_bytes = generate_fee_schedule_pdf(
            client_entity_name=cd["client_entity_name"],
            client_representative=cd["client_representative"],
            client_email=cd["client_email"],
        )
        return (pdf_bytes, "Nihao_Group_Fee_Schedule.pdf")

    if document_id == "risk_disclosure":
        from app.services.pdf_generator import generate_risk_disclosure_pdf
        pdf_bytes = generate_risk_disclosure_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return (pdf_bytes, "Nihao_Group_Risk_Disclosure.pdf")

    if document_id == "kyc_form":
        from app.services.pdf_generator import generate_kyc_pdf
        from ..models.models import KYCFormData, KYCDocument as KYCDocModel

        fd_result = await db.execute(
            sa_select(KYCFormData).where(KYCFormData.user_id == user.id)
        )
        form_record = fd_result.scalar_one_or_none()
        form_dict = None
        if form_record and getattr(form_record, "is_submitted", False):
            form_dict = {
                "pep_declarations": form_record.pep_declarations,
                "has_carbon_experience": form_record.has_carbon_experience,
                "carbon_experience_years": form_record.carbon_experience_years,
                "carbon_credits_traded": form_record.carbon_credits_traded,
                "investment_objectives": form_record.investment_objectives,
                "risk_appetite": form_record.risk_appetite,
                "source_of_funds": form_record.source_of_funds,
                "expected_annual_volume": form_record.expected_annual_volume,
                "intended_use_description": form_record.intended_use_description,
                "tax_residency_country": form_record.tax_residency_country,
                "subject_to_crs": form_record.subject_to_crs,
                "declarations_accepted": form_record.declarations_accepted,
            }

        docs_result = await db.execute(
            sa_select(KYCDocModel).where(KYCDocModel.user_id == user.id)
        )
        docs_list = [
            {"type": d.document_type.value, "status": d.status.value, "file_name": d.file_name}
            for d in docs_result.scalars().all()
        ]

        pdf_bytes = generate_kyc_pdf(
            client_entity_name=cd["client_entity_name"],
            client_representative=cd["client_representative"],
            client_email=cd["client_email"],
            form_data=form_dict,
            documents_status=docs_list if docs_list else None,
        )
        return (pdf_bytes, "Nihao_Group_KYC_Application.pdf")

    if document_id == "derivatives":
        from app.services.pdf_generator import generate_derivatives_pdf
        pdf_bytes = generate_derivatives_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return (pdf_bytes, "Nihao_Group_Derivatives_Agreement.pdf")

    # ── Static files ──
    base_path = os.environ.get("DOCUMENT_BASE_PATH", "/app/documents")
    file_path = os.path.join(base_path, doc["filename"])

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Document file not found on server: {file_path}")

    with open(file_path, "rb") as f:
        content = f.read()
    return (content, doc["filename"])


# Document IDs to attach per email type (see docs/DOCUMENT_EMAIL_MAPPING.md)
ACCOUNT_APPROVED_ATTACHMENTS = ["msa", "custody", "fee_schedule", "risk_disclosure", "derivatives"]
DEPOSIT_ANNOUNCED_ATTACHMENTS = ["bank_confirmations", "registry_overview"]
