FROM python:3

WORKDIR /usr/src/aiodocker

RUN pip3 install pytest pytest-asyncio
COPY requirements.txt /usr/src/aiodocker/
RUN pip3 install -r requirements.txt

COPY . /usr/src/aiodocker

ENV PYTHONPATH /usr/src/aiodocker
