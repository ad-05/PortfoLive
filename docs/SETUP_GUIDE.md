# PortfoLive: Complete Setup Guide (from zero)

Follow the parts **in order**. Each part ends with a **Check** so you know it worked before moving on.
Parts 1-3 cost nothing. Parts 4+ create AWS resources that **cost money** (see Part 0).

## Part 0: What you are building, and what it costs

```
You push code to GitHub
  -> Jenkins (EC2) notices it and runs the pipeline:
       tests + coverage -> SonarQube scan + quality gate -> Docker image -> OWASP ZAP scan
       -> push to Docker Hub -> blue/green deploy to Kubernetes -> Slack message
  -> Kubernetes (k3s on EC2) runs the app (2 colors x 2+ pods, autoscaling)
  -> Users publish portfolios -> S3 -> CloudFront -> live URL
Prometheus + Grafana + Alertmanager watch the app and all 3 servers and alert Slack.
```

| Piece | Where it runs | Created by |
|---|---|---|
| VPC, subnet, 3 EC2 servers, S3, CloudFront, IAM | AWS | **Terraform** |
| Docker, Jenkins, SonarQube, k3s, monitoring | the 3 servers | **Ansible** |
| Build, test, scan, deploy | Jenkins | **Jenkinsfile** |

**Cost:** three EC2 servers (2x t3.medium, 1x t3.large) run roughly **$4-5 per day** while on, plus small
S3/CloudFront/storage charges. Check current prices on the AWS pricing page. **Stop or destroy them when you are
not working** (Part 13). Set a budget alert in Part 4 so you are warned.

**Time:** about 3-4 hours for a first full run, mostly waiting for installs.

**Honest note:** the application code and tests, the alert rules, and the Ansible/Terraform syntax were checked
automatically. The full AWS + Jenkins + Kubernetes chain could not be run end to end by the author, so **expect
to fix small things on your first run.** Part 14 lists likely problems and fixes.

---

## Part 1: Install tools on your laptop

| Tool | Version | Used for |
|---|---|---|
| Git | any recent | version control |
| Python | 3.11 or newer | backend, running tests |
| Node.js | 20 LTS | React frontend |
| Docker Desktop | recent | local containers |
| Terraform | 1.5 or newer | AWS infrastructure |
| Ansible | 2.15 or newer | server configuration |
| AWS CLI v2 | recent | AWS login |

- **Windows:** install **WSL2 (Ubuntu)** and do *everything in Part 4 onward inside the Ubuntu terminal*. Ansible does
  not run natively on Windows. Docker Desktop has a "WSL integration" switch in Settings; turn it on.
- **macOS:** `brew install git python node terraform ansible awscli` and install Docker Desktop.
- **Ubuntu/WSL:** `sudo apt install git python3-venv nodejs npm ansible awscli`; get Terraform from HashiCorp's apt repo.

**Check:** `git --version`, `python3 --version`, `node --version`, `docker --version`, `terraform version`,
`ansible --version`, `aws --version` all print versions.

---

## Part 2: Run everything locally first (no AWS)

Unzip the project and open a terminal in the `portfolive` folder.

**2a. Backend tests**
```bash
cd server
python3 -m venv .venv && source .venv/bin/activate     # Windows (non-WSL): .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest                                                  # expect: 13 passed, ~93% coverage
```

**2b. Run the app (two terminals)**
```bash
# terminal 1 (inside server/, venv active)
uvicorn app.main:create_app --factory --reload --port 4000
# terminal 2
cd client && npm install && npm run dev                 # open http://localhost:5173
```
Sign up, fill in the form, pick a template, click **Publish**. Locally the site is saved on disk and served at
`http://localhost:4000/sites/<your-username>/`. API docs: `http://localhost:4000/docs`.

**2c. The full local stack with monitoring**
```bash
docker compose up --build
```
| URL | What |
|---|---|
| http://localhost:4000 | the app (register with `admin@example.com` to unlock the **Admin** tab) |
| http://localhost:9090 | Prometheus (Status > Rules shows the 9 alert rules) |
| http://localhost:9093 | Alertmanager |
| http://localhost:3000 | Grafana (`admin` / `admin`), dashboard **PortfoLive Overview** is pre-loaded |

