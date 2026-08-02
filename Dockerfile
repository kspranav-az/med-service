# MedService single-container inference image.
# Runs both the RAG Chat Agent and Semantic Autocomplete services in one container.
# Designed for CPU-only deployment on a small server.
# Preprocessing scripts are not run at container startup; data must be mounted.

FROM python:3.12-slim-bookworm

ARG TARGETARCH

WORKDIR /app

# System libraries required by torch/spacy at runtime, plus supervisor.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgomp1 supervisor \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency metadata and install production Python deps.
# The pyproject.toml pins torch to the CPU-only wheel on Linux.
COPY pyproject.toml uv.lock ./
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        export CFLAGS="-march=armv8-a" CXXFLAGS="-march=armv8-a"; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential python3-dev \
    && uv sync --extra rag --extra autocomplete --no-group dev \
    && apt-get purge -y build-essential python3-dev \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# Copy application code.
COPY . .

# Install the SciSpaCy NER model used by autocomplete.
# This model is too large to list as a normal dependency, so it is installed explicitly.
RUN uv pip install \
    https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz

ENV PYTHONPATH=/app \
    HF_HOME=/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers

# Both services listen inside the container.
EXPOSE 8000 8001

CMD ["/usr/bin/supervisord", "-c", "/app/supervisord.conf"]
