# Some simple testing tasks (sorry, UNIX only).

flake: .flake

.flake:
	@flake8 aiodocker tests

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
