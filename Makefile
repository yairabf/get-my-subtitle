.PHONY: help install setup build up up-infra down restart logs dev-manager dev-downloader dev-translator test test-unit test-integration test-cov test-watch lint format check clean clean-docker clean-all

# Colors for terminal output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Python executable (use venv if available)
PYTHON := $(shell if [ -d "venv" ]; then echo "./venv/bin/python"; else echo "python3"; fi)
PYTEST := $(shell if [ -d "venv" ]; then echo "./venv/bin/pytest"; else echo "pytest"; fi)
BLACK := $(shell if [ -d "venv" ]; then echo "./venv/bin/black"; else echo "black"; fi)
ISORT := $(shell if [ -d "venv" ]; then echo "./venv/bin/isort"; else echo "isort"; fi)

##@ Help

help: ## Display this help message
	@echo "$(BLUE)Get My Subtitle - Development Automation$(NC)"
	@echo ""
	@echo "$(GREEN)Usage:$(NC) make [target]"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(NC)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Setup & Environment

install: ## Install Python dependencies
	@echo "$(GREEN)Installing dependencies...$(NC)"
	pip install -r requirements.txt

setup: ## Complete project setup (venv, deps, .env)
	@echo "$(GREEN)Setting up project...$(NC)"
	@if [ ! -d "venv" ]; then \
		echo "$(YELLOW)Creating virtual environment...$(NC)"; \
		python3 -m venv venv; \
	fi
	@echo "$(YELLOW)Activating virtual environment and installing dependencies...$(NC)"
	@. venv/bin/activate && pip install -r requirements.txt
	@if [ ! -f ".env" ]; then \
		echo "$(YELLOW)Creating .env file from template...$(NC)"; \
		cp env.template .env; \
		echo "$(RED)⚠️  Please update .env with your API keys$(NC)"; \
	fi
	@echo "$(GREEN)✓ Setup complete!$(NC)"

##@ Docker Operations

build: ## Build all Docker images
	@echo "$(GREEN)Building Docker images...$(NC)"
	docker-compose build

up: ## Start all services (full Docker mode)
	@echo "$(GREEN)Starting all services...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)✓ Services started!$(NC)"
	@echo "$(YELLOW)API available at: http://localhost:8000$(NC)"
	@echo "$(YELLOW)RabbitMQ UI at: http://localhost:15672$(NC)"

up-infra: ## Start only Redis & RabbitMQ (hybrid mode)
	@echo "$(GREEN)Starting infrastructure services...$(NC)"
	docker-compose up -d redis rabbitmq
	@echo "$(GREEN)✓ Infrastructure services started!$(NC)"

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down

restart: ## Restart all services
	@echo "$(YELLOW)Restarting all services...$(NC)"
	docker-compose restart

logs: ## Follow logs from all services
	docker-compose logs -f

##@ Development (Hybrid Mode)

dev-manager: ## Run manager locally with hot reload
	@echo "$(GREEN)Starting manager service locally...$(NC)"
	@. venv/bin/activate && cd manager && uvicorn main:app --reload --host 0.0.0.0 --port 8000

dev-downloader: ## Run downloader worker locally
	@echo "$(GREEN)Starting downloader worker locally...$(NC)"
	@. venv/bin/activate && cd downloader && python worker.py

dev-translator: ## Run translator worker locally
	@echo "$(GREEN)Starting translator worker locally...$(NC)"
	@. venv/bin/activate && cd translator && python worker.py

##@ Testing

test: ## Run all tests (skips integration tests requiring services)
	@echo "$(GREEN)Running all tests (unit tests only)...$(NC)"
	$(PYTEST) -m "not integration"

test-all: ## Run all tests including integration tests
	@echo "$(GREEN)Running all tests including integration...$(NC)"
	$(PYTEST)

test-unit: ## Run unit tests only
	@echo "$(GREEN)Running unit tests...$(NC)"
	$(PYTEST) -m unit

test-integration: ## Run integration tests only
	@echo "$(GREEN)Running integration tests...$(NC)"
	$(PYTEST) -m integration

test-cov: ## Run tests with coverage report
	@echo "$(GREEN)Running tests with coverage...$(NC)"
	$(PYTEST) --cov=common --cov=manager --cov=downloader --cov=translator --cov-report=term-missing --cov-report=html
	@echo "$(YELLOW)HTML coverage report generated in htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode
	@echo "$(GREEN)Running tests in watch mode...$(NC)"
	@if [ -f "./venv/bin/ptw" ] || command -v ptw >/dev/null 2>&1; then \
		$(shell if [ -d "venv" ]; then echo "./venv/bin/ptw"; else echo "ptw"; fi); \
	else \
		echo "$(RED)pytest-watch not installed. Install with: pip install pytest-watch$(NC)"; \
		echo "$(YELLOW)Running tests once instead...$(NC)"; \
		$(PYTEST); \
	fi

##@ Code Quality

lint: ## Check code formatting
	@echo "$(GREEN)Checking code formatting...$(NC)"
	@echo "$(BLUE)Running black...$(NC)"
	@$(BLACK) --check . || (echo "$(RED)✗ Black formatting check failed$(NC)" && exit 1)
	@echo "$(BLUE)Running isort...$(NC)"
	@$(ISORT) --check-only . || (echo "$(RED)✗ Isort check failed$(NC)" && exit 1)
	@echo "$(GREEN)✓ All formatting checks passed!$(NC)"

format: ## Auto-fix code formatting
	@echo "$(GREEN)Formatting code...$(NC)"
	$(BLACK) .
	$(ISORT) .
	@echo "$(GREEN)✓ Code formatted!$(NC)"

check: lint test ## Run lint + tests (pre-commit style check)
	@echo "$(GREEN)✓ All checks passed!$(NC)"

##@ Cleanup

clean: ## Remove Python cache files
	@echo "$(YELLOW)Cleaning Python cache files...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleaned!$(NC)"

clean-docker: ## Remove Docker containers, volumes, and images
	@echo "$(YELLOW)Cleaning Docker resources...$(NC)"
	docker-compose down -v
	@echo "$(RED)Removing project Docker images...$(NC)"
	docker-compose down --rmi local 2>/dev/null || true
	@echo "$(GREEN)✓ Docker cleaned!$(NC)"

clean-all: clean clean-docker ## Full cleanup
	@echo "$(GREEN)✓ Full cleanup complete!$(NC)"

