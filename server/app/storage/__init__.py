from typing import Protocol


class SiteStorage(Protocol):
    name: str

    def publish(self, username: str, html: str) -> str:
        """Store the site and return its public URL."""

    def invalidate(self, username: str) -> None:
        """Purge any CDN cache for this user's site."""
