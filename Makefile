.PHONY: help install install-all update-deps test-module test-integration test-load-rest test-load-mqtt lint migrate migrate-rollback build-data-pipe start clean

help:
	@echo "Pepeunit Backend - Commands:"
	@echo ""
	@echo "install:          Install main project dependencies"
	@echo "install-all:      Install all dependencies including dev and load tests"
	@echo "update-deps:      Update all project dependencies with UV"
	@echo "build-data-pipe:  Build the data pipe binary with local Go"
	@echo "start:            Clean, build data pipe, and run the server on port 5291"
	@echo "clean:            Stop the server, data pipe, and remove lock files"
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

build-data-pipe:
	@echo "Build data pipe..."
	@mkdir -p bin
	cd data_pipe && CGO_ENABLED=0 go build -ldflags="-s -w" -o ../bin/data_pipe .

start: clean
	@$(MAKE) --no-print-directory build-data-pipe
	@echo "Run server..."
	uv run python -m uvicorn_conf

clean:
	@echo "Clean lock files and stop the server and data pipe..."
	@rm -f tmp/*.lock tmp/data_pipe.supervisor.pid
	@ours=$$(ps -o pgid= -p $$PPID | tr -d ' '); \
	for proc in /proc/[0-9]*; do \
		pid=$${proc#/proc/}; \
		cwd=$$(readlink /proc/$$pid/cwd 2>/dev/null || true); \
		[ "$$cwd" = "$(CURDIR)" ] || continue; \
		cmd=$$(tr '\0' ' ' < /proc/$$pid/cmdline 2>/dev/null || true); \
		case "$$cmd" in \
			*uvicorn_conf*|*datapipe_process*|*app.configs.job_stop*|*bin/data_pipe*) ;; \
			*) continue ;; \
		esac; \
		pgid=$$(ps -o pgid= -p $$pid | tr -d ' '); \
		[ -n "$$pgid" ] && [ "$$pgid" != "$$ours" ] || continue; \
		kill -KILL -$$pgid 2>/dev/null || kill -KILL $$pid 2>/dev/null || true; \
	done
	@kill -9 $$(lsof -t -i:5291) 2>/dev/null || true
