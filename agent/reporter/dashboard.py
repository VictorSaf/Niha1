# agent/reporter/dashboard.py
import time
from pathlib import Path
from jinja2 import Environment, FileSystemLoader


def generate_report(
    scenario: str,
    model: str,
    results: list[dict],
    screenshots: list[dict],
    elapsed: float,
    iteration_count: int,
    output_path: str = "/tmp/niha_agent/report.html"
) -> str:
    """Generate HTML report and return path."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)), autoescape=True)
    template = env.get_template("report.html.j2")

    passed = sum(1 for r in results if r["status"] == "PASS")

    html = template.render(
        scenario=scenario,
        model=model,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        elapsed=f"{elapsed:.1f}",
        success=passed == len(results) and len(results) > 0,
        passed=passed,
        total=len(results),
        results=results,
        screenshots=screenshots,
        screenshot_count=len(screenshots),
        iteration_count=iteration_count,
    )

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(html)
    return output_path