**Check:** you can publish a portfolio, and Grafana shows non-empty panels after you click around for a minute.
Stop with `Ctrl+C` then `docker compose down`.

---

## Part 3: GitHub (version control and collaboration)

1. Create a GitHub account if needed. Click **New repository**: name `portfolive`, **Private** (recommended), no README.
2. In the project folder:
   ```bash
   git init -b main
   git add -A && git status        # confirm NO secrets files appear (.gitignore handles them)
   git commit -m "Initial commit: PortfoLive"
   git remote add origin https://github.com/<you>/portfolive.git
   git push -u origin main
   ```
   GitHub asks you to log in; use a **Personal Access Token** as the password
   (GitHub > Settings > Developer settings > Personal access tokens > Fine-grained, give it *Contents: read & write*).
3. **Add teammates:** repo **Settings > Collaborators > Add people**.
4. **Edit `.github/CODEOWNERS`**: replace `@your-github-username` with real handles.
5. **Protect `main`** (repo admin): Settings > Branches > *Add branch ruleset* for `main`:
   require a pull request, require 1 approval, require review from Code Owners, block force pushes.
   *(Private repos on a free personal account may not enforce rules; GitHub will say so. The workflow is still graded by your commit/PR history.)*
6. Optional: create a **Projects** board and issues from the templates in `.github/ISSUE_TEMPLATE`.
7. Practise the workflow once, as described in `docs/GIT_WORKFLOW.md` (feature branch, PR, review, squash-merge).
   Keep using PRs for everything afterward; your commit history is part of the evidence.

**Check:** the code is on GitHub and a test PR merged.

---

## Part 4: AWS account preparation

1. Create an AWS account. **Do not use the root user for daily work.**
2. IAM > Users > Create user `portfolive-admin` > attach policy `AdministratorAccess` (fine for a class project) >
   Security credentials > **Create access key** (use case: CLI). Save the two values.
3. `aws configure` and enter the access key, secret, region `ap-south-1` (Mumbai; any region works), output `json`.
   Verify: `aws sts get-caller-identity`.
4. **Budget alert:** Billing > Budgets > Create budget > *Zero spend* or a $20 monthly budget, with your email.
5. **EC2 key pair (for SSH):** EC2 console > *Key Pairs* > Create key pair, name `portfolive`, type RSA, format `.pem`.
   Move the download to `~/.ssh/portfolive.pem` and run `chmod 400 ~/.ssh/portfolive.pem`.
   *(WSL: copy it into the Linux home first, since `chmod` does not work on `/mnt/c`.)*
6. Find your public IP: https://checkip.amazonaws.com (for example `203.0.113.5`). You will use `203.0.113.5/32`.
   **If your IP changes** (new network, router restart), re-run `terraform apply` with the new value.

**Check:** `aws sts get-caller-identity` shows your account.

---

## Part 5: Terraform, create the cloud infrastructure

```bash
cd terraform
terraform init
terraform apply \
  -var bucket_name=portfolive-<your-unique-suffix> \
  -var key_name=portfolive \
  -var admin_cidr=<your-ip>/32 \
  -var ssh_private_key_path=~/.ssh/portfolive.pem
```
Add `-var enable_cloudfront=true` only once AWS has verified your account for CloudFront (new accounts get a
"verification required" error). The default is **off**: published sites are then served from S3 website hosting
(public bucket, HTTP only, no CDN cache). Turn it on later by re-running `terraform apply` with the same variables
plus `-var enable_cloudfront=true`, then re-run the Ansible playbook so the app picks up the new URL.
Type `yes`. It takes about 5 minutes. `bucket_name` must be globally unique, lowercase.

