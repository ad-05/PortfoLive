import pytest
from botocore.stub import ANY, Stubber
import boto3
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.render import render_portfolio
from app.schemas import PortfolioData
from app.storage.local import LocalStorage
from app.storage.s3 import S3Storage


class SpyStorage(LocalStorage):
    def __init__(self, *a):
        super().__init__(*a)
        self.invalidated = []

    def invalidate(self, username):
        self.invalidated.append(username)


@pytest.fixture
def ctx(tmp_path):
    settings = Settings(jwt_secret="test-secret-test-secret-test-secret-1234", admin_email="admin@x.com", data_dir=tmp_path)
    storage = SpyStorage(settings.sites_dir, "http://x")
    return TestClient(create_app(settings, storage)), storage, settings


def register(client, username, email, password="password123"):
    return client.post("/api/auth/register", json={"username": username, "email": email, "password": password})


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- rendering ----------
def test_render_escapes_html_and_drops_bad_links():
    data = PortfolioData(name="<script>alert(1)</script>", github="javascript:alert(1)")
    html = render_portfolio("minimal", data)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "javascript:" not in html


def test_social_links_are_normalised_not_dropped():
    d = PortfolioData(name="J", linkedin="linkedin.com/in/jane", github="janedoe")
    assert d.linkedin == "https://linkedin.com/in/jane"
    assert d.github == "https://github.com/janedoe"
    assert PortfolioData(name="J", linkedin="in/jane").linkedin == "https://www.linkedin.com/in/jane"
    assert PortfolioData(name="J", linkedin="https://www.linkedin.com/in/jane").linkedin == "https://www.linkedin.com/in/jane"
    assert PortfolioData(name="J", linkedin="javascript:alert(document.cookie)").linkedin == ""


@pytest.mark.parametrize("template", ["minimal", "midnight", "serif", "aurora", "terminal"])
def test_every_template_shows_contact_links(template):
    data = PortfolioData(name="Jane Doe", email="j@x.com", github="janedoe", linkedin="in/jane")
    html = render_portfolio(template, data)
    assert 'href="https://www.linkedin.com/in/jane"' in html and "LinkedIn" in html
    assert 'href="https://github.com/janedoe"' in html and 'href="mailto:j@x.com"' in html


def test_render_rejects_unknown_template():
    with pytest.raises(Exception, match="Unknown template"):
        render_portfolio("../../etc/passwd", PortfolioData(name="A"))


def test_name_is_required(ctx):
    client, *_ = ctx
    token = register(client, "jane", "jane@x.com").json()["token"]
    r = client.put("/api/portfolio", headers=auth(token), json={"template": "minimal", "data": {"name": "  "}})
    assert r.status_code == 400 and r.json()["error"] == "Name is required"


# ---------- full flow ----------
def test_register_publish_update_history_admin(ctx):
    client, storage, settings = ctx
    r = register(client, "jane", "jane@x.com")
    assert r.status_code == 201
    token = r.json()["token"]

    assert register(client, "jane", "j2@x.com").status_code == 409          # duplicate
    assert register(client, "admin", "a@x.com").status_code == 400          # reserved name
    assert register(client, "bob", "bob@x.com", "short").status_code == 400  # weak password

    h = auth(token)
    assert client.post("/api/publish", headers=h).status_code == 400         # nothing saved yet
    body = {"template": "midnight", "data": {
        "name": "Jane Doe", "skills": ["Python", "", "FastAPI"],
        "projects": [{"name": "PortfoLive", "link": "https://github.com/x", "description": "d"}, {"name": ""}],
    }}
    assert client.put("/api/portfolio", headers=h, json=body).json() == {"saved": True}
    saved = client.get("/api/portfolio", headers=h).json()
    assert saved["data"]["skills"] == ["Python", "FastAPI"]                  # blanks dropped
    assert len(saved["data"]["projects"]) == 1

    first = client.post("/api/publish", headers=h).json()
    assert first["action"] == "publish" and storage.invalidated == []        # no invalidation on first publish
    second = client.post("/api/publish", headers=h).json()
    assert second["action"] == "update" and storage.invalidated == ["jane"]  # targeted invalidation

    assert "Jane Doe" in (settings.sites_dir / "jane" / "index.html").read_text()
    assert client.get("/sites/jane/").status_code == 200                     # served locally
    assert len(client.get("/api/deployments", headers=h).json()) == 2

    assert client.get("/api/admin/stats", headers=h).status_code == 403
    admin = register(client, "boss", "admin@x.com").json()["token"]
    stats = client.get("/api/admin/stats", headers=auth(admin)).json()
    assert stats["success"] == 2 and stats["users"] == 2


