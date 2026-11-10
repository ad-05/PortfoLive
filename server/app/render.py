from pathlib import Path

from fastapi import HTTPException
from jinja2 import Environment, FileSystemLoader

from .schemas import PortfolioData

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
SUFFIX = ".html.j2"

# autoescape=True: every {{ value }} is HTML-escaped -> user input can't inject markup/scripts
_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=True, trim_blocks=True, lstrip_blocks=True)

# Files starting with "_" are shared bases, not selectable templates.
TEMPLATES = sorted(p.name.removesuffix(SUFFIX) for p in TEMPLATE_DIR.glob(f"[!_]*{SUFFIX}"))


def render_portfolio(template: str, data: PortfolioData) -> str:
    if template not in TEMPLATES:  # whitelist: also blocks path traversal
        raise HTTPException(400, f'Unknown template "{template}"')
    return _env.get_template(template + SUFFIX).render(**data.cleaned().model_dump())
