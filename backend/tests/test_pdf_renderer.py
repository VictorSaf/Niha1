"""Tests for the HTML + WeasyPrint PDF renderer."""
import pytest

_has_weasyprint = False
try:
    import weasyprint  # noqa: F401
    _has_weasyprint = True
except (ImportError, OSError):
    # OSError when weasyprint loads but system libs (e.g. libgobject) are missing
    pass

_skip_weasyprint = pytest.mark.skipif(not _has_weasyprint, reason="WeasyPrint not installed")

# Defer imports so collection succeeds when weasyprint fails to load (e.g. missing libgobject)
if _has_weasyprint:
    from app.services.pdf_generator.renderer import render_pdf  # noqa: E402
    from app.services.pdf_generator.nda_generator import generate_nda_pdf  # noqa: E402
else:
    render_pdf = None
    generate_nda_pdf = None


@_skip_weasyprint
def test_render_pdf_returns_valid_pdf():
    """render_pdf should return bytes starting with PDF magic number."""
    result = render_pdf("board_resolution", {})
    assert isinstance(result, bytes), "Expected bytes output"
    assert result[:4] == b"%PDF", f"Expected PDF magic number, got: {result[:20]}"
    assert len(result) > 5_000, f"PDF too small ({len(result)} bytes) — likely empty or broken"


@_skip_weasyprint
def test_render_pdf_with_doc_ref():
    """doc_ref context variable is accepted without errors."""
    result = render_pdf("board_resolution", {"doc_ref": "NIHA-BR-2026-001"})
    assert result[:4] == b"%PDF"
    assert len(result) > 5_000


@_skip_weasyprint
def test_render_pdf_with_explicit_doc_date():
    """Explicit doc_date overrides the default today() value without errors."""
    result = render_pdf("board_resolution", {"doc_date": "01 January 2026"})
    assert result[:4] == b"%PDF"
    assert len(result) > 5_000


@_skip_weasyprint
def test_nda_generator_returns_pdf():
    """NDA generator produces a valid PDF."""
    result = generate_nda_pdf(
        client_entity_name="Test Corp Ltd",
        client_representative="John Smith",
        client_email="john@testcorp.com",
    )
    assert result[:4] == b"%PDF"
    assert len(result) > 10_000


@_skip_weasyprint
def test_nda_generator_with_all_params():
    """NDA generator accepts all optional parameters."""
    from datetime import date
    result = generate_nda_pdf(
        client_entity_name="Acme Corp",
        client_entity_type="Limited Company",
        client_jurisdiction="Hong Kong SAR",
        client_representative="Jane Doe",
        client_email="jane@acme.com",
        effective_date=date(2026, 1, 1),
        doc_ref="NIHA-NDA-2026-TEST",
    )
    assert result[:4] == b"%PDF"
    assert len(result) > 10_000


@_skip_weasyprint
def test_nda_generator_signature_preserved():
    """Function signature must remain identical for API compatibility."""
    import inspect
    sig = inspect.signature(generate_nda_pdf)
    params = list(sig.parameters.keys())
    expected = ["client_entity_name", "client_entity_type", "client_jurisdiction",
                "client_representative", "client_email", "effective_date",
                "doc_ref", "output_path"]
    assert params == expected, f"Signature changed — got {params}, expected {expected}"


_has_reportlab = False
try:
    import reportlab  # noqa: F401
    _has_reportlab = True
except ImportError:
    pass

_skip_reportlab = pytest.mark.skipif(not _has_reportlab, reason="ReportLab not installed")


@_skip_reportlab
def test_msa_generator_returns_pdf():
    from app.services.pdf_generator.msa_generator import generate_msa_pdf
    result = generate_msa_pdf(
        client_entity_name="Test Corp Ltd",
        client_representative="John Smith",
        client_email="john@testcorp.com",
    )
    assert result[:4] == b"%PDF"
    assert len(result) > 10_000


@_skip_reportlab
def test_msa_generator_signature_preserved():
    import inspect
    from app.services.pdf_generator.msa_generator import generate_msa_pdf
    sig = inspect.signature(generate_msa_pdf)
    params = list(sig.parameters.keys())
    expected = ["client_entity_name", "client_entity_type", "client_jurisdiction",
                "client_representative", "client_email", "effective_date",
                "doc_ref", "output_path"]
    assert params == expected, f"Signature changed: {params}"


@_skip_reportlab
def test_fee_schedule_generator_returns_pdf():
    from app.services.pdf_generator.fee_schedule_generator import generate_fee_schedule_pdf
    result = generate_fee_schedule_pdf(
        client_entity_name="Test Corp Ltd",
        client_representative="John Smith",
        client_email="john@testcorp.com",
    )
    assert result[:4] == b"%PDF"
    assert len(result) > 10_000


@_skip_reportlab
def test_fee_schedule_generator_signature_preserved():
    import inspect
    from app.services.pdf_generator.fee_schedule_generator import generate_fee_schedule_pdf
    sig = inspect.signature(generate_fee_schedule_pdf)
    params = list(sig.parameters.keys())
    expected = ["client_entity_name", "client_representative", "client_email",
                "effective_date", "doc_ref", "output_path"]
    assert params == expected, f"Signature changed: {params}"
