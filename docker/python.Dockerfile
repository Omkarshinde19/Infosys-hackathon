# One image for the Python services: engine, sink and stream (different commands in compose).
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY contracts contracts
COPY services services
COPY topology topology
RUN pip install --no-cache-dir -e .
