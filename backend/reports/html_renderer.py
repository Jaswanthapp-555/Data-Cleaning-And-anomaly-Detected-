"""HTML report renderer using Jinja2."""
import os
import re
from jinja2 import Environment, FileSystemLoader


def render_html_report(report_data: dict) -> str:
    """Render the HTML report from the report data model."""
    template_dir = os.path.join(os.path.dirname(__file__), "..", "..", "templates")
    env = Environment(loader=FileSystemLoader(template_dir), autoescape=True)
    env.filters["fmt_val"] = _fmt_val
    env.filters["pct"] = lambda v: f"{v:.1f}%" if v is not None else "—"
    env.filters["score_class"] = _score_class
    env.filters["sev_class"] = _sev_class
    env.filters["wrap_text"] = _wrap_text

    template = env.get_template("report.html.j2")
    return template.render(data=report_data)


def _fmt_val(val):
    if val is None:
        return "—"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def _score_class(score):
    if score is None or not isinstance(score, (int, float)):
        return "score-na"
    if score >= 90:
        return "score-excellent"
    if score >= 75:
        return "score-good"
    if score >= 60:
        return "score-fair"
    if score >= 40:
        return "score-poor"
    return "score-critical"


def _sev_class(sev):
    mapping = {
        "critical": "sev-critical",
        "high": "sev-high",
        "medium": "sev-medium",
        "low": "sev-low",
        "info": "sev-info",
    }
    return mapping.get(str(sev).lower(), "sev-info")


def _wrap_text(text, max_len=18):
    if text is None:
        return "—"
    s = str(text)
    if not s.strip():
        return "—"
    def wrap_word(word):
        if len(word) <= max_len:
            return word
        if any(c in word for c in "_-./:@"):
            return re.sub(r'([_\-./:@])', r'\1 ', word)
        return " ".join([word[i:i+max_len] for i in range(0, len(word), max_len)])
    return re.sub(r'\S+', lambda m: wrap_word(m.group(0)), s)
