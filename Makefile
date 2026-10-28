.PHONY: help install dev backend frontend test build docker clean

help:
	@echo "make install   → dépendances backend + frontend"
	@echo "make backend   → API FastAPI sur :8000"
	@echo "make frontend  → Vite sur :5173"
	@echo "make test      → pytest + typecheck frontend"
	@echo "make docker    → docker compose up --build"

install:
	cd backend && pip install -r requirements-dev.txt
	cd frontend && npm install

backend:
	cd backend && uvicorn app.main:app --reload --port 8000

frontend:
	cd frontend && npm run dev

test:
	cd backend && pytest -q
	cd frontend && npm run typecheck

build:
	cd frontend && npm run build

docker:
	docker compose up --build

clean:
	rm -rf backend/data/runs/* backend/data/vectors/* backend/data/uploads/* frontend/dist
