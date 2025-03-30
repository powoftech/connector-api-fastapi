# Use an official Python runtime as a parent image
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

SHELL ["/bin/bash", "-c"]

RUN python -m venv .venv
RUN source ./.venv/bin/activate
RUN python -m pip install .

COPY ./app ./app

EXPOSE 8000

CMD ["sh", "-c", "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"]
