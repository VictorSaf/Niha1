"""
Unit tests for docs_settings_service: list_documents and get_preview_path.
Run from backend container: pytest tests/test_docs_settings_service.py -v
"""

from pathlib import Path
from unittest.mock import patch

import app.services.docs_settings_service as docs_settings_service


class TestGetPreviewPath:
    """Tests for get_preview_path path validation and resolution."""

    def test_returns_none_for_empty_path(self):
        """Empty or whitespace path is rejected."""
        docs_root = Path("/fake/docs")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=docs_root):
            assert docs_settings_service.get_preview_path("") is None
            assert docs_settings_service.get_preview_path("   ") is None

    def test_returns_none_for_path_traversal(self):
        """Paths containing .. are rejected."""
        docs_root = Path("/fake/docs")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=docs_root):
            assert docs_settings_service.get_preview_path("../etc/passwd") is None
            assert docs_settings_service.get_preview_path("features/../../secrets.md") is None

    def test_returns_none_for_absolute_path(self):
        """Leading slash is rejected."""
        docs_root = Path("/fake/docs")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=docs_root):
            assert docs_settings_service.get_preview_path("/features/plan.md") is None

    def test_returns_none_for_nonexistent_file(self, tmp_path):
        """Path under docs/ that is not a file returns None."""
        with patch.object(docs_settings_service, "_get_docs_root", return_value=tmp_path):
            assert docs_settings_service.get_preview_path("missing.md") is None
            (tmp_path / "sub").mkdir()
            assert docs_settings_service.get_preview_path("sub/also_missing.pdf") is None

    def test_returns_path_for_valid_file_under_docs(self, tmp_path):
        """Valid relative path to existing file returns resolved Path."""
        (tmp_path / "features").mkdir()
        (tmp_path / "features" / "0056_PLAN.md").write_text("# Plan")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=tmp_path):
            result = docs_settings_service.get_preview_path("features/0056_PLAN.md")
        assert result is not None
        assert result.name == "0056_PLAN.md"
        assert result.read_text() == "# Plan"

    def test_normalizes_leading_dot_slash(self, tmp_path):
        """Path starting with ./ is accepted and normalized."""
        (tmp_path / "readme.md").write_text("Hi")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=tmp_path):
            result = docs_settings_service.get_preview_path("./readme.md")
        assert result is not None
        assert result.name == "readme.md"


class TestListDocuments:
    """Tests for list_documents shape, filtering, and manifest merge."""

    def test_returns_empty_list_when_docs_root_missing(self):
        """When docs root is not a directory, returns empty list."""
        with patch.object(docs_settings_service, "_get_docs_root", return_value=Path("/nonexistent/docs")):
            result = docs_settings_service.list_documents()
        assert result == []

    def test_returns_only_md_and_pdf_sorted(self, tmp_path):
        """Only .md and .pdf files are listed; result is sorted by path."""
        (tmp_path / "a.md").write_text("")
        (tmp_path / "b.pdf").write_text("")
        (tmp_path / "ignore.txt").write_text("")
        (tmp_path / "ignore.html").write_text("")
        with patch("app.services.docs_settings_service._get_docs_root", return_value=tmp_path):
            result = docs_settings_service.list_documents()
        assert len(result) == 2
        paths = [r["path"] for r in result]
        assert paths == sorted(paths)
        assert set(p["type"] for p in result) == {"md", "pdf"}
        assert all("path" in r and "name" in r and "type" in r and "role" in r and "email_templates" in r for r in result)

    def test_respects_max_depth(self, tmp_path):
        """Files deeper than DOCS_MAX_DEPTH are excluded."""
        (tmp_path / "one").mkdir()
        (tmp_path / "one" / "two").mkdir()
        (tmp_path / "one" / "two" / "three").mkdir()
        (tmp_path / "one" / "two" / "three" / "deep.md").write_text("")
        with patch.object(docs_settings_service, "_get_docs_root", return_value=tmp_path):
            result = docs_settings_service.list_documents()
        # rel.parts = ('one','two','three','deep.md'), len=4 > DOCS_MAX_DEPTH (3) so excluded
        assert len(result) == 0

    def test_manifest_merge_adds_role_and_email_templates(self, tmp_path):
        """When manifest exists, role and email_templates are merged into entries."""
        (tmp_path / "doc1.md").write_text("")
        (tmp_path / "doc2.md").write_text("")
        (tmp_path / "documents_manifest.json").write_text(
            '{"doc1.md": {"role": "APPROVED", "email_templates": ["account_approved.html"]}}'
        )
        with patch("app.services.docs_settings_service._get_docs_root", return_value=tmp_path):
            result = docs_settings_service.list_documents()
        by_path = {r["path"]: r for r in result}
        assert by_path["doc1.md"]["role"] == "APPROVED"
        assert by_path["doc1.md"]["email_templates"] == ["account_approved.html"]
        assert by_path["doc2.md"]["role"] is None
        assert by_path["doc2.md"]["email_templates"] == []


class TestGetDocumentPreviewPath:
    """Tests for get_document_preview_path (documents/ root)."""

    def test_returns_none_for_empty_or_traversal(self):
        """Empty, whitespace, .. and absolute are rejected."""
        root = Path("/fake/documents")
        with patch.object(docs_settings_service, "_get_documents_root", return_value=root):
            assert docs_settings_service.get_document_preview_path("") is None
            assert docs_settings_service.get_document_preview_path("../etc/passwd") is None
            assert docs_settings_service.get_document_preview_path("/foo.pdf") is None

    def test_returns_path_for_valid_file_under_documents(self, tmp_path):
        """Valid relative path to existing file under documents/ returns Path."""
        (tmp_path / "NIHA_Test.pdf").write_bytes(b"%PDF-1.4")
        with patch.object(docs_settings_service, "_get_documents_root", return_value=tmp_path):
            result = docs_settings_service.get_document_preview_path("NIHA_Test.pdf")
        assert result is not None
        assert result.name == "NIHA_Test.pdf"


class TestListDocumentsFromDocumentsFolder:
    """Tests for list_documents_from_documents_folder."""

    def test_returns_empty_when_documents_root_missing(self):
        """When documents root is not a directory, returns empty list."""
        with patch.object(
            docs_settings_service, "_get_documents_root", return_value=Path("/nonexistent/documents")
        ):
            result = docs_settings_service.list_documents_from_documents_folder()
        assert result == []

    def test_returns_pdf_and_docx_with_used_and_email_templates(self, tmp_path):
        """Lists .pdf and .docx; used and email_templates come from catalog/attachments."""
        (tmp_path / "NIHA_Bank_Confirmation_Letters.pdf").write_bytes(b"%PDF")
        (tmp_path / "other.pdf").write_bytes(b"%PDF")
        with patch.object(docs_settings_service, "_get_documents_root", return_value=tmp_path):
            result = docs_settings_service.list_documents_from_documents_folder()
        by_name = {r["name"]: r for r in result}
        assert "NIHA_Bank_Confirmation_Letters.pdf" in by_name
        assert by_name["NIHA_Bank_Confirmation_Letters.pdf"]["used"] is True
        assert "deposit_announced.html" in by_name["NIHA_Bank_Confirmation_Letters.pdf"]["email_templates"]
        assert by_name["other.pdf"]["used"] is False
        assert by_name["other.pdf"]["email_templates"] == []