What it created: a VPC, subnet, internet gateway, route table, a security group that only lets **your IP** reach
SSH/Jenkins/SonarQube/Grafana/etc., three Ubuntu EC2 servers, an S3 bucket (private behind CloudFront, or public website hosting when CloudFront is off), an optional CloudFront distribution, and a
least-privilege IAM user for the app. It also wrote **`ansible/inventory.ini`** (server IPs) and
**`ansible/group_vars/all/terraform.yml`** (bucket name, CloudFront ID, app AWS keys). Both are git-ignored.

**Check:** `terraform output server_public_ips` shows 3 IPs, and `ansible/inventory.ini` exists.
Test SSH: `ssh -i ~/.ssh/portfolive.pem ubuntu@<jenkins-ip>` (type `exit` to leave).

---

## Part 6: Ansible, install and configure the servers

```bash
cd ../ansible
cp group_vars/all/secrets.yml.example group_vars/all/secrets.yml
```
Edit `secrets.yml` and replace every `CHANGE_ME`:
- `jwt_secret`: run `openssl rand -hex 32` and paste the result
- `admin_email`: the email you will register with in the app to get the Admin tab
- `grafana_admin_password`, `sonar_db_password`: choose strong passwords
- `slack_webhook_url`: leave the placeholder for now; set it in Part 10

(Optional but recommended: `ansible-vault encrypt group_vars/all/secrets.yml`, then add `--ask-vault-pass` below.)

```bash
ansible all -m ping          # expect 3x "pong"
ansible-playbook site.yml    # 15-25 minutes
```
The playbook refuses to start if secrets are missing or still `CHANGE_ME`; that is intentional.

It installs Docker everywhere, node_exporter (host metrics) everywhere, Jenkins + kubectl on the Jenkins server,
SonarQube + PostgreSQL on the SonarQube server, and k3s + Prometheus + Alertmanager + Grafana + the app's Secret on
the Kubernetes server. At the end it prints the **Jenkins unlock password** and a list of URLs.

It also saves the Kubernetes login files to `ansible/artifacts/` (`k3s-private.yaml` for Jenkins,
`k3s-public.yaml` for your laptop). **Treat them like passwords.**

**Check:** open the URLs printed at the end:
- Jenkins `http://<jenkins-ip>:8080` shows "Unlock Jenkins"
- SonarQube `http://<sonar-ip>:9000` shows a login page
- Prometheus `http://<k8s-ip>:30090/targets` shows `node` targets UP (the `portfolive` job stays empty until the first deploy)
- Grafana `http://<k8s-ip>:30300`, login `admin` + your password, dashboard **PortfoLive Overview**

---

## Part 7: Configure SonarQube (about 5 minutes, manual)

1. Open `http://<sonar-ip>:9000`, log in `admin` / `admin`, set a new password when asked.
2. Top right avatar > **My Account > Security > Generate Tokens**: name `jenkins`, type **User token**,
   expiry 90 days > Generate. **Copy it now**, it is shown once.
3. **Webhook (required, otherwise the quality gate step in Jenkins hangs):** Administration > Configuration >
   **Webhooks** > Create: name `jenkins`, URL `http://<jenkins-PRIVATE-ip>:8080/sonarqube-webhook/`
   (the private IP is in `ansible/inventory.ini`, field `private_ip`), leave secret empty > Create.

---

## Part 8: Configure Docker Hub

1. Create an account at hub.docker.com. Note your **username**.
2. Account Settings > Personal access tokens > Generate, permission *Read & Write*. Copy it.
3. After the first successful push (Part 9), open the new `portfolive` repository on Docker Hub > Settings and make it
   **Public** if it is not already. (Kubernetes pulls anonymously, so a private repo would fail with
   `ImagePullBackOff`. Verify the visibility setting yourself; defaults on Docker Hub can change.)

---

## Part 9: Configure Jenkins and run the pipeline

1. Open `http://<jenkins-ip>:8080`, paste the unlock password (re-print it with
   `ssh -i ~/.ssh/portfolive.pem ubuntu@<jenkins-ip> sudo cat /var/lib/jenkins/secrets/initialAdminPassword`).
