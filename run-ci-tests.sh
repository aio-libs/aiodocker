#! /bin/sh

find * -name '*.py[co]' | xargs rm -f
pip install pytest pytest-asyncio codecov pytest-cov
pip install -r requirements/dev.txt
pip install -e .

python -B -m pytest --cov=aiodocker --cov-report=xml tests
