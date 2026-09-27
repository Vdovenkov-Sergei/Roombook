# Makefile for Roombook
# Usage: make <command>
# List all commands: make help

.PHONY: help install format lint type-check security style test run pre-commit clean all

# Variables
UV := uv
PACKAGE := app

# ANSI color codes
CYAN := \033[0;36m
GREEN := \033[0;32m
NC := \033[0m

help: ## Show this help message
	@printf "$(CYAN)Available commands:$(NC)\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2}'

install: ## Install dependencies via uv
	$(UV) sync

format: ## Format code with ruff
	$(UV) run ruff format .

lint: ## Check code with ruff
	$(UV) run ruff check .

type-check: ## Check types with mypy
	$(UV) run mypy $(PACKAGE)

security: ## Scan code for security issues with bandit
	$(UV) run bandit -c pyproject.toml -r $(PACKAGE)

style: format lint type-check security ## Run all style and quality checks

test: ## Run the test suite (with coverage)
	$(UV) run pytest --cov=$(PACKAGE) --cov-report=term-missing

run: ## Run the FastAPI app with auto-reload
	$(UV) run uvicorn $(PACKAGE).main:app --reload

pre-commit: ## Run all pre-commit hooks on all files
	$(UV) run pre-commit run --all-files

clean: ## Clean cache files and temporary directories
	find . -type d -name "__pycache__" ! -path "./.venv/*" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" ! -path "./.venv/*" -delete 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage 2>/dev/null || true

all: clean style test ## Clean, run all style checks, and test (full cycle)
