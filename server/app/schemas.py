"""Pydantic models for the portfolio form. Input is trimmed, length-capped and URL-checked here,
so everything downstream (templates, storage) only ever sees clean data."""
import re
from typing import Annotated

from pydantic import AfterValidator, BaseModel, BeforeValidator, Field


def _clean(n: int):
    return lambda v: ("" if v is None else str(v)).strip()[:n]


def _url(v) -> str:
    """Accepts https://x, http://x, or a bare domain like linkedin.com/in/jane (https:// is added).
    Any other scheme (javascript:, data:, ftp:...) is dropped, so it can never reach an href."""
    v = _clean(200)(v)
    if re.match(r"^https?://\S+$", v, re.I):
        return v
    if re.match(r"^[a-z][a-z0-9+.\-]*:", v, re.I):  # some other scheme -> blocked
        return ""
    if re.match(r"^(www\.)?[\w\-]+(\.[\w\-]+)+(/\S*)?$", v, re.I):  # bare domain
        return "https://" + v
    return ""


def _social(base: str, bare: str = ""):
    """Like _url, but also accepts just the handle (e.g. 'janedoe' or 'in/janedoe')."""
    def fix(v) -> str:
        v = _clean(200)(v).lstrip("@")
        if re.match(r"^[\w\-.]+(/[\w\-.%]+)*/?$", v) and "." not in v.split("/")[0]:
            return base + (bare if "/" not in v else "") + v  # a bare handle, not a domain
        return _url(v)
    return fix


def _compact(v):
    return [x for x in (v or []) if x not in ("", None)] if isinstance(v, list) else []


def _required(v: str) -> str:
    if not v:
        raise ValueError("Name is required")
    return v


Short = lambda n: Annotated[str, BeforeValidator(_clean(n))]  # noqa: E731
Url = Annotated[str, BeforeValidator(_url)]
GithubUrl = Annotated[str, BeforeValidator(_social("https://github.com/"))]
LinkedinUrl = Annotated[str, BeforeValidator(_social("https://www.linkedin.com/", "in/"))]


class Project(BaseModel):
    name: Short(80) = ""
    description: Short(400) = ""
    link: Url = ""


class Education(BaseModel):
    school: Short(120) = ""
    degree: Short(120) = ""
    years: Short(30) = ""


class PortfolioData(BaseModel):
    name: Annotated[str, BeforeValidator(_clean(80)), AfterValidator(_required)]
    title: Short(100) = ""
    bio: Short(1500) = ""
    email: Short(120) = ""
    github: GithubUrl = ""      # https://github.com/x, github.com/x or just x
    linkedin: LinkedinUrl = ""  # https://linkedin.com/in/x, linkedin.com/in/x or in/x
    skills: Annotated[list[Short(40)], BeforeValidator(lambda v: _compact([_clean(40)(x) for x in v]) if isinstance(v, list) else []), Field(max_length=30)] = []
    projects: Annotated[list[Project], BeforeValidator(_compact), Field(max_length=12)] = []
    education: Annotated[list[Education], BeforeValidator(_compact), Field(max_length=8)] = []

    def cleaned(self) -> "PortfolioData":
        """Drops half-empty entries (a project with no name, a school with no name)."""
        self.projects = [p for p in self.projects if p.name]
        self.education = [e for e in self.education if e.school]
        return self


class PortfolioIn(BaseModel):
    template: str = "minimal"
    data: PortfolioData


class PreviewIn(PortfolioIn):
    pass


class RegisterIn(BaseModel):
    username: str = ""
    email: str = ""
    password: str = ""


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""
