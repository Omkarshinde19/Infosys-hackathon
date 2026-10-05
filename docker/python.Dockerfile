# One image for the Python services: engine, sink and stream (different commands in compose).
FROM python:3.13-slim
WORKDIR /app
# regopy (the in-process Rego policy engine) needs libatomic.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY contracts contracts
COPY services services
COPY topology topology
COPY policies policies
# Hashed accounts only: config/DEMO_ACCOUNTS.md (readable passwords) stays out of the image.
COPY config/users.yaml config/users.yaml
# CPU-only PyTorch first, so the GNN/LSTM models don't pull in GPU libraries.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -e .
