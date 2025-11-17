# dockerfile
# Base image
FROM python:3.11-slim

LABEL org.opencontainers.image.description="Command-line tools for integrating Trapper and Zooniverse."

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    EDITOR=nano \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:/usr/local/bin:$PATH"

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    nano \
    curl \
    git \
    unzip \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/


# Copy app code
COPY . /app
WORKDIR /app

RUN groupadd -g 1000 trapper && useradd -u 1000 -g 1000 -m -d /home/trapper trapper && \
    chown -R trapper:trapper /app
RUN mkdir -p /home/trapper/.cache/uv && chown -R trapper:trapper /home/trapper/.cache

# Create data directory
RUN mkdir -p /data && chown -R trapper:trapper /data

USER trapper

# Install Python dependencies via UV
RUN XDG_CACHE_HOME=/home/trapper/.cache uv sync --frozen --no-dev

WORKDIR /data

# Shell completions
RUN echo 'eval "$(wildintel-tools --show-completion bash)"' >> /home/trapper/.bashrc

USER root

# Entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command
CMD ["bash", "-c", "source /app/.venv/bin/activate && exec bash"]
