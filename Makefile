# Some simple testing tasks (sorry, UNIX only).

flake: .flake

.flake:
	@flake8 aiodocker tests

develop:
	@pip install -e .

install:
	@pip install -U pip
	@pip install -Ur requirements.txt

create-tar:
	@tar -cvf tests/docker/docker_context.tar -C tests/docker/tar/ .
