DB_COMPOSE = docker compose -f infra/docker-compose.yml

.PHONY: db-up db-down migrate seed test lint api web

db-up:
	$(DB_COMPOSE) up -d

db-down:
	$(DB_COMPOSE) down

migrate:
	cd pipeline && uv run alembic upgrade head

seed:
	cd pipeline && uv run python -m seeds.catalog

test:
	cd pipeline && uv run pytest

lint:
	cd pipeline && uv run ruff check .
	cd web && npm run lint:vocab

api:
	cd pipeline && uv run uvicorn app.main:app --reload

web:
	cd web && npm run dev
