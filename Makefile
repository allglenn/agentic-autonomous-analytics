.PHONY: venv install run dev run-dev test docker-up docker-down seed

# ── Virtual environment ────────────────────────────────────────────
venv:
	python3 -m venv .venv
	@echo "Run: source .venv/bin/activate"

install:
	pip install -r requirements.txt

# ── Local run ──────────────────────────────────────────────────────
run:
	python3 main.py

dev:
	uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

run-dev: dev

# ── Tests ──────────────────────────────────────────────────────────
test:
	pytest tests/ -v

# ── Docker ─────────────────────────────────────────────────────────
docker-up:
	docker compose up --build

docker-down:
	docker compose down

# ── Seed data ──────────────────────────────────────────────────────
seed:
	python3 scripts/seed_data.py

seed-large:
	python3 scripts/seed_data.py --orders 5000
