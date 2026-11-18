.PHONY: install test test-python test-julia resolve-julia repomix clean docker-build

install:
	maturin develop --release

test:
	PYTHONPATH=. pytest

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