def test_login_and_auth_required(ctx):
    client, *_ = ctx
    register(client, "jane", "jane@x.com")
    assert client.post("/api/auth/login", json={"email": "jane@x.com", "password": "wrongpass1"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "jane@x.com", "password": "password123"}).status_code == 200
    assert client.get("/api/portfolio").status_code == 401
    assert client.get("/api/me", headers=auth("garbage")).status_code == 401


def test_failed_deploy_is_recorded(ctx):
    client, storage, _ = ctx
    token = register(client, "jane", "jane@x.com").json()["token"]
    h = auth(token)
    client.put("/api/portfolio", headers=h, json={"template": "minimal", "data": {"name": "J"}})

    def boom(*_):
        raise RuntimeError("S3 down")
    storage.publish = boom
    with pytest.raises(RuntimeError):
        client.post("/api/publish", headers=h)
    history = client.get("/api/deployments", headers=h).json()
    assert history[0]["status"] == "failed" and "S3 down" in history[0]["error"]


def test_metrics_endpoint(ctx):
    client, *_ = ctx
    assert "portfolive_deployments_total" in client.get("/metrics").text


# ---------- boto3 S3 / CloudFront (stubbed, no AWS needed) ----------
def test_s3_storage_uploads_and_invalidates():
    s3 = boto3.client("s3", region_name="ap-south-1", aws_access_key_id="x", aws_secret_access_key="x")
    cf = boto3.client("cloudfront", region_name="us-east-1", aws_access_key_id="x", aws_secret_access_key="x")
    with Stubber(s3) as s3_stub, Stubber(cf) as cf_stub:
        s3_stub.add_response("put_object", {}, {
            "Bucket": "b", "Key": "jane/index.html", "Body": b"<html></html>",
            "ContentType": "text/html; charset=utf-8", "CacheControl": "public, max-age=300",
        })
        cf_stub.add_response("create_invalidation", {}, {
            "DistributionId": "DIST1",
            "InvalidationBatch": {"CallerReference": ANY,
                                  "Paths": {"Quantity": 1, "Items": ["/jane/*"]}},
        })
        storage = S3Storage("b", "DIST1", "https://d1.cloudfront.net/", s3_client=s3, cloudfront_client=cf)
        assert storage.publish("jane", "<html></html>") == "https://d1.cloudfront.net/jane/"
        storage.invalidate("jane")
        s3_stub.assert_no_pending_responses()
        cf_stub.assert_no_pending_responses()


def test_s3_storage_without_cloudfront_skips_invalidation():
    s3 = boto3.client("s3", region_name="ap-south-1", aws_access_key_id="x", aws_secret_access_key="x")
    with Stubber(s3) as s3_stub:
        s3_stub.add_response("put_object", {}, {
            "Bucket": "b", "Key": "jane/index.html", "Body": b"<html></html>",
            "ContentType": "text/html; charset=utf-8", "CacheControl": "public, max-age=300",
        })
        storage = S3Storage("b", "", "http://b.s3-website.ap-south-1.amazonaws.com/", s3_client=s3)
        assert storage.cloudfront is None
        assert storage.publish("jane", "<html></html>") == "http://b.s3-website.ap-south-1.amazonaws.com/jane/"
        storage.invalidate("jane")  # no CloudFront call, no error
        s3_stub.assert_no_pending_responses()


def test_s3_settings_need_url_but_not_distribution_id(monkeypatch):
    for k, v in {"STORAGE": "s3", "S3_BUCKET": "b", "CLOUDFRONT_URL": "http://b.s3-website.x"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("CLOUDFRONT_DISTRIBUTION_ID", raising=False)
    assert Settings.from_env().cloudfront_distribution_id == ""
    monkeypatch.delenv("CLOUDFRONT_URL")
    with pytest.raises(RuntimeError):
        Settings.from_env()


# ---------- security headers + HTTP metrics ----------
def test_security_headers_and_csp(ctx):
    client, *_ = ctx
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_generated_sites_get_script_free_csp(ctx):
    client, _, settings = ctx
    token = register(client, "jane", "jane@x.com").json()["token"]
    h = auth(token)
    client.put("/api/portfolio", headers=h, json={"template": "minimal", "data": {"name": "J"}})
    client.post("/api/publish", headers=h)
    csp = client.get("/sites/jane/").headers["content-security-policy"]
    assert "default-src 'none'" in csp and "script-src" not in csp


def test_api_responses_are_not_cached(ctx):
    client, *_ = ctx
    assert client.get("/api/templates").headers["cache-control"] == "no-store"


def test_http_metrics_use_route_templates(ctx):
    client, *_ = ctx
    client.get("/api/templates")
    text = client.get("/metrics").text
    assert 'portfolive_http_requests_total{method="GET",route="/api/templates",status="200"}' in text


def test_openapi_spec_available_for_dast(ctx):
    client, *_ = ctx
    assert client.get("/openapi.json").json()["info"]["title"] == "PortfoLive API"