2. Choose **Install suggested plugins**, then create your admin user.
3. **Install one more plugin:** Manage Jenkins > Plugins > Available > search **SonarQube Scanner** > install, tick restart.
4. **Add credentials:** Manage Jenkins > Credentials > System > Global > Add Credentials. Create these four
   (the **ID** must match exactly):

   | Kind | ID | Value |
   |---|---|---|
   | Username with password | `dockerhub` | your Docker Hub username + the access token as password |
   | Secret file | `kubeconfig` | upload `ansible/artifacts/k3s-private.yaml` |
   | Secret text | `sonar-token` | the SonarQube token from Part 7 |
   | Secret text | `slack-webhook` | your webhook URL (use `https://example.com` until Part 10) |

5. **Connect SonarQube:** Manage Jenkins > System > *SonarQube servers* > Add: Name **`sonarqube`** (exact),
   Server URL `http://<sonar-PRIVATE-ip>:9000`, Server authentication token = `sonar-token`. Save.
6. **Create the pipeline:** New Item > name `portfolive` > **Pipeline** > OK. Under *Pipeline*:
   Definition **Pipeline script from SCM**, SCM **Git**, Repository URL = your GitHub URL.
   If the repo is private, add a credential (*Username with password*: GitHub username + the Personal Access Token).
   Branch `*/main`, Script Path `Jenkinsfile`. Save.
7. Click **Build Now**. Watch **Console Output**. Stages run: Prepare, Unit tests + coverage, SonarQube analysis,
   Quality gate, Build image, DAST: OWASP ZAP, Push image, Deploy (blue/green).

