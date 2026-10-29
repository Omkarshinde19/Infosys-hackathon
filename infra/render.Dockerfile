# The engine alone, for a single small web service (Render free tier, 512 MB).
# No Kafka, TimescaleDB or Redis: the gateway runs its single-process mode and keeps
# incident history in SQLite, which is wiped when the service restarts.
FROM python:3.13-slim
WORKDIR /app
# regopy (the in-process Rego policy engine) needs libatomic.
RUN apt-get update && apt-get install -y --no-install-recommends libatomic1 \
    && rm -rf /var/lib/apt/lists/*
COPY pyproject.toml ./
COPY contracts contracts
COPY services services
# Topology, safety policy and hashed accounts only: config/DEMO_ACCOUNTS.md (readable
# passwords) stays out of the image.
COPY config/campus.yaml config/healing.rego config/users.yaml config/
# Documentation the Ask NetHeal assistant can search (RAG).
COPY README.md ./
COPY docs docs
COPY theory theory
# CPU-only PyTorch first, so the GNN/LSTM models don't pull in GPU libraries.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -e .

RUN useradd -m -u 1000 netheal && chown -R netheal /app
USER netheal

# Measured at ~470 MB with these, against ~505 MB without: one allocator arena
# pair and one math thread keep the engine inside a 512 MB instance.
ENV PYTHONUNBUFFERED=1 \
    NETHEAL_STATE_PATH=/tmp/controller.sqlite3 \
    MALLOC_ARENA_MAX=2 \
    OMP_NUM_THREADS=1 \
    MKL_NUM_THREADS=1

# Render sets PORT
EXPOSE 10000
CMD ["sh", "-c", "uvicorn services.gateway.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
