# MedService inference image.
# Builds a container with the chat and autocomplete FastAPI services only.
# Preprocessing scripts are not run at container startup; data must be mounted.

FROM python:3.12-slim-bookworm

WORKDIR /app

# System libraries required by torch/spacy at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency metadata and install production Python deps.
COPY pyproject.toml uv.lock ./
RUN uv sync --extra rag --extra autocomplete --no-group dev

# Copy application code.
COPY . .

# Install the SciSpaCy NER model used by autocomplete.
# This model is too large to list as a normal dependency, so it is installed explicitly.
RUN uv pip install \
    https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_core_sci_lg-0.5.4.tar.gz

ENV PYTHONPATH=/app

# Both services listen inside the container; the exact command is overridden per service.
EXPOSE 8000 8001

CMD ["uv", "run", "uvicorn", "services.rag_chat_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
