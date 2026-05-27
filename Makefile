# Some simple testing tasks (sorry, UNIX only).

lint:
ifdef CI
	uv run pre-commit run --all-files --show-diff-on-failure
else
	uv run pre-commit run --all-files
endif
	uv run mypy


develop:
	@uv sync --extra dev --extra lint --extra test --extra doc

install:
	@uv sync --extra dev --extra lint --extra test --extra doc
	uv run pre-commit install

create-tar:
	@tar -cvf tests/docker/docker_context.tar -C tests/docker/tar/ .

doc:
	@make -C docs html SPHINXOPTS="-W -E"
	@echo "open file://`pwd`/docs/_build/html/index.html"

test:
	bash test.sh
