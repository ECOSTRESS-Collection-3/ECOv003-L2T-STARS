# Define package and environment variables
PACKAGE_NAME = ECOv003-L2T-STARS
MODULE_NAME = ECOv003_L2T_STARS
ENVIRONMENT_NAME = $(PACKAGE_NAME)
PYTHON_VERSION ?= 3.12
DOCKER_IMAGE_NAME = $(shell echo $(PACKAGE_NAME) | tr '[:upper:]' '[:lower:]')
REPOMIX_IGNORE := "**/*.lock,**/*.md,**/*.txt,**/*.ipynb,**/Manifest.toml,*-repomix*.xml"

.PHONY: clean rust-clean rust-build rust-rebuild test test-rust smoke-test wheel-test build twine-upload dist install-package install uninstall reinstall environment remove-environment colima-start docker-build docker-build-environment docker-build-installation docker-interactive docker-remove repomix repomix-skeleton

# --- Cleaning and Maintenance ---

clean: rust-clean
	@echo "Cleaning up build artifacts..."
	rm -rf *.o *.out *.log
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf .pytest_cache
	rm -f *-repomix*.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +

rust-clean:
	@echo "Cleaning Rust build artifacts..."
	rm -rf target/
	rm -f $(MODULE_NAME)/_stars_rust*.so $(MODULE_NAME)/_stars_rust*.pyd

rust-build:
	@echo "Building and installing the Rust extension and dev dependencies..."
	python -m maturin develop --release --extras dev

rust-rebuild:
	$(MAKE) rust-clean
	$(MAKE) rust-build

# --- Testing ---

test-rust:
	@echo "Running Rust formatting, clippy, and unit tests..."
	cargo fmt -- --check
	cargo clippy --all-targets -- -D warnings
	DYLD_FALLBACK_LIBRARY_PATH="$(shell python -c 'import sysconfig; print(sysconfig.get_config_var("LIBDIR") or "")')" cargo test --release

test: rust-build test-rust
	@echo "Running pytest suite..."
	PYTHONPATH=. pytest

smoke-test:
	@echo "Running smoke tests..."
	PYTHONPATH=. python -I -m $(MODULE_NAME).smoke_test

wheel-test:
	@echo "Building release wheel and running isolated smoke test..."
	rm -rf dist/
	python -m maturin build --release --out dist
	python -m venv /tmp/ecov003_l2t_stars_wheel_verify
	/tmp/ecov003_l2t_stars_wheel_verify/bin/pip install --upgrade pip
	/tmp/ecov003_l2t_stars_wheel_verify/bin/pip install dist/*.whl
	cd /tmp && /tmp/ecov003_l2t_stars_wheel_verify/bin/python -I -m $(MODULE_NAME).smoke_test
	rm -rf /tmp/ecov003_l2t_stars_wheel_verify

# --- Package Management ---

build:
	@echo "Building package..."
	python -m build

twine-upload:
	@echo "Uploading package to PyPI..."
	twine upload dist/*

dist: clean build twine-upload
	@echo "Distribution process complete."

install-package: rust-build
	@echo "Development package and Rust extension installed."

install: install-package
	@echo "Package installed; source builds require a Rust toolchain."

uninstall:
	@echo "Uninstalling $(PACKAGE_NAME)..."
	pip uninstall $(PACKAGE_NAME)

reinstall: uninstall install
	@echo "Package reinstalled."

# --- Environment Management ---

environment:
	@echo "Creating mamba environment: $(ENVIRONMENT_NAME)..."
	mamba create -y -n $(ENVIRONMENT_NAME) -c conda-forge python=$(PYTHON_VERSION) pip "setuptools<81" rust maturin

remove-environment:
	@echo "Removing mamba environment: $(ENVIRONMENT_NAME)..."
	mamba env remove -y -n $(ENVIRONMENT_NAME)

# --- Docker & Colima ---

colima-start:
	@echo "Starting Colima..."
	colima start -m 16 -a x86_64 -d 100

docker-build:
	@echo "Building Docker image: $(DOCKER_IMAGE_NAME):latest..."
	docker build -t $(DOCKER_IMAGE_NAME):latest .

docker-build-environment:
	@echo "Building Docker environment target..."
	docker build --target environment -t $(DOCKER_IMAGE_NAME):latest .

docker-build-installation:
	@echo "Building Docker installation target..."
	docker build --target installation -t $(DOCKER_IMAGE_NAME):latest .

docker-interactive:
	@echo "Starting interactive Docker session..."
	docker run -it $(DOCKER_IMAGE_NAME) fish

docker-remove:
	@echo "Removing Docker image: $(DOCKER_IMAGE_NAME)..."
	docker rmi -f $(DOCKER_IMAGE_NAME)

# --- Repomix ---

repomix:
	npx repomix -o "$(PACKAGE_NAME)-repomix.xml" --ignore $(REPOMIX_IGNORE) --copy

repomix-skeleton:
	npx repomix -o "$(PACKAGE_NAME)-repomix-skeleton.xml" --ignore $(REPOMIX_IGNORE) --compress --copy

show-issues:
	gh issue list --state open --json number,title,body --template '{{range .}}## #{{.number}}: {{.title}}{{"\n\n"}}{{.body}}{{"\n\n---\n\n"}}{{end}}'