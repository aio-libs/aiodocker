#! /bin/sh

find * -name '*.py[co]' | xargs rm -f
pip install pytest pytest-asyncio codecov pytest-cov
pip install -r requirements.txt
pip install -e .

python -B -m pytest --cov=aiodocker tests && codecov
