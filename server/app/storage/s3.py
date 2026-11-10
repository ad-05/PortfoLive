"""Prod storage: one shared S3 bucket (a prefix per user), optionally behind a CloudFront distribution.

Without a distribution id the sites are served from S3 website hosting and there is no cache to purge."""
import time

import boto3


class S3Storage:
    name = "s3"

    def __init__(self, bucket: str, distribution_id: str, cdn_url: str, region: str = "ap-south-1",
                 s3_client=None, cloudfront_client=None):
        # Clients are injectable so tests can stub AWS without network calls.
        self.bucket, self.distribution_id = bucket, distribution_id
        self.cdn_url = cdn_url.rstrip("/")
        self.s3 = s3_client or boto3.client("s3", region_name=region)
        self.cloudfront = None
        if distribution_id:
            self.cloudfront = cloudfront_client or boto3.client("cloudfront", region_name=region)

    def publish(self, username: str, html: str) -> str:
        self.s3.put_object(
            Bucket=self.bucket,
            Key=f"{username}/index.html",
            Body=html.encode("utf-8"),
            ContentType="text/html; charset=utf-8",
            CacheControl="public, max-age=300",
        )
        return f"{self.cdn_url}/{username}/"

    def invalidate(self, username: str) -> None:
        if not self.distribution_id:  # S3 website mode: nothing cached in front of the bucket
            return
        # Targeted: only this user's path, not the whole distribution.
        self.cloudfront.create_invalidation(
            DistributionId=self.distribution_id,
            InvalidationBatch={
                "CallerReference": f"{username}-{time.time_ns()}",
                "Paths": {"Quantity": 1, "Items": [f"/{username}/*"]},
            },
        )
