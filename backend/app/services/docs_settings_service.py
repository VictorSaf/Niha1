"""
Service for Settings → Documents tab: list docs from repo docs/ or documents/ and serve previews.

- docs/: draft documentation (.md, .pdf), optional manifest for role/email_templates.
- documents/: platform documentation (.pdf, .docx); used/NU from DOCUMENT_CATALOG and email attachments.
Path resolution is restricted to the chosen subtree.
Supports documents_manifest.json and documents_manifest.yaml (PyYAML) for docs/.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from .document_catalog import DOCUMENT_CATALOG
from .document_delivery_service import (
    ACCOUNT_APPROVED_ATTACHMENTS,
    DEPOSIT_ANNOUNCED_ATTACHMENTS,
)

logger = logging.getLogger(__name__)

# Allowed extensions for list endpoint (docs/)
DOCS_EXTENSIONS = (".md", ".pdf")
# Max depth under docs/ to scan (e.g. docs/, docs/features/, docs/commands/)
DOCS_MAX_DEPTH = 3

# documents/ folder: platform PDFs and optional docx sources
DOCUMENTS_EXTENSIONS = (".pdf", ".docx")
DOCUMENTS_MAX_DEPTH = 2


def _get_docs_root() -> Path:
    """Resolve docs directory relative to repo root (parent of backend)."""
    # admin.py lives at backend/app/api/v1/admin.py; we use docs_settings_service at backend/app/services/
    # So backend root = this_file.parent.parent, repo root = backend.parent, docs = repo_root / "docs"
    backend_root = Path(__file__).resolve().parent.parent
    repo_root = backend_root.parent
    return repo_root / "docs"


def _get_documents_root() -> Path:
    """Resolve documents directory (platform PDF/docx source) relative to repo root."""
    backend_root = Path(__file__).resolve().parent.parent
    repo_root = backend_root.parent
    return repo_root / "documents"


def _safe_relative_path(base: Path, path: Path) -> str | None:
    """Return path as relative to base, or None if path is not under base (path traversal)."""
    try:
        rel = path.resolve().relative_to(base.resolve())
    except ValueError:
        return None
    parts = rel.parts
    if ".." in parts or path.resolve() == base.resolve():
        return None
    return str(rel).replace("\\", "/")


def _load_manifest(docs_root: Path) -> dict[str, dict[str, Any]]:
    """Load optional manifest: maps path (relative to docs/) to { role?, email_templates? }."""
    for name in ("documents_manifest.json", "_documents_manifest.json", "documents_manifest.yaml", "_documents_manifest.yaml"):
        p = docs_root / name
        if not p.is_file():
            continue
        try:
            with open(p, encoding="utf-8") as f:
                if p.suffix in (".yaml", ".yml"):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)
        except Exception as e:
            logger.warning("Could not parse docs manifest %s: %s", p, e)
            return {}
        if isinstance(data, dict):
            return data
        return {}
    return {}


def list_documents() -> list[dict[str, Any]]:
    """
    List all draft documentation files under docs/ (and one level of subdirs).
    Returns list of { path, name, type, role?, email_templates? }.
    path is relative to docs/ (e.g. "features/0056_PLAN.md").
    """
    docs_root = _get_docs_root()
    if not docs_root.is_dir():
        logger.warning("Docs root not found: %s", docs_root)
        return []

    manifest = _load_manifest(docs_root)
    result: list[dict[str, Any]] = []
    for item in docs_root.rglob("*"):
        if not item.is_file():
            continue
        ext_key = item.suffix.lower().lstrip(".")
        if ext_key not in (e.lstrip(".") for e in DOCS_EXTENSIONS):
            continue
        # Limit depth (e.g. docs/a/b/c.md -> depth 3)
        try:
            rel = item.resolve().relative_to(docs_root.resolve())
        except ValueError:
            continue
        if len(rel.parts) > DOCS_MAX_DEPTH:
            continue
        path_key = str(rel).replace("\\", "/")
        name = item.name
        entry: dict[str, Any] = {
            "path": path_key,
            "name": name,
            "type": ext_key,
        }
        meta = manifest.get(path_key) or manifest.get(f"./{path_key}") or {}
        entry["role"] = meta.get("role")
        entry["email_templates"] = meta.get("email_templates") or []
        result.append(entry)

    result.sort(key=lambda x: (x["path"].lower(), x["name"]))
    return result


def get_preview_path(path_param: str) -> Path | None:
    """
    Validate path_param (relative to docs/) and return full Path, or None if invalid.
    Prevents path traversal (no .., no absolute).
    """
    path_param = (path_param or "").strip().replace("\\", "/")
    if not path_param or ".." in path_param or path_param.startswith("/"):
        return None
    # Normalize: remove leading ./
    if path_param.startswith("./"):
        path_param = path_param[2:]
    docs_root = _get_docs_root()
    full = (docs_root / path_param).resolve()
    root_resolved = docs_root.resolve()
    if not str(full).startswith(str(root_resolved)):
        return None
    if not full.is_file():
        return None
    return full


# ---------------------------------------------------------------------------
# documents/ folder: platform docs list + preview (Settings → Documents source)
# ---------------------------------------------------------------------------

def _catalog_by_filename() -> tuple[dict[str, dict], set[str], dict[str, list[str]]]:
    """
    Build lookup from filename -> catalog entry, set of used filenames, and filename -> email_templates.
    used = filename appears in DOCUMENT_CATALOG; email_templates = where that doc_id is attached.
    """
    by_filename: dict[str, dict] = {}
    used_filenames: set[str] = set()
    filename_to_templates: dict[str, list[str]] = {}

    for doc in DOCUMENT_CATALOG:
        fn = doc.get("filename") or ""
        if not fn:
            continue
        by_filename[fn] = doc
        used_filenames.add(fn)
        templates: list[str] = []
        doc_id = doc.get("id") or ""
        if doc_id in ACCOUNT_APPROVED_ATTACHMENTS:
            templates.append("account_approved.html")
        if doc_id in DEPOSIT_ANNOUNCED_ATTACHMENTS:
            templates.append("deposit_announced.html")
        if templates:
            filename_to_templates[fn] = templates

    return by_filename, used_filenames, filename_to_templates


def list_documents_from_documents_folder() -> list[dict[str, Any]]:
    """
    List platform documentation from repo documents/ (.pdf and .docx).
    Returns path (relative to documents/), name, type, used, email_templates, and catalog fields when matched.
    used = True if filename exists in DOCUMENT_CATALOG; otherwise False (display as NU).
    """
    documents_root = _get_documents_root()
    if not documents_root.is_dir():
        logger.warning("Documents root not found: %s", documents_root)
        return []

    by_filename, used_filenames, filename_to_templates = _catalog_by_filename()
    result: list[dict[str, Any]] = []

    for item in documents_root.rglob("*"):
        if not item.is_file():
            continue
        if item.suffix.lower() not in (e for e in DOCUMENTS_EXTENSIONS):
            continue
        try:
            rel = item.resolve().relative_to(documents_root.resolve())
        except ValueError:
            continue
        if len(rel.parts) > DOCUMENTS_MAX_DEPTH:
            continue
        path_key = str(rel).replace("\\", "/")
        name = item.name
        ext_key = item.suffix.lower().lstrip(".")
        used = name in used_filenames
        email_templates = filename_to_templates.get(name) or []
        catalog_entry = by_filename.get(name)

        entry: dict[str, Any] = {
            "path": path_key,
            "name": name,
            "type": ext_key,
            "used": used,
            "email_templates": email_templates,
        }
        if catalog_entry:
            entry["title"] = catalog_entry.get("title") or ""
            entry["title_ro"] = catalog_entry.get("title_ro") or ""
            entry["phase"] = catalog_entry.get("phase") or ""
            entry["phase_name"] = catalog_entry.get("phase_name") or ""
            entry["category"] = catalog_entry.get("category") or ""
            entry["min_role"] = catalog_entry.get("min_role") or ""
        result.append(entry)

    result.sort(key=lambda x: (x["path"].lower(), x["name"]))
    return result


def get_document_preview_path(path_param: str) -> Path | None:
    """
    Validate path_param (relative to documents/) and return full Path, or None if invalid.
    Prevents path traversal. Used for Settings → Documents preview.
    """
    path_param = (path_param or "").strip().replace("\\", "/")
    if not path_param or ".." in path_param or path_param.startswith("/"):
        return None
    if path_param.startswith("./"):
        path_param = path_param[2:]
    documents_root = _get_documents_root()
    full = (documents_root / path_param).resolve()
    root_resolved = documents_root.resolve()
    if not str(full).startswith(str(root_resolved)):
        return None
    if not full.is_file():
        return None
    return full
