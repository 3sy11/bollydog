FROM python:3.12-slim

COPY . /bollydog
WORKDIR /bollydog

RUN pip install .
RUN pip install --no-cache-dir -r /bollydog/requirements/requirements.txt
RUN pip install --no-cache-dir -r /bollydog/requirements/requirements-dev.txt
