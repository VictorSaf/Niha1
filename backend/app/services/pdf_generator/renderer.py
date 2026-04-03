"""
NIHA PDF Renderer — central WeasyPrint + Jinja2 rendering utility.

New PDF generation uses render_pdf(). Existing ReportLab generators are being migrated to this pipeline.
Static documents: called by generate_static_docs.py
Dynamic documents: called by individual *_generator.py wrappers
"""

from pathlib import Path
from datetime import date
import jinja2

_BASE_DIR = Path(__file__).parent
TEMPLATES_DIR = _BASE_DIR / "templates"
STYLES_DIR = _BASE_DIR / "styles"

_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=True,
)


def render_pdf(template_name: str, context: dict) -> bytes:
    """
    Render a Jinja2 HTML template to PDF bytes via WeasyPrint.

    Args:
        template_name: Template filename without extension (e.g. 'nda')
        context: Template variables dict

    Returns:
        PDF file as bytes
    """
    context = dict(context)  # don't mutate caller's dict
    context.setdefault("doc_date", date.today().strftime("%d %B %Y"))
    context.setdefault("doc_ref", "")

    html_string = _jinja_env.get_template(f"{template_name}.html.j2").render(**context)
    import weasyprint  # lazy: avoid import at package load so pytest can collect without weasyprint installed
    return weasyprint.HTML(
        string=html_string,
        base_url=str(STYLES_DIR),
    ).write_pdf()
