
install:
	pip install -r deployment/requirements.txt

test:
	cd deployment && pytest

build:
	python3 -m pip install --upgrade build
	cd deployment && python3 -m build