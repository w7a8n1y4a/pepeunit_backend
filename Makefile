.PHONY: help install install-all update-deps test-module test-integration test-load-rest test-load-mqtt lint migrate migrate-rollback uvi gun clean

help:
	@echo "Pepeunit Backend - Commands:"
	@echo ""
	@echo "install:          Install main project dependencies"
	@echo "install-all:      Install all dependencies including dev and load tests"
	@echo "update-deps:      Update all project dependencies with UV"
	@echo "uvi:              Run development server with uvicorn on port 5291 with 2 workers"
	@echo "gun:              Run production server with gunicorn on port 5291 with 2 workers"
	@echo "clean:            Clean temporary files and stop processes on port 5291"
	@echo "lint:             Check and fix code with Ruff"
	@echo "migrate:          Apply all database migrations"
	@echo "migrate-rollback: Rollback last database migration"
	@echo "test-module:      Run module tests"
	@echo "test-integration: Run integration tests"
	@echo "test-load-rest:   Run REST API load testing"
	@echo "test-load-mqtt:   Run MQTT load testing"

install:
	@echo "Install main dependencies..."
	uv sync

install-all:
	@echo "Install all dependencies..."
	uv sync --extra dev --extra load

update-deps:
	@echo "Update all project dependencies with UV..."
	uv sync --upgrade

test-module:
	@echo "Module test run..."
	uv run pytest app -v

test-integration:
	@echo "Integration test run..."
	uv run pytest tests -v

test-load-rest:
	@echo "REST load test run..."
	uv run locust -f tests/load/locustfile.py

test-load-mqtt:
	@echo "MQTT load test run..."
	uv run python -m tests.load.load_test_mqtt

lint:
	@echo "Ruff magic run..."
	uv run ruff check --fix

migrate:
	@echo "Upgrade with alembic..."
	uv run alembic upgrade head

migrate-rollback:
	@echo "Rollback one migration with alembic..."
	uv run alembic downgrade head-1

uvi:
	@echo "Run uvicorn server..."
	uv run python -m uvicorn_conf

gun:
	@echo "Run gunicorn server..."
	uv run gunicorn app.main:app \
		--bind 0.0.0.0:5291 \
		--config gunicorn_conf.py \
		--timeout 300 \
		--workers=2 \
		--worker-class uvicorn.workers.UvicornWorker \
		--worker-tmp-dir=/dev/shm

clean:
	@echo "Clean lock files and kill processes on port 5291..."
	@rm -rf tmp/*.lock || true
	@kill -9 $$(lsof -t -i:5291) 2>/dev/null || true
