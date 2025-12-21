CI := 1

.PHONY: help build dev-fmt all check fmt lint mypy test security update-spec e2e coverage

# Default target - show help
.DEFAULT_GOAL := help

# Show this help message
help:
	@awk '/^# / { desc=substr($$0, 3) } /^[a-zA-Z0-9_-]+:/ && desc { target=$$1; sub(/:$$/, "", target); printf "%-20s - %s\n", target, desc; desc="" }' Makefile | sort

# Build/install the package in development mode
build:
	pip install -e ./gts

# Fix formatting issues
dev-fmt:
	ruff format gts/src

# Run all checks and build
all: check build

# Check code formatting
fmt:
	ruff format --check gts/src

# Run linter (ruff)
lint:
	ruff check gts/src

# Run clippy-equivalent linter with auto-fix
clippy:
	ruff check --fix gts/src

# Run type checker
mypy:
	mypy gts/src/gts --ignore-missing-imports

# Run all tests
test:
	pytest tests/ -v

# Check dependencies for security vulnerabilities
security:
	@command -v pip-audit >/dev/null || (echo "Installing pip-audit..." && pip install pip-audit)
	pip-audit

# Measure code coverage
coverage:
	pytest tests/ --cov=gts --cov-report=xml --cov-report=term

# Update gts-spec submodule to latest
update-spec:
	git submodule update --remote .gts-spec

# Run end-to-end tests against gts-spec
e2e: build
	@echo "Starting server in background..."
	@python -m gts server --port 8000 & echo $$! > .server.pid
	@sleep 2
	@echo "Running e2e tests..."
	@PYTHONDONTWRITEBYTECODE=1 pytest -p no:cacheprovider --log-file=e2e.log ./.gts-spec/tests || (kill `cat .server.pid` 2>/dev/null; rm -f .server.pid; exit 1)
	@echo "Stopping server..."
	@kill `cat .server.pid` 2>/dev/null || true
	@rm -f .server.pid
	@echo "E2E tests completed successfully"

# Run all quality checks
check: fmt lint test e2e
