FROM python:3

WORKDIR /usr/src/aiodocker

COPY requirements.txt /usr/src/aiodocker/
RUN pip install -r requirements.txt

COPY . /usr/src/aiodocker

ENV PYTHONPATH /usr/src/aiodocker
