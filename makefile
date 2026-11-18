PYTHON ?= python
PYTHON_LIBDIR := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('LIBDIR') or '')")

.PHONY: install test test-rust test-python test-julia resolve-julia repomix clean docker-build

install:
	maturin develop --release

test: test-rust
	PYTHONPATH=. pytest

test-rust:
	DYLD_FALLBACK_LIBRARY_PATH="$(PYTHON_LIBDIR):$$DYLD_FALLBACK_LIBRARY_PATH" \
	LD_LIBRARY_PATH="$(PYTHON_LIBDIR):$$LD_LIBRARY_PATH" \
	cargo test --release

test-python:
	ECOv003-L2T-STARS test-python

test-julia:
	ECOv003-L2T-STARS test-julia

resolve-julia:
	julia --project=ECOv003_L2T_STARS -e 'using Pkg; Pkg.resolve(); Pkg.instantiate(); Pkg.precompile()'

repomix:
	npx repomix --ignore "test_bundle/**,target/**,**/Manifest.toml,**/*.ipynb,**/*.tif,**/*.pdf,**/*.dat,**/*.jpeg,**/*.pyc,build/**,__pycache__/**,*.egg-info/**,repomix-output.xml"

clean:
	rm -rf *.o *.out *.log
	rm -rf build/ dist/ target/ *.egg-info .pytest_cache .coverage htmlcov
	rm -f repomix-output.xml
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker build -t ecov003-l2t-stars:latest .