DB_COMPOSE = docker compose -f infra/docker-compose.yml
EBAY_SOURCE ?= fixtures
GOLD ?= all

.PHONY: db-up db-down migrate seed snapshot match rematch normalize-conditions load-fixture-gold evaluate evaluate-fixtures evaluate-conditions aggregate recompute verify-aggregates expire expire-dry test lint api web

db-up:
	$(DB_COMPOSE) up -d

db-down:
	$(DB_COMPOSE) down

migrate:
	cd pipeline && uv run alembic upgrade head

seed:
	cd pipeline && uv run python -m seeds.catalog

snapshot:
	cd pipeline && EBAY_SOURCE=$(EBAY_SOURCE) uv run python -m jobs.daily_snapshot

match:
	cd pipeline && uv run python -m jobs.run_matching

rematch:
	cd pipeline && uv run python -m jobs.run_matching --all

normalize-conditions:
	cd pipeline && uv run python -m jobs.normalize_conditions

load-fixture-gold:
	cd pipeline && uv run python -m jobs.load_fixture_gold

evaluate:
	cd pipeline && uv run python -m jobs.evaluate_matcher --gold-origin $(GOLD)

evaluate-fixtures:
	cd pipeline && uv run python -m jobs.load_fixture_gold
	cd pipeline && uv run python -m jobs.evaluate_matcher --gold-origin fixture_seed --enforce

evaluate-conditions:
	cd pipeline && uv run python -m jobs.evaluate_conditions --enforce

aggregate:
	cd pipeline && uv run python -m jobs.daily_aggregates

recompute:
	cd pipeline && uv run python -m jobs.recompute_aggregates --since $(SINCE) $(if $(UNTIL),--until $(UNTIL),) $(if $(BAG),--bag $(BAG),) $(if $(NOTE),--note "$(NOTE)",)

verify-aggregates:
	cd pipeline && uv run python -m jobs.verify_aggregates

expire:
	cd pipeline && uv run python -m jobs.expire_raw

expire-dry:
	cd pipeline && uv run python -m jobs.expire_raw --dry-run

test:
	cd pipeline && uv run pytest

lint:
	cd pipeline && uv run ruff check .
	cd web && npm run lint:vocab

api:
	cd pipeline && uv run uvicorn app.main:app --reload

web:
	cd web && npm run dev
