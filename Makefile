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
	@tar -cvf tests/docker/tar/docker_context.tar tests/docker/tar/Dockerfile tests/docker/tar/app.py