After this, Jenkins polls GitHub every ~3 minutes and builds automatically on new commits to `main`.
(Polling is used on purpose so Jenkins' port never has to be opened to the internet. For instant webhooks you would
open port 8080 to GitHub's IP ranges, which is less secure.)

**Check:**
- Build is green; **Build Artifacts** contains `zap-reports/zap-baseline.html` and `zap-api.html`.
- SonarQube shows project `portfolive` with coverage near 90%.
- `http://<k8s-ip>:30080` shows the PortfoLive app.
- Then make the Docker Hub repo public if needed (Part 8).

---

## Part 10: Slack notifications (ChatOps, optional)

1. https://api.slack.com/apps > **Create New App > From scratch** > name `PortfoLive`, pick your workspace.
2. **Incoming Webhooks** > turn on > **Add New Webhook to Workspace** > choose a channel (e.g. `#devops`) > copy the URL.
3. Jenkins: edit the `slack-webhook` credential and paste the URL. Next build posts start/success/failure messages.
4. Alertmanager: put the same URL in `ansible/group_vars/all/secrets.yml` as `slack_webhook_url`, then
   `cd ansible && ansible-playbook site.yml --limit k3s-server` (about 3 minutes).

**Test alerts end to end:**
```bash
curl -XPOST http://<k8s-ip>:30093/api/v2/alerts -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"ManualTest","severity":"warning"},"annotations":{"summary":"Test alert","description":"Hello from Alertmanager"}}]'
```
A message should appear in Slack within about 30 seconds.

**Using Microsoft Teams instead:** Jenkins works unchanged with a Teams *Incoming Webhook* (or Workflows webhook) URL in
the `slack-webhook` credential, since both accept `{"text": "..."}`. Newer Alertmanager versions also have a
native `msteams_configs` receiver; check the Alertmanager documentation for the options your version supports, then
replace the `slack_configs` block in `monitoring/alertmanager.yml`. Run `amtool check-config` before applying.

---

## Part 11: Use the app for real, and demonstrate everything

1. Open `http://<k8s-ip>:30080`, register using the **same email as `admin_email`** > you get the **Admin** tab.
2. Fill in the form > **Publish**. You get a URL like `https://dxxxx.cloudfront.net/<username>/` (or `http://<bucket>.s3-website.<region>.amazonaws.com/<username>/`
   with CloudFront off). Open it. (With CloudFront, the first load can take a minute while it warms up.) Edit and publish again to see an *update*
   (targeted cache invalidation; skipped when CloudFront is off) in **Deployments**.
3. **Blue/green demo:** edit a template in `server/templates/`, commit on a branch, open a PR, merge.
   Jenkins builds; in the console you see `Live: blue -> deploying green`, then traffic flips.
   Show with `kubectl get pods -L color` and `kubectl get svc portfolive -o jsonpath='{.spec.selector}'`.
   **Rollback in 2 seconds:**
   `kubectl patch svc portfolive -p '{"spec":{"selector":{"app":"portfolive","color":"blue"}}}'`
4. **Autoscaling demo:** `kubectl get hpa -w`, then load the app, e.g.
   `docker run --rm williamyeh/hey -z 60s -c 50 http://<k8s-ip>:30080/api/templates`. Replicas rise toward 6.
5. **Monitoring demo:** Grafana dashboard; Prometheus > Alerts. Kill a pod (`kubectl delete pod <name>`) and watch recovery.
6. **Alert demo:** in the EC2 console stop the SonarQube server for 3 minutes. Alertmanager fires **HostDown** to Slack.
   Start the server again and you get the "resolved" message. (Its public IP changes, see Part 13.)

To use `kubectl` from your laptop: `export KUBECONFIG=$PWD/ansible/artifacts/k3s-public.yaml`.

---

## Part 12: What each requirement maps to (for your report)

| Requirement | Where it is | How to show it |
|---|---|---|
| Git, GitHub, shared repo, branches, PRs, history | `.github/`, `docs/GIT_WORKFLOW.md` | GitHub PR list and commit graph |
| AWS, Terraform (VPC, subnets, networking, EC2) | `terraform/main.tf` | `terraform apply` output, AWS console |
| Ansible, Ubuntu, SSH | `ansible/` (5 roles + playbook) | `ansible-playbook site.yml` run; `ssh` to a server |
| Docker | `Dockerfile` (multi-stage), `docker-compose.yml` | `docker images`, image on Docker Hub |
| Jenkins CI/CD (build, test, scan, deploy) | `Jenkinsfile` | green pipeline with all stages |
| SonarQube | `sonar-project.properties`, pipeline stages | SonarQube project dashboard + quality gate |
| OWASP ZAP (DAST) | "DAST: OWASP ZAP" stage | HTML reports in Jenkins build artifacts |
| Kubernetes (replicas, rollouts, service discovery) | `k8s/app/` | `kubectl get deploy,hpa,svc`; blue/green flip; rollback |
| Prometheus, Grafana | `monitoring/`, `k8s/monitoring/` | dashboard **PortfoLive Overview** |
| Alertmanager | `monitoring/alert-rules.yml`, `alertmanager.yml` | Alerts page; test alert in Slack |
| ChatOps (optional) | `notify()` in Jenkinsfile, Alertmanager Slack receiver | Slack messages |

Security measures you can mention: private S3 bucket reachable only through CloudFront (when enabled), least-privilege IAM, security
group limited to your IP, secrets kept out of Git (Ansible vars / Kubernetes Secrets / Jenkins credentials), input
validation + HTML escaping + Content-Security-Policy on generated sites, security headers, container runs as non-root,
SAST (SonarQube) and DAST (ZAP) gates before deploy.

---

## Part 13: Stop the billing

- **Pause for a few days:** EC2 console > select the 3 servers > Instance state > **Stop**. You still pay a little
  for disks. **Public IPs change on restart**, so afterwards run `terraform apply` (same variables) to refresh
  `ansible/inventory.ini`, and update the IPs you use in your browser.
- **Remove everything:** `cd terraform && terraform destroy` (type `yes`), about 5 minutes. This deletes the servers, S3
  bucket (and published sites), and CloudFront. CloudFront deletion can take 10-15 minutes.
  Afterwards confirm in the AWS console (EC2, S3, CloudFront) that nothing is left, and check Billing next day.
- Delete the Docker Hub token and the AWS access keys you no longer need.

---

## Part 14: Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `terraform apply`: bucket name already exists | Choose another `bucket_name` (global namespace). |
| `terraform apply`: `InvalidKeyPair.NotFound` | `key_name` must match the EC2 key pair name **in the same region**. |
| `ansible all -m ping` times out | Your IP changed (re-run `terraform apply` with the new `admin_cidr`), or servers still booting (wait 2 min). |
| `Permission denied (publickey)` | Wrong `ssh_private_key_path`, or key file permissions: `chmod 400`. |
| Playbook stops: "Missing or placeholder variables" | Finish `secrets.yml` (no `CHANGE_ME`, `jwt_secret` 32+ chars) and run `terraform apply` first. |
| Jenkins repo/key task fails | Jenkins rotates its package signing key sometimes. Update `jenkins_key_url` in `ansible/roles/jenkins/defaults/main.yml` from https://pkg.jenkins.io/ . |
| SonarQube won't start | Needs 4 GB RAM and `vm.max_map_count` (role sets it). Check `ssh ... sudo docker logs sonarqube-sonarqube-1`. |
| Pipeline stuck at "Quality gate" | The SonarQube webhook (Part 7 step 3) is missing or uses the public IP. Use the Jenkins **private** IP. |
| `docker: permission denied` in Jenkins | The Ansible run adds `jenkins` to the docker group and restarts Jenkins; re-run the playbook. |
| `withSonarQubeEnv` error "no server named sonarqube" | Name it exactly `sonarqube` (Part 9 step 5). |
| Coverage shows 0% in SonarQube | The `sed` path-fix step in the Jenkinsfile; check `reports/coverage.xml` paths start with `server/app/`. |
| ZAP stage fails the build | Open `zap-baseline.html`. Only FAIL-level findings stop the build; warnings do not. Fix the finding or suppress a known false positive with a ZAP rules file. |
| ZAP stage: `app` not resolving / health wait fails | See the container log: `docker logs portfolive-dast-<n>`. Usually a Python import error in the image. |
| `ImagePullBackOff` in Kubernetes | Docker Hub repo is private. Make it public (Part 8). |
| App pods `CrashLoopBackOff`, log says permission denied on `/data` | The volume is owned by root: `kubectl exec` is not possible while crashing, so run on the k3s server `sudo chmod -R 777 /var/lib/rancher/k3s/storage/*portfolive-data*` then delete the pods. |
| Pods running but `/api/publish` fails with AWS error | Check `kubectl logs deploy/portfolive-<color>`; usually wrong bucket/region in `terraform.yml`, or (with CloudFront on) a missing CloudFront ID. |
| Published site shows `AccessDenied` | With CloudFront: OAC takes a few minutes after creation. With S3 website mode: re-run `terraform apply` (the public-access block must be relaxed before the public policy applies). Either way, check the URL has the trailing `/<username>/`. |
| Prometheus `portfolive` job has no targets | No deploy has happened yet, or pods lack the `prometheus.io/scrape` annotation (they have it in `k8s/app`). |
| Alerts fire but nothing reaches Slack | `slack_webhook_url` still the placeholder; rerun Ansible for `k3s-server` (Part 10). Check Alertmanager UI > Status. |
| HPA shows `<unknown>` CPU | metrics-server needs ~1 minute after k3s starts; wait and recheck `kubectl top pods`. |
| `kubectl` from laptop times out | Your IP changed (Terraform `admin_cidr`) or the file `k3s-public.yaml` has stale IP; re-run Ansible to refresh. |

---

## Part 15: Known limitations (say these yourself, it reads well)

- **SQLite on a shared volume** works because k3s is a single node. For multi-node or high availability, move to RDS (PostgreSQL).
- **One Kubernetes node, one subnet, public IPs on all servers:** fine for a project, not production. Production
  would use private subnets, a NAT gateway, a load balancer, TLS everywhere, and managed Kubernetes (EKS).
- **No HTTPS on the app itself** (only CloudFront sites have it; with CloudFront off, published sites are HTTP-only on a public bucket). Add a domain, ACM certificate, and an ingress/ALB.
- **ZAP API scan is unauthenticated**, so it exercises public endpoints only.
- **Prometheus data is not persisted** (resets if its pod restarts).
- Secrets are kept in Kubernetes Secrets (base64, not encrypted at rest by default).
- No rate limiting or email verification on signup.
