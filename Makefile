# Some simple testing tasks (sorry, UNIX only).

lint:
ifdef CI
	pre-commit run --all-files --show-diff-on-failure
else
	pre-commit run --all-files
endif


develop:
	@pip install -e .

install:
	@pip install -U pip
	@pip install -Ur requirements/dev.txt
	pre-commit install

create-tar:
	@tar -cvf tests/docker/docker_context.tar -C tests/docker/tar/ .

doc:
	@make -C docs html SPHINXOPTS="-W -E"
	@echo "open file://`pwd`/docs/_build/html/index.html"

test:
	bash test.sh
