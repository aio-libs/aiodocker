# Some simple testing tasks (sorry, UNIX only).

flake: .flake

.flake:
	@flake8 aiodocker tests
	if python -c "import sys; sys.exit(sys.version_info<(3,6))"; then \
		black --check aiodocker tests setup.py; \
	fi

fmt:
	black aiodocker tests setup.py

develop:
	@pip install -e .

install:
	@pip install -U pip
	@pip install -Ur requirements/dev.txt

create-tar:
	@tar -cvf tests/docker/docker_context.tar -C tests/docker/tar/ .


doc:
	@make -C docs html SPHINXOPTS="-W -E"
	@echo "open file://`pwd`/docs/_build/html/index.html"
