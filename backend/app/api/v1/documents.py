"""
Document Library API — serves platform legal documents based on user role.

Each document is mapped to a phase in the user journey (F0–F7).
The endpoint filters documents by the authenticated user's current role,
returning only the documents they are entitled to see at their stage.

Phase mapping:
  F0 (Internal/Admin)    → ADMIN only
  F1 (PRE_NDA → NDA)     → NDA+ (first client document)
  F2 (KYC → APPROVED)    → KYC+
  F3 (APPROVED)           → APPROVED+
  F4 (FUNDING → CEA)      → FUNDING+
  F5 (CEA → EUA)          → CEA+
  F6 (Ongoing/Periodic)   → CEA+ (reports)
  F7 (Reference/Internal) → ADMIN only
"""

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import get_current_user
from ...models.models import UserRole
from ...services.document_catalog import DOCUMENT_CATALOG, user_has_min_role

router = APIRouter(prefix="/documents", tags=["documents"])


class PlatformDocument(BaseModel):
    """A document in the NIHA platform document library."""
    id: str
    title: str
    title_ro: str  # Romanian title
    filename: str
    phase: str  # F0–F7
    phase_name: str
    category: str  # 'legal', 'compliance', 'operational', 'trading', 'reporting', 'internal'
    description: str
    description_ro: str
    min_role: str  # Minimum role required to access
    admin_only: bool
    trigger: str  # When this document becomes relevant
    audience: str  # Who the document is for


def get_documents_for_role(user_role: UserRole) -> list[dict]:
    """Return documents accessible by the given role."""
    results = []
    for doc in DOCUMENT_CATALOG:
        min_role_str = doc["min_role"]

        # Admin-only documents
        if doc["admin_only"]:
            if user_role == UserRole.ADMIN:
                results.append(doc)
            continue

        # Check if user has at least the minimum required role
        try:
            min_role = UserRole(min_role_str)
        except ValueError:
            continue

        if user_has_min_role(user_role, min_role):
            results.append(doc)

    return results


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------

class DocumentItem(BaseModel):
    id: str
    title: str
    titleRo: str
    filename: str
    phase: str
    phaseName: str
    category: str
    description: str
    descriptionRo: str
    adminOnly: bool
    trigger: str
    audience: str
    downloadUrl: str


class DocumentLibraryResponse(BaseModel):
    documents: list[DocumentItem]
    totalCount: int
    userRole: str
    phases: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/library", response_model=DocumentLibraryResponse)
