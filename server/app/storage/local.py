"""Dev storage: writes the site to disk; FastAPI serves it at /sites/<user>/."""
from pathlib import Path


class LocalStorage:
    name = "local"

    def __init__(self, root: Path, base_url: str):
        self.root, self.base_url = root, base_url.rstrip("/")

    def publish(self, username: str, html: str) -> str:
        site = self.root / username
        site.mkdir(parents=True, exist_ok=True)
        (site / "index.html").write_text(html, encoding="utf-8")
        return f"{self.base_url}/sites/{username}/"

    def invalidate(self, username: str) -> None:
        pass  # no CDN locally
