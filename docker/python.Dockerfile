# One image for the Python services: engine, sink and stream (different commands in compose).
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml ./
COPY contracts contracts
COPY services services
COPY topology topology
# CPU-only PyTorch first, so the GNN/LSTM models don't pull in GPU libraries.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -e .