async def get_document_library(
    phase: Optional[str] = None,
    category: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Get the document library filtered by the current user's role.

    Documents are progressively unlocked as the user advances through the
    onboarding flow. Admin users see all documents.

    Optional query params:
      - phase: Filter by phase (F0, F1, F2, F3, F4, F5, F6, F7)
      - category: Filter by category (legal, compliance, operational, trading, reporting, internal)
    """
    user_role = UserRole(current_user.role) if isinstance(current_user.role, str) else current_user.role

    docs = get_documents_for_role(user_role)

    # Apply filters
    if phase:
        docs = [d for d in docs if d["phase"] == phase]
    if category:
        docs = [d for d in docs if d["category"] == category]

    # Build response items
    items = []
    for d in docs:
        items.append(DocumentItem(
            id=d["id"],
            title=d["title"],
            titleRo=d["title_ro"],
            filename=d["filename"],
            phase=d["phase"],
            phaseName=d["phase_name"],
            category=d["category"],
            description=d["description"],
            descriptionRo=d["description_ro"],
            adminOnly=d["admin_only"],
            trigger=d["trigger"],
            audience=d["audience"],
            downloadUrl=f"/api/v1/documents/download/{d['id']}",
        ))

    # Collect unique phases present in results
    seen_phases = {}
    for item in items:
        if item.phase not in seen_phases:
            seen_phases[item.phase] = item.phaseName
    phases = [{"code": k, "name": v} for k, v in seen_phases.items()]

    return DocumentLibraryResponse(
        documents=items,
        totalCount=len(items),
        userRole=user_role.value,
        phases=phases,
    )


@router.get("/download/{document_id}")
async def download_document(
    document_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),  # noqa: B008
):
    """
    Download a specific document by ID.

    Access is controlled by the user's role — they can only download
    documents available at their current journey stage.
    """
    from fastapi.responses import FileResponse

    user_role = UserRole(current_user.role) if isinstance(current_user.role, str) else current_user.role

    # Find the document
    doc = None
    for d in DOCUMENT_CATALOG:
        if d["id"] == document_id:
            doc = d
            break

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Check access
    if doc["admin_only"] and user_role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied — admin only document")

    if not doc["admin_only"]:
        try:
            min_role = UserRole(doc["min_role"])
        except ValueError:
            raise HTTPException(status_code=500, detail="Invalid document configuration")

        if not user_has_min_role(user_role, min_role):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied — requires role {doc['min_role']} or higher"
            )

    # ── Dynamic PDF generation for supported documents ──
    # Helper: extract common client data from current_user
    def _client_data():
        entity = current_user.entity if hasattr(current_user, 'entity') else None
        return {
            "client_entity_name": entity.name if entity else None,
            "client_entity_type": entity.entity_type if entity and entity.entity_type else None,
            "client_jurisdiction": entity.jurisdiction.value if entity and entity.jurisdiction else None,
            "client_email": current_user.email,
            "client_representative": (
                f"{current_user.first_name or ''} {current_user.last_name or ''}".strip() or None
            ),
        }

    def _pdf_response(pdf_bytes: bytes, filename: str):
        from io import BytesIO
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    # NDA
    if document_id == "nda":
        from app.services.pdf_generator import generate_nda_pdf
        cd = _client_data()
        pdf_bytes = generate_nda_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_NDA.pdf")

    # MSA
    if document_id == "msa":
        from app.services.pdf_generator import generate_msa_pdf
        cd = _client_data()
        pdf_bytes = generate_msa_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_MSA.pdf")

    # Custody Agreement
    if document_id == "custody":
        from app.services.pdf_generator import generate_custody_pdf
        cd = _client_data()
        pdf_bytes = generate_custody_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_Custody_Agreement.pdf")

    # Fee Schedule
    if document_id == "fee_schedule":
        from app.services.pdf_generator import generate_fee_schedule_pdf
        cd = _client_data()
        pdf_bytes = generate_fee_schedule_pdf(
            client_entity_name=cd["client_entity_name"],
            client_representative=cd["client_representative"],
            client_email=cd["client_email"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_Fee_Schedule.pdf")

    # Risk Disclosure Statement
    if document_id == "risk_disclosure":
        from app.services.pdf_generator import generate_risk_disclosure_pdf
        cd = _client_data()
        pdf_bytes = generate_risk_disclosure_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_Risk_Disclosure.pdf")

    # KYC / Client Onboarding Application
    if document_id == "kyc_form":
        from app.services.pdf_generator import generate_kyc_pdf
        from sqlalchemy import select as sa_select
        from ...models.models import KYCFormData, KYCDocument as KYCDocModel
        cd = _client_data()

        # Fetch form data if available
        fd_result = await db.execute(
            sa_select(KYCFormData).where(KYCFormData.user_id == current_user.id)
        )
        form_record = fd_result.scalar_one_or_none()
        form_dict = None
        if form_record and form_record.is_submitted:
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

        # Fetch document statuses
        docs_result = await db.execute(
            sa_select(KYCDocModel).where(KYCDocModel.user_id == current_user.id)
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
        return _pdf_response(pdf_bytes, "Nihao_Group_KYC_Application.pdf")

    # Carbon Derivatives Master Agreement
    if document_id == "derivatives":
        from app.services.pdf_generator import generate_derivatives_pdf
        cd = _client_data()
        pdf_bytes = generate_derivatives_pdf(
            client_entity_name=cd["client_entity_name"],
            client_entity_type=cd["client_entity_type"],
            client_jurisdiction=cd["client_jurisdiction"],
            client_email=cd["client_email"],
            client_representative=cd["client_representative"],
        )
        return _pdf_response(pdf_bytes, "Nihao_Group_Derivatives_Agreement.pdf")

    # ── Static file fallback for other documents ──
    base_path = os.environ.get("DOCUMENT_BASE_PATH", "/app/documents")
    file_path = os.path.join(base_path, doc["filename"])

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Document file not found on server")

    media_type = (
        "application/pdf"
        if doc["filename"].lower().endswith(".pdf")
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    return FileResponse(
        path=file_path,
        filename=doc["filename"],
        media_type=media_type,
    )

