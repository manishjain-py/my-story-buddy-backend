# Makefile for My Story Buddy Backend

.PHONY: help install install-dev test test-unit test-integration test-coverage clean lint format type-check run dev

# Default target
help:
	@echo "Available commands:"
	@echo "  install      - Install production dependencies"
	@echo "  install-dev  - Install development and test dependencies"
	@echo "  test         - Run all tests"
	@echo "  test-unit    - Run only unit tests"
	@echo "  test-integration - Run only integration tests"
	@echo "  test-coverage - Run tests with coverage report"
	@echo "  lint         - Run linting checks"
	@echo "  format       - Format code"
	@echo "  type-check   - Run type checking"
	@echo "  run          - Run the application in production mode"
	@echo "  dev          - Run the application in development mode"
	@echo "  clean        - Clean up generated files"

# Installation
install:
	pip install -r config/requirements.txt

install-dev: install
	pip install -r tests/requirements-test.txt
	pip install black isort mypy flake8

# Testing
test:
	cd src && python -m pytest ../tests/ -v

test-unit:
	cd src && python -m pytest ../tests/ -v -m "not integration"

test-integration:
	cd src && python -m pytest ../tests/ -v -m "integration"

test-coverage:
	cd src && python -m pytest ../tests/ --cov=. --cov-report=html --cov-report=term-missing

test-watch:
	cd src && python -m pytest ../tests/ -f

# Coverage Analysis
coverage:
	python3 scripts/coverage.py

coverage-quick:
	python3 scripts/coverage.py --quick

coverage-trend:
	python3 scripts/coverage.py --trend

coverage-watch:
	python3 scripts/coverage-watch.py

coverage-dashboard:
	python3 scripts/coverage-dashboard.py

coverage-dashboard-open:
	python3 scripts/coverage-dashboard.py --auto-open

coverage-check:
	python3 scripts/coverage.py --check 80

# Alternative: Use the new Python runner
coverage-simple:
	python3 run_coverage.py

coverage-simple-quick:
	python3 run_coverage.py --quick

coverage-simple-dashboard:
	python3 run_coverage.py --dashboard

coverage-simple-watch:
	python3 run_coverage.py --watch

# Code quality
lint:
	flake8 src/ tests/
	isort --check-only src/ tests/
	black --check src/ tests/

format:
	isort src/ tests/
	black src/ tests/

type-check:
	mypy src/

# Development
run:
	cd src && python -m uvicorn main:app --host 0.0.0.0 --port 8003

dev:
	cd src && python -m uvicorn main:app --host 0.0.0.0 --port 8003 --reload

# Docker
docker-build:
	docker build -f deployment/docker/Dockerfile.ec2 -t my-story-buddy-backend:latest .

docker-run:
	docker run -p 8003:8003 -e OPENAI_API_KEY=${OPENAI_API_KEY} my-story-buddy-backend:latest

# Cleanup
clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf dist/
	rm -rf build/

# Database
db-migrate:
	cd src && python -c "import asyncio; from core.database import create_tables; asyncio.run(create_tables())"

# Health checks
health:
	curl -f http://localhost:8003/health || exit 1

# CI/CD helpers
ci-test: install-dev test-coverage

ci-lint: install-dev lint type-check