# PortfoLive

Automated personal-portfolio generator with self-service deployment, delivered with a full DevOps toolchain.
Users sign up, fill in a form, pick a template, click **Publish**, and get a live URL on AWS (S3 website hosting, or CloudFront when `enable_cloudfront=true`).

**New here? Open [`docs/SETUP_GUIDE.md`](docs/SETUP_GUIDE.md) and follow it from Part 1.**

## Architecture
```
User -> React -> FastAPI -> Jinja2 template -> boto3 -> S3 (-> CloudFront, optional) -> live URL
                    |-> SQLite (users, portfolios, deployment history)
                    |-> /metrics -> Prometheus -> Grafana, Alertmanager -> Slack

GitHub -> Jenkins: tests+coverage -> SonarQube gate -> Docker build -> OWASP ZAP -> push -> blue/green deploy -> Slack
Terraform (VPC, 3 EC2, S3, optional CloudFront, IAM)  ->  Ansible (Docker, Jenkins, SonarQube, k3s, monitoring)
```

## Where things are
| Path | What |
|---|---|
| `server/` | FastAPI backend: routes, Pydantic validation, Jinja2 templates, boto3 storage, tests |
| `client/` | React (Vite) frontend: login, live-preview editor, history, admin dashboard |
| `Dockerfile`, `docker-compose.yml` | Multi-stage image (with a test stage); local app + Prometheus + Alertmanager + Grafana |
| `Jenkinsfile`, `sonar-project.properties` | CI/CD: test, SonarQube, ZAP, blue/green deploy, Slack |
| `terraform/` | AWS infrastructure; writes the Ansible inventory and variables |
| `ansible/` | Roles: `common`, `docker`, `jenkins`, `sonarqube`, `k3s`, `k8s_bootstrap` |
| `k8s/app/` | Blue and green Deployments, autoscalers, Service, shared volume |
| `k8s/monitoring/`, `monitoring/` | Prometheus, Alertmanager, Grafana manifests, alert rules (with unit tests), dashboard |
| `.github/`, `docs/GIT_WORKFLOW.md` | PR template, issue templates, CODEOWNERS, branching rules |
| `Makefile` | `make help` lists shortcuts (test, up, tf-apply, ansible, ...) |

## Quick start (local, no AWS)
```bash
cd server && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt && pytest          # 13 tests
cd .. && docker compose up --build                       # http://localhost:4000, Grafana :3000
```
