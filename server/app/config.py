import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    jwt_secret: str = "dev-only-change-me"
    admin_email: str = ""
    data_dir: Path = Path("data")
    port: int = 4000
    storage: str = "local"                # "local" (dev) or "s3" (prod)
    public_base_url: str = ""
    s3_bucket: str = ""
    cloudfront_distribution_id: str = ""  # optional; empty = serve straight from S3 website hosting
    cloudfront_url: str = ""              # public base URL (CloudFront, or the S3 website endpoint)
    aws_region: str = "ap-south-1"
    production: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "portfolive.db"

    @property
    def sites_dir(self) -> Path:
        return self.data_dir / "sites"

    @classmethod
    def from_env(cls) -> "Settings":
        e = os.environ
        s = cls(
            jwt_secret=e.get("JWT_SECRET", cls.jwt_secret),
            admin_email=e.get("ADMIN_EMAIL", ""),
            data_dir=Path(e.get("DATA_DIR", "data")),
            port=int(e.get("PORT", 4000)),
            storage=e.get("STORAGE", "local"),
            public_base_url=e.get("PUBLIC_BASE_URL", ""),
            s3_bucket=e.get("S3_BUCKET", ""),
            cloudfront_distribution_id=e.get("CLOUDFRONT_DISTRIBUTION_ID", ""),
            cloudfront_url=e.get("CLOUDFRONT_URL", ""),
            aws_region=e.get("AWS_REGION", "ap-south-1"),
            production=e.get("APP_ENV", "") == "production",
        )
        if s.production and (s.jwt_secret == cls.jwt_secret or len(s.jwt_secret) < 32):
            raise RuntimeError("JWT_SECRET must be set (32+ chars) in production")
        # CLOUDFRONT_DISTRIBUTION_ID is optional: empty means "no CloudFront", and CLOUDFRONT_URL is then the S3 website URL.
        if s.storage == "s3" and not (s.s3_bucket and s.cloudfront_url):
            raise RuntimeError("STORAGE=s3 needs S3_BUCKET and CLOUDFRONT_URL (the public base URL of the sites)")
        return s
