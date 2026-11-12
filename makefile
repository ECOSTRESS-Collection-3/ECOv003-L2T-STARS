# Define package and environment variables
PACKAGE_NAME = ECOv003-L2T-STARS
ENVIRONMENT_NAME = $(PACKAGE_NAME)
DOCKER_IMAGE_NAME = $(shell echo $(PACKAGE_NAME) | tr '[:upper:]' '[:lower:]')
PYTHON_VERSION = $(if $(PYTHON),$(PYTHON),3.12)
JULIA_VERSION = $(if $(JULIA),$(JULIA),1.11)
JULIA_PROJECT_NAME = $(if $(JULIA_PROJECT),$(JULIA_PROJECT),$(subst -,_,$(PACKAGE_NAME)))

.PHONY: clean test smoke-test smoke-test-python smoke-test-julia test-julia \
        build twine-upload dist install-package install uninstall reinstall \
        environment remove-environment install-julia resolve-julia \
        julia-version colima-start docker-build docker-build-environment \
        docker-build-installation docker-interactive docker-remove

# --- Cleaning and Maintenance ---

clean:
	@echo "Cleaning up build artifacts..."
	rm -rf *.o *.out *.log
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# --- Testing ---

test:
	@echo "Running Python test suite..."
	PYTHONPATH=. pytest

smoke-test:
	@echo "Running smoke tests..."
	$(PACKAGE_NAME) test

smoke-test-python:
	@echo "Running Python smoke tests..."
	$(PACKAGE_NAME) test-python

smoke-test-julia:
	@echo "Running Julia smoke tests..."
	$(PACKAGE_NAME) test-julia

test-julia:
	@echo "Testing Julia environment..."
	julia --project=$(JULIA_PROJECT_NAME) $(JULIA_PROJECT_NAME)/julia_smoke_test.jl $(JULIA_PROJECT_NAME)/process_ECOSTRESS_data_fusion_distributed_bias.jl

# --- Package Management ---

build:
	@echo "Building package..."
	python -m build

twine-upload:
	@echo "Uploading package to PyPI..."
	twine upload dist/*

dist: clean build twine-upload
	@echo "Distribution process complete."

install-package:
	@echo "Installing package in development mode..."
	pip install --no-cache-dir --index-url https://pypi.org/simple -e '.[dev]'

install: install-julia install-package
	@echo "All installations complete."

uninstall:
	@echo "Uninstalling $(PACKAGE_NAME)..."
	pip uninstall -y $(PACKAGE_NAME)

reinstall: uninstall install
	@echo "Package reinstalled."

# --- Environment Management ---

environment:
	@echo "Creating mamba environment: $(ENVIRONMENT_NAME)..."
	mamba create -y -n $(ENVIRONMENT_NAME) -c conda-forge python=$(PYTHON_VERSION)

remove-environment:
	@echo "Removing mamba environment: $(ENVIRONMENT_NAME)..."
	mamba env remove -y -n $(ENVIRONMENT_NAME) || true

install-julia:
	@echo "Ensuring Julia $(JULIA_VERSION) is active..."
	@if command -v juliaup >/dev/null 2>&1; then \
		juliaup add $(JULIA_VERSION) 2>/dev/null || true; \
		juliaup override set $(JULIA_VERSION); \
	else \
		julia -e 'if !startswith(string(VERSION), "$(JULIA_VERSION)") error("Expected Julia $(JULIA_VERSION) but found $$VERSION. Please update your active Julia version.") end'; \
	fi
	@echo "Installing pinned Julia packages from Manifest.toml..."
	julia --project=$(JULIA_PROJECT_NAME) -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

julia-version:
	@echo "Setting project Julia version to $(JULIA_VERSION)..."
	python set_julia_version.py $(JULIA_VERSION)

resolve-julia:
	@echo "Resolving Julia dependencies and updating Manifest.toml..."
	julia --project=$(JULIA_PROJECT_NAME) -e 'using Pkg; Pkg.resolve(); Pkg.precompile()'

# --- Docker & Colima ---

colima-start:
	@echo "Starting Colima (x86_64 emulation)..."
	colima start -m 16 -a x86_64 -d 100

docker-build:
	@echo "Building Docker image: $(DOCKER_IMAGE_NAME):latest..."
	docker build --platform linux/amd64 -t $(DOCKER_IMAGE_NAME):latest .

docker-build-environment:
	@echo "Building Docker environment target..."
	docker build --platform linux/amd64 --target environment -t $(DOCKER_IMAGE_NAME):latest .

docker-build-installation:
	@echo "Building Docker installation target..."
	docker build --platform linux/amd64 --target installation -t $(DOCKER_IMAGE_NAME):latest .

docker-interactive:
	@echo "Starting interactive Docker session..."
	docker run --rm -it $(DOCKER_IMAGE_NAME):latest fish

docker-remove:
	@echo "Removing Docker image: $(DOCKER_IMAGE_NAME)..."
	docker rmi -f $(DOCKER_IMAGE_NAME):latest