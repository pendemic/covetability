DB_COMPOSE = docker compose -f infra/docker-compose.yml
EBAY_SOURCE ?= fixtures
TRENDS_SOURCE ?= fixtures
GOLD ?= all

.PHONY: db-up db-down db-test-setup migrate seed seed-history refresh reset-live snapshot match rematch normalize-conditions load-fixture-gold evaluate evaluate-fixtures evaluate-conditions aggregate recompute verify-aggregates expire expire-dry trends score stability apply-stability covet-digest test lint api web

db-up:
	$(DB_COMPOSE) up -d

db-down:
	$(DB_COMPOSE) down

migrate:
	cd pipeline && uv run alembic upgrade head

seed:
	cd pipeline && uv run python -m seeds.catalog

seed-history:
	cd pipeline && uv run python -m jobs.seed_history --days $(if $(DAYS),$(DAYS),120) $(if $(END),--end $(END),)

refresh:
	cd pipeline && EBAY_SOURCE=$(EBAY_SOURCE) uv run python -m jobs.refresh

reset-live:
	cd pipeline && uv run python -m jobs.reset_live $(if $(YES),--yes,) $(if $(LISTINGS),--listings,)

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

trends:
	cd pipeline && TRENDS_SOURCE=$(TRENDS_SOURCE) uv run python -m jobs.weekly_trends

score:
	cd pipeline && uv run python -m jobs.daily_score $(if $(RELIST_PRECISION),--relist-precision $(RELIST_PRECISION),)

stability:
	cd pipeline && uv run python -m jobs.stability_report

apply-stability:
	cd pipeline && uv run python -m jobs.apply_stability_decision

covet-digest:
	cd pipeline && uv run python -m jobs.covet_digest

TEST_DB_URL ?= postgresql+psycopg://covetability:covetability@localhost:15432/covetability_test

# Create + migrate a dedicated test database (safe to re-run). Tests refuse to
# run against the main DB, so this must exist first.
db-test-setup:
	docker exec covetability-postgres psql -U covetability -d covetability -tc "SELECT 1 FROM pg_database WHERE datname='covetability_test'" | grep -q 1 || docker exec covetability-postgres createdb -U covetability covetability_test
	cd pipeline && DATABASE_URL=$(TEST_DB_URL) uv run alembic upgrade head

test:
	cd pipeline && TEST_DATABASE_URL=$(TEST_DB_URL) uv run pytest

lint:
	cd pipeline && uv run ruff check .
	cd web && npm run lint:vocab

api:
	cd pipeline && uv run uvicorn app.main:app --reload

web:
	cd web && npm run dev
