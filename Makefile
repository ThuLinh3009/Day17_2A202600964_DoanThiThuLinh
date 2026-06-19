## Day 17 — Data Pipeline Engineering lab.
## Two paths: lite (default, no Docker) and dbt (Python <=3.13).

VENV := .venv
PY   := $(VENV)/bin/python
PIP  := $(VENV)/bin/pip

.DEFAULT_GOAL := help

help: ## Show this help
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m<target>\033[0m\n\n"} \
	      /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

setup: ## [lite] Create venv + install the graded-core deps
	python3 -m venv $(VENV) && $(PIP) -q install -r requirements.txt

verify: ## [lite] End-to-end smoke test — expect "ALL PASS" (14 checks)
	@DISABLE_PANDERA_IMPORT_WARNING=True $(PY) verify.py

run: ## [lite] Medallion pipeline: dedup + quarantine + Gold
	@$(PY) main.py

flywheel: ## [lite] Agent traces -> Bronze -> eval/DPO datasets + point-in-time features
	@$(PY) flywheel.py

kg: ## [lite] Bonus: build a knowledge graph from the docs and query it
	@$(PY) kg_demo.py

test: ## [lite] Run pytest (16 tests)
	@DISABLE_PANDERA_IMPORT_WARNING=True $(PY) -m pytest -q

dbt: ## [dbt] Build + test the dbt-duckdb project (needs Python 3.10-3.13)
	cd dbt_project && DBT_PROFILES_DIR=. dbt build

docker-up: ## [docker] Optional realism bonus: Airflow 3 + Redpanda
	docker compose -f docker/docker-compose.yml up

clean: ## Wipe venv, warehouse, derived datasets, quarantine
	rm -rf $(VENV) warehouse.duckdb quarantine.csv datasets \
	       **/__pycache__ .pytest_cache

.PHONY: help setup verify run flywheel kg test dbt docker-up clean
