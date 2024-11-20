# Some simple testing tasks (sorry, UNIX only).

lint:
ifdef CI
	pre-commit run --all-files --show-diff-on-failure
else
	pre-commit run --all-files
endif
	mypy


develop:
	@pip install -e .[dev]

install:
	@pip install -U pip
	@pip install -e .[dev]
	pre-commit install

create-tar:
	@tar -cvf tests/docker/docker_context.tar -C tests/docker/tar/ .

doc:
	@make -C docs html SPHINXOPTS="-W -E"
	@echo "open file://`pwd`/docs/_build/html/index.html"

test:
	bash test.sh
