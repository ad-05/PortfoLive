from prometheus_client import Counter, Histogram

DEPLOYS = Counter("portfolive_deployments_total", "Deployments by status", ["status"])
DEPLOY_SECONDS = Histogram(
    "portfolive_deployment_duration_seconds", "Deployment duration",
    buckets=(0.1, 0.5, 1, 2, 5, 10),
)

HTTP_REQUESTS = Counter(
    "portfolive_http_requests_total", "HTTP requests", ["method", "route", "status"]
)
HTTP_SECONDS = Histogram(
    "portfolive_http_request_duration_seconds", "HTTP request duration", ["route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5),
)
