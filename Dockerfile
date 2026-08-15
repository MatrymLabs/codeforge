# CodeForge -- the world in a box.
# Multi-arch base: builds native on x86 CI and the Raspberry Pi alike.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Package source, then install (the console scripts `spark`/`codeforge` land on PATH).
COPY pyproject.toml README.md LICENSE ./
COPY forge.py ./
COPY kernel/ kernel/
COPY adapters/ adapters/
COPY content/ content/
RUN pip install --no-cache-dir .

# Never run a network service as root -- even a toy one. A FIXED numeric UID (not just a name) lets
# an orchestrator enforce runAsNonRoot and a read-only root filesystem against a known identity.
RUN useradd --uid 10001 --create-home smith && mkdir -p /data && chown -R smith /app /data
USER 10001

# The package installs to site-packages, apart from the seed files, so point the
# loader back at the seeds we copied into /app. Canonical state lives on /data so
# a volume carries it across containers:
#   docker run -p 4000:4000 -v codeforge_data:/data codeforge
# Boot a different game with:  -e FORGE_SEED=sword-art-online
ENV CODEFORGE_SEEDS_ROOT=/app/content/blueprints \
    CODEFORGE_DB=/data/codeforge.db

EXPOSE 4000

# Liveness: a hung server (port bound but not accepting) is detected so an orchestrator can restart
# it. A plain TCP connect to the game port -- no sensitive detail is exposed. Uses the interpreter
# already in the image, so no extra package is added to the attack surface.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 4000), 3).close()"]

CMD ["spark"]
