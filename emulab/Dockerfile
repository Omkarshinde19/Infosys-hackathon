# Emulated campus network: Mininet + Open vSwitch with real packets, run as a privileged container.
# Build context is the repo root (see docker-compose.yml).
FROM ubuntu:24.04
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        mininet openvswitch-switch iproute2 iputils-ping iperf3 python3 python3-pip curl \
    && rm -rf /var/lib/apt/lists/* \
    && pip3 install --no-cache-dir --break-system-packages fastapi uvicorn pyyaml networkx
WORKDIR /emulab
COPY emulab/agent.py emulab/entrypoint.sh ./
COPY topology/campus.yaml ./
EXPOSE 9000
HEALTHCHECK --interval=3s --retries=60 CMD curl -sf http://localhost:9000/health | grep -q '"ready":true'
ENTRYPOINT ["sh", "entrypoint.sh"]
