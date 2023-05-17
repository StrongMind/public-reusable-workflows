
install:
	pip install --upgrade setuptools wheel build
	pip install -r deployment/requirements.txt

test:
	cd deployment/src && pytest

build:
	cd deployment && python3 -m build
	mkdir -p ./dist && cp deployment/dist/*.whl ./dist/.
