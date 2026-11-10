# Handy shortcuts. Run `make help`.
.PHONY: help test api client up down tf-init tf-apply tf-destroy ansible kubeconfig alerts-test

help:            ## list commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

test:            ## run backend tests with coverage
	cd server && pytest

api:             ## run the API locally on :4000
	cd server && uvicorn app.main:create_app --factory --reload --port 4000

client:          ## run the React dev server on :5173
	cd client && npm install && npm run dev

up:              ## app + Prometheus + Alertmanager + Grafana in Docker
	docker compose up --build

down:            ## stop the local stack
	docker compose down

tf-init:         ## terraform init
	cd terraform && terraform init

tf-apply:        ## create AWS infrastructure (asks for bucket_name, key_name, admin_cidr)
	cd terraform && terraform apply

tf-destroy:      ## DELETE all AWS resources (stops the billing)
	cd terraform && terraform destroy

ansible:         ## configure the servers
	cd ansible && ansible-playbook site.yml

kubeconfig:      ## use the cluster from your laptop
	@echo 'export KUBECONFIG=$(PWD)/ansible/artifacts/k3s-public.yaml'

alerts-test:     ## validate Prometheus alert rules (needs promtool)
	promtool check rules monitoring/alert-rules.yml && promtool test rules monitoring/tests/alert-rules.test.yml
