
install:
	pip install --upgrade setuptools wheel build
	pip install -r deployment/requirements.txt

test:
	cd deployment/src && pytest

build:
	sed -i 's/{PACKAGE_VERSION}/$(VERSION)/g' deployment/pyproject.toml
	cd deployment && python3 -m build
	mkdir -p ./dist && cp deployment/dist/*.whl ./dist/.
