
install:
	pip install -r deployment/requirements.txt

test:
	cd deployment && pytest

build:
	cd deployment && python -m build