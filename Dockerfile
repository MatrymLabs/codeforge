# CodeForge -- the world in a box.
# Multi-arch base: builds native on x86 CI and the Raspberry Pi alike.
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# Package source, then install (the console scripts `spark`/`codeforge` land on PATH).
COPY pyproject.toml README.md LICENSE ./
COPY forge.py ./
COPY parts/ parts/
COPY seeds/ seeds/
RUN pip install --no-cache-dir .

# Never run a network service as root -- even a toy one.
RUN useradd --create-home smith && mkdir -p /data && chown -R smith /app /data
USER smith

# The package installs to site-packages, apart from the seed files, so point the
# loader back at the seeds we copied into /app. Canonical state lives on /data so
# a volume carries it across containers:
#   docker run -p 4000:4000 -v codeforge_data:/data codeforge
# Boot a different game with:  -e FORGE_SEED=sword-art-online
ENV CODEFORGE_SEEDS_ROOT=/app/seeds \
    CODEFORGE_DB=/data/codeforge.db

EXPOSE 4000
CMD ["spark"]